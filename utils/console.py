"""Print the measured results in a form that is easy to read."""

from service.settings import PRICE_DATE
from service.strategies_service import CASCADE_THRESHOLDS, LEVELS, LEVEL_LABELS, NAMES, ORDER
from utils.formatting import fmt_ms, fmt_num, fmt_pct, fmt_pct_se, fmt_usd

PROFILES = ["small", "medium", "large"]


def _line():
    print("-" * 92)


def _title(text):
    print()
    _line()
    print(text)
    _line()


def _cell(text, width):
    text = str(text)
    if len(text) > width:
        return text[:width]
    return text.ljust(width)


def _table(header, rows, widths):
    print("  ".join(_cell(item, width) for item, width in zip(header, widths)))
    print("  ".join("-" * width for width in widths))
    for row in rows:
        print("  ".join(_cell(item, width) for item, width in zip(row, widths)))


def _cost_per_ok(summary):
    if summary["cost_per_adequate"] is None:
        return "—"
    return fmt_usd(summary["cost_per_adequate"])


def print_results(result):
    meta = result["meta"]
    strategies = result["strategies"]
    profiles = meta["profiles"]

    print()
    print("=" * 92)
    print("EXPERIMENTO — OTIMIZAÇÃO DO USO DE IA EM APLICAÇÕES DE SOFTWARE")
    print("Chamadas reais via LangChain. Métricas lidas da resposta da API.")
    print("=" * 92)
    print("Tarefas: " + str(meta["task_count"]) + " (10 baixas, 10 médias e 10 altas)")
    print("Repetições: " + str(meta["repetitions"]) + "    Semente: " + str(meta["seed"]))
    print("Execuções: " + str(len(result["records"])))

    _title("1. MODELOS — o que foi chamado")
    print("Preços configurados no .env, referência da tabela standard em " + PRICE_DATE + ".")
    print("O custo de cada chamada usa os tokens que a API devolveu, não uma estimativa.")
    print()
    for profile in PROFILES:
        data = profiles[profile]
        print(data["label"] + "  |  " + data["model"])
        print(
            "  Entrada "
            + fmt_usd(data["input_price"])
            + " / 1 milhão    Saída "
            + fmt_usd(data["output_price"])
            + " / 1 milhão"
        )
    judge = profiles["judge"]
    print()
    print("Avaliador da adequação: " + judge["model"])
    print("O custo do avaliador não entra na comparação entre estratégias.")
    print(
        "Custo total do avaliador nesta rodada: "
        + fmt_usd(result["checks"]["judge_cost"])
    )
    print("Limiares da cascata: 0,70, 0,80 e 0,90. Abaixo do limiar, a solicitação sobe de perfil.")
    print(
        "Confiança observada nesta rodada: de "
        + fmt_num(result["checks"]["confidence_min"], 2)
        + " a "
        + fmt_num(result["checks"]["confidence_max"], 2)
        + "."
    )
    print(
        "Confiança lida na resposta: "
        + fmt_pct(result["checks"]["confidence_parsed_rate"])
        + " das execuções trouxeram a linha CONFIANCA."
    )

    _title("2. RESULTADO GERAL — o que cada estratégia produziu")
    print("Adequação: percentual julgado como ADEQUADA, com o erro padrão.")
    print("Custo médio: dólares por solicitação, só das chamadas da estratégia.")
    print("Em 10 mil: esse custo vezes " + fmt_num(meta["projection_requests"], 0) + " solicitações.")
    print("Custo/ok: custo total dividido pelo número de respostas adequadas.")
    print("Tempo: média da latência sem os picos. Chamadas: média de inferências da estratégia.")
    print()
    rows = []
    for key in ORDER:
        summary = strategies[key]
        rows.append([
            NAMES[key],
            fmt_pct_se(summary["adequacy"], summary["adequacy_se"]),
            fmt_usd(summary["mean_cost"]),
            fmt_usd(summary["projection"]),
            _cost_per_ok(summary),
            fmt_ms(summary["mean_latency"]),
            fmt_num(summary["mean_calls"], 2),
        ])
    _table(
        ["Estratégia", "Adequação", "Custo médio", "Em 10 mil", "Custo/ok", "Tempo", "Chamadas"],
        rows,
        [24, 16, 14, 12, 14, 12, 8],
    )

    routing = strategies["routing"]
    large = strategies["always_large"]
    print()
    print("Como ler uma linha:")
    print(
        "  No roteamento, cerca de "
        + fmt_num(routing["adequacy"] * 100, 0)
        + " de cada 100 solicitações foram julgadas adequadas."
    )
    print("  Cada solicitação custou em média " + fmt_usd(routing["mean_cost"]) + ".")
    print(
        "  Em "
        + fmt_num(meta["projection_requests"], 0)
        + " solicitações, o custo fica em torno de "
        + fmt_usd(routing["projection"])
        + "."
    )
    print(
        "  No perfil grande, o mesmo volume ficaria em torno de "
        + fmt_usd(large["projection"])
        + ", com adequação de "
        + fmt_pct(large["adequacy"])
        + "."
    )

    _title("3. POR COMPLEXIDADE — onde o perfil pequeno se aproxima do grande")
    print("Adequação")
    rows = []
    for key in ORDER:
        item = result["by_level"][key]
        rows.append([
            NAMES[key],
            fmt_pct(item["low"]["adequacy"]),
            fmt_pct(item["medium"]["adequacy"]),
            fmt_pct(item["high"]["adequacy"]),
        ])
    _table(["Estratégia", "Baixa", "Média", "Alta"], rows, [24, 12, 12, 12])

    print()
    print("Custo médio por solicitação")
    rows = []
    for key in ORDER:
        item = result["by_level"][key]
        rows.append([
            NAMES[key],
            fmt_usd(item["low"]["mean_cost"]),
            fmt_usd(item["medium"]["mean_cost"]),
            fmt_usd(item["high"]["mean_cost"]),
        ])
    _table(["Estratégia", "Baixa", "Média", "Alta"], rows, [24, 14, 14, 14])

    _title("4. PICOS DE TEMPO — o que saiu do cálculo da latência")
    print("O método é o intervalo interquartil (IQR), com fator 1,5, separado por estratégia.")
    print("O pico sai apenas da média de tempo. Custo e adequação continuam com todas as execuções.")
    print()
    rows = []
    for key in ORDER:
        summary = strategies[key]
        rows.append([
            NAMES[key],
            str(summary["count"]),
            str(summary["outlier_count"]),
            fmt_pct(summary["outlier_rate"]),
            fmt_ms(summary["mean_latency"]),
            fmt_ms(summary["mean_latency_with_spikes"]),
        ])
    _table(
        ["Estratégia", "Execuções", "Picos", "%", "Tempo sem pico", "Tempo com pico"],
        rows,
        [24, 12, 10, 10, 16, 16],
    )

    _title("5. COMPRESSÃO, ROTEAMENTO E CASCATA")
    compression = result["compression"]["overall"]
    print(
        "Estimativa local de tokens de entrada: "
        + fmt_num(compression["tokens_before"], 0)
        + " antes da compressão e "
        + fmt_num(compression["tokens_after"], 0)
        + " depois."
    )
    print("Redução média estimada: " + fmt_pct(compression["reduction"]) + ".")
    print("O custo publicado acima usa a contagem oficial da API, não esta estimativa.")
    for level in LEVELS:
        item = result["compression"][level]
        print(
            "  "
            + LEVEL_LABELS[level]
            + ": "
            + fmt_num(item["tokens_before"], 0)
            + " → "
            + fmt_num(item["tokens_after"], 0)
            + " ("
            + fmt_pct(item["reduction"])
            + ")"
        )

    checks = result["checks"]
    print()
    print("Erro do classificador no roteamento, contra o nível da coleta: " + fmt_pct(checks["routing_error"]) + ".")
    print("Para onde o roteamento enviou as solicitações:")
    for profile in PROFILES:
        share = checks["routing_by_profile"].get(profile, 0)
        print("  " + profiles[profile]["label"] + ": " + fmt_pct(share))
    print()
    print("Confiança das respostas, na faixa de 0,70 a 0,99:")
    bands = checks["confidence_bands"]
    total = checks["confidence_count"] or 1
    print("  Abaixo de 0,70: " + str(bands["below_070"]) + " (" + fmt_pct(bands["below_070"] / total) + ")")
    print("  De 0,70 a 0,79: " + str(bands["from_070_to_079"]) + " (" + fmt_pct(bands["from_070_to_079"] / total) + ")")
    print("  De 0,80 a 0,89: " + str(bands["from_080_to_089"]) + " (" + fmt_pct(bands["from_080_to_089"] / total) + ")")
    print("  De 0,90 a 0,99: " + str(bands["from_090_to_099"]) + " (" + fmt_pct(bands["from_090_to_099"] / total) + ")")
    print()
    print("Onde cada cascata parou:")
    for key in CASCADE_THRESHOLDS:
        print("  " + NAMES[key])
        for profile in PROFILES:
            share = checks["cascades"][key].get(profile, 0)
            print("    " + profiles[profile]["label"] + ": " + fmt_pct(share))

    _title("6. LEITURA DOS NÚMEROS")
    for sentence in result["reading"]:
        print("- " + sentence)
        print()

    _title("ARQUIVOS")
    files = result["files"]
    print("PDF:  " + files["pdf"])
    print("CSV:  " + files["executions"])
    print("CSV:  " + files["summary"])
    print("CSV:  " + files["human_review"])
    for chart in files["charts"]:
        print("PNG:  " + chart)
    print()
    print("Abra o PDF para levar as tabelas e os gráficos ao texto de metodologia e resultados.")
    print("=" * 92)
