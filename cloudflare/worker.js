// QuackVoo 🦆 — o bot do Telegram (Cloudflare Worker, grátis)
// • Menu com botões: responde NA HORA (o Worker fala direto com o Telegram).
// • Barco e lancha: busca Yjara + Navegam daqui mesmo, em segundos.
// • O que precisa dos seus dados de voo (status, buscar agora, alvo…) acorda o vigia no GitHub (~1 min).
// Segredos: GH_TOKEN (Actions: write no quackvoo-monitor) e SERPAPI_KEY. KV "QV": guarda o token do bot e suas
// configurações, que o próprio vigia manda (provando com OIDC que é o seu repositório). Só obedece ao seu chat.

const REPO = "neto81cobain-bot/quackvoo-monitor";
const PAINEL = "https://neto81cobain-bot.github.io/quackvoo-monitor/painel.html";
const YJ_SITE = "https://yjaraviagens.com", YJ_API = "https://app.techrios.online/api";
const NAV = "https://navegam-fluvial-api-prod-979984919366.us-central1.run.app";
const WA_YJARA = "5593991893803", WA_NAV = "5592988552157";
const UA = { "User-Agent": "Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0 Mobile Safari/537.36",
             Accept: "application/json", "Accept-Language": "pt-BR,pt;q=0.9" };
const DIAS = 4;  // dias por página na busca de barco

const txt = (t, s = 200) => new Response(t, { status: s, headers: { "Content-Type": "text/plain; charset=utf-8" } });
const esc = (s) => String(s ?? "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
const rs = (v) => "R$ " + Number(v).toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 }).replace(",00", "");
const SEMANA = ["dom", "seg", "ter", "qua", "qui", "sex", "sáb"];
const hojeBR = () => new Date(Date.now() - 3 * 3600e3).toISOString().slice(0, 10);
const maisDias = (iso, n) => new Date(Date.parse(iso + "T12:00:00Z") + n * 864e5).toISOString().slice(0, 10);
const diaBR = (iso) => { const d = new Date(iso + "T12:00:00Z"); return `${SEMANA[d.getUTCDay()]} ${iso.slice(8, 10)}/${iso.slice(5, 7)}`; };

// ---------------------------------------------------------------- cidades
const NOMES = { oriximina: "Oriximiná", santarem: "Santarém", "terra-santa": "Terra Santa", obidos: "Óbidos", belem: "Belém",
  "alter-do-chao": "Alter do Chão", macapa: "Macapá", maues: "Maués", curua: "Curuá", gurupa: "Gurupá", nhamunda: "Nhamundá",
  urucara: "Urucará", trombetas: "Porto Trombetas", "monte-alegre": "Monte Alegre", juruti: "Juruti", parintins: "Parintins",
  manaus: "Manaus", faro: "Faro", alenquer: "Alenquer", prainha: "Prainha", almeirim: "Almeirim", itacoatiara: "Itacoatiara",
  santana: "Santana", breves: "Breves", itaituba: "Itaituba", barreirinha: "Barreirinha", "boa-vista-do-ramos": "Boa Vista do Ramos",
  "porto-de-moz": "Porto de Moz" };
const APELIDOS = { stm: "santarem", "porto-trombetas": "trombetas", mao: "manaus", bel: "belem", orx: "oriximina", orixi: "oriximina" };
const CIDADES = Object.keys(NOMES);
const semAcento = (s) => String(s).normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
function slug(c) {
  let s = semAcento(c).trim().replace(/\/(pa|am|ap)\b/g, "").replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
  return APELIDOS[s] || s;
}
const nome = (s) => NOMES[s] || s.replace(/-/g, " ").replace(/\b\w/g, (l) => l.toUpperCase());
const NAV_FIXO = { manaus: 1, parintins: 27, "terra-santa": 24, faro: 21, nhamunda: 20, santarem: 69, juruti: 72, obidos: 73 };

// "Oriximiná Santarém 12/12", "Oriximiná para Terra Santa", "orx > stm" → {o, d, dia}
function dataBR(s) {
  const m = String(s).match(/^(\d{1,2})\/(\d{1,2})(?:\/(\d{2,4}))?$/);
  if (!m) return null;
  const hoje = hojeBR();
  const ano = m[3] ? (m[3].length === 2 ? "20" + m[3] : m[3]) : hoje.slice(0, 4);
  let dia = `${ano}-${m[2].padStart(2, "0")}-${m[1].padStart(2, "0")}`;
  if (!m[3] && dia < hoje) dia = `${+ano + 1}${dia.slice(4)}`;
  return dia;
}
// "Oriximiná Santarém 12/12", "Oriximiná para Terra Santa", "orx > stm 12/12 a 15/12" → {o, d, dia, n}
function trecho(t) {
  let a = String(t).replace(/^\/barco(@\w+)?/i, "").trim().split(/\s+/).filter(Boolean);
  let dia = null, n = null;
  const datas = [];
  while (a.length && (dataBR(a[a.length - 1]) || /^(a|até|ate|-)$/i.test(a[a.length - 1]))) { const x = a.pop(); if (dataBR(x)) datas.unshift(dataBR(x)); }
  if (datas.length) {
    dia = datas[0];
    if (datas[1]) n = Math.round((Date.parse(datas[1]) - Date.parse(datas[0])) / 864e5) + 1;
  }
  const res = (o, d) => ({ o, d, dia, n: n && n > 0 ? Math.min(n, 7) : null });
  const junto = a.join(" ");
  const partes = junto.split(/\s*(?:>|→|->|,|\bpara\b|\bpra\b|\bate\b|\baté\b|\bx\b)\s*/i).filter(Boolean);
  if (partes.length === 2) return res(slug(partes[0]), slug(partes[1]));
  const tk = a.map(slug);
  for (let i = 1; i < tk.length; i++) {
    const o = slug(tk.slice(0, i).join("-")), d = slug(tk.slice(i).join("-"));
    if (CIDADES.includes(o) && CIDADES.includes(d)) return res(o, d);
  }
  return null;
}

const wa = (n) => { let d = String(n || "").replace(/\D/g, ""); if (!d) return ""; if (d.length <= 11) d = "55" + d; return `https://wa.me/${d}`; };

// ---------------------------------------------------------------- Yjara
async function chaveYjara(env, nova = false) {
  if (!nova) { const k = await env.QV?.get("yj_key"); if (k) return k; }
  const h = await (await fetch(YJ_SITE + "/", { headers: UA })).text();
  const m = h.match(/src="(\/assets\/main-[^"]+\.js)"/);
  if (!m) throw new Error("Yjara mudou o site");
  const js = await (await fetch(YJ_SITE + m[1], { headers: UA })).text();
  const k = js.match(/getAppApiToken\(\)\{return"([^"]+)"/);
  if (!k) throw new Error("Yjara mudou a busca");
  await env.QV?.put("yj_key", k[1], { expirationTtl: 43200 });
  return k[1];
}
async function yjara(env, chave, o, d, dia, max = 6) {
  // a API pagina (às vezes 1 por página): pede 50 e segue as páginas
  const out = [];
  for (let pg = 1; pg <= max; pg++) {
    const p = new URLSearchParams({ origem: o, destino: d, data_hora: dia, quantia: "1", subdomain: "yjaraviagens", per_page: "50", page: String(pg) });
    const r = await fetch(`${YJ_API}/trechos-viagem?${p}`, { headers: { ...UA, "X-API-KEY": chave } });
    if (r.status === 401 || r.status === 403) throw new Error("chave");
    const t = (await r.json().catch(() => ({})))?.data?.trechos || {};
    out.push(...(t.data || []));
    if (pg >= (t.last_page || 1)) break;
  }
  return out;
}
const limpa = (s) => String(s || "").replace(/\s*-\s*(Lancha|Navio|Barco|Ferry.*)$/i, "").trim();
const linkYj = (o, d, dia) => `${YJ_SITE}/escolher-passagem/${o}/${d}/somente-ida/${dia}`;

async function diaYjara(env, chave, o, d, dia) {
  const [lista, todos] = await Promise.all([yjara(env, chave, o, d, dia), yjara(env, chave, o, "", dia, 3).catch(() => [])]);
  const grupos = {};
  for (const x of todos) (grupos[x.id_viagem] ||= []).push([String(x.trecho || "").split(" x ").pop().split("/")[0], +x.valor_num || 0]);
  return lista.map((x) => {
    const preco = +x.valor_num || 0;
    const via = (grupos[x.id_viagem] || []).filter(([n, p]) => p < preco && slug(n) !== d).sort((a, b) => a[1] - b[1]).map(([n]) => n);
    return { id: String(x.id_viagem || x.id), barco: limpa(x.embarcacao) || x.tipo_embarcacao || "", tipo: `${x.tipo_embarcacao || ""} ${x.embarcacao || ""}`, empresa: (x.empresa?.nome_fantasia || "").trim(),
             hora: String(x.horario || "").slice(-5), dur: x.tempo_viagem, preco, via: [...new Set(via)], url: linkYj(o, d, dia), fonte: "Yjara" };
  });
}

// ---------------------------------------------------------------- Navegam
async function cidadesNav(env) {
  const c = await env.QV?.get("nav_cid", "json");
  if (c) return c;
  const out = { ...NAV_FIXO };
  try {
    for (let pg = 1; pg <= 4; pg++) {
      const j = await (await fetch(`${NAV}/ecommerce/popular-destinations?page=${pg}&page_size=50`, { headers: UA })).json();
      const dd = j?.result?.data || [];
      for (const x of dd) out[slug(x.name)] ??= x.id;
      if (dd.length < 50) break;
    }
    await env.QV?.put("nav_cid", JSON.stringify(out), { expirationTtl: 86400 * 3 });
  } catch {}
  return out;
}
async function navegam(env, o, d, ini, dias) {
  const cid = await cidadesNav(env);
  const io = cid[o], id = cid[d];
  if (!io || !id) return {};
  const fim = maisDias(ini, dias - 1), out = {};
  for (let pg = 1; pg <= 6; pg++) {
    const j = await (await fetch(`${NAV}/ecommerce/travels?origin_id=${io}&destination_id=${id}&page=${pg}`, { headers: UA })).json().catch(() => ({}));
    const dd = j?.result?.data || [];
    for (const x of dd) {
      const s = String(x.departure_date || ""), dia = s.slice(0, 10);
      if (dia < ini || dia > fim) continue;
      let dur = "";
      const h = (Date.parse(x.arrival_date) - Date.parse(x.departure_date)) / 36e5;
      if (h > 0) dur = `${Math.floor(h)}:${String(Math.round((h % 1) * 60)).padStart(2, "0")}`;
      const b = x.boat || {};
      (out[dia] ||= []).push({ id: "nav" + x.id, barco: b.name || "", empresa: "Navegam", tipo: `${b.type || ""} ${b.name || ""}`, hora: s.slice(11, 16), dur,
        preco: +(x.sale_cost || x.transportation_cost || 0), comida: +(x.feeding_cost || 0), zap: b.whatsapp_sale === true ? `${wa(WA_NAV)}?text=${encodeURIComponent(`Oi! Quero passagem no ${b.name || "barco"} saindo ${dia.slice(8, 10)}/${dia.slice(5, 7)}`)}` : "",
        url: `https://navegam.com.br/busca?origem=${io}&destino=${id}&ida=${dia}&type=ida&passageiros=1`, fonte: "Navegam" });
    }
    if (dd.length < 10 || (dd.length && String(dd[dd.length - 1].departure_date).slice(0, 10) > fim)) break;
  }
  return out;
}

async function buscarBarcos(env, o, d, ini, dias) {
  let chave, erros = [];
  try { chave = await chaveYjara(env); } catch (e) { erros.push(e.message); }
  const datas = Array.from({ length: dias }, (_, i) => maisDias(ini, i));
  const umDia = async (dia) => {
    if (!chave) return [];
    try { return await diaYjara(env, chave, o, d, dia); }
    catch (e) {
      if (e.message !== "chave") { erros.push("Yjara"); return []; }
      chave = await chaveYjara(env, true);
      return diaYjara(env, chave, o, d, dia).catch(() => []);
    }
  };
  const [yj, nav] = await Promise.all([Promise.all(datas.map(umDia)), navegam(env, o, d, ini, dias).catch(() => ({}))]);
  const out = {};
  datas.forEach((dia, i) => {
    const v = [...(yj[i] || []), ...(nav[dia] || [])].sort((a, b) => a.hora.localeCompare(b.hora));
    if (v.length) out[dia] = v;
  });
  return out;
}

function contatos(cfg, o, d) {
  return (cfg?.agenda || []).filter((c) => { const a = [slug(c.de), slug(c.para)]; return (a[0] === o && a[1] === d) || (a[0] === d && a[1] === o) || (!c.para && a[0] && [o, d].includes(a[0])); });
}

// ---------------------------------------------------------------- padrão visual (igual pra barco e avião)
// título · subtítulo em itálico · 💚 melhor opção · blocos por dia · cada item: ícone hora · preço · duração / └ detalhe
const PEQUENAS = new Set(["do", "da", "de", "dos", "das", "e"]);
const ROMANOS = /^(i|ii|iii|iv|v|vi|vii|viii|ix|x|xi|xii)$/i;
function nomeBarco(n) {
  const p = String(n || "").replace(/^\s*(l\/?m|f\/?b|n\/?m|b\/?m|e\/?m)\.?\s+/i, "").trim().split(/\s+/);
  return p.map((w, i) => ROMANOS.test(w) ? w.toUpperCase() : (w.length <= 3 && !PEQUENAS.has(w.toLowerCase()) && /^[A-Z]+$/.test(w)) ? w
    : PEQUENAS.has(w.toLowerCase()) && i ? w.toLowerCase() : w.charAt(0).toUpperCase() + w.slice(1).toLowerCase()).join(" ");
}
const icone = (v) => /lancha|expresso|speed|jato|\blm\b|l\/m/i.test(`${v.tipo || ""} ${v.barco || ""}`) ? "🚤" : "⛴️";
function duracao(d) { const m = String(d || "").match(/^(\d{1,2})[:hH](\d{2})/); return m ? `${+m[1]}h${m[2] !== "00" ? m[2] : ""}` : ""; }
const visivel = (h) => h.replace(/<[^>]+>/g, "").replace(/&(amp|lt|gt|quot);/g, "x").length;

function textoBarcos(o, d, ini, n, saidas, cfg) {
  const todos = Object.values(saidas).flat();
  const fim = maisDias(ini, n - 1);
  const periodo = n === 1 ? diaBR(ini) : `${diaBR(ini)} a ${diaBR(fim)}`;
  const L = [`🚤 <b>${nome(o)} → ${nome(d)}</b>`];
  if (!todos.length) {
    L.push(`<i>${periodo} · nenhuma saída à venda online</i>`, "",
           "A venda online costuma abrir uns 5 dias antes. Lancha pequena vende no porto ou pelo WhatsApp 👇");
  } else {
    const menor = todos.reduce((a, b) => (b.preco < a.preco ? b : a));
    const diaMenor = Object.keys(saidas).find((k) => saidas[k].includes(menor));
    L.push(`<i>${periodo} · ${todos.length} ${todos.length > 1 ? "saídas" : "saída"}</i>`, "",
           `💚 <b>Mais barato: <a href="${menor.url}">${rs(menor.preco)}</a></b> · ${diaBR(diaMenor)} ${menor.hora} · ${esc(nomeBarco(menor.barco))}`);
    const blocos = [];
    for (const [dia, vs] of Object.entries(saidas)) {
      const B = ["", `<b>${diaBR(dia)}</b>`];
      for (const v of vs) {
        const dur = duracao(v.dur);
        B.push(`${icone(v)} <b>${v.hora}</b> · <a href="${v.url}">${rs(v.preco)}</a>` + (v.comida ? ` + ${rs(v.comida)} comida` : "") + (dur ? ` · ${dur}` : "")
               + (v.preco === menor.preco ? " 💚" : ""));
        const det = [esc(nomeBarco(v.barco))];
        if (v.via?.length) det.push(`<i>para em ${esc(v.via.join(", "))}</i>`);
        if (v.zap) det.push(`<a href="${v.zap}">WhatsApp</a>`);
        B.push(`      └ ${det.join(" · ")}`);
      }
      blocos.push(B.join("\n"));
    }
    let corpo = "", cortou = 0;
    for (const b of blocos) { if (visivel(L.join("\n") + corpo + b) > 3300) { cortou++; continue; } corpo += "\n" + b; }
    L.push(corpo.slice(1));
    if (cortou) L.push("", `<i>+${cortou} dia(s) não couberam: toque em Mais ▶️</i>`);
  }
  const ag = contatos(cfg, o, d);
  if (ag.length) {
    L.push("", "📒 <b>Também pergunte</b>");
    for (const c of ag.slice(0, 6)) L.push(`💬 <a href="${wa(c.whatsapp)}">${esc(c.nome)}</a>`);
  }
  L.push("", `<i>🚤 lancha · ⛴️ barco · toque no preço pra comprar · ajuda: <a href="${wa(WA_YJARA)}">Yjara</a> · <a href="${wa(WA_NAV)}">Navegam</a></i>`);
  return L.join("\n");
}

// calendário em botões: escolhe a data sem digitar
const MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"];
function calendario(ctx, mes, minimo) {
  const [a, m] = mes.split("-").map(Number);
  const primeiro = new Date(Date.UTC(a, m - 1, 1)), dias = new Date(Date.UTC(a, m, 0)).getUTCDate();
  const ant = new Date(Date.UTC(a, m - 2, 1)).toISOString().slice(0, 7), prox = new Date(Date.UTC(a, m, 1)).toISOString().slice(0, 7);
  const linhas = [[[ant >= minimo.slice(0, 7) ? "◀️" : " ", ant >= minimo.slice(0, 7) ? `c|${ctx}|${ant}` : "x"], [`${MESES[m - 1]} ${a}`, "x"], ["▶️", `c|${ctx}|${prox}`]],
                  ["S", "T", "Q", "Q", "S", "S", "D"].map((l) => [l, "x"])];
  let linha = Array.from({ length: (primeiro.getUTCDay() + 6) % 7 }, () => [" ", "x"]);
  for (let dd = 1; dd <= dias; dd++) {
    const iso = `${mes}-${String(dd).padStart(2, "0")}`;
    linha.push(iso < minimo ? ["·", "x"] : [String(dd), `k|${ctx}|${iso}`]);
    if (linha.length === 7) { linhas.push(linha); linha = []; }
  }
  if (linha.length) { while (linha.length < 7) linha.push([" ", "x"]); linhas.push(linha); }
  return linhas.filter((l, i) => i < 2 || l.some(([, v]) => v !== "x"));  // some semanas que já passaram
}

// ---------------------------------------------------------------- Telegram
async function tg(env, cfg, metodo, dados) {
  if (!cfg?.bot) return null;
  const r = await fetch(`https://api.telegram.org/bot${cfg.bot}/${metodo}`, { method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify(dados) });
  const j = await r.json().catch(() => null);
  if (!j?.ok && !/not modified|query is too old|query ID is invalid/.test(j?.description || ""))
    await env.QV?.put("tg_erro", JSON.stringify({ quando: new Date().toISOString(), metodo, erro: j?.description || r.status }), { expirationTtl: 86400 * 7 });
  return j;
}
const kb = (linhas) => ({ inline_keyboard: linhas.filter((l) => l?.length).map((l) => l.map(([t, v]) =>
  /^https?:/.test(v) ? { text: t, url: v } : { text: t, callback_data: v.slice(0, 64) })) });

async function mostrar(env, cfg, chat, msgId, texto, botoes) {
  const base = { chat_id: chat, text: texto, parse_mode: "HTML", disable_web_page_preview: true, reply_markup: botoes ? kb(botoes) : undefined };
  if (msgId) {
    const r = await tg(env, cfg, "editMessageText", { ...base, message_id: msgId });
    if (r?.ok || /not modified/.test(r?.description || "")) return r;
  }
  return tg(env, cfg, "sendMessage", base);
}

const VOLTAR = [["🏠 Menu", "m"]];
function telas(cfg, tela) {
  const rotas = cfg.rotas || [];
  if (tela === "m") return ["🐭 <b>Xaropinho das viagens</b>\nO que você quer ver?", [
    [["✈️ Passagem de avião", "m:av"]], [["🚤 Barco e lancha", "m:bc"]], [["🌴 Promoções do Norte", "m:pr"]],
    [["🔔 O que estou vigiando", "m:vg"], ["⚙️ Ajustes", "m:cf"]]]];
  if (tela === "m:av") {
    const L = ["✈️ <b>Passagem de avião</b>"];
    rotas.forEach((r, i) => L.push(`${i + 1}. ${esc(r.nome)}` + (r.preco_alvo ? ` · 🎯 ${rs(r.preco_alvo)}` : "")
      + (r.ativa === false ? " · ⏸️ pausada" : r.pausada_ate ? ` · ⏸️ até ${r.pausada_ate.slice(8, 10)}/${r.pausada_ate.slice(5, 7)}` : "")));
    L.push("", "<i>Eu te aviso sozinho quando o preço cai. Aqui você pede na hora:</i>");
    const b = [[["📊 Preços agora", "/status"], ["🔎 Buscar tudo agora", "/agora"]],
               [["📅 Preço numa data", `c|a.0|${String((rotas[0]?.ida_entre || [])[0] || hojeBR()).slice(0, 7) < hojeBR().slice(0, 7) ? hojeBR().slice(0, 7) : String((rotas[0]?.ida_entre || [])[0] || hojeBR()).slice(0, 7)}`], ["🎯 Mudar alvo", "p:alvo"]]];
    rotas.slice(0, 3).forEach((r, i) => {
      const pausada = r.ativa === false || r.pausada_ate;
      b.push([pausada ? [`▶️ Reativar ${rotas.length > 1 ? i + 1 : "avisos"}`, `/ativar ${i + 1}`] : [`⏸️ Pausar ${rotas.length > 1 ? i + 1 + " " : ""}7 dias`, `/pausar ${i + 1} 7`]]);
    });
    b.push(VOLTAR);
    return [L.join("\n"), b];
  }
  if (tela === "m:bc") {
    const vistos = new Set(), b = [];
    const add = (o, d) => { const k = `${o}|${d}`; if (vistos.has(k) || !o || !d) return; vistos.add(k); b.push([`${nome(o)} → ${nome(d)}`, `b|${o}|${d}|0`]); };
    for (const x of cfg.barcos || []) add(slug(x.de), slug(x.para));
    for (const x of cfg.recentes || []) add(x[0], x[1]);
    if (b.length < 4) [["oriximina", "santarem"], ["santarem", "oriximina"], ["oriximina", "trombetas"], ["trombetas", "oriximina"]].forEach(([o, d]) => add(o, d));
    const linhas = [];
    for (let i = 0; i < Math.min(b.length, 8); i += 2) linhas.push(b.slice(i, i + 2));
    return ["🚤 <b>Barco e lancha</b>\nEscolha o trecho (próximos dias, Yjara + Navegam):",
      [...linhas, [["✍️ Outro trecho", "p:trecho"]], [["📒 Agenda de lanchas", "m:ag"], ["🔔 Vigiados", "m:bv"]], VOLTAR]];
  }
  if (tela === "m:ag") {
    const ag = cfg.agenda || [];
    const L = ["📒 <b>Agenda de lanchas</b>", "<i>Lanchas que vendem pelo WhatsApp/Instagram. Aparecem quando você busca o trecho delas.</i>", ""];
    ag.forEach((c, i) => L.push(`${i + 1}. ${esc(c.nome)} · ${nome(slug(c.de))}${c.para ? " ↔ " + nome(slug(c.para)) : ""} · <a href="${wa(c.whatsapp)}">WhatsApp</a>`));
    if (!ag.length) L.push("Ainda vazia.");
    const b = [[["➕ Adicionar contato", "p:contato"]]];
    const apagar = ag.slice(0, 8).map((_, i) => [`🗑 ${i + 1}`, `/agenda apagar ${i + 1}`]);
    for (let i = 0; i < apagar.length; i += 4) b.push(apagar.slice(i, i + 4));
    b.push([["🚤 Barcos", "m:bc"], ...VOLTAR]);
    return [L.join("\n"), b];
  }
  if (tela === "m:bv" || tela === "m:vg") {
    const bs = cfg.barcos || [];
    const L = tela === "m:vg" ? ["🔔 <b>O que estou vigiando</b>", "", "✈️ <b>Avião</b> (2 buscas por dia + checagens rápidas)"] : ["🔔 <b>Trechos de barco vigiados</b>"];
    if (tela === "m:vg") rotas.forEach((r) => L.push(` • ${esc(r.nome)}` + (r.preco_alvo ? ` · 🎯 ${rs(r.preco_alvo)}` : "") + (r.ativa === false || r.pausada_ate ? " ⏸️" : "")));
    if (tela === "m:vg") L.push("", "🚤 <b>Barco</b> (a cada 3 h: saída nova e queda de preço)");
    bs.forEach((x, i) => L.push(` ${i + 1}. ${nome(slug(x.de))} → ${nome(slug(x.para))}` + (x.ativo === false ? " ⏸️" : "")));
    if (!bs.length) L.push(" <i>nenhum trecho — abra um trecho em 🚤 e toque em 🔔 Avisar</i>");
    if (tela === "m:vg") L.push("", "🌴 <b>Promoções</b>: canais, blogs, GOL/Azul e Radar do Norte, o dia todo");
    const parar = bs.slice(0, 8).map((x, i) => [`🗑 Parar ${i + 1}`, `/pararbarco ${i + 1}`]);
    const b = [];
    for (let i = 0; i < parar.length; i += 3) b.push(parar.slice(i, i + 3));
    b.push([["🚤 Barcos", "m:bc"], ...VOLTAR]);
    return [L.join("\n"), b];
  }
  if (tela === "m:pr") return ["🌴 <b>Promoções</b>\nEu já te mando sozinho as boas. Aqui você pede a lista:", [
    [["🏷️ Últimas promoções", "/promos"]], [["🌴 Destinos baratos saindo do Norte", "/radar"]], VOLTAR]];
  if (tela === "m:cf") return ["⚙️ <b>Ajustes</b>\nRotas, horários, alvo, palavras de promoção e trechos de barco ficam no painel.", [
    [["🔧 Abrir painel", PAINEL]], [["⌨️ Comandos digitados", "/ajuda"]], VOLTAR]];
  return telas(cfg, "m");
}

const PEDIDOS = {
  trecho: "✍️ Escreva o trecho (e, se quiser, as datas):\n<code>Oriximiná Terra Santa</code>\n<code>Santarém para Óbidos 12/12</code>\n<code>Oriximiná Santarém 20/12 a 24/12</code>",
  contato: "📒 Mande o contato assim (separado por vírgula):\n<code>Lancha Fulano, 93 99999-9999, Oriximiná, Santarém</code>\n<i>O último trecho é opcional: só a cidade já serve.</i>",
  alvo: "🎯 Escreva o novo preço-alvo (ex.: <code>1800</code>). Com mais de uma rota: <code>2 1800</code>",
  data: "📅 Escreva a data (ex.: <code>29/05</code> ou ida e volta <code>29/05 05/06</code>)",
};

async function acordarVigia(env, inputs) {
  return fetch(`https://api.github.com/repos/${REPO}/actions/workflows/vigia.yml/dispatches`, {
    method: "POST",
    headers: { Authorization: `Bearer ${env.GH_TOKEN}`, Accept: "application/vnd.github+json", "Content-Type": "application/json", "User-Agent": "quackvoo-worker" },
    body: JSON.stringify({ ref: "main", inputs }),
  });
}
const pedirVigia = (env, chat, texto) => acordarVigia(env, { comando: JSON.stringify({ chat, texto }) });

async function barco(env, cfg, chat, msgId, o, d, ini, n = DIAS) {
  n = Math.max(1, Math.min(7, +n || DIAS));
  const r0 = await mostrar(env, cfg, chat, msgId, `🔎 Procurando <b>${nome(o)} → ${nome(d)}</b>…\n<i>${n === 1 ? diaBR(ini) : diaBR(ini) + " a " + diaBR(maisDias(ini, n - 1))}</i>`);
  msgId = msgId || r0?.result?.message_id;
  let saidas = {}, erro = "";
  try { saidas = await buscarBarcos(env, o, d, ini, n); } catch (e) { erro = e.message; }
  const t = erro ? `🚤 <b>${nome(o)} → ${nome(d)}</b>\n⚠️ As lojas não responderam agora (${esc(erro)}). Tente de novo em instantes.` : textoBarcos(o, d, ini, n, saidas, cfg);
  const hoje = hojeBR();
  const vigiado = (cfg.barcos || []).some((x) => slug(x.de) === o && slug(x.para) === d);
  const antes = maisDias(ini, -n) < hoje ? hoje : maisDias(ini, -n);
  const b = [[...(ini > hoje ? [["◀️ Antes", `b|${o}|${d}|${antes}|${n}`]] : []), ["📅 Datas", `c|b.${o}.${d}|${ini.slice(0, 7)}`], ["Mais ▶️", `b|${o}|${d}|${maisDias(ini, n)}|${n}`]],
             [["🔁 Volta", `b|${d}|${o}|${ini}|${n}`], vigiado ? ["🔔 Já vigiado", "m:bv"] : ["🔔 Avisar saídas novas", `/vigiarbarco ${o} para ${d}`]],
             [["🚤 Outro trecho", "m:bc"], ...VOLTAR]];
  await mostrar(env, cfg, chat, msgId, t, b);
  const rec = [[o, d], ...(cfg.recentes || []).filter(([a, c]) => !(a === o && c === d))].slice(0, 6);
  if (JSON.stringify(rec) !== JSON.stringify(cfg.recentes)) { cfg.recentes = rec; await env.QV.put("cfg", JSON.stringify(cfg)); }
}

async function tratar(env, u, cfg) {
  const cq = u.callback_query, m = u.message;
  const chat = String((cq?.message || m)?.chat?.id || "");
  if (!chat || chat !== String(cfg.chat)) return;
  if (cq) {
    const v = String(cq.data || ""), msgId = cq.message.message_id;
    if (v === "m" || v.startsWith("m:")) {
      await tg(env, cfg, "answerCallbackQuery", { callback_query_id: cq.id });
      const [t, b] = telas(cfg, v);
      return mostrar(env, cfg, chat, msgId, t, b);
    }
    if (v.startsWith("b|")) {
      const [, o, d, ini, n] = v.split("|");
      await tg(env, cfg, "answerCallbackQuery", { callback_query_id: cq.id, text: "🔎 Buscando…" });
      return barco(env, cfg, chat, msgId, o, d, ini === "0" || ini < hojeBR() ? hojeBR() : ini, n);
    }
    if (v === "x") return tg(env, cfg, "answerCallbackQuery", { callback_query_id: cq.id });
    if (v.startsWith("c|")) {  // calendário
      await tg(env, cfg, "answerCallbackQuery", { callback_query_id: cq.id });
      const [, ctx, mes] = v.split("|");
      const hoje = hojeBR();
      if (ctx.startsWith("b.")) {
        const [, o, d] = ctx.split(".");
        return mostrar(env, cfg, chat, msgId, `📅 <b>${nome(o)} → ${nome(d)}</b>\nEscolha o dia da viagem:`,
          [...calendario(ctx, mes < hoje.slice(0, 7) ? hoje.slice(0, 7) : mes, hoje), [["◀️ Voltar", `b|${o}|${d}|0`], ...VOLTAR]]);
      }
      const r = (cfg.rotas || [])[+ctx.slice(2) || 0];
      if (!r) return;
      return mostrar(env, cfg, chat, msgId, `📅 <b>${esc(r.origem)} → ${esc(r.destino)}</b>\nEscolha a data da ida (busca 1 preço na SerpAPI):`,
        [...calendario(ctx, mes, hoje), [["✈️ Avião", "m:av"], ...VOLTAR]]);
    }
    if (v.startsWith("k|")) {  // dia escolhido no calendário
      const [, ctx, dia] = v.split("|");
      if (ctx.startsWith("b.")) {
        await tg(env, cfg, "answerCallbackQuery", { callback_query_id: cq.id });
        const [, o, d] = ctx.split(".");
        return mostrar(env, cfg, chat, msgId, `📅 <b>${nome(o)} → ${nome(d)}</b>\nA partir de <b>${diaBR(dia)}</b>, quantos dias mostrar?`,
          [[["Só esse dia", `b|${o}|${d}|${dia}|1`], ["3 dias", `b|${o}|${d}|${dia}|3`]], [["5 dias", `b|${o}|${d}|${dia}|5`], ["7 dias", `b|${o}|${d}|${dia}|7`]],
           [["◀️ Outro dia", `c|${ctx}|${dia.slice(0, 7)}`], ...VOLTAR]]);
      }
      const r = (cfg.rotas || [])[+ctx.slice(2) || 0];
      await tg(env, cfg, "answerCallbackQuery", { callback_query_id: cq.id, text: "⏳ Buscando… chega em ~1 min." });
      await pedirVigia(env, chat, `/buscar ${r.origem} ${r.destino} ${dia.slice(8, 10)}/${dia.slice(5, 7)}/${dia.slice(0, 4)}`);
      return mostrar(env, cfg, chat, msgId, `✈️ Buscando <b>${esc(r.origem)} → ${esc(r.destino)}</b> em ${diaBR(dia)}/${dia.slice(2, 4)}…\n<i>O preço chega numa mensagem nova em ~1 min.</i>`,
        [[["📅 Outra data", `c|${ctx}|${dia.slice(0, 7)}`]], [["✈️ Avião", "m:av"], ...VOLTAR]]);
    }
    if (v.startsWith("p:")) {
      await tg(env, cfg, "answerCallbackQuery", { callback_query_id: cq.id });
      await env.QV.put("pedido", v.slice(2), { expirationTtl: 900 });
      return tg(env, cfg, "sendMessage", { chat_id: chat, text: PEDIDOS[v.slice(2)], parse_mode: "HTML", reply_markup: { force_reply: true, input_field_placeholder: "escreva aqui" } });
    }
    if (v.startsWith("/")) {
      await tg(env, cfg, "answerCallbackQuery", { callback_query_id: cq.id, text: "⏳ Já vai! Chega em ~1 min." });
      return pedirVigia(env, chat, v);
    }
    return tg(env, cfg, "answerCallbackQuery", { callback_query_id: cq.id });
  }
  const t = String(m?.text || "").trim();
  if (!t) return;
  const menu = () => { const [tx, b] = telas(cfg, "m"); return mostrar(env, cfg, chat, null, tx, b); };
  if (/^\/(start|menu)\b/i.test(t) || /^(menu|oi|olá|ola|bom dia|boa tarde|boa noite)$/i.test(t)) { await env.QV.delete("pedido"); return menu(); }
  if (/^\/barco\b/i.test(t)) {
    const x = trecho(t);
    if (x) return barco(env, cfg, chat, null, x.o, x.d, x.dia || hojeBR(), x.n || (x.dia ? 3 : DIAS));
    return mostrar(env, cfg, chat, null, PEDIDOS.trecho);
  }
  if (t.startsWith("/")) return pedirVigia(env, chat, t);

  const pedido = await env.QV.get("pedido");
  if (pedido) await env.QV.delete("pedido");
  if (pedido === "contato" || /^(lancha|barco|contato)\b.*,/i.test(t)) {
    const p = t.split(/\s*[,;\n]\s*/).filter(Boolean);
    const i = p.findIndex((s) => s.replace(/\D/g, "").length >= 8);
    if (i < 0) return mostrar(env, cfg, chat, null, "Faltou o número do WhatsApp.\n\n" + PEDIDOS.contato);
    const nomeC = p.filter((_, k) => k < i).join(" ") || "Lancha", fone = p[i].replace(/\D/g, ""), resto = p.slice(i + 1);
    let de = "", para = "";
    if (resto.length >= 2) { de = slug(resto[0]); para = slug(resto[1]); }
    else if (resto.length === 1) { const x = trecho(resto[0]); if (x) { de = x.o; para = x.d; } else de = slug(resto[0]); }
    if (!de) return mostrar(env, cfg, chat, null, "Faltou o trecho (ou ao menos a cidade).\n\n" + PEDIDOS.contato);
    (cfg.agenda ||= []).push({ nome: nomeC, whatsapp: fone, de, ...(para ? { para } : {}) });
    await env.QV.put("cfg", JSON.stringify(cfg));
    await pedirVigia(env, chat, `/agenda add ${fone} ${de} ${para || "-"} ${nomeC}`);
    const [tx, b] = telas(cfg, "m:ag");
    return mostrar(env, cfg, chat, null, `✅ Salvei <b>${esc(nomeC)}</b>.\n\n` + tx, b);
  }
  if (pedido === "alvo") {
    const n = t.match(/^(?:(\d)\s+)?(?:r\$\s*)?([\d.]+)/i);
    if (!n) return mostrar(env, cfg, chat, null, PEDIDOS.alvo);
    await pedirVigia(env, chat, `/alvo ${n[1] || 1} ${n[2].replace(/\./g, "")}`);
    return mostrar(env, cfg, chat, null, "⏳ Mudando o alvo… a confirmação chega em ~1 min.");
  }
  if (pedido === "data") {
    const r = (cfg.rotas || [])[0];
    const ds = t.match(/\d{1,2}\/\d{1,2}(?:\/\d{2,4})?/g);
    if (!r || !ds) return mostrar(env, cfg, chat, null, PEDIDOS.data);
    await pedirVigia(env, chat, `/buscar ${r.origem} ${r.destino} ${ds.slice(0, 2).join(" ")}`);
    return mostrar(env, cfg, chat, null, `🔎 Buscando ${esc(r.origem)}→${esc(r.destino)} em ${ds[0]}… chega em ~1 min.`);
  }
  const x = trecho(t);
  if (x && (pedido === "trecho" || (CIDADES.includes(x.o) && CIDADES.includes(x.d)))) return barco(env, cfg, chat, null, x.o, x.d, x.dia || hojeBR(), x.n || (x.dia ? 3 : DIAS));
  if (pedido === "trecho") return mostrar(env, cfg, chat, null, "Não entendi o trecho.\n\n" + PEDIDOS.trecho);
  return menu();
}

// O GitHub Actions prova quem é com um token OIDC assinado pelo próprio GitHub.
const b64url = (t) => Uint8Array.from(atob(t.replace(/-/g, "+").replace(/_/g, "/").padEnd(Math.ceil(t.length / 4) * 4, "=")), (c) => c.charCodeAt(0));
async function githubAssinou(jwt) {
  try {
    const [h, p, sig] = jwt.split(".");
    const cab = JSON.parse(new TextDecoder().decode(b64url(h)));
    const dados = JSON.parse(new TextDecoder().decode(b64url(p)));
    if (dados.iss !== "https://token.actions.githubusercontent.com" || dados.aud !== "quackvoo"
        || dados.repository !== REPO || !(dados.exp * 1000 > Date.now())) return false;
    const jwks = await (await fetch("https://token.actions.githubusercontent.com/.well-known/jwks")).json();
    const jwk = jwks.keys.find((k) => k.kid === cab.kid);
    if (!jwk) return false;
    const chave = await crypto.subtle.importKey("jwk", jwk, { name: "RSASSA-PKCS1-v1_5", hash: "SHA-256" }, false, ["verify"]);
    return await crypto.subtle.verify("RSASSA-PKCS1-v1_5", chave, b64url(sig), new TextEncoder().encode(`${h}.${p}`));
  } catch { return false; }
}
const jwtDe = (req) => (req.headers.get("Authorization") || "").replace(/^Bearer\s+/i, "");

export default {
  // relógio confiável: a cada 15 min acorda o vigia (o agendamento do GitHub às vezes pula horários)
  async scheduled(evento, env, ctx) {
    if (env.GH_TOKEN) ctx.waitUntil(acordarVigia(env, {}));
  },

  async fetch(req, env, ctx) {
    const url = new URL(req.url);
    if (!env.GH_TOKEN) return txt("Falta o segredo GH_TOKEN no Worker.", 500);

    if (req.method === "GET" && url.pathname === "/ligar") {
      const r = await acordarVigia(env, { webhook: `${url.origin}/telegram` });
      return r.ok ? txt("✅ Pedido enviado! Em ~1 minuto o bot te manda “Comandos rápidos ligados”.")
                  : txt(`❌ O GitHub recusou (${r.status}).\n${await r.text()}`, 500);
    }
    if (req.method === "GET" && url.pathname === "/chave-serp") {
      const jwt = jwtDe(req);
      if (!env.SERPAPI_KEY || !jwt || !(await githubAssinou(jwt))) return txt("não", 403);
      return txt(env.SERPAPI_KEY);
    }
    if (req.method === "POST" && url.pathname === "/registrar") {  // o vigia manda token do bot + suas configurações
      const jwt = jwtDe(req);
      if (!jwt || !(await githubAssinou(jwt))) return txt("não", 403);
      const novo = await req.json().catch(() => null);
      if (!novo?.bot || !novo?.chat) return txt("faltou bot/chat", 400);
      const velho = (await env.QV.get("cfg", "json")) || {};
      await env.QV.put("cfg", JSON.stringify({ ...novo, recentes: velho.recentes || [] }));
      return txt("ok");
    }
    if (req.method === "GET" && url.pathname === "/barco") {  // prévia pública (só dados públicos das lojas)
      const x = trecho(url.searchParams.get("t") || "");
      if (!x) return txt("use /barco?t=Oriximiná Santarém", 400);
      const ini = x.dia || hojeBR(), n = x.n || DIAS;
      const s = await buscarBarcos(env, x.o, x.d, ini, n);
      return url.searchParams.has("json") ? new Response(JSON.stringify(s, null, 1), { headers: { "Content-Type": "application/json; charset=utf-8" } })
                                          : txt(textoBarcos(x.o, x.d, ini, n, s, (await env.QV.get("cfg", "json")) || {}).replace(/<[^>]+>/g, ""));
    }
    if (req.method === "GET" && url.pathname === "/simular") {  // teste de ponta a ponta (chave só no cofre)
      const k = await env.QV.get("sim_token");
      if (!k || url.searchParams.get("k") !== k) return txt("não", 403);
      const cfg = await env.QV.get("cfg", "json");
      const t = url.searchParams.get("t") || "/menu", cq = url.searchParams.get("cq");
      const u = cq ? { callback_query: { id: "0", data: cq, message: { chat: { id: cfg.chat }, message_id: +(url.searchParams.get("mid") || 0) } } }
                   : { message: { chat: { id: cfg.chat }, text: t } };
      try { await tratar(env, u, cfg); return txt("ok"); } catch (e) { return txt("erro: " + (e.stack || e), 500); }
    }
    if (req.method !== "POST" || url.pathname !== "/telegram") return txt("Xaropinho das viagens 🐭 no ar.");

    const u = await req.json().catch(() => ({}));
    const cfg = env.QV ? await env.QV.get("cfg", "json") : null;
    if (cfg?.bot) {
      ctx.waitUntil(tratar(env, u, cfg).catch((e) => console.log("erro:", e.stack || e)));
      return txt("ok");
    }
    // ainda não registrado: repassa os comandos pro vigia, como antes
    const cq = u.callback_query, m = u.message;
    if (cq?.message && String(cq.data || "").startsWith("/"))
      await acordarVigia(env, { comando: JSON.stringify({ chat: cq.message.chat.id, texto: cq.data, cq: cq.id }) });
    else if (m && String(m.text || "").startsWith("/"))
      await acordarVigia(env, { comando: JSON.stringify({ chat: m.chat.id, texto: m.text }) });
    return txt("ok");
  },
};
