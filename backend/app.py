import asyncio
import os
import re
import shutil
import tempfile
import time
from collections import defaultdict, deque
from pathlib import Path
from typing import Literal
from urllib.parse import urlparse

import yt_dlp
import imageio_ffmpeg
from fastapi import BackgroundTasks, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field


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


def download_audio(url: str, bitrate: int) -> tuple[Path, str, Path]:
    temp_dir = Path(tempfile.mkdtemp(prefix="hina_converter_"))
    try:
        probe_options = {
            "quiet": True,
            "no_warnings": True,
            "noplaylist": True,
            "skip_download": True,
            "socket_timeout": 20,
            "retries": 1,
        }
        with yt_dlp.YoutubeDL(probe_options) as ydl:
            info = ydl.extract_info(url, download=False)

        duration = int(info.get("duration") or 0)
        if not duration:
            raise HTTPException(400, "Não foi possível verificar a duração desse conteúdo.")
        if duration > MAX_DURATION_SECONDS:
            minutes = MAX_DURATION_SECONDS // 60
            raise HTTPException(400, f"O conteúdo ultrapassa o limite de {minutes} minutos.")

        title = info.get("title") or "audio"
        video_id = re.sub(r"[^a-zA-Z0-9_-]", "", str(info.get("id") or "audio"))[:80] or "audio"
        output_template = str(temp_dir / f"{video_id}.%(ext)s")

        download_options = {
            "ffmpeg_location": FFMPEG_EXE,
            "format": "bestaudio/best",
            "outtmpl": output_template,
            "quiet": True,
            "no_warnings": True,
            "noplaylist": True,
            "socket_timeout": 30,
            "retries": 2,
            "fragment_retries": 2,
            "continuedl": False,
            "overwrites": True,
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
            raise RuntimeError("O arquivo final não foi gerado.")

        output = candidates[0]
        if output.stat().st_size > MAX_OUTPUT_BYTES:
            raise HTTPException(413, "O MP3 final ficou grande demais para este serviço.")

        return output, clean_filename(title), temp_dir
    except Exception:
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "hina-converter-api"}


@app.post("/api/download")
async def create_download(payload: DownloadRequest, request: Request, background_tasks: BackgroundTasks):
    enforce_rate_limit(request)
    url = validate_youtube_url(payload.url.strip())

    try:
        path, filename, temp_dir = await asyncio.wait_for(
            asyncio.to_thread(download_audio, url, payload.bitrate),
            timeout=180,
        )
    except asyncio.TimeoutError as exc:
        raise HTTPException(504, "O processamento demorou demais. Tente outro conteúdo.") from exc
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(502, "Não foi possível preparar o áudio desse link.") from exc

    background_tasks.add_task(shutil.rmtree, temp_dir, True)
    return FileResponse(
        path,
        media_type="audio/mpeg",
        filename=filename,
        background=background_tasks,
    )
