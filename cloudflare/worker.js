// QuackVoo 🦆 — porteiro do Telegram (Cloudflare Worker, grátis)
// Recebe seu comando na hora e acorda o vigia no GitHub (resposta em ~1 min).
// Só precisa de UM segredo: GH_TOKEN (token do GitHub com Actions: write no quackvoo-monitor).
// Depois de publicar, abra  https://SEU-WORKER.workers.dev/ligar  uma vez.
// Segurança: o vigia só obedece ao seu TELEGRAM_CHAT_ID; o Worker apenas repassa.

const REPO = "neto81cobain-bot/quackvoo-monitor";
const txt = (t, s = 200) => new Response(t, { status: s, headers: { "Content-Type": "text/plain; charset=utf-8" } });

async function acordarVigia(env, inputs) {
  return fetch(`https://api.github.com/repos/${REPO}/actions/workflows/vigia.yml/dispatches`, {
    method: "POST",
    headers: { Authorization: `Bearer ${env.GH_TOKEN}`, Accept: "application/vnd.github+json", "User-Agent": "quackvoo-worker" },
    body: JSON.stringify({ ref: "main", inputs }),
  });
}

export default {
  async fetch(req, env) {
    const url = new URL(req.url);
    if (!env.GH_TOKEN) return txt("Falta o segredo GH_TOKEN no Worker (Settings → Variables and Secrets).", 500);

    if (req.method === "GET" && url.pathname === "/ligar") {
      // o vigia (que já tem o token do bot) registra este endereço no Telegram
      const r = await acordarVigia(env, { webhook: `${url.origin}/telegram` });
      return r.ok ? txt("✅ Pedido enviado! Em ~1 minuto o bot te manda “Comandos rápidos ligados”.")
                  : txt(`❌ O GitHub recusou (${r.status}): confira se o GH_TOKEN tem Actions: Read and write no quackvoo-monitor.\n${await r.text()}`, 500);
    }
    if (req.method !== "POST" || url.pathname !== "/telegram") return txt("QuackVoo 🦆 no ar.");

    const m = (await req.json().catch(() => ({}))).message;
    if (!m || !String(m.text || "").startsWith("/")) return txt("ok");
    await acordarVigia(env, { comando: JSON.stringify({ chat: m.chat.id, texto: m.text }) });
    return txt("ok");
  },
};
