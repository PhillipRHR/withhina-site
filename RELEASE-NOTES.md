# WithHina v1.2 — Mascote à esquerda

- Hina movida para o lado esquerdo do cabeçalho do conversor.
- Balão de fala e rótulo Hina Converter movidos para a direita.
- Breakpoints desktop, tablet e mobile ajustados para preservar a mesma composição.
- Elementos decorativos reposicionados para acompanhar a nova direção visual.

# Hina Converter — Release preparada

## Interface

- Hina reclinada integrada ao topo do conversor.
- Fundo da ilustração tratado para uso transparente.
- Imagem WebP otimizada com fallback PNG.
- Paleta branco perolado, rosa suave, dourado e marrom-escuro.
- Layout responsivo para desktop e celular.
- Mensagens contextuais da Hina.

## Conversor

- Arquivo local com 128/192/256/320 kbps.
- Link com 128/192/256/320 kbps.
- Backend recebe a qualidade escolhida.
- Tratamento de erros e feedback de progresso.

## Backend

- Validação de URL do YouTube.
- Limite de duração.
- Limite de tamanho do resultado.
- Rate limit básico.
- Timeout de processamento.
- CORS configurável.
- Headers de segurança.
- Limpeza de arquivos temporários.
- Container executado como usuário sem privilégios.

## Site

- Página `Hina.html` refeita para a identidade atual.
- Política de privacidade revisada.
- Termos revisados.
- Consentimento opcional para Analytics.
- SEO básico, sitemap, robots.txt, favicon, manifest e 404.
- `render.yaml` na raiz para facilitar deploy do backend.

### Ajuste de mascote
- Hina reduzida no topo do conversor para funcionar como mascote, não como imagem principal.
- Área de apresentação compactada para priorizar a ferramenta.
- Balão reposicionado à esquerda e personagem à direita, com escala menor no desktop e no celular.
