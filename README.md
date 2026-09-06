# WithHina / Hina Converter

Projeto do **WithHina.com**, com o Hina Converter como ferramenta principal.

## O que funciona

- **Arquivo local:** converte áudio e vídeo para MP3 no navegador usando FFmpeg.wasm.
- **Link:** envia um link do YouTube para o backend em `backend/`, que usa `yt-dlp` + FFmpeg e devolve o MP3.
- **Qualidade:** 128, 192, 256 ou 320 kbps nos dois modos.
- **Hina:** mensagens mudam conforme o estado da conversão.
- **Responsivo:** layout preparado para desktop e celular.
- **Analytics com consentimento:** o Google Analytics só é carregado se o visitante aceitar estatísticas.
- **AdSense:** estrutura pronta, mas permanece desligada enquanto os IDs estiverem vazios.

## Estrutura

```text
/
├─ index.html              # Conversor
├─ Hina.html               # Página sobre a Hina
├─ privacy.html            # Política de privacidade
├─ terms.html              # Termos de uso
├─ styles.css
├─ app.js
├─ config.js               # URLs/IDs configuráveis
├─ hina-reclined.webp      # Imagem otimizada usada no site
├─ hina-reclined.png       # Fallback PNG
├─ CNAME                   # withhina.com
├─ render.yaml             # Deploy do backend a partir da raiz
└─ backend/
   ├─ app.py
   ├─ Dockerfile
   ├─ requirements.txt
   └─ render.yaml
```

## 1. Publicar o frontend no GitHub Pages

O repositório deve publicar a raiz do projeto. O arquivo `CNAME` já contém:

```text
withhina.com
```

No GitHub:

1. **Settings → Pages**.
2. Escolha a branch principal e a pasta `/ (root)`.
3. Salve.
4. Confirme que o domínio personalizado é `withhina.com`.
5. Ative **Enforce HTTPS** quando a opção estiver disponível.

O modo **Arquivo** já funciona sem backend.

## 2. Publicar o backend

O projeto contém `render.yaml` na raiz e um Dockerfile dentro de `backend/`.

No Render, Railway ou serviço equivalente:

1. Conecte este repositório.
2. Publique `backend/` como Web Service Docker.
3. Garanta que a variável `ALLOWED_ORIGINS` contenha:

```text
https://withhina.com,https://www.withhina.com
```

4. Verifique o endpoint:

```text
GET /health
```

Ele deve responder com `status: ok`.

## 3. Conectar o modo Link

Depois do backend estar online, abra `config.js` e preencha:

```js
linkApiUrl: "https://SEU-BACKEND-AQUI"
```

Sem barra `/` no final.

Depois faça commit/push. O GitHub Pages atualizará o frontend.

## 4. Analytics

O ID atual está em `config.js`:

```js
analyticsId: "G-BQ02QCMFJY"
```

O script só carrega quando o visitante escolhe **Aceitar estatísticas**. A preferência fica em `localStorage`.

Para desligar o Analytics completamente:

```js
analyticsId: ""
```

## 5. AdSense

Durante o beta, deixe:

```js
adsenseClient: ""
```

Depois da aprovação, preencha `adsenseClient` e `adsenseSlots.top`. O espaço publicitário fica abaixo do conversor, longe do botão de download.

## Limites do backend

Por padrão:

- somente URLs do YouTube;
- até 60 minutos por mídia;
- 6 solicitações a cada 10 minutos por IP;
- timeout de 180 segundos;
- arquivo MP3 final limitado a aproximadamente 180 MB.

Esses valores podem ser alterados por variáveis de ambiente.

> Observação: o rate limit atual é em memória. Para múltiplas instâncias do backend, use Redis ou outro armazenamento compartilhado.

## Teste local

Frontend:

```bash
python -m http.server 8000
```

Abra `http://localhost:8000`.

Backend:

```bash
cd backend
python -m venv .venv
# ative o ambiente virtual
pip install -r requirements.txt
uvicorn app:app --reload --port 8080
```

Para testar Link localmente, use temporariamente em `config.js`:

```js
linkApiUrl: "http://localhost:8080"
```

## Antes do lançamento público

- testar Chrome, Edge, Firefox e Android;
- testar arquivos pequenos e grandes;
- testar 128/192/256/320 kbps;
- testar erros de link e rate limit;
- confirmar política de privacidade e termos;
- só depois ativar anúncios.
