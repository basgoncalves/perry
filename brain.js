/* Perry's general brain — used when a question isn't about your own finances.
   1. "Smart mode" (opt-in, Settings): a small AI model (Qwen2.5 1.5B) that runs
      entirely on this device via WebGPU. ~1 GB download once, then cached;
      works offline. Your data never leaves the phone.
   2. Otherwise: a quick Wikipedia lookup. */
const MODEL = 'Qwen2.5-1.5B-Instruct-q4f16_1-MLC';
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
  const sys = "You are Perry, a witty, warm, general-purpose Jarvis-style assistant. Always address the user as 'my lord' (never 'sir'). " +
    "Help with anything: questions, explanations, ideas, writing, planning, maths, jokes, chit-chat. Your replies are read aloud, " +
    "so answer in 1-3 short conversational sentences, no lists or markdown. If you don't know a fact, say so instead of inventing it. " +
    "Today is " + new Date().toDateString() + ". " +
    "Only if the user asks about their own money, use this context: " + context + " Never give personalised buy/sell advice.";
  history.push({ role: 'user', content: q });
  while (history.length > 8) history.shift();
  const r = await engine.chat.completions.create({
    messages: [{ role: 'system', content: sys }, ...history],
    temperature: 0.6, max_tokens: 200
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
    ? "I'm offline, my lord, and Smart Perry isn't loaded — I can only do your finances right now."
    : "I couldn't find that, my lord. Say 'help' for what I do best.";
}
