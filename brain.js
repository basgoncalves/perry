/* Perry's general brain — used when a question isn't about your own finances.
   1. "Smart mode" (opt-in, Settings): a small AI model (Qwen2.5 0.5B) that runs
      entirely on this device via WebGPU. ~400 MB download once, then cached;
      works offline. Your data never leaves the phone.
   2. Otherwise: a quick Wikipedia lookup. */
const MODEL = 'Qwen2.5-0.5B-Instruct-q4f16_1-MLC';
const WEBLLM = 'https://cdn.jsdelivr.net/npm/@mlc-ai/web-llm@0.2.86/+esm';
let engine = null, loading = null;
const history = [];

export const smartSupported = () => !!navigator.gpu;

export async function loadSmart(onProgress = () => {}) {
  if (engine) return engine;
  if (!smartSupported()) throw new Error("This browser has no WebGPU, so the on-device model can't run here.");
  loading ??= (async () => {
    const webllm = await import(WEBLLM);
    engine = await webllm.CreateMLCEngine(MODEL, {
      initProgressCallback: p => onProgress(Math.round((p.progress || 0) * 100), p.text || '')
    });
    return engine;
  })().catch(e => { loading = null; throw e; });
  return loading;
}

export const smartReady = () => !!engine;

async function askModel(q, context) {
  const sys = "You are Perry, a witty, concise Jarvis-style assistant who calls the user 'sir'. " +
    "Answer in at most 3 short sentences. If unsure, say so instead of inventing facts. " +
    "Never give personalised buy/sell advice. Context about the user's finances (use only if relevant): " + context;
  history.push({ role: 'user', content: q });
  while (history.length > 8) history.shift();
  const r = await engine.chat.completions.create({
    messages: [{ role: 'system', content: sys }, ...history],
    temperature: 0.4, max_tokens: 160
  });
  const a = r.choices[0].message.content.trim();
  history.push({ role: 'assistant', content: a });
  return a;
}

async function askWikipedia(q) {
  const term = q.replace(/^(what|who|where|when|which|how)( is| are| was| were| did| does| do)?( the| a| an)?\s+/i, '')
                .replace(/\?+$/, '').replace(/ in the world$/i, '');
  const u = 'https://en.wikipedia.org/w/api.php?origin=*&format=json&action=query&generator=search&gsrlimit=1' +
            '&prop=extracts&exintro=1&explaintext=1&exsentences=2&redirects=1&gsrsearch=' + encodeURIComponent(term);
  const d = await (await fetch(u)).json();
  const p = d.query && Object.values(d.query.pages)[0];
  if (!p || !p.extract) return null;
  return `${p.extract.trim()}\n— Wikipedia: ${p.title}` +
         (smartSupported() && !engine ? "\n(Turn on Smart Perry in Settings for proper conversation.)" : '');
}

export async function think(q, context = '') {
  if (engine) {
    try { return await askModel(q, context); } catch (e) { console.warn(e); }
  }
  try {
    const w = await askWikipedia(q);
    if (w) return w;
  } catch (e) { console.warn(e); }
  return navigator.onLine === false
    ? "I'm offline, sir, and Smart Perry isn't loaded — I can only do your finances right now."
    : "I couldn't find that, sir. Say 'help' for what I do best.";
}
