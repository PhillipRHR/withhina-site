# Deploy do WithHina

## Etapa A — GitHub Pages

1. Envie todos os arquivos da raiz para o repositório do site.
2. Confirme que `CNAME` contém apenas `withhina.com`.
3. No GitHub, abra **Settings → Pages**.
4. Publique a branch principal a partir de `/ (root)`.
5. Defina `withhina.com` como domínio personalizado.
6. Ative HTTPS.

Nesse ponto o modo **Arquivo** já pode ser testado publicamente.

## Etapa B — Backend do modo Link

1. Crie um Web Service a partir do mesmo repositório.
2. Use o `render.yaml` da raiz ou configure a pasta `backend` como Root Directory.
3. O serviço deve usar Docker e expor a porta definida em `PORT`.
4. Configure `ALLOWED_ORIGINS=https://withhina.com,https://www.withhina.com`.
5. Depois do deploy, teste `https://SEU-BACKEND/health`.
6. Copie a URL HTTPS do backend.

## Etapa C — Conectar frontend e backend

Abra `config.js` e altere:

```js
linkApiUrl: "https://SEU-BACKEND"
```

Faça novo commit/push. Depois teste a aba **Link** no domínio real.

## Etapa D — Beta

Teste antes de monetizar:

- Desktop: Chrome, Edge e Firefox.
- Android: Chrome.
- Arquivo local: MP4, WEBM, WAV, M4A e FLAC.
- Bitrates: 128, 192, 256 e 320 kbps.
- Arquivos maiores, sem ultrapassar 250 MB.
- Link válido, link inválido e vídeo acima do limite.
- Mensagens da Hina em sucesso e erro.
- Política de privacidade, termos, página Hina e página 404.

## Etapa E — Analytics

O Analytics já está configurado em `config.js`, mas só carrega após consentimento do visitante.

Para desligar durante testes:

```js
analyticsId: ""
```

## Etapa F — AdSense

Não preencha o AdSense durante o beta. Depois da aprovação do domínio, coloque os IDs em `config.js`.

O espaço de anúncio já está separado do botão de download.
