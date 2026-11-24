"""Testa quais fontes de promoção dá pra ler (RSS, Google Notícias, Telegram público)."""
import re, html
from urllib.parse import quote
import requests
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0 Safari/537.36",
      "Accept-Language": "pt-BR,pt;q=0.9"}
RSS = {
 "Melhores Destinos": "https://www.melhoresdestinos.com.br/feed",
 "Passageiro de Primeira": "https://passageirodeprimeira.com/feed/",
 "Portal Amazônia": "https://portalamazonia.com/feed/",
 "Pontos pra Voar": "https://pontospravoar.com/feed/",
 "Cartões e Viagens": "https://cartoeseviagens.com.br/feed/",
 "Aeroin": "https://www.aeroin.net/feed/",
 "Aeroflap": "https://www.aeroflap.com.br/feed/",
 "Panrotas": "https://www.panrotas.com.br/rss",
 "CVC Dicas": "https://www.cvc.com.br/dicas-de-viagem/feed/",
 "Viaje na Viagem": "https://www.viajenaviagem.com/feed/",
 "Promobit": "https://www.promobit.com.br/feed/",
}
for q in ["pacote saindo de Manaus", "pacote viagem saindo de Belém", "promoção passagens Manaus", "promoção passagens Belém",
          "passagens Santarém promoção", "Azul promoção passagens", "LATAM promoção passagens", "Gol promoção passagens"]:
    RSS[f"GNews: {q}"] = "https://news.google.com/rss/search?q=" + quote(q + " when:7d") + "&hl=pt-BR&gl=BR&ceid=BR:pt-419"
for nome, url in RSS.items():
    try:
        r = requests.get(url, headers=UA, timeout=25)
        itens = re.findall(r"<item>.*?<title>(.*?)</title>", r.text, re.S)
        tit = [html.unescape(re.sub(r"<!\[CDATA\[|\]\]>", "", t)).strip()[:70] for t in itens[:2]]
        print(f"RSS {nome:38} {r.status_code} itens={len(itens)} | {' || '.join(tit)}")
    except Exception as e:
        print(f"RSS {nome:38} ERRO {str(e)[:80]}")
for canal in ["canalcartoeseviagens", "melhoresdestinos", "passageirodeprimeira", "pontospravoar", "passagensimperdiveis",
              "promocoesdepassagens", "passagensaereasbaratas", "viajarbarato", "voeazul", "latamairlines", "voegol", "cvcviagens",
              "promobit", "pelando", "passagenspromo", "mundodemilhas"]:
    try:
        r = requests.get(f"https://t.me/s/{canal}", headers=UA, timeout=25)
        msgs = re.findall(r'class="tgme_widget_message_text[^"]*"[^>]*>(.*?)</div>', r.text, re.S)
        datas = re.findall(r'<time datetime="([^"]+)"', r.text)
        ult = html.unescape(re.sub(r"<[^>]+>", " ", msgs[-1]))[:70].strip() if msgs else ""
        print(f"TG  {canal:38} {r.status_code} msgs={len(msgs)} última={datas[-1][:10] if datas else '-'} | {ult}")
    except Exception as e:
        print(f"TG  {canal:38} ERRO {str(e)[:80]}")
