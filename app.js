(() => {
  "use strict";

  const MAX_FILE_SIZE = 250 * 1024 * 1024;
  const CORE_PATH = "https://unpkg.com/@ffmpeg/core@0.11.0/dist/ffmpeg-core.js";
  const CONSENT_KEY = "withhina_analytics_consent_v1";
  const config = window.HINA_CONFIG || {};
  const $ = (selector) => document.querySelector(selector);
  const $$ = (selector) => [...document.querySelectorAll(selector)];

  const elements = {
    fileInput: $("#media-file"),
    fileLabel: $("#file-label"),
    dropZone: $("#drop-zone"),
    bitrate: $("#bitrate"),
    convertFile: $("#convert-file"),
    status: $("#status"),
    statusText: $("#status-text"),
    statusPercent: $("#status-percent"),
    progressBar: $("#progress-bar"),
    result: $("#result"),
    resultName: $("#result-name"),
    download: $("#download-result"),
    consentBanner: $("#consent-banner"),
    consentAccept: $("#consent-accept"),
    consentEssential: $("#consent-essential")
  };

  let selectedFile = null;
  let ffmpeg = null;
  let resultUrl = null;
  let analyticsLoaded = false;

  function clearFeedback() {
    if (elements.status) elements.status.hidden = true;
    if (elements.result) elements.result.hidden = true;
    if (elements.progressBar) elements.progressBar.style.width = "0%";
    if (elements.statusPercent) elements.statusPercent.textContent = "";
    if (resultUrl) {
      URL.revokeObjectURL(resultUrl);
      resultUrl = null;
    }
  }

  function showStatus(message, percent = null, isError = false) {
    if (!elements.status) return;
    if (elements.result) elements.result.hidden = true;
    elements.status.hidden = false;
    elements.status.classList.toggle("is-error", isError);
    elements.statusText.textContent = message;
    if (percent === null) {
      elements.statusPercent.textContent = "";
      elements.progressBar.style.width = isError ? "100%" : "12%";
    } else {
      const value = Math.max(0, Math.min(100, Math.round(percent)));
      elements.statusPercent.textContent = `${value}%`;
      elements.progressBar.style.width = `${value}%`;
    }
  }

  function showResult(blob, filename) {
    if (!elements.result) return;
    if (resultUrl) URL.revokeObjectURL(resultUrl);
    resultUrl = URL.createObjectURL(blob);
    if (elements.status) elements.status.hidden = true;
    elements.result.hidden = false;
    elements.resultName.textContent = filename;
    elements.download.href = resultUrl;
    elements.download.download = filename;
  }

  function safeBaseName(name) {
    return name
      .replace(/\.[^/.]+$/, "")
      .normalize("NFKD")
      .replace(/[\u0300-\u036f]/g, "")
      .replace(/[^a-zA-Z0-9 _-]/g, "")
      .trim()
      .slice(0, 120) || "audio";
  }

  function resetSelectedFileLabel() {
    if (!elements.fileLabel || !elements.dropZone || !elements.convertFile) return;
    elements.fileLabel.textContent = "Escolha um áudio ou vídeo";
    elements.dropZone.classList.remove("has-file");
    elements.convertFile.disabled = true;
  }

  function selectFile(file) {
    clearFeedback();
    if (!file) {
      selectedFile = null;
      resetSelectedFileLabel();
      return;
    }
    if (!(file.type.startsWith("audio/") || file.type.startsWith("video/"))) {
      selectedFile = null;
      resetSelectedFileLabel();
      showStatus("Escolha um arquivo de áudio ou vídeo válido.", null, true);
      return;
    }
    if (file.size > MAX_FILE_SIZE) {
      selectedFile = null;
      resetSelectedFileLabel();
      showStatus("Esse arquivo ultrapassa o limite de 250 MB.", null, true);
      return;
    }
    selectedFile = file;
    elements.fileLabel.textContent = file.name;
    elements.dropZone.classList.add("has-file");
    elements.convertFile.disabled = false;
  }

  async function getFFmpeg() {
    if (!window.FFmpeg) throw new Error("O componente de conversão não pôde ser carregado.");
    if (!ffmpeg) {
      const { createFFmpeg } = window.FFmpeg;
      ffmpeg = createFFmpeg({ log: false, corePath: CORE_PATH });
      ffmpeg.setProgress(({ ratio }) => showStatus("Convertendo para MP3…", ratio * 100));
    }
    if (!ffmpeg.isLoaded()) {
      showStatus("Carregando o conversor pela primeira vez…", 5);
      await ffmpeg.load();
    }
    return ffmpeg;
  }

  async function convertLocalFile() {
    if (!selectedFile || !elements.convertFile) return;
    elements.convertFile.disabled = true;
    const extension = (selectedFile.name.split(".").pop() || "media").replace(/[^a-z0-9]/gi, "");
    const inputName = `input.${extension || "media"}`;
    const outputName = "output.mp3";
    try {
      const engine = await getFFmpeg();
      const { fetchFile } = window.FFmpeg;
      engine.FS("writeFile", inputName, await fetchFile(selectedFile));
      showStatus("Extraindo e convertendo o áudio…", 10);
      await engine.run(
        "-i", inputName,
        "-vn",
        "-codec:a", "libmp3lame",
        "-b:a", `${elements.bitrate.value}k`,
        outputName
      );
      const data = engine.FS("readFile", outputName);
      const blob = new Blob([data.buffer], { type: "audio/mpeg" });
      showResult(blob, `${safeBaseName(selectedFile.name)}.mp3`);
      try { engine.FS("unlink", inputName); } catch {}
      try { engine.FS("unlink", outputName); } catch {}
    } catch (error) {
      console.error(error);
      showStatus("Não foi possível converter esse arquivo. Tente outro formato ou um arquivo menor.", null, true);
    } finally {
      elements.convertFile.disabled = false;
    }
  }

  function setupPurchase() {
    const buttons = $$('[data-price-region]');
    const price = $('#purchase-price');
    const label = $('#purchase-label');
    const caption = $('#purchase-caption');
    const buyButton = $('#purchase-button');
    const heroBuy = $('#hero-buy');
    const navBuy = $('#nav-buy');
    if (!buttons.length || !price || !buyButton) return;

    const checkout = config.buyUrls || {};
    const products = {
      br: {
        price: 'R$ 24,99',
        label: 'Preço no Brasil',
        caption: 'Pagamento único · sem assinatura',
        button: 'Comprar o app',
        hero: 'Comprar o app — R$ 24,99',
        nav: 'Comprar app',
        fallback: 'mailto:support@withhina.com?subject=Comprar%20WithHina%20-%20Brasil'
      },
      intl: {
        price: 'US$ 4.99',
        label: 'International price',
        caption: 'One-time purchase · no subscription',
        button: 'Buy the app',
        hero: 'Buy the app — US$ 4.99',
        nav: 'Buy app',
        fallback: 'mailto:support@withhina.com?subject=Buy%20WithHina%20-%20International'
      }
    };

    function apply(region) {
      const item = products[region] || products.br;
      buttons.forEach((button) => {
        const active = button.dataset.priceRegion === region;
        button.classList.toggle('is-active', active);
        button.setAttribute('aria-pressed', String(active));
      });
      price.textContent = item.price;
      if (label) label.textContent = item.label;
      if (caption) caption.textContent = item.caption;
      buyButton.textContent = item.button;
      buyButton.href = checkout[region] || item.fallback;
      if (/^https?:/i.test(buyButton.href)) {
        buyButton.target = '_blank';
        buyButton.rel = 'noopener';
      } else {
        buyButton.removeAttribute('target');
        buyButton.removeAttribute('rel');
      }
      if (heroBuy) heroBuy.textContent = item.hero;
      if (navBuy) navBuy.textContent = item.nav;
    }

    const defaultRegion = /^pt-BR$/i.test(navigator.language || '') ? 'br' : 'intl';
    buttons.forEach((button) => button.addEventListener('click', () => apply(button.dataset.priceRegion)));
    apply(defaultRegion);
  }

  function setupAds() {
    const client = config.adsenseClient;
    if (!client) return;
    const script = document.createElement("script");
    script.async = true;
    script.crossOrigin = "anonymous";
    script.src = `https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=${encodeURIComponent(client)}`;
    document.head.appendChild(script);
    $$(".ad-container").forEach((container) => {
      const position = container.dataset.adPosition;
      const slot = config.adsenseSlots && config.adsenseSlots[position];
      if (!slot) return;
      const ad = container.querySelector(".adsbygoogle");
      ad.dataset.adClient = client;
      ad.dataset.adSlot = slot;
      container.hidden = false;
      script.addEventListener("load", () => (window.adsbygoogle = window.adsbygoogle || []).push({}), { once: true });
    });
  }

  function loadAnalytics() {
    const measurementId = config.analyticsId;
    if (!measurementId || analyticsLoaded) return;
    analyticsLoaded = true;
    window.dataLayer = window.dataLayer || [];
    window.gtag = function gtag(){ window.dataLayer.push(arguments); };
    window.gtag("js", new Date());
    window.gtag("config", measurementId, { anonymize_ip: true });
    const script = document.createElement("script");
    script.async = true;
    script.src = `https://www.googletagmanager.com/gtag/js?id=${encodeURIComponent(measurementId)}`;
    document.head.appendChild(script);
  }

  function setAnalyticsConsent(value) {
    try { localStorage.setItem(CONSENT_KEY, value); } catch {}
    if (elements.consentBanner) elements.consentBanner.hidden = true;
    if (value === "accepted") loadAnalytics();
  }

  function setupAnalyticsConsent() {
    if (!config.analyticsId || !elements.consentBanner) return;
    let stored = null;
    try { stored = localStorage.getItem(CONSENT_KEY); } catch {}
    if (stored === "accepted") { loadAnalytics(); return; }
    if (stored === "essential") return;
    elements.consentBanner.hidden = false;
    elements.consentAccept?.addEventListener("click", () => setAnalyticsConsent("accepted"));
    elements.consentEssential?.addEventListener("click", () => setAnalyticsConsent("essential"));
  }

  if (elements.fileInput) elements.fileInput.addEventListener("change", () => selectFile(elements.fileInput.files[0]));
  if (elements.convertFile) elements.convertFile.addEventListener("click", convertLocalFile);

  if (elements.dropZone) {
    ["dragenter", "dragover"].forEach((type) => elements.dropZone.addEventListener(type, (event) => {
      event.preventDefault();
      elements.dropZone.classList.add("is-dragging");
    }));
    ["dragleave", "drop"].forEach((type) => elements.dropZone.addEventListener(type, (event) => {
      event.preventDefault();
      elements.dropZone.classList.remove("is-dragging");
    }));
    elements.dropZone.addEventListener("drop", (event) => selectFile(event.dataTransfer.files[0]));
  }

  const year = $("#current-year");
  if (year) year.textContent = new Date().getFullYear();
  setupPurchase();
  setupAds();
  setupAnalyticsConsent();
})();
