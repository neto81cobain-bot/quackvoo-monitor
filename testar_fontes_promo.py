import re, html, requests
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0 Safari/537.36", "Accept-Language": "pt-BR,pt;q=0.9"}
def limpa(t): return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", t)))
for url in ["https://www.voegol.com.br/ofertas", "https://passagens.voeazul.com.br/pt/ofertas-azul"]:
    r = requests.get(url, headers=UA, timeout=30)
    t = limpa(r.text)
    print("=====", url)
    for m in list(re.finditer(r"\((BEL|MAO|STM)\)", t))[:4]:
        print("CTX:", t[max(0, m.start()-200): m.start()+250])
    i = t.find("R$")
    print("PRIMEIRO R$:", t[max(0, i-300): i+150])
    # json embutido?
    js = re.findall(r'"(origin|destination|price|departure|airportCode|iata)[A-Za-z]*"\s*:\s*"?([^",}]{1,40})', r.text)
    print("JSON?:", js[:20])
    print("next_data:", "__NEXT_DATA__" in r.text, "| application/json scripts:", len(re.findall(r'<script[^>]*application/(ld\+)?json', r.text)))
