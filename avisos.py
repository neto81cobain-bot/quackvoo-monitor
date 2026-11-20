def montar_telegram(res_avisar: list[tuple[dict, list[str]]]) -> str:
    linhas = [
        "<b>Quack! 🦆</b>",
        f"<i>Relatório de {hoje.strftime('%d/%m/%Y')} · preços do Google Voos (totais, com taxas)</i>",
        "",
    ]
    for r, motivos in res_avisar:
        if "melhor" not in r:
            linhas.append(f"⚠️ <b>{r['nome']}</b>: {'; '.join(r['erros'])}")
            linhas.append("")
            continue

        m, per = r["melhor"], r.get("periodo")
        tipo = f"ida e volta, {r['noites']} noites" if r["noites"] else "só ida"
        sem = sorted(r.get("semana", []), key=lambda x: x[1])
        c = r.get("conexao")

        linhas.append(f"✈️ <b>{r['nome']}</b> · <i>{tipo} · {r['adultos']} adulto(s)</i>")
        if motivos:
            linhas.extend(motivos)
        linhas.append("")
        linhas.append(f"<b>{A.reais(m['preco'])}</b>")
        linhas.append(f"saindo <b>{A.br(m['dia'])}</b> · <a href=\"{m['url']}\">abrir no Google Voos</a>")

        if per:
            linhas.append(f"📅 Melhor semana: <b>{A.br(per['inicio'])} a {A.br(per['fim'])}</b> (média {A.reais(per['media'])})")
        if sem:
            linhas.append(f"📆 Dia da semana mais barato pra sair: <b>{sem[0][0]}</b>; mais caro: {sem[-1][0]}")

        top = sorted(r["calendario"].items(), key=lambda kv: kv[1]["preco"])[:5]
        if top:
            linhas.append("")
            linhas.append("<b>Os 5 dias mais baratos</b>")
            for idx, (k, v) in enumerate(top, 1):
                linhas.append(f"{idx}. <a href=\"{v['url']}\">{A.br(k)}</a> — <b>{A.reais(v['preco'])}</b>")

        if r.get("meses"):
            linhas.append("")
            linhas.append("<pre>")
            linhas.append(f"{'Mês':<7} {'Menor':>9} {'Dia':<10} {'Média':>9}")
            for x in r["meses"]:
                linhas.append(f"{str(x['mes'])[:7]:<7} {A.reais(x['menor']):>9} {A.br(x['dia'])[:10]:<10} {A.reais(x['media']):>9}")
            linhas.append("</pre>")

        if c and c.get("economia", 0) > 0:
            linhas.append("")
            linhas.append("🔀 <b>Conexão por conta própria</b>")
            linhas.extend(texto_conexao(c, r["origem"], r["destino"], r["noites"]))
            linhas.append(f"<b>Economia: {A.reais(c['economia'])}</b>")
            linhas.extend(c.get("horarios", []))
            linhas.append("<i>São passagens separadas: se o 1º voo atrasar, a cia do 2º não te protege, e a mala precisa ser despachada de novo. Deixe 4h+ de folga ou durma na conexão.</i>")

        linhas.append("")
        linhas.append("────────────────────────")
        linhas.append("")

    linhas.append("<i>Preços mudam a toda hora: confira antes de pagar. Gerado pelo QuackVoo Monitor.</i>")
    return "\n".join(linhas).strip()
