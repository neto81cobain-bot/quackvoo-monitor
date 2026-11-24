// QuackVoo 🦆 — porteiro do Telegram (Cloudflare Worker, grátis)
// Recebe seu comando na hora e acorda o vigia no GitHub (resposta em ~1 min).
// Segredos do Worker: BOT_TOKEN (token do bot) e GH_TOKEN (token do GitHub com Actions: write).
// Depois de publicar, abra  https://SEU-WORKER.workers.dev/ligar  uma vez.

const REPO = "neto81cobain-bot/quackvoo-monitor";

async function segredo(env) {
  const h = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(env.BOT_TOKEN));
  return [...new Uint8Array(h)].map(b => b.toString(16).padStart(2, "0")).join("").slice(0, 40);
}
const tg = (env, metodo, corpo) => fetch(`https://api.telegram.org/bot${env.BOT_TOKEN}/${metodo}`, {
  method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(corpo) });

export default {
  async fetch(req, env) {
    const url = new URL(req.url);
    if (!env.BOT_TOKEN || !env.GH_TOKEN) return new Response("Faltam os segredos BOT_TOKEN e GH_TOKEN.", { status: 500 });

    if (req.method === "GET" && url.pathname === "/ligar") {
      const r = await tg(env, "setWebhook", { url: `${url.origin}/telegram`, secret_token: await segredo(env), allowed_updates: ["message"] });
      const j = await r.json();
      return new Response(j.ok ? "✅ Ligado! Mande /status pro bot." : "❌ " + JSON.stringify(j), { headers: { "Content-Type": "text/plain; charset=utf-8" } });
    }
    if (req.method === "GET" && url.pathname === "/desligar") {
      const j = await (await tg(env, "deleteWebhook", {})).json();
      return new Response(j.ok ? "Desligado (o vigia volta a ler os comandos sozinho)." : JSON.stringify(j), { headers: { "Content-Type": "text/plain; charset=utf-8" } });
    }
    if (req.method !== "POST" || url.pathname !== "/telegram") return new Response("QuackVoo 🦆 no ar.", { headers: { "Content-Type": "text/plain; charset=utf-8" } });
    if (req.headers.get("X-Telegram-Bot-Api-Secret-Token") !== await segredo(env)) return new Response("não", { status: 403 });

    const m = (await req.json()).message;
    if (!m || !(m.text || "").startsWith("/")) return new Response("ok");
    await tg(env, "sendChatAction", { chat_id: m.chat.id, action: "typing" });
    const r = await fetch(`https://api.github.com/repos/${REPO}/actions/workflows/vigia.yml/dispatches`, {
      method: "POST",
      headers: { Authorization: `Bearer ${env.GH_TOKEN}`, Accept: "application/vnd.github+json", "User-Agent": "quackvoo-worker" },
      body: JSON.stringify({ ref: "main", inputs: { comando: JSON.stringify({ chat: m.chat.id, texto: m.text }) } }),
    });
    if (!r.ok) await tg(env, "sendMessage", { chat_id: m.chat.id, text: `⚠️ Não consegui acordar o vigia (GitHub ${r.status}). Confira o GH_TOKEN do Worker.` });
    return new Response("ok");
  },
};
