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
| 🏷️ Promoções postadas | blogs (Melhores Destinos, Passageiro de Primeira, Pontos pra Voar, Viaje na Viagem), Portal Amazônia, Panrotas, Catraca Livre, G1 AM/PA, A Crítica, canais públicos do Telegram (Melhores Destinos, Passageiro de Primeira, Cartões e Viagens, Promobit) e Google Notícias; avisa post do seu destino, saindo do Norte, 📦 pacotes e promoção das companhias (ignora milhas/pontos) | grátis |
| 🛟 Depois da compra | `/comprei 1 1172 29/05`: vigia por 24 h; se cair, avisa pra recomprar e desistir da antiga (ANAC: compra com 7+ dias do voo) | centavos |
| ⏰ Busca pulada | se o GitHub pular o horário agendado, o vigia dispara a busca de novo | grátis |
| 🩺 Saúde | avisa se o monitor parar, se der erro de token ou se a Apify/SerpAPI estiver acabando (pausa a checagem rápida acima de 85%) | grátis |

Todo aviso vem com o **veredito**: 🔥 promoção forte / ✅ bom / 😐 normal / 💸 caro, e um conselho
(compre agora ou espere), com base na faixa típica do Google, nos preços das suas datas, na tendência e
em quanto falta pra viagem. O relatório traz também gráfico da evolução, calendário colorido, feriados
no período e links pra comparar no Skyscanner e no Kayak.

Som: só promoção forte, recorde, alvo e queda pós-compra tocam. O resto chega em silêncio; entre 22h e
7h tudo é silencioso, menos 🔥 e 🛟.

### 🌴 Radar do Norte
A cada 4 h (grátis, pelo Fli) olha pra onde está barato voar saindo de Manaus, Belém, Santarém e Trombetas
(mude em `radar_origens`). Guarda o preço de cada destino e avisa na hora quando um cair 25%+ abaixo do normal;
domingo manda o resumo. Posts dos blogs que citam "saindo de Belém/Manaus…" também avisam.

### ✈️ Ofertas oficiais das companhias
A cada 2 h lê as páginas de ofertas da **GOL** (voegol.com.br/ofertas) e da **Azul** (passagens.voeazul.com.br:
melhores-ofertas, ofertas-azul, ofertas-imperdiveis). Avisa quando um trecho saindo do Norte cai 15%+ abaixo do
que a cia costuma anunciar, ou quando aparece oferta pro destino de uma rota sua saindo da origem ou de um hub das
escalas (ex.: GRU → Santa Cruz). A 1ª rodada só aprende. Tudo entra no resumo de domingo e no `/radar`.

### 🚤 Barco e lancha
Saídas, horários e preços de duas plataformas de venda online: **Yjara Viagens** (Pará e Baixo Amazonas) e
**Navegam** (Amazonas, inclusive Terra Santa, Faro e Nhamundá). Cada pedaço de uma viagem com escala é vendido
como trecho próprio: dá pra comprar só Oriximiná → Santarém num barco que vem de Manaus, e a busca mostra onde a
embarcação para antes ("para antes em Juruti, Óbidos"). A busca roda direto no Worker da Cloudflare: resposta em segundos.
Barcos da Navegam com venda pelo WhatsApp trazem o link; no fim de cada busca vão os WhatsApps da Yjara e da Navegam.

**📒 Agenda de lanchas**: lancha pequena que só vende pelo WhatsApp/Instagram. Cadastre no painel ou no bot
(`Lancha Fulano, 93 99999-9999, Oriximiná, Santarém`); o contato aparece em "Também pergunte" quando você busca
aquele trecho (nos dois sentidos). Sem "para", aparece em qualquer trecho daquela cidade.

### 🏠 Menu com botões (/menu)
O bot tem menu: ✈️ Passagem de avião · 🚤 Barco e lancha · 🌴 Promoções · 🔔 O que estou vigiando · ⚙️ Ajustes.
Navegar e buscar barco é instantâneo (o Worker responde sozinho). O que depende dos seus dados de voo (preços agora,
buscar tudo, mudar alvo, pausar) acorda o vigia no GitHub e chega em ~1 min. Também dá pra só escrever um trecho:
`Oriximiná Santarém`, `Santarém para Óbidos 12/12`.

Como funciona por dentro: o vigia manda pro Worker (provando com OIDC que é este repositório) o token do bot e um
resumo das rotas, trechos e agenda; o Worker guarda num cofre KV (`quackvoo-qv`) e só obedece ao seu chat.

### Botões nos avisos
Cada aviso traz 🎯 Alvo (90% do preço atual), ✅ Comprei (liga a rede de segurança de 24 h), ⏸️ Pausar 7 dias e
📊 Status.

### Comandos digitados (continuam valendo)

```
/menu                        menu com botões
/status · /rotas · /agora · /promos · /radar
/buscar MAO VVI 29/05 [05/06] preço de uma data (1 busca SerpAPI)
/alvo 1 1800 · /pausar 1 [7] · /ativar 1
/comprei 1 1172 29/05        rede de segurança de 24 h
/barco Oriximiná Santarém    saídas de barco/lancha (na hora)
/vigiarbarco Oriximiná Santarém · /barcos · /pararbarco 1
/agenda · /agenda apagar 1   contatos de lanchas
```
Com uma rota só, o número é opcional. O bot só obedece ao seu `TELEGRAM_CHAT_ID`.

## Custos
- **GitHub Actions:** grátis em repositório público (o vigia roda ~96 vezes por dia, ~30 s cada).
  Se o repositório virar privado, o vigia sozinho passa dos 2.000 min grátis: aumente o intervalo dele.
- **Apify:** ~US$ 0,20 por 1.000 dias de calendário. Escalas são testadas **uma vez por semana**
  (`conexoes_toda`). Uma rota de ~3 meses com 6 escalas + checagem rápida a cada 2 h fica perto de
  US$ 3/mês, dentro dos **US$ 5 grátis**. O painel mostra a estimativa.
- **Fli (grátis):** biblioteca aberta que lê o Google Voos direto. Os trechos das escalas são buscados nele
  primeiro; a Apify só completa quando ele cobre menos de 60% dos dias (trechos que o Fli nunca acha vão direto pra Apify). Ele **não** acha Manaus → Santa Cruz
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
