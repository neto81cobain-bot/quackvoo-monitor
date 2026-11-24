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

## Pra não perder promoção

Além das 2 buscas completas por dia (`monitor.py`), o **vigia** (`vigia.py`) roda a cada ~15 min:

| O quê | Como | Custo |
|---|---|---|
| ⚡ Checagem rápida | a cada 2 h (ajustável), só nos ~8 dias mais baratos de cada rota | ~US$ 0,90/mês |
| 🏷️ Promoções dos blogs | Melhores Destinos, Passagens Imperdíveis e Passageiro de Primeira; avisa se o post fala do seu destino | grátis |
| 🛟 Depois da compra | `/comprei 1 1172 29/05`: vigia por 24 h; se cair, avisa pra recomprar e desistir da antiga (ANAC: compra com 7+ dias do voo) | centavos |
| ⏰ Busca pulada | se o GitHub pular o horário agendado, o vigia dispara a busca de novo | grátis |
| 🩺 Saúde | avisa se o monitor parar, se der erro de token ou se a Apify/SerpAPI estiver acabando (pausa a checagem rápida acima de 85%) | grátis |

Todo aviso vem com o **veredito**: 🔥 promoção forte / ✅ bom / 😐 normal / 💸 caro, e um conselho
(compre agora ou espere), com base na faixa típica do Google, nos preços das suas datas, na tendência e
em quanto falta pra viagem. O relatório traz também gráfico da evolução, calendário colorido, feriados
no período e links pra comparar no Skyscanner e no Kayak.

Som: só promoção forte, recorde, alvo e queda pós-compra tocam. O resto chega em silêncio; entre 22h e
7h tudo é silencioso, menos 🔥 e 🛟.

### Comandos do Telegram (respondo em até ~15 min)

```
/status                      preços, recorde e créditos
/rotas                       suas rotas (com número)
/agora                       busca completa agora
/buscar MAO VVI 29/05 [05/06] preço de uma data (1 busca SerpAPI)
/calendario 1 [06/2027]      dias baratos do mês em 🟩🟨🟥
/grafico 1                   evolução do preço
/promos                      últimas promoções achadas
/alvo 1 1800                 muda o preço-alvo
/pausar 1  ·  /ativar 1      liga/desliga a rota
/nova MAO VVI 01/06/2027 30/06/2027 [noites]
/apagar 1 sim
/comprei 1 1172 29/05        rede de segurança de 24 h
```
Com uma rota só, o número é opcional. O bot só obedece ao seu `TELEGRAM_CHAT_ID`.

## Custos
- **GitHub Actions:** grátis em repositório público (o vigia roda ~96 vezes por dia, ~30 s cada).
  Se o repositório virar privado, o vigia sozinho passa dos 2.000 min grátis: aumente o intervalo dele.
- **Apify:** ~US$ 0,20 por 1.000 dias de calendário. Escalas são testadas **uma vez por semana**
  (`conexoes_toda`). Uma rota de ~3 meses com 6 escalas + checagem rápida a cada 2 h fica perto de
  US$ 3/mês, dentro dos **US$ 5 grátis**. O painel mostra a estimativa.
- **Fli (grátis):** biblioteca aberta que lê o Google Voos direto. Os trechos das escalas são buscados nele
  primeiro; a Apify só completa quando ele cobre menos de 80% dos dias. Ele **não** acha Manaus → Santa Cruz
  (o Google não mostra essa rota pra ele), então a rota principal segue na Apify. Se a Apify passar de 85%,
  a checagem rápida usa só o Fli. Teste qualquer rota em Actions → "Teste das fontes de preço".
- **SerpAPI:** 1 busca por aviso (horário do voo + opinião do Google), 2 quando sugere escala e 1 por `/buscar`.

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
