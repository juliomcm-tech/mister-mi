// A widget is display content, not a prediction source or an API credential.
const STORAGE_KEY = 'mister-mi.oddspedia-widget';
const MAX_CODE_BYTES = 256 * 1024;
const PROVIDER_URL = /https:\/\/(?:[a-z0-9-]+\.)*oddspedia\.com(?=[/?#\s"'<>\\]|$)/i;
const ORIGINS = 'https://oddspedia.com https://*.oddspedia.com';
export const WIDGET_SANDBOX = 'allow-scripts allow-popups allow-popups-to-escape-sandbox';
export const WIDGET_CSP = `default-src 'none'; script-src 'unsafe-inline' ${ORIGINS}; style-src 'unsafe-inline' ${ORIGINS}; img-src data: ${ORIGINS}; font-src data: ${ORIGINS}; connect-src ${ORIGINS}; frame-src ${ORIGINS}; media-src ${ORIGINS}; object-src 'none'; base-uri 'none'; form-action 'none'`;

export function validateWidgetCode(value) {
 if (typeof value !== 'string' || !value.trim()) throw new Error('Cola o código completo do widget fornecido pela Oddspedia.');
 const code = value.trim();
 if (new TextEncoder().encode(code).length > MAX_CODE_BYTES) throw new Error('O código excede 256 KB. Confirma que copiaste apenas o widget.');
 if (!/<(?:iframe|script)(?=[\s>])/i.test(code) || !PROVIDER_URL.test(code)) throw new Error('Não reconheci um widget Oddspedia. Copia o código de incorporação completo, incluindo as etiquetas HTML.');
 return code;
}

export function widgetHeight(value) {
 const height = Number(value);
 return Number.isFinite(height) ? Math.min(1600, Math.max(400, Math.round(height))) : 760;
}

export function widgetDocument(value) {
 const code = validateWidgetCode(value);
 // CSP is first and cannot be relaxed by a policy inside the pasted fragment.
 // No allow-same-origin: provider scripts cannot read the app or its storage.
 return `<!doctype html><html lang="pt"><head><meta charset="utf-8"><meta http-equiv="Content-Security-Policy" content="${WIDGET_CSP}"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="referrer" content="strict-origin-when-cross-origin"><style>html,body{margin:0;padding:0;min-height:100%;background:#fff}body{overflow:auto}iframe{max-width:100%}</style></head><body>${code}</body></html>`;
}

export function createWidgetFrame(doc, code, height) {
 const frame = doc.createElement('iframe');
 frame.className = 'oddspedia-frame';
 frame.title = 'Oddspedia — jogos e comparação de odds';
 frame.setAttribute('sandbox', WIDGET_SANDBOX);
 frame.setAttribute('referrerpolicy', 'strict-origin-when-cross-origin');
 frame.style.height = `${widgetHeight(height)}px`;
 frame.srcdoc = widgetDocument(code);
 return frame;
}

export function initOddspediaWidget({onOpen, onToast, storage = localStorage}) {
 const $ = id => document.getElementById(id);
 let saved = null, mounted = '', currentView = '';
 try {
  const value = JSON.parse(storage.getItem(STORAGE_KEY));
  if (value?.code) saved = {code:validateWidgetCode(value.code), height:widgetHeight(value.height)};
 } catch { /* A corrupt preference must not prevent the app from opening. */ }
 $('oddspedia-code').value = saved?.code ?? '';
 $('oddspedia-height').value = saved?.height ?? 760;
 $('oddspedia-domain').textContent = location.hostname;
 const status = message => { $('oddspedia-status').textContent = message; };
 const sync = () => {
  const configured = Boolean(saved);
  $('oddspedia-empty').hidden = configured;
  $('oddspedia-content').hidden = !configured;
  $('oddspedia-remove').disabled = !configured;
  $('oddspedia-attribution').hidden = !configured;
  const logo = $('oddspedia-logo');
  if (configured && !logo.getAttribute('src')) logo.src = 'https://widgets.oddspedia.com/img/static/Oddspedia_logo.svg';
  if (!configured) logo.removeAttribute('src');
  if (configured && currentView === 'fontes') {
   const key = `${saved.height}:${saved.code}`;
   if (key !== mounted) {
    $('oddspedia-mount').replaceChildren(createWidgetFrame(document, saved.code, saved.height));
    mounted = key;
   }
  } else {
   $('oddspedia-mount').replaceChildren();
   mounted = '';
  }
 };
 status(saved ? 'Código guardado neste dispositivo. O widget está disponível em Fontes.' : 'Ainda sem widget configurado.');
 $('oddspedia-form').onsubmit = event => {
  event.preventDefault();
  try {
   const next = {code:validateWidgetCode($('oddspedia-code').value), height:widgetHeight($('oddspedia-height').value)};
   storage.setItem(STORAGE_KEY, JSON.stringify(next));
   saved = next;
   $('oddspedia-height').value = next.height;
   status('Código guardado neste dispositivo. A apresentação depende da configuração do domínio na Oddspedia.');
   sync();
   onOpen();
   onToast('Widget guardado. Confirma a apresentação no painel Oddspedia.');
  } catch (error) {
   status(error.name === 'QuotaExceededError' || error.name === 'SecurityError' ? 'O navegador não permitiu guardar o widget. Verifica o armazenamento deste site.' : error.message);
  }
 };
 $('oddspedia-remove').onclick = () => {
  try { storage.removeItem(STORAGE_KEY); }
  catch { status('O navegador não permitiu remover a configuração.'); return; }
  saved = null;
  $('oddspedia-code').value = '';
  status('Widget removido deste dispositivo.');
  sync();
  onToast('Widget removido.');
 };
 sync();
 return {show(view) { currentView = view; sync(); }};
}
