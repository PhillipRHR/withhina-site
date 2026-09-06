import asyncio
import logging
import os
import re
import shutil
import subprocess
import tempfile
import time
from collections import defaultdict, deque
from pathlib import Path
from typing import Any, Literal
from urllib.parse import urlparse

import yt_dlp
import imageio_ffmpeg
import httpx
from fastapi import BackgroundTasks, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field


logger = logging.getLogger("hina-converter")
logger.setLevel(logging.INFO)

class YTDLPDiagnosticLogger:
    def _emit(self, level: str, message: str) -> None:
        text = str(message)
        lowered = text.lower()
        interesting = (
            "[pot]" in lowered
            or "po token" in lowered
            or "bgutil" in lowered
            or "player client" in lowered
            or "player_client" in lowered
        )
        if not interesting and level == "debug":
            return
        if level == "error":
            logger.error("yt-dlp: %s", text)
        else:
            logger.warning("yt-dlp: %s", text)

    def debug(self, message: str) -> None:
        self._emit("debug", message)

    def info(self, message: str) -> None:
        self._emit("info", message)

    def warning(self, message: str) -> None:
        self._emit("warning", message)

    def error(self, message: str) -> None:
        self._emit("error", message)


YTDLP_DIAGNOSTIC_LOGGER = YTDLPDiagnosticLogger()

MAX_DURATION_SECONDS = int(os.getenv("MAX_DURATION_SECONDS", "3600"))
MAX_OUTPUT_BYTES = int(os.getenv("MAX_OUTPUT_BYTES", str(180 * 1024 * 1024)))
RATE_LIMIT_REQUESTS = int(os.getenv("RATE_LIMIT_REQUESTS", "6"))
RATE_LIMIT_WINDOW = int(os.getenv("RATE_LIMIT_WINDOW", str(10 * 60)))
YOUTUBE_HOSTS = {
    "youtube.com",
    "www.youtube.com",
    "m.youtube.com",
    "music.youtube.com",
    "youtu.be",
    "www.youtu.be",
}
ORIGINS = [
    value.strip()
    for value in os.getenv(
        "ALLOWED_ORIGINS",
        "https://withhina.com,https://www.withhina.com,http://localhost:8000,http://127.0.0.1:8000",
    ).split(",")
    if value.strip()
]

FFMPEG_EXE = imageio_ffmpeg.get_ffmpeg_exe()

PIPED_API_INSTANCES = [
    value.strip().rstrip("/")
    for value in os.getenv(
        "PIPED_API_INSTANCES",
        ",".join([
            "https://pipedapi.kavin.rocks",
            "https://pipedapi.leptons.xyz",
            "https://pipedapi.nosebs.ru",
            "https://pipedapi-libre.kavin.rocks",
            "https://piped-api.privacy.com.de",
            "https://pipedapi.adminforge.de",
            "https://api.piped.yt",
            "https://pipedapi.drgns.space",
            "https://pipedapi.owo.si",
            "https://pipedapi.ducks.party",
            "https://piped-api.codespace.cz",
            "https://pipedapi.reallyaweso.me",
            "https://api.piped.private.coffee",
            "https://pipedapi.darkness.services",
            "https://pipedapi.orangenet.cc",
        ]),
    ).split(",")
    if value.strip()
]

INVIDIOUS_INSTANCES = [
    value.strip().rstrip("/")
    for value in os.getenv("INVIDIOUS_INSTANCES", "").split(",")
    if value.strip()
]

ALT_DISCOVERY_TIMEOUT = float(os.getenv("ALT_DISCOVERY_TIMEOUT", "6.5"))
ALT_MEDIA_TIMEOUT = float(os.getenv("ALT_MEDIA_TIMEOUT", "25"))
POT_PROVIDER_URL = os.getenv("POT_PROVIDER_URL", "http://127.0.0.1:4416").rstrip("/")

YTDLP_STRATEGIES = [
    {
        "name": "mweb+pot",
        "client": "mweb",
        "use_pot": True,
        "notes": "rota principal com BgUtils PO Token",
    },
    {
        "name": "visionos",
        "client": "visionos",
        "use_pot": False,
        "notes": "cliente Apple usado pelas versões atuais do yt-dlp",
    },
    {
        "name": "web_embedded",
        "client": "web_embedded",
        "use_pot": False,
        "notes": "rota sem PO Token para vídeos incorporáveis",
    },
    {
        "name": "android_vr",
        "client": "android_vr",
        "use_pot": False,
        "notes": "fallback Android VR; pode oferecer apenas formatos limitados",
    },
    {
        "name": "web_safari",
        "client": "web_safari",
        "use_pot": True,
        "notes": "último fallback web/HLS",
    },
]


def extractor_args_for(strategy: dict[str, Any]) -> dict[str, dict[str, list[str]]]:
    args: dict[str, dict[str, list[str]]] = {
        "youtube": {
            "player_client": [str(strategy["client"])],
            "pot_trace": ["true"],
        },
    }
    if strategy.get("use_pot"):
        args["youtubepot-bgutilhttp"] = {
            "base_url": [POT_PROVIDER_URL],
        }
    return args

app = FastAPI(title="Hina Converter API", docs_url=None, redoc_url=None, openapi_url=None)
app.add_middleware(
    CORSMiddleware,
    allow_origins=ORIGINS,
    allow_credentials=False,
    allow_methods=["POST", "GET", "OPTIONS"],
    allow_headers=["Content-Type"],
    expose_headers=["Content-Disposition"],
)

requests_by_ip: dict[str, deque[float]] = defaultdict(deque)


class DownloadRequest(BaseModel):
    url: str = Field(min_length=12, max_length=2048)
    bitrate: Literal[128, 192, 256, 320] = 192


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Cache-Control"] = "no-store"
    return response


def clean_filename(value: str) -> str:
    value = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", value).strip().rstrip(".")
    value = re.sub(r"\s+", " ", value)
    return (value[:150] or "audio") + ".mp3"


def validate_youtube_url(value: str) -> str:
    try:
        parsed = urlparse(value)
    except ValueError as exc:
        raise HTTPException(400, "Link inválido.") from exc

    hostname = (parsed.hostname or "").lower().rstrip(".")
    if parsed.scheme not in {"http", "https"} or hostname not in YOUTUBE_HOSTS:
        raise HTTPException(400, "No momento, o modo Link aceita apenas endereços do YouTube.")
    if parsed.username or parsed.password:
        raise HTTPException(400, "Link inválido.")
    return value


def extract_youtube_video_id(value: str) -> str:
    parsed = urlparse(value)
    host = (parsed.hostname or "").lower()
    if host in {"youtu.be", "www.youtu.be"}:
        video_id = parsed.path.strip("/").split("/", 1)[0]
    else:
        from urllib.parse import parse_qs
        if parsed.path.startswith("/shorts/"):
            video_id = parsed.path.split("/shorts/", 1)[1].split("/", 1)[0]
        elif parsed.path.startswith("/embed/"):
            video_id = parsed.path.split("/embed/", 1)[1].split("/", 1)[0]
        else:
            video_id = parse_qs(parsed.query).get("v", [""])[0]

    if not re.fullmatch(r"[A-Za-z0-9_-]{6,20}", video_id or ""):
        raise HTTPException(400, "Não foi possível identificar o vídeo do YouTube.")
    return video_id


def should_try_piped(exc: Exception) -> bool:
    message = str(exc).lower()
    signals = (
        "not a bot",
        "sign in to confirm",
        "cookies",
        "http error 403",
        "forbidden",
        "unable to download webpage",
        "youtube client strategies failed",
    )
    return any(signal in message for signal in signals)


async def _piped_candidate(client: httpx.AsyncClient, api_base: str, video_id: str) -> dict[str, Any] | None:
    try:
        response = await client.get(f"{api_base}/streams/{video_id}")
        response.raise_for_status()
        payload = response.json()

        duration = int(payload.get("duration") or 0)
        if duration > MAX_DURATION_SECONDS:
            minutes = MAX_DURATION_SECONDS // 60
            raise HTTPException(400, f"O conteúdo ultrapassa o limite de {minutes} minutos.")
        if not duration:
            return None

        streams = [
            stream for stream in (payload.get("audioStreams") or [])
            if stream.get("url")
        ]
        if not streams:
            return None

        streams.sort(key=lambda item: int(item.get("bitrate") or 0), reverse=True)
        stream = streams[0]
        return {
            "source": "piped",
            "instance": api_base,
            "url": stream["url"],
            "bitrate": int(stream.get("bitrate") or 0),
            "duration": duration,
            "title": payload.get("title") or f"youtube-{video_id}",
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.warning("Piped indisponível: %s (%s)", api_base, type(exc).__name__)
        return None


async def _invidious_candidate(client: httpx.AsyncClient, base: str, video_id: str) -> dict[str, Any] | None:
    try:
        response = await client.get(f"{base}/api/v1/videos/{video_id}")
        response.raise_for_status()
        payload = response.json()

        duration = int(payload.get("lengthSeconds") or 0)
        if duration > MAX_DURATION_SECONDS:
            minutes = MAX_DURATION_SECONDS // 60
            raise HTTPException(400, f"O conteúdo ultrapassa o limite de {minutes} minutos.")
        if not duration:
            return None

        formats = [
            item for item in (payload.get("adaptiveFormats") or [])
            if item.get("url") and str(item.get("type") or "").startswith("audio/")
        ]
        if not formats:
            return None

        formats.sort(key=lambda item: int(item.get("bitrate") or 0), reverse=True)
        stream = formats[0]
        return {
            "source": "invidious",
            "instance": base,
            "url": stream["url"],
            "bitrate": int(stream.get("bitrate") or 0),
            "duration": duration,
            "title": payload.get("title") or f"youtube-{video_id}",
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.warning("Invidious indisponível: %s (%s)", base, type(exc).__name__)
        return None


async def discover_alternative_candidates(video_id: str) -> list[dict[str, Any]]:
    timeout = httpx.Timeout(ALT_DISCOVERY_TIMEOUT, connect=min(4.0, ALT_DISCOVERY_TIMEOUT))
    headers = {
        "User-Agent": "WithHina/1.9.4 (+https://withhina.com)",
        "Accept": "application/json",
    }

    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True, headers=headers) as client:
        tasks = [
            *[_piped_candidate(client, base, video_id) for base in PIPED_API_INSTANCES],
            *[_invidious_candidate(client, base, video_id) for base in INVIDIOUS_INSTANCES],
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

    candidates: list[dict[str, Any]] = []
    for result in results:
        if isinstance(result, HTTPException):
            raise result
        if isinstance(result, dict):
            candidates.append(result)

    # Prefer higher-quality streams, while keeping all successful providers as fallbacks.
    candidates.sort(key=lambda item: int(item.get("bitrate") or 0), reverse=True)
    logger.warning("Fallback discovery: %d candidato(s) para %s", len(candidates), video_id)
    return candidates


async def _stream_is_reachable(candidate: dict[str, Any]) -> bool:
    timeout = httpx.Timeout(7.0, connect=4.0)
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Range": "bytes=0-1",
        "Accept": "*/*",
    }
    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True, headers=headers) as client:
            async with client.stream("GET", candidate["url"]) as response:
                response.raise_for_status()
                async for chunk in response.aiter_bytes(2048):
                    if chunk:
                        return True
        return False
    except Exception as exc:
        logger.warning(
            "Stream inacessível: %s %s (%s)",
            candidate.get("source"),
            candidate.get("instance"),
            type(exc).__name__,
        )
        return False


async def choose_reachable_candidate(candidates: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not candidates:
        return None

    # Race up to six candidate streams instead of waiting for one provider at a time.
    pool = candidates[:6]
    tasks = [asyncio.create_task(_stream_is_reachable(candidate)) for candidate in pool]
    task_to_candidate = dict(zip(tasks, pool))

    try:
        for completed in asyncio.as_completed(tasks):
            reachable = await completed
            if reachable:
                chosen = task_to_candidate.get(completed)
                if chosen is None:
                    # as_completed may wrap awaitables; resolve by locating a completed true task.
                    for task, candidate in task_to_candidate.items():
                        if task.done() and not task.cancelled():
                            try:
                                if task.result():
                                    chosen = candidate
                                    break
                            except Exception:
                                pass
                if chosen is not None:
                    for task in tasks:
                        if not task.done():
                            task.cancel()
                    logger.warning(
                        "Fallback escolhido: %s %s",
                        chosen.get("source"),
                        chosen.get("instance"),
                    )
                    return chosen
    finally:
        for task in tasks:
            if not task.done():
                task.cancel()

    return None


def _transcode_to_mp3(source_path: Path, output: Path, bitrate: int) -> None:
    process = subprocess.run(
        [
            FFMPEG_EXE,
            "-y",
            "-i", str(source_path),
            "-vn",
            "-codec:a", "libmp3lame",
            "-b:a", f"{bitrate}k",
            str(output),
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
        timeout=120,
    )
    if process.returncode != 0 or not output.exists():
        raise RuntimeError("FFmpeg não conseguiu converter o áudio alternativo.")


async def fetch_alternative_stream(url: str, bitrate: int) -> tuple[Path, str, Path]:
    video_id = extract_youtube_video_id(url)
    candidates = await discover_alternative_candidates(video_id)
    if not candidates:
        raise RuntimeError("Nenhum provedor alternativo retornou stream.")

    # We try a small number of reachable candidates. The reachability race makes this much
    # faster than the old sequential fallback when several public instances are down.
    remaining = list(candidates)
    last_error: Exception | None = None

    for _ in range(min(3, len(remaining))):
        chosen = await choose_reachable_candidate(remaining)
        if chosen is None:
            break
        remaining = [item for item in remaining if item is not chosen]

        temp_dir = Path(tempfile.mkdtemp(prefix="hina_alt_"))
        source_path = temp_dir / "source_audio"
        output = temp_dir / "output.mp3"
        total = 0

        try:
            timeout = httpx.Timeout(ALT_MEDIA_TIMEOUT, connect=6.0)
            headers = {
                "User-Agent": "Mozilla/5.0",
                "Accept": "*/*",
            }
            async with httpx.AsyncClient(timeout=timeout, follow_redirects=True, headers=headers) as client:
                async with client.stream("GET", chosen["url"]) as media:
                    media.raise_for_status()
                    with source_path.open("wb") as handle:
                        async for chunk in media.aiter_bytes(1024 * 1024):
                            if not chunk:
                                continue
                            total += len(chunk)
                            if total > MAX_OUTPUT_BYTES:
                                raise HTTPException(413, "O áudio ficou grande demais para este serviço.")
                            handle.write(chunk)

            await asyncio.to_thread(_transcode_to_mp3, source_path, output, bitrate)

            if output.stat().st_size > MAX_OUTPUT_BYTES:
                raise HTTPException(413, "O MP3 final ficou grande demais para este serviço.")

            title = chosen.get("title") or f"youtube-{video_id}"
            return output, clean_filename(str(title)), temp_dir
        except HTTPException:
            shutil.rmtree(temp_dir, ignore_errors=True)
            raise
        except Exception as exc:
            last_error = exc
            logger.warning(
                "Fallback falhou após seleção: %s %s (%s)",
                chosen.get("source"),
                chosen.get("instance"),
                type(exc).__name__,
            )
            shutil.rmtree(temp_dir, ignore_errors=True)

    raise RuntimeError(f"Todos os streams alternativos falharam: {last_error}")


def client_address(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",", 1)[0].strip()[:128]
    return (request.client.host if request.client else "unknown")[:128]


def enforce_rate_limit(request: Request) -> None:
    address = client_address(request)
    now = time.monotonic()
    bucket = requests_by_ip[address]

    while bucket and now - bucket[0] > RATE_LIMIT_WINDOW:
        bucket.popleft()

    if len(bucket) >= RATE_LIMIT_REQUESTS:
        raise HTTPException(429, "Limite temporário atingido. Tente novamente em alguns minutos.")

    bucket.append(now)


def _download_audio_with_strategy(
    url: str,
    bitrate: int,
    strategy: dict[str, Any],
) -> tuple[Path, str, Path]:
    temp_dir = Path(tempfile.mkdtemp(prefix=f"hina_{strategy['name'].replace('+', '_')}_"))
    extractor_args = extractor_args_for(strategy)
    strategy_name = str(strategy["name"])
    client_name = str(strategy["client"])

    logger.warning(
        "YouTube strategy start: %s client=%s pot=%s",
        strategy_name,
        client_name,
        bool(strategy.get("use_pot")),
    )

    try:
        probe_options = {
            "quiet": False,
            "verbose": True,
            "no_warnings": False,
            "noplaylist": True,
            "skip_download": True,
            "socket_timeout": 20,
            "retries": 1,
            "extractor_args": extractor_args,
            "logger": YTDLP_DIAGNOSTIC_LOGGER,
        }

        with yt_dlp.YoutubeDL(probe_options) as ydl:
            info = ydl.extract_info(url, download=False)

        duration = int(info.get("duration") or 0)
        if not duration:
            raise RuntimeError(
                f"{strategy_name}: não foi possível verificar a duração do conteúdo."
            )
        if duration > MAX_DURATION_SECONDS:
            minutes = MAX_DURATION_SECONDS // 60
            raise HTTPException(400, f"O conteúdo ultrapassa o limite de {minutes} minutos.")

        title = info.get("title") or "audio"
        video_id = re.sub(
            r"[^a-zA-Z0-9_-]",
            "",
            str(info.get("id") or "audio"),
        )[:80] or "audio"
        output_template = str(temp_dir / f"{video_id}.%(ext)s")

        download_options = {
            "ffmpeg_location": FFMPEG_EXE,
            # Some fallback clients (notably android_vr) may only expose a
            # muxed A/V format. "bestaudio/best" intentionally allows that
            # final "best" fallback; FFmpeg extracts only the audio below.
            "format": "bestaudio/best",
            "outtmpl": output_template,
            "quiet": False,
            "verbose": True,
            "no_warnings": False,
            "noplaylist": True,
            "socket_timeout": 30,
            "retries": 2,
            "fragment_retries": 2,
            "continuedl": False,
            "overwrites": True,
            "extractor_args": extractor_args,
            "logger": YTDLP_DIAGNOSTIC_LOGGER,
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": str(bitrate),
            }],
        }

        with yt_dlp.YoutubeDL(download_options) as ydl:
            ydl.download([url])

        candidates = list(temp_dir.glob("*.mp3"))
        if not candidates:
            raise RuntimeError(
                f"{strategy_name}: o arquivo final não foi gerado."
            )

        output = candidates[0]
        if output.stat().st_size > MAX_OUTPUT_BYTES:
            raise HTTPException(413, "O MP3 final ficou grande demais para este serviço.")

        logger.warning(
            "YouTube strategy success: %s client=%s",
            strategy_name,
            client_name,
        )
        return output, clean_filename(str(title)), temp_dir

    except HTTPException:
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise
    except Exception as exc:
        shutil.rmtree(temp_dir, ignore_errors=True)
        logger.warning(
            "YouTube strategy failed: %s client=%s (%s): %s",
            strategy_name,
            client_name,
            type(exc).__name__,
            str(exc)[:500],
        )
        raise


def download_audio(url: str, bitrate: int) -> tuple[Path, str, Path]:
    failures: list[str] = []

    for strategy in YTDLP_STRATEGIES:
        try:
            return _download_audio_with_strategy(url, bitrate, strategy)
        except HTTPException:
            raise
        except Exception as exc:
            failures.append(
                f"{strategy['name']}={type(exc).__name__}:{str(exc)[:180]}"
            )

    # The endpoint recognizes this marker and then executes the public-provider
    # fallback as the final route.
    raise RuntimeError(
        "youtube client strategies failed | " + " | ".join(failures)
    )


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "hina-converter-api"}


@app.post("/api/download")
async def create_download(payload: DownloadRequest, request: Request, background_tasks: BackgroundTasks):
    enforce_rate_limit(request)
    url = validate_youtube_url(payload.url.strip())

    try:
        try:
            path, filename, temp_dir = await asyncio.wait_for(
                asyncio.to_thread(download_audio, url, payload.bitrate),
                timeout=120,
            )
        except Exception as first_error:
            if isinstance(first_error, HTTPException):
                raise
            if not should_try_piped(first_error):
                raise
            path, filename, temp_dir = await asyncio.wait_for(
                fetch_alternative_stream(url, payload.bitrate),
                timeout=75,
            )
    except asyncio.TimeoutError as exc:
        raise HTTPException(504, "O processamento demorou demais. Tente novamente em alguns instantes.") from exc
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            502,
            "O YouTube recusou a rota com PO Token e os provedores alternativos também não conseguiram entregar o áudio agora. Tente novamente em alguns instantes.",
        ) from exc

    background_tasks.add_task(shutil.rmtree, temp_dir, True)
    return FileResponse(
        path,
        media_type="audio/mpeg",
        filename=filename,
        background=background_tasks,
    )
