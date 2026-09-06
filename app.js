(() => {
  "use strict";

  const MAX_FILE_SIZE = 250 * 1024 * 1024;
  const CORE_PATH = "https://unpkg.com/@ffmpeg/core@0.11.0/dist/ffmpeg-core.js";
  const CONSENT_KEY = "withhina_analytics_consent_v1";
  const config = window.HINA_CONFIG || {};
  const $ = (selector) => document.querySelector(selector);
  const $$ = (selector) => [...document.querySelectorAll(selector)];

  const HINA_MESSAGES = {
    idle: ["Oi, eu sou a Hina.", "Como quer começar?"],
    fileReady: ["Tudo certo.", "Quando quiser, eu converto esse arquivo para MP3."],
    linkReady: ["Me envie o link.", "Eu preparo o áudio para você."],
    processing: ["Só um momento.", "Estou preparando seu áudio…"],
    success: ["Prontinho.", "Seu MP3 está aqui."],
    error: ["Hmm…", "Algo não colaborou. Vamos tentar de novo?"]
  };

  const elements = {
    tabs: $$(".tab"),
    filePanel: $("#file-panel"),
    linkPanel: $("#link-panel"),
    fileInput: $("#media-file"),
    fileLabel: $("#file-label"),
    dropZone: $("#drop-zone"),
    bitrate: $("#bitrate"),
    convertFile: $("#convert-file"),
    urlInput: $("#media-url"),
    linkBitrate: $("#link-bitrate"),
    convertLink: $("#convert-link"),
    status: $("#status"),
    statusText: $("#status-text"),
    statusPercent: $("#status-percent"),
    progressBar: $("#progress-bar"),
    result: $("#result"),
    resultName: $("#result-name"),
    download: $("#download-result"),
    hinaTitle: $("#hina-title"),
    hinaBody: $("#hina-body"),
    consentBanner: $("#consent-banner"),
    consentAccept: $("#consent-accept"),
    consentEssential: $("#consent-essential")
  };

  let selectedFile = null;
  let ffmpeg = null;
  let resultUrl = null;
  let activeTab = "file";
  let analyticsLoaded = false;

  function setHinaMessage(key) {
    const [title, body] = HINA_MESSAGES[key] || HINA_MESSAGES.idle;
    if (elements.hinaTitle) elements.hinaTitle.textContent = title;
    if (elements.hinaBody) elements.hinaBody.textContent = body;
  }

  function syncIdleMessage() {
    if (activeTab === "link") {
      setHinaMessage("linkReady");
      return;
    }
    setHinaMessage(selectedFile ? "fileReady" : "idle");
  }

  function switchTab(name) {
    activeTab = name;
    elements.tabs.forEach((tab) => {
      const active = tab.dataset.tab === name;
      tab.classList.toggle("is-active", active);
      tab.setAttribute("aria-selected", String(active));
    });
    elements.filePanel.hidden = name !== "file";
    elements.linkPanel.hidden = name !== "link";
    clearFeedback(true);
    syncIdleMessage();
  }

  function clearFeedback(preserveMessage = false) {
    elements.status.hidden = true;
    elements.result.hidden = true;
    elements.progressBar.style.width = "0%";
    elements.statusPercent.textContent = "";
    if (resultUrl) {
      URL.revokeObjectURL(resultUrl);
      resultUrl = null;
    }
    if (!preserveMessage) syncIdleMessage();
  }

  function showStatus(message, percent = null, isError = false) {
    elements.result.hidden = true;
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
    setHinaMessage(isError ? "error" : "processing");
  }

  function showResult(blob, filename) {
    if (resultUrl) URL.revokeObjectURL(resultUrl);
    resultUrl = URL.createObjectURL(blob);
    elements.status.hidden = true;
    elements.result.hidden = false;
    elements.resultName.textContent = filename;
    elements.download.href = resultUrl;
    elements.download.download = filename;
    setHinaMessage("success");
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
    elements.fileLabel.textContent = "Escolha um áudio ou vídeo";
    elements.dropZone.classList.remove("has-file");
    elements.convertFile.disabled = true;
  }

  function selectFile(file) {
    clearFeedback(true);
    if (!file) {
      selectedFile = null;
      resetSelectedFileLabel();
      syncIdleMessage();
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
    setHinaMessage("fileReady");
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
    if (!selectedFile) return;
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
      engine.FS("unlink", inputName);
      engine.FS("unlink", outputName);
    } catch (error) {
      console.error(error);
      showStatus("Não foi possível converter esse arquivo. Tente outro formato ou um arquivo menor.", null, true);
    } finally {
      elements.convertFile.disabled = false;
    }
  }

  function filenameFromHeader(header) {
    const utf = header && header.match(/filename\*=UTF-8''([^;]+)/i);
    const plain = header && header.match(/filename="?([^";]+)"?/i);
    try {
      return decodeURIComponent((utf && utf[1]) || (plain && plain[1]) || "audio.mp3");
    } catch {
      return "audio.mp3";
    }
  }

  async function convertLink() {
    const url = elements.urlInput.value.trim();
    if (!/^https?:\/\//i.test(url)) {
      showStatus("Cole um link completo e válido.", null, true);
      elements.urlInput.focus();
      return;
    }
    if (!config.linkApiUrl) {
      showStatus("O modo Link ainda precisa receber o endereço do servidor. O modo Arquivo já está disponível.", null, true);
      return;
    }

    elements.convertLink.disabled = true;
    showStatus("Buscando e preparando o áudio…", 12);
    try {
      const response = await fetch(`${config.linkApiUrl.replace(/\/$/, "")}/api/download`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          url,
          bitrate: Number(elements.linkBitrate.value)
        })
      });

      if (!response.ok) {
        const payload = await response.json().catch(() => ({}));
        throw new Error(payload.detail || "Não foi possível processar esse link.");
      }

      showStatus("Finalizando o MP3…", 85);
      const blob = await response.blob();
      const filename = filenameFromHeader(response.headers.get("content-disposition"));
      showResult(blob, filename.endsWith(".mp3") ? filename : `${filename}.mp3`);
    } catch (error) {
      showStatus(error.message || "Não foi possível processar esse link.", null, true);
    } finally {
      elements.convertLink.disabled = false;
    }
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
    try {
      localStorage.setItem(CONSENT_KEY, value);
    } catch {
      // O site continua funcionando mesmo se o armazenamento local estiver bloqueado.
    }
    if (elements.consentBanner) elements.consentBanner.hidden = true;
    if (value === "accepted") loadAnalytics();
  }

  function setupAnalyticsConsent() {
    if (!config.analyticsId || !elements.consentBanner) return;

    let stored = null;
    try {
      stored = localStorage.getItem(CONSENT_KEY);
    } catch {
      stored = null;
    }

    if (stored === "accepted") {
      loadAnalytics();
      return;
    }
    if (stored === "essential") return;

    elements.consentBanner.hidden = false;
    elements.consentAccept.addEventListener("click", () => setAnalyticsConsent("accepted"));
    elements.consentEssential.addEventListener("click", () => setAnalyticsConsent("essential"));
  }

  elements.tabs.forEach((tab) => tab.addEventListener("click", () => switchTab(tab.dataset.tab)));
  elements.fileInput.addEventListener("change", () => selectFile(elements.fileInput.files[0]));
  elements.convertFile.addEventListener("click", convertLocalFile);
  elements.convertLink.addEventListener("click", convertLink);
  elements.urlInput.addEventListener("focus", () => {
    if (activeTab === "link" && elements.status.hidden && elements.result.hidden) setHinaMessage("linkReady");
  });
  elements.urlInput.addEventListener("keydown", (event) => {
    if (event.key === "Enter") convertLink();
  });

  ["dragenter", "dragover"].forEach((type) => elements.dropZone.addEventListener(type, (event) => {
    event.preventDefault();
    elements.dropZone.classList.add("is-dragging");
  }));
  ["dragleave", "drop"].forEach((type) => elements.dropZone.addEventListener(type, (event) => {
    event.preventDefault();
    elements.dropZone.classList.remove("is-dragging");
  }));
  elements.dropZone.addEventListener("drop", (event) => selectFile(event.dataTransfer.files[0]));

  const year = $("#current-year");
  if (year) year.textContent = new Date().getFullYear();
  setupAds();
  setupAnalyticsConsent();
  syncIdleMessage();
})();
