"""Ofertas oficiais publicadas pelas próprias companhias (páginas de ofertas da GOL e da Azul).
Lê os trechos com preço, guarda o histórico de cada um e diz quais valem a pena. Grátis."""
import html
import re
from datetime import date
from statistics import median

import requests

import analise as A
from aeroportos import nome as nome_aero

PAGINAS = {
    "GOL": ["https://www.voegol.com.br/ofertas"],
    "Azul": ["https://passagens.voeazul.com.br/pt/melhores-ofertas", "https://passagens.voeazul.com.br/pt/ofertas-azul",
             "https://passagens.voeazul.com.br/pt/ofertas-imperdiveis"],
}
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0 Safari/537.36",
      "Accept-Language": "pt-BR,pt;q=0.9"}
PADRAO = re.compile(
    r"(?P<o>[A-Za-zÀ-ú .'-]{2,40}?) \((?P<oc>[A-Z]{3})\) (?:Para )?(?P<d>[A-Za-zÀ-ú .'-]{2,45}?) \((?P<dc>[A-Z]{3})\) "
    r"(?:Data de viagem de ida |Ida: )?(?P<ida>\d{2}/\d{2}/\d{4})(?: - (?P<volta>\d{2}/\d{2}/\d{4}))? "
    r"A partir de R\$ ?(?P<preco>[\d.]+,\d{2})")
LIXO = ("Reserve agora", "Buscar voos", "keyboard_arrow_left", "keyboard_arrow_right", "Ida e volta", "Só ida", "Econômica")


def _nome(txt: str, cod: str) -> str:
    n = nome_aero(cod)
    if n != cod:
        return n
    for l in LIXO:
        txt = txt.split(l)[-1]
    return txt.strip(" -/") or cod


def _iso(dmy: str) -> str:
    d, m, a = dmy.split("/")
    return f"{a}-{m}-{d}"


def ler(cia: str, url: str) -> list[dict]:
    r = requests.get(url, headers=UA, timeout=40)
    r.raise_for_status()
    t = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", r.text)))
    t = re.sub(r"\.css-[\w-]+\{[^}]*\}", " ", t)
    out = []
    for m in PADRAO.finditer(t):
        ida = _iso(m["ida"])
        if ida <= date.today().isoformat():
            continue
        out.append({"cia": cia, "origem": m["oc"], "destino": m["dc"], "nome_o": _nome(m["o"], m["oc"]), "nome_d": _nome(m["d"], m["dc"]),
                    "ida": ida, "volta": _iso(m["volta"]) if m["volta"] else None,
                    "preco": round(float(m["preco"].replace(".", "").replace(",", "."))), "pagina": url})
    return out


def coletar() -> tuple[list[dict], list[str]]:
    ofertas, erros = [], []
    for cia, urls in PAGINAS.items():
        for u in urls:
            try:
                ofertas += ler(cia, u)
            except Exception as e:
                erros.append(f"{cia} {u.split('/')[-1]}: {str(e)[:70]}")
    unicas = {}
    for o in ofertas:  # mesma cia+trecho+tipo: fica a mais barata
        k = f"{o['cia']}:{o['origem']}>{o['destino']}:{'rt' if o['volta'] else 'ow'}"
        if k not in unicas or o["preco"] < unicas[k]["preco"]:
            unicas[k] = {**o, "chave": k}
    return list(unicas.values()), erros


def avaliar(est: dict, ofertas: list[dict], origens: list[str], destinos: list[str], agora_iso: str) -> list[dict]:
    """Guarda o histórico e devolve as que merecem aviso: saindo do Norte (ou pro destino de uma rota sua)
    e bem abaixo do que a própria cia costuma anunciar nesse trecho (ou primeira vez que aparece pro seu destino)."""
    of = est.setdefault("oficiais", {"hist": {}, "avisadas": {}, "ultimas": {}})
    boas = []
    for o in ofertas:
        k = o["chave"]
        h = of["hist"].setdefault(k, [])
        normal = median(p for _, p in h) if len(h) >= 3 else None
        if not h or h[-1][1] != o["preco"]:
            h.append([agora_iso[:10], o["preco"]])
            of["hist"][k] = h[-40:]
        o["normal"] = normal
        interessa = o["origem"] in origens or o["destino"] in destinos
        if not interessa:
            continue
        of["ultimas"][k] = {**o, "visto": agora_iso}
        ja = of["avisadas"].get(k)
        caiu = normal and o["preco"] <= 0.85 * normal
        novo_destino = o["destino"] in destinos and not ja
        if (caiu or novo_destino) and (not ja or o["preco"] < ja * 0.95):
            of["avisadas"][k] = o["preco"]
            boas.append(o)
    return sorted(boas, key=lambda x: x["preco"])


def linha(o: dict, url_google) -> str:
    tipo = f"ida {A.d(o['ida']).strftime('%d/%m')} · volta {A.d(o['volta']).strftime('%d/%m')}" if o["volta"] else f"só ida · {A.d(o['ida']).strftime('%d/%m')}"
    g = url_google(o["origem"], o["destino"], o["ida"], o.get("volta")).replace("&", "&amp;")
    extra = f" · <i>{round((1 - o['preco'] / o['normal']) * 100)}% abaixo do que a {o['cia']} costuma anunciar</i>" if o.get("normal") and o["preco"] < o["normal"] else ""
    return (f"<b>{o['nome_o']} → {o['nome_d']}</b> <a href=\"{o['pagina']}\">{A.reais(o['preco'])}</a> ({o['cia']}, {tipo})"
            f" · <a href=\"{g}\">Google</a>{extra}")
