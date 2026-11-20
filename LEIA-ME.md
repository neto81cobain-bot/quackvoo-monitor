# QuackVoo Monitor 🦆✈️

Todo dia às **8h** ele olha o calendário do Google Voos das suas rotas e te manda
**e-mail e/ou WhatsApp** quando:

- 📉 o preço **caiu** X% desde a última olhada
- 🎯 ficou **abaixo do seu preço-alvo**
- 🏆 bateu o **menor preço já visto**
- 🔀 achou uma **conexão por conta própria** mais barata (ex.: MAO→GRU + GRU→VVI)
- 📬 e um **resumo semanal** (domingo), mesmo sem novidade

Cada aviso traz: dia mais barato, **semana mais barata**, dia da semana mais barato,
os 5 melhores dias, o menor preço de cada mês e o link direto do Google Voos.

---

## 1. Editar suas rotas
Abra `rotas.yaml` no GitHub (ícone de lápis) e troque origem, destino, datas,
noites, preço-alvo e aeroportos de conexão. Salve com **Commit changes**.

## 2. Colocar as chaves (uma vez)
No repositório: **Settings → Secrets and variables → Actions → New repository secret**.

| Nome | O que é | Obrigatório |
|---|---|---|
| `APIFY_TOKEN` | Token da Apify (Settings → API & Integrations) | ✅ |
| `SERPAPI_KEY` | Chave da SerpAPI (confere horários da conexão) | opcional |
| `EMAIL_USER` | Seu Gmail | para e-mail |
| `EMAIL_APP_PASSWORD` | **Senha de app** do Gmail (veja abaixo) | para e-mail |
| `EMAIL_TO` | Quem recebe (pode ser o mesmo Gmail; vários separados por vírgula) | opcional |
| `WHATSAPP_PHONE` | Seu número com DDI, ex.: `5593999999999` | para WhatsApp |
| `CALLMEBOT_KEY` | Chave do CallMeBot (veja abaixo) | para WhatsApp |

**Senha de app do Gmail:** conta Google → Segurança → ative a *Verificação em duas etapas* →
pesquise **"Senhas de app"** → crie uma chamada QuackVoo → copie os 16 caracteres.

**WhatsApp (CallMeBot, grátis):** abra o site do CallMeBot (pesquise "callmebot whatsapp api"),
salve o número que aparece lá nos seus contatos e mande pelo WhatsApp a frase que o site indica
(*I allow callmebot to send me messages*). Ele responde com sua **apikey**.
É um serviço gratuito de terceiros e às vezes oscila; o e-mail é o canal garantido.

## 3. Testar agora
Aba **Actions → QuackVoo Monitor → Run workflow → Run workflow**.
Em 1–3 minutos chega o primeiro relatório. Se der erro, clique na execução vermelha
e veja a mensagem (ela diz qual chave falta).

Depois disso ele roda sozinho todo dia. Pra mudar o horário, edite o `cron` em
`.github/workflows/quackvoo.yml` (está em UTC: `7 11` = 8h07 de Brasília).

## Custos
- **GitHub Actions:** grátis (cada execução usa ~1–3 min dos 2.000 min/mês).
- **Apify:** ~US$ 0,20 por 1.000 dias de calendário. O teste de conexões roda **só às segundas**
  (mude em `conexoes_toda`) porque é o que mais consome. Uma rota com janela de 3 meses e
  5 conexões fica em torno de US$ 1–2/mês, dentro dos **US$ 5 grátis**.
- **SerpAPI:** só 2 buscas quando sugere uma conexão.

## Sobre as conexões por conta própria
São **duas passagens separadas**. Se o 1º voo atrasar, a companhia do 2º não te ajuda,
e a mala precisa ser retirada e despachada de novo. O script avisa quando a folga entre os
voos é menor que 4 h; na dúvida, durma na conexão (`conexao_dias: [1]`).
Voos internacionais com conexão no Brasil: lembre que você passa pela imigração na saída do 2º voo.

## Rodar no computador (opcional)
```
pip install -r requirements.txt
python monitor.py --demo     # testa com dados de exemplo, sem internet
```
