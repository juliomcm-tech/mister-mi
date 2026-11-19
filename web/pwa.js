/** Installation is always user initiated; offline mode never supplies old predictions. */
export function initPWA({ onStatus, onOffline } = {}) {
  const $ = id => document.getElementById(id);
  const buttons = [$("install-app"), $("install-app-settings")].filter(Boolean);
  const listeners = [];
  let promptEvent = null, disposed = false, applyingUpdate = false, prompting = false, idle = null;
  let registration = null, resolveRegistration;
  const registered = new Promise(resolve => { resolveRegistration = resolve; });
  const listen = (target, type, handler) => {
    if (!target?.addEventListener) return;
    target.addEventListener(type, handler);
    listeners.push(() => target.removeEventListener(type, handler));
  };
  const standalone = () => window.matchMedia?.("(display-mode: standalone)").matches || navigator.standalone === true;
  let isInstalled = !!standalone();
  const status = (state, message) => {
    if (disposed) return;
    const label = $("install-status");
    if (label) { label.textContent = message; label.dataset.state = state; }
    onStatus?.({ state, message });
  };
  const installed = () => {
    isInstalled = true;
    for (const button of buttons) button.hidden = true;
    promptEvent = null;
    status("installed", "Mister Mi está instalado neste dispositivo.");
  };
  const instructions = () => {
    const ios = /iphone|ipad|ipod/i.test(navigator.userAgent || "")
      || (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1);
    const message = ios
      ? "No iPhone ou iPad, abre esta página no Safari, toca em Partilhar e escolhe Adicionar ao ecrã principal. Confirma em Adicionar."
      : "Abre o menu do navegador e procura Instalar aplicação ou Adicionar ao ecrã principal. A opção depende do navegador e do dispositivo.";
    const body = $("install-instructions"), dialog = $("install-dialog");
    if (body) body.textContent = message;
    if (dialog && !dialog.open) {
      if (typeof dialog.showModal === "function") dialog.showModal();
      else { dialog.hidden = false; dialog.setAttribute("open", ""); }
    }
    status("manual", message);
  };
  const install = async event => {
    event?.preventDefault();
    if (isInstalled || standalone()) { installed(); return; }
    if (prompting) return;
    if (!promptEvent) { instructions(); return; }
    const candidate = promptEvent;
    promptEvent = null;
    prompting = true;
    try {
      await candidate.prompt();
      const choice = await candidate.userChoice;
      if (!disposed && !isInstalled) status(choice?.outcome === "accepted" ? "requested" : "available",
        choice?.outcome === "accepted" ? "Pedido de instalação aceite. Aguarda a confirmação do navegador."
          : "Podes voltar a instalar o Mister Mi pelo menu do navegador.");
    } catch { if (!disposed && !isInstalled) instructions(); }
    finally { prompting = false; }
  };
  for (const button of buttons) { button.hidden = !!standalone(); listen(button, "click", install); }
  listen(window, "beforeinstallprompt", event => {
    if (isInstalled || standalone() || typeof event.prompt !== "function") return;
    event.preventDefault();
    promptEvent = event;
    status("available", "Mister Mi pode ser instalado no teu dispositivo.");
  });
  listen(window, "appinstalled", installed);
  const connectivity = () => onOffline?.(navigator.onLine === false);
  listen(window, "online", connectivity);
  listen(window, "offline", connectivity);
  connectivity();
  if (standalone()) installed();
  else status("available", "Instala o Mister Mi para o abrir a partir do ecrã principal.");

  const updateAvailable = () => {
    if (disposed) return;
    const banner = $("app-update");
    if (banner) banner.hidden = !(registration?.waiting && navigator.serviceWorker.controller);
  };
  listen($("apply-update"), "click", event => {
    event.preventDefault();
    if (!registration?.waiting) return;
    applyingUpdate = true;
    registration.waiting.postMessage({ type: "SKIP_WAITING" });
  });
  const register = async () => {
    if (disposed) return;
    try {
      registration = await navigator.serviceWorker.register("./sw.js", { scope: "./" });
      if (disposed) { resolveRegistration(registration); return; }
      updateAvailable();
      const watchInstalling = () => {
        const worker = registration.installing;
        listen(worker, "statechange", () => { if (worker.state === "installed") updateAvailable(); });
      };
      listen(registration, "updatefound", watchInstalling);
      watchInstalling();
      listen(navigator.serviceWorker, "controllerchange", () => {
        if (applyingUpdate) window.location.reload();
        else updateAvailable();
      });
      resolveRegistration(registration);
    } catch {
      // Manual home-screen installation can still be available without offline support.
      if (!standalone()) status("manual", "O modo offline não ficou disponível. Podes tentar instalar pelo menu do navegador.");
      resolveRegistration(null);
    }
  };
  if ("serviceWorker" in navigator && window.isSecureContext !== false) {
    idle = window.requestIdleCallback ? window.requestIdleCallback(register, { timeout: 2000 }) : window.setTimeout(register, 0);
  } else resolveRegistration(null);
  return {
    registration: registered,
    dispose() {
      disposed = true;
      for (const remove of listeners) remove();
      if (idle !== null) {
        if (window.requestIdleCallback) window.cancelIdleCallback?.(idle);
        else window.clearTimeout(idle);
      }
      resolveRegistration(null);
    },
  };
}
