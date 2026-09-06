# Hina Converter API

Backend necessário apenas para a aba **Link** do WithHina.com. A aba **Arquivo** funciona inteiramente no navegador.

## Stack

- FastAPI
- yt-dlp
- FFmpeg
- Docker

## Endpoints

- `GET /health` — health check.
- `POST /api/download` — recebe JSON com `url` e `bitrate` (`128`, `192`, `256` ou `320`).

Exemplo:

```json
{
  "url": "https://www.youtube.com/watch?v=...",
  "bitrate": 192
}
```

## Variáveis de ambiente

- `ALLOWED_ORIGINS` — origens CORS separadas por vírgula.
- `MAX_DURATION_SECONDS` — padrão `3600`.
- `MAX_OUTPUT_BYTES` — padrão aproximado de `180 MB`.
- `RATE_LIMIT_REQUESTS` — padrão `6`.
- `RATE_LIMIT_WINDOW` — padrão `600` segundos.

## Publicação

Use o `render.yaml` da raiz do repositório ou crie um Web Service Docker apontando para a pasta `backend`.

Depois da publicação, copie a URL HTTPS do serviço para `linkApiUrl` em `../config.js`.

## Segurança operacional

O serviço valida o host do link, limita duração, aplica rate limit básico, usa timeout e remove os arquivos temporários após a resposta.

O rate limit é em memória e serve para uma única instância. Se o serviço crescer para múltiplas réplicas, troque essa parte por Redis ou equivalente.
