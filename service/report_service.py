"""CSV, charts and PDF built from the measured API calls."""

import csv
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from reportlab.lib import colors
from reportlab.lib.enums import TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import HRFlowable, Image, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from prompts.tasks import load_tasks
from service.settings import PRICE_DATE, PRICE_SOURCE
from service.strategies_service import CASCADE_THRESHOLDS, DESCRIPTIONS, LEVELS, LEVEL_LABELS, NAMES, ORDER, SHORT_NAMES
from utils.formatting import fmt_ms, fmt_num, fmt_pct, fmt_pct_se, fmt_usd
from utils.text import compress_prompt, estimate_tokens

ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "resultados"
CHART_DIR = OUTPUT_DIR / "graficos"

PROFILE_ORDER = ["small", "medium", "large"]
COLORS = ["#4C78A8", "#F58518", "#54A24B", "#E45756", "#72B7B2", "#B279A2", "#FF9DA7", "#9D755D"]


def _register_fonts():
    regular = Path(r"C:\Windows\Fonts\arial.ttf")
    bold = Path(r"C:\Windows\Fonts\arialbd.ttf")
    if regular.exists() and bold.exists():
        pdfmetrics.registerFont(TTFont("Arial", str(regular)))
        pdfmetrics.registerFont(TTFont("Arial-Bold", str(bold)))
        return "Arial", "Arial-Bold"
    return "Helvetica", "Helvetica-Bold"


def _esc(text):
    return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _csv_num(value, digits):
    if value is None:
        return ""
    return fmt_num(value, digits)


def _trunc(text, limit=800):
    text = (text or "").strip()
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."


def _save_csv(result):
    executions_path = OUTPUT_DIR / "execucoes.csv"
    fields = [
        "strategy", "task_code", "true_complexity", "estimated_complexity", "repetition",
        "final_profile", "final_model", "models_used", "call_count",
        "input_tokens", "output_tokens", "cost_usd", "latency_ms",
        "confidence", "confidence_parsed", "used_compression", "cascade_threshold",
        "task_criterion", "task_prompt",
        "adequate", "judge_raw", "judge_justification", "judge_cost_usd",
        "latency_outlier", "answer",
    ]
    with executions_path.open("w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=fields, delimiter=";", extrasaction="ignore")
        writer.writeheader()
        for record in result["records"]:
            row = dict(record)
            row["cost_usd"] = _csv_num(record["cost_usd"], 8)
            row["latency_ms"] = _csv_num(record["latency_ms"], 2)
            row["confidence"] = _csv_num(record["confidence"], 4)
            row["judge_cost_usd"] = _csv_num(record["judge_cost_usd"], 8)
            writer.writerow(row)

    summary_path = OUTPUT_DIR / "resumo_estrategias.csv"
    summary_fields = [
        "strategy", "adequacy", "adequacy_se", "mean_cost_usd", "projection_usd",
        "cost_per_adequate_usd", "mean_latency_ms", "mean_latency_with_spikes_ms",
        "mean_calls", "spikes", "spike_rate",
        "adequacy_low", "adequacy_medium", "adequacy_high",
        "cost_low", "cost_medium", "cost_high",
    ]
    with summary_path.open("w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=summary_fields, delimiter=";")
        writer.writeheader()
        for key in ORDER:
            item = result["strategies"][key]
            levels = result["by_level"][key]
            writer.writerow({
                "strategy": NAMES[key],
                "adequacy": _csv_num(item["adequacy"], 4),
                "adequacy_se": _csv_num(item["adequacy_se"], 4),
                "mean_cost_usd": _csv_num(item["mean_cost"], 8),
                "projection_usd": _csv_num(item["projection"], 4),
                "cost_per_adequate_usd": _csv_num(item["cost_per_adequate"], 8),
                "mean_latency_ms": _csv_num(item["mean_latency"], 2),
                "mean_latency_with_spikes_ms": _csv_num(item["mean_latency_with_spikes"], 2),
                "mean_calls": _csv_num(item["mean_calls"], 3),
                "spikes": item["outlier_count"],
                "spike_rate": _csv_num(item["outlier_rate"], 4),
                "adequacy_low": _csv_num(levels["low"]["adequacy"], 4),
                "adequacy_medium": _csv_num(levels["medium"]["adequacy"], 4),
                "adequacy_high": _csv_num(levels["high"]["adequacy"], 4),
                "cost_low": _csv_num(levels["low"]["mean_cost"], 8),
                "cost_medium": _csv_num(levels["medium"]["mean_cost"], 8),
                "cost_high": _csv_num(levels["high"]["mean_cost"], 8),
            })
    review_path = _save_human_review_csv(result)
    return executions_path, summary_path, review_path


def _save_human_review_csv(result):
    """Inadequate executions plus columns for a human reviewer."""
    path = OUTPUT_DIR / "revisao_humana.csv"
    fields = [
        "strategy", "task_code", "true_complexity", "task_criterion", "task_prompt",
        "answer", "adequate", "judge_raw", "judge_justification",
        "humano_adequada", "observacao_humana",
    ]
    inadequate = [record for record in result["records"] if not record["adequate"]]
    inadequate.sort(key=lambda item: (item["task_code"], ORDER.index(item["strategy"])))

    with path.open("w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=fields, delimiter=";")
        writer.writeheader()
        for record in inadequate:
            writer.writerow({
                "strategy": NAMES[record["strategy"]],
                "task_code": record["task_code"],
                "true_complexity": record["true_complexity"],
                "task_criterion": record.get("task_criterion", ""),
                "task_prompt": record.get("task_prompt", ""),
                "answer": record.get("answer", ""),
                "adequate": record["adequate"],
                "judge_raw": record.get("judge_raw", ""),
                "judge_justification": record.get("judge_justification", ""),
                "humano_adequada": "",
                "observacao_humana": "",
            })
    return path


def _figure(title, ylabel):
    figure, axis = plt.subplots(figsize=(10, 5.2))
    axis.set_title(title, loc="left", fontsize=13, pad=12)
    axis.set_ylabel(ylabel)
    axis.grid(axis="y", linestyle="--", alpha=0.4)
    axis.set_axisbelow(True)
    return figure, axis


def _save_figure(figure, name):
    path = CHART_DIR / name
    figure.tight_layout()
    figure.savefig(path, dpi=140, bbox_inches="tight")
    plt.close(figure)
    return path


def _bars(title, ylabel, values, filename, formatter, ylim=None):
    figure, axis = _figure(title, ylabel)
    labels = [SHORT_NAMES[key] for key in ORDER]
    bars = axis.bar(labels, values, color=COLORS)
    axis.bar_label(bars, labels=[formatter(value) for value in values], padding=3, fontsize=8)
    axis.tick_params(axis="x", labelsize=8, labelrotation=25)
    if ylim:
        axis.set_ylim(*ylim)
    return _save_figure(figure, filename)


def _complexity_chart(result):
    figure, axis = _figure("Adequação por complexidade", "Adequação (%)")
    width = 0.09
    count = len(ORDER)
    for index, key in enumerate(ORDER):
        shift = (index - (count - 1) / 2) * width
        positions = [base + shift for base in range(len(LEVELS))]
        heights = [result["by_level"][key][level]["adequacy"] * 100 for level in LEVELS]
        axis.bar(positions, heights, width, label=SHORT_NAMES[key], color=COLORS[index])
    axis.set_xticks(range(len(LEVELS)))
    axis.set_xticklabels([LEVEL_LABELS[level] for level in LEVELS])
    axis.set_ylim(0, 118)
    axis.legend(ncol=3, fontsize=8, frameon=False)
    return _save_figure(figure, "adequacao_por_complexidade.png")


def save_charts(result):
    strategies = result["strategies"]
    paths = [
        _bars(
            "Custo projetado para 10.000 solicitações",
            "Dólares (US$)",
            [strategies[key]["projection"] for key in ORDER],
            "custo_projetado.png",
            lambda value: fmt_num(value, 2),
        ),
        _bars(
            "Adequação geral",
            "Adequação (%)",
            [strategies[key]["adequacy"] * 100 for key in ORDER],
            "adequacao_geral.png",
            lambda value: fmt_num(value, 1),
            (0, 118),
        ),
        _complexity_chart(result),
        _bars(
            "Custo por resposta adequada",
            "Dólares (US$)",
            [strategies[key]["cost_per_adequate"] or 0 for key in ORDER],
            "custo_por_resposta_adequada.png",
            lambda value: fmt_num(value, 5),
        ),
        _bars(
            "Latência média sem picos",
            "Milissegundos",
            [strategies[key]["mean_latency"] for key in ORDER],
            "latencia_media.png",
            lambda value: fmt_num(value, 0),
        ),
    ]
    return paths


def _styles(font, bold):
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        name="DocTitle", fontName=bold, fontSize=15, leading=19,
        textColor=colors.HexColor("#1F4E79"), spaceAfter=6,
    ))
    styles.add(ParagraphStyle(
        name="Section", fontName=bold, fontSize=12, leading=15,
        textColor=colors.HexColor("#1F4E79"), spaceBefore=10, spaceAfter=6,
    ))
    styles.add(ParagraphStyle(
        name="BodyTextDoc", fontName=font, fontSize=10, leading=14,
        alignment=TA_JUSTIFY, spaceAfter=6,
    ))
    styles.add(ParagraphStyle(
        name="NoteDoc", fontName=font, fontSize=9, leading=12,
        textColor=colors.HexColor("#333333"), spaceAfter=6,
    ))
    styles.add(ParagraphStyle(name="Cell", fontName=font, fontSize=7.5, leading=9.5))
    styles.add(ParagraphStyle(
        name="AnnexCase", fontName=bold, fontSize=10, leading=13,
        textColor=colors.HexColor("#1F4E79"), spaceBefore=8, spaceAfter=4,
    ))
    styles.add(ParagraphStyle(
        name="AnnexBody", fontName=font, fontSize=8.5, leading=11,
        alignment=TA_JUSTIFY, spaceAfter=4,
    ))
    styles.add(ParagraphStyle(
        name="HeadCell", fontName=bold, fontSize=7.5, leading=9.5, textColor=colors.white,
    ))
    return styles


def _pdf_table(data, widths, font, bold):
    table = Table(data, colWidths=widths, repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1F4E79")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), bold),
        ("FONTNAME", (0, 1), (-1, -1), font),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F4F7FB")]),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#D0D7E2")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 3),
        ("RIGHTPADDING", (0, 0), (-1, -1), 3),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    return table


def _header(texts, style):
    return [Paragraph(_esc(text), style) for text in texts]


def _paragraph(text, style):
    return Paragraph(_esc(text), style)


def _footer(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(colors.HexColor("#555555"))
    canvas.drawString(1.7 * cm, 0.8 * cm, "Experimento com API — TCC — otimização do uso de IA")
    canvas.drawRightString(A4[0] - 1.7 * cm, 0.8 * cm, "Página " + str(doc.page))
    canvas.restoreState()


def _build_pdf(result, charts, path, font, bold):
    styles = _styles(font, bold)
    meta = result["meta"]
    strategies = result["strategies"]
    profiles = meta["profiles"]
    story = []

    story.append(_paragraph(
        "Otimização do uso de inteligência artificial em aplicações de software",
        styles["DocTitle"],
    ))
    story.append(_paragraph("Relatório do experimento — metodologia e resultados", styles["Section"]))
    story.append(_paragraph(
        "O experimento compara três modelos, o roteamento pela complexidade, "
        "três cascatas (limiares 0,70, 0,80 e 0,90) e a compressão de prompt seguida de roteamento. "
        "Cada solicitação é enviada de verdade à API, por meio do LangChain. "
        "As métricas são os tokens devolvidos pela API, o custo calculado com a tabela de preços, "
        "o tempo medido na máquina e a adequação julgada por um modelo avaliador.",
        styles["BodyTextDoc"],
    ))

    story.append(_paragraph("Parte A — Método", styles["Section"]))
    story.append(HRFlowable(width="100%", thickness=0.6, color=colors.HexColor("#1F4E79"), spaceBefore=2, spaceAfter=6))
    story.append(_paragraph("Instrumentação", styles["Section"]))
    story.append(_paragraph(
        "A coleta foi feita em Python 3, com LangChain (ChatOpenAI) e a API da OpenAI. "
        "Os gráficos usam Matplotlib e este PDF usa ReportLab. "
        "A temperatura das chamadas é 0 e a semente enviada ao provedor é "
        + str(meta["seed"])
        + ". Os preços de referência da tabela standard, em "
        + PRICE_DATE
        + ", estão em "
        + PRICE_SOURCE
        + ". O valor usado em cada chamada é o que está no arquivo .env.",
        styles["BodyTextDoc"],
    ))

    header = _header(["Perfil", "Modelo", "Entrada / 1M", "Saída / 1M"], styles["HeadCell"])
    rows = [header]
    for profile in PROFILE_ORDER:
        data = profiles[profile]
        rows.append([
            data["label"],
            data["model"],
            fmt_usd(data["input_price"]),
            fmt_usd(data["output_price"]),
        ])
    judge = profiles["judge"]
    rows.append(["Avaliador", judge["model"], fmt_usd(judge["input_price"]), fmt_usd(judge["output_price"])])
    story.append(_pdf_table(rows, [3.5 * cm, 5.5 * cm, 4 * cm, 4 * cm], font, bold))
    story.append(Spacer(1, 8))
    story.append(_paragraph(
        "Custo (US$) = tokens de entrada devolvidos pela API / 1.000.000 × preço de entrada "
        "+ tokens de saída devolvidos pela API / 1.000.000 × preço de saída.",
        styles["BodyTextDoc"],
    ))
    story.append(_paragraph(
        "A latência é o tempo de relógio entre o envio da chamada e a volta da resposta, em milissegundos. "
        "Ela inclui a rede desta máquina. Na cascata e no roteamento, o tempo da solicitação é a soma das chamadas daquela estratégia.",
        styles["BodyTextDoc"],
    ))
    story.append(_paragraph(
        "A adequação não é sorteada. Um modelo avaliador ("
        + judge["model"]
        + ") lê a solicitação, o critério da tarefa e a resposta. "
        "Se a resposta atender, ele responde ADEQUADA. Se não atender, responde INADEQUADA "
        "e escreve MOTIVO: com uma justificativa objetiva. "
        "O custo e o tempo desse avaliador ficam de fora da comparação, porque ele é instrumento de medida, não parte da aplicação.",
        styles["BodyTextDoc"],
    ))
    story.append(_paragraph(
        "Cada resposta de aplicação termina com uma linha CONFIANCA, um número de 0 a 1 escrito pelo próprio modelo. "
        "Há três cascatas, com limiares 0,70, 0,80 e 0,90. A solicitação sobe de perfil quando a confiança fica abaixo do limiar daquela cascata. "
        "Se a linha não vier, a confiança entra como 0 e a cascata sobe. "
        "A faixa examinada no resultado vai de 0,70 a 0,99.",
        styles["BodyTextDoc"],
    ))

    story.append(_paragraph("Coleta de dados", styles["Section"]))
    story.append(_paragraph(
        "Foram escritas "
        + str(meta["task_count"])
        + " solicitações de aplicações de software: 10 de complexidade baixa, 10 de complexidade média "
        "e 10 de complexidade alta. Cada uma tem um critério do que conta como resposta adequada. "
        "Cada solicitação passou "
        + str(meta["repetitions"])
        + " vez(es) por cada estratégia, em "
        + str(len(result["records"]))
        + " execuções. O nível de complexidade foi definido na elaboração das tarefas e serve para medir o erro do classificador.",
        styles["BodyTextDoc"],
    ))

    header = _header(["Código", "Nível", "Tipo", "Título"], styles["HeadCell"])
    rows = [header]
    for task in load_tasks():
        rows.append([task["code"], LEVEL_LABELS[task["complexity"]], task["kind"], task["title"]])
    story.append(_pdf_table(rows, [2.2 * cm, 2.6 * cm, 3.4 * cm, 8.6 * cm], font, bold))
    story.append(Spacer(1, 8))

    story.append(_paragraph("Fontes de erro", styles["Section"]))
    for item in [
        "A latência inclui a rede e a fila do provedor. Um atraso pontual não é um erro do modelo.",
        "O classificador é o perfil pequeno. Ele pode errar o nível que foi atribuído na coleta.",
        "A confiança é declarada pelo modelo na própria resposta. Ela não é uma probabilidade calibrada.",
        "O avaliador também é um modelo e pode marcar como adequada uma resposta fraca, ou o contrário.",
        "A compressão apaga palavras frequentes do português. Ela pode apagar uma palavra que importava.",
        "O preço vem da tabela configurada. Ele acompanha os tokens da API, mas não é a fatura do provedor.",
    ]:
        story.append(_paragraph("• " + item, styles["BodyTextDoc"]))

    story.append(_paragraph("Tratamento dos pontos discrepantes", styles["Section"]))
    story.append(_paragraph(
        "O pico de latência é procurado pelo intervalo interquartil, com fator 1,5, dentro de cada estratégia. "
        "Um ponto abaixo de Q1 − 1,5 × IQR ou acima de Q3 + 1,5 × IQR sai apenas da média, da mediana e do desvio da latência. "
        "Custo e adequação usam todas as execuções. Uma resposta inadequada permanece no resultado. "
        "As linhas discrepantes continuam no CSV, na coluna latency_outlier.",
        styles["BodyTextDoc"],
    ))

    story.append(_paragraph("Análise", styles["Section"]))
    story.append(_paragraph(
        "Para cada estratégia são calculadas a proporção de respostas adequadas, o erro padrão dessa proporção, "
        "o custo médio, o custo por resposta adequada, a latência média e o número médio de chamadas. "
        "O erro padrão da proporção é a raiz de p × (1 − p) / n. "
        "A projeção multiplica o custo médio pela quantidade configurada de solicitações e mantém o mix da amostra. "
        "O roteamento pede ao perfil pequeno que classifique a solicitação em low, medium ou high e envia o prompt ao perfil correspondente. "
        "A compressão remove palavras muito frequentes antes dessa classificação. "
        "Cada cascata chama o perfil pequeno e só segue para o médio, e depois para o grande, se a confiança ficar abaixo do seu limiar (0,70, 0,80 ou 0,90).",
        styles["BodyTextDoc"],
    ))
    for key in ORDER:
        story.append(_paragraph(NAMES[key] + ". " + DESCRIPTIONS[key], styles["BodyTextDoc"]))
    story.append(_paragraph(
        "Não há instrumento físico nem certificado de calibração. "
        "O controle equivalente é a semente, a temperatura 0, a tabela de preços do .env e o critério escrito de cada tarefa.",
        styles["BodyTextDoc"],
    ))

    story.append(PageBreak())
    story.append(_paragraph("Parte B — Resultados", styles["Section"]))
    story.append(HRFlowable(width="100%", thickness=0.6, color=colors.HexColor("#1F4E79"), spaceBefore=2, spaceAfter=6))
    story.append(_paragraph("1. Visão geral", styles["Section"]))

    header = _header(
        ["Estratégia", "Adequação", "Custo médio", "Projeção", "Custo/ok", "Tempo", "Chamadas"],
        styles["HeadCell"],
    )
    rows = [header]
    cell = styles["Cell"]
    for key in ORDER:
        item = strategies[key]
        if item["cost_per_adequate"] is None:
            cost_per_ok = "—"
        else:
            cost_per_ok = fmt_usd(item["cost_per_adequate"])
        rows.append([
            Paragraph(_esc(NAMES[key]), cell),
            Paragraph(_esc(fmt_pct_se(item["adequacy"], item["adequacy_se"])), cell),
            Paragraph(_esc(fmt_usd(item["mean_cost"])), cell),
            Paragraph(_esc(fmt_usd(item["projection"])), cell),
            Paragraph(_esc(cost_per_ok), cell),
            Paragraph(_esc(fmt_ms(item["mean_latency"])), cell),
            Paragraph(_esc(fmt_num(item["mean_calls"], 2)), cell),
        ])
    story.append(_pdf_table(
        rows,
        [3.3 * cm, 2.8 * cm, 2.3 * cm, 2.2 * cm, 2.4 * cm, 2.2 * cm, 2 * cm],
        font,
        bold,
    ))
    story.append(Spacer(1, 8))
    story.append(_paragraph(
        "Cada bloco abaixo é uma estratégia. A linha geral repete a tabela de cima. "
        "As colunas Baixa, Média e Alta separam o mesmo indicador pelo nível da tarefa.",
        styles["NoteDoc"],
    ))

    story.append(PageBreak())
    story.append(_paragraph("2. Resultado de cada estratégia", styles["Section"]))
    checks = result["checks"]
    for key in ORDER:
        item = strategies[key]
        levels = result["by_level"][key]
        story.append(Spacer(1, 6))
        story.append(_paragraph(NAMES[key], styles["Section"]))
        story.append(_paragraph(DESCRIPTIONS[key], styles["NoteDoc"]))
        detail = [_header(["Indicador", "Baixa", "Média", "Alta", "Geral"], styles["HeadCell"])]
        detail.append([
            "Adequação",
            fmt_pct(levels["low"]["adequacy"]),
            fmt_pct(levels["medium"]["adequacy"]),
            fmt_pct(levels["high"]["adequacy"]),
            fmt_pct_se(item["adequacy"], item["adequacy_se"]),
        ])
        detail.append([
            "Custo médio",
            fmt_usd(levels["low"]["mean_cost"]),
            fmt_usd(levels["medium"]["mean_cost"]),
            fmt_usd(levels["high"]["mean_cost"]),
            fmt_usd(item["mean_cost"]),
        ])
        story.append(_pdf_table(detail, [3.2 * cm, 3.2 * cm, 3.2 * cm, 3.2 * cm, 4 * cm], font, bold))
        story.append(Spacer(1, 4))
        if item["cost_per_adequate"] is None:
            cost_per_ok = "—"
        else:
            cost_per_ok = fmt_usd(item["cost_per_adequate"])
        story.append(_paragraph(
            "Projeção para "
            + fmt_num(meta["projection_requests"], 0)
            + " solicitações: "
            + fmt_usd(item["projection"])
            + ". Custo por resposta adequada: "
            + cost_per_ok
            + ". Tempo médio sem picos: "
            + fmt_ms(item["mean_latency"])
            + ". Chamadas médias: "
            + fmt_num(item["mean_calls"], 2)
            + ".",
            styles["BodyTextDoc"],
        ))
        if key in CASCADE_THRESHOLDS:
            share = checks["cascades"][key]
            story.append(_paragraph(
                "Onde parou: pequeno "
                + fmt_pct(share.get("small", 0))
                + ", médio "
                + fmt_pct(share.get("medium", 0))
                + ", grande "
                + fmt_pct(share.get("large", 0))
                + ".",
                styles["BodyTextDoc"],
            ))

    story.append(PageBreak())
    story.append(_paragraph("3. Confiança, de 0,70 a 0,99", styles["Section"]))
    story.append(_paragraph(
        "A confiança escrita pelo modelo nesta rodada foi de "
        + fmt_num(checks["confidence_min"], 2)
        + " a "
        + fmt_num(checks["confidence_max"], 2)
        + ". A tabela conta em qual faixa cada resposta final caiu. "
        "Os limiares das três cascatas são 0,70, 0,80 e 0,90.",
        styles["BodyTextDoc"],
    ))
    band_count = checks["confidence_count"] or 1
    bands = checks["confidence_bands"]
    band_rows = [_header(["Faixa de confiança", "Respostas", "Parcela"], styles["HeadCell"])]
    for label, band_key in [
        ("Abaixo de 0,70", "below_070"),
        ("De 0,70 a 0,79", "from_070_to_079"),
        ("De 0,80 a 0,89", "from_080_to_089"),
        ("De 0,90 a 0,99", "from_090_to_099"),
        ("1,00", "from_100"),
    ]:
        amount = bands[band_key]
        band_rows.append([label, str(amount), fmt_pct(amount / band_count)])
    story.append(_pdf_table(band_rows, [6 * cm, 4 * cm, 4 * cm], font, bold))
    story.append(Spacer(1, 8))
    story.append(_paragraph("Comparação das três cascatas", styles["Section"]))
    cascade_rows = [_header(
        ["Cascata", "Adequação", "Custo médio", "Chamadas", "Parou no pequeno", "Parou no médio", "Parou no grande"],
        styles["HeadCell"],
    )]
    for key in CASCADE_THRESHOLDS:
        item = strategies[key]
        share = checks["cascades"][key]
        cascade_rows.append([
            Paragraph(_esc(NAMES[key]), styles["Cell"]),
            Paragraph(_esc(fmt_pct(item["adequacy"])), styles["Cell"]),
            Paragraph(_esc(fmt_usd(item["mean_cost"])), styles["Cell"]),
            Paragraph(_esc(fmt_num(item["mean_calls"], 2)), styles["Cell"]),
            Paragraph(_esc(fmt_pct(share.get("small", 0))), styles["Cell"]),
            Paragraph(_esc(fmt_pct(share.get("medium", 0))), styles["Cell"]),
            Paragraph(_esc(fmt_pct(share.get("large", 0))), styles["Cell"]),
        ])
    story.append(_pdf_table(
        cascade_rows,
        [2.6 * cm, 2.2 * cm, 2.4 * cm, 2.2 * cm, 2.6 * cm, 2.4 * cm, 2.6 * cm],
        font,
        bold,
    ))
    story.append(Spacer(1, 8))

    story.append(PageBreak())
    story.append(_paragraph("4. Adequação por complexidade", styles["Section"]))
    rows = [_header(["Estratégia", "Baixa", "Média", "Alta"], styles["HeadCell"])]
    for key in ORDER:
        item = result["by_level"][key]
        rows.append([
            NAMES[key],
            fmt_pct(item["low"]["adequacy"]),
            fmt_pct(item["medium"]["adequacy"]),
            fmt_pct(item["high"]["adequacy"]),
        ])
    story.append(_pdf_table(rows, [6 * cm, 3.6 * cm, 3.6 * cm, 3.6 * cm], font, bold))
    story.append(Spacer(1, 8))

    story.append(_paragraph("5. Custo médio por complexidade", styles["Section"]))
    rows = [_header(["Estratégia", "Baixa", "Média", "Alta"], styles["HeadCell"])]
    for key in ORDER:
        item = result["by_level"][key]
        rows.append([
            NAMES[key],
            fmt_usd(item["low"]["mean_cost"]),
            fmt_usd(item["medium"]["mean_cost"]),
            fmt_usd(item["high"]["mean_cost"]),
        ])
    story.append(_pdf_table(rows, [6 * cm, 3.6 * cm, 3.6 * cm, 3.6 * cm], font, bold))
    story.append(Spacer(1, 8))

    story.append(_paragraph("6. Picos de latência", styles["Section"]))
    rows = [_header(
        ["Estratégia", "Execuções", "Picos", "%", "Tempo sem pico", "Tempo com pico"],
        styles["HeadCell"],
    )]
    for key in ORDER:
        item = strategies[key]
        rows.append([
            NAMES[key],
            str(item["count"]),
            str(item["outlier_count"]),
            fmt_pct(item["outlier_rate"]),
            fmt_ms(item["mean_latency"]),
            fmt_ms(item["mean_latency_with_spikes"]),
        ])
    story.append(_pdf_table(rows, [4.2 * cm, 2.4 * cm, 2 * cm, 2 * cm, 3.4 * cm, 3.4 * cm], font, bold))
    story.append(Spacer(1, 8))

    compression = result["compression"]
    example = result["example"]
    story.append(_paragraph("7. Compressão dos prompts", styles["Section"]))
    story.append(_paragraph(
        "Antes do envio, a compressão reduz palavras muito frequentes. "
        "Na estimativa local, a redução média foi "
        + fmt_pct(compression["overall"]["reduction"])
        + ". O exemplo "
        + example["code"]
        + " passou de "
        + str(example["tokens_before"])
        + " para "
        + str(example["tokens_after"])
        + " tokens estimados. O custo do experimento usa a contagem da API.",
        styles["BodyTextDoc"],
    ))
    story.append(_paragraph("Prompt comprimido de " + example["code"] + ": " + example["compressed"], styles["NoteDoc"]))

    story.append(_paragraph("8. Classificador", styles["Section"]))
    story.append(_paragraph(
        "O erro do classificador no roteamento, comparado com o nível definido na coleta, foi "
        + fmt_pct(checks["routing_error"])
        + ". Na compressão com roteamento, esse erro foi "
        + fmt_pct(checks["compression_routing_error"])
        + ". A linha CONFIANCA foi lida em "
        + fmt_pct(checks["confidence_parsed_rate"])
        + " das execuções. O avaliador custou "
        + fmt_usd(checks["judge_cost"])
        + " no total, fora da tabela de estratégias.",
        styles["BodyTextDoc"],
    ))
    route_rows = [_header(["Destino", "Roteamento"], styles["HeadCell"])]
    for profile in PROFILE_ORDER:
        route_rows.append([
            profiles[profile]["label"],
            fmt_pct(checks["routing_by_profile"].get(profile, 0)),
        ])
    story.append(_pdf_table(route_rows, [8 * cm, 6 * cm], font, bold))
    story.append(Spacer(1, 10))

    story.append(PageBreak())
    story.append(_paragraph("9. Gráficos", styles["Section"]))
    for chart in charts:
        story.append(Image(str(chart), width=16.2 * cm, height=8.4 * cm))
        story.append(Spacer(1, 8))

    story.append(PageBreak())
    story.append(_paragraph("10. Interpretação", styles["Section"]))
    for sentence in result["reading"]:
        story.append(_paragraph(sentence, styles["BodyTextDoc"]))

    story.append(_paragraph("Precisão e limitações", styles["Section"]))
    story.append(_paragraph(
        "A incerteza da adequação está no erro padrão da tabela. Com poucas repetições, esse intervalo fica mais largo. "
        "A latência carrega a variação da rede. A tabela de picos mostra o efeito de tirar os atrasos extremos da média. "
        "O avaliador, a confiança declarada e o classificador são as três fontes de erro que mais pesam na leitura.",
        styles["BodyTextDoc"],
    ))
    for item in [
        "O avaliador pode discordar de um leitor humano. O critério de cada tarefa está no código, no CSV e no Anexo A.",
        "A confiança escrita pelo modelo pode vir alta mesmo quando a resposta está fraca.",
        "A compressão por palavras frequentes não é o compressor neural LLMLingua.",
        "A projeção mantém o mix desta amostra. Outro mix de produção muda o custo.",
        "Não há norma de laboratório nem certificado de calibração de instrumento físico para esta coleta.",
    ]:
        story.append(_paragraph("• " + item, styles["BodyTextDoc"]))

    _append_review_annex(story, result, styles)

    document = SimpleDocTemplate(
        str(path),
        pagesize=A4,
        leftMargin=1.7 * cm,
        rightMargin=1.7 * cm,
        topMargin=1.5 * cm,
        bottomMargin=1.4 * cm,
        title="Relatório do experimento — otimização do uso de IA",
        author="Experimento de TCC",
    )
    document.build(story, onFirstPage=_footer, onLaterPages=_footer)


def _append_review_annex(story, result, styles):
    inadequate = [record for record in result["records"] if not record["adequate"]]
    inadequate.sort(key=lambda item: (item["task_code"], ORDER.index(item["strategy"])))

    story.append(PageBreak())
    story.append(_paragraph("Anexo A — Registro para revisão humana", styles["Section"]))
    story.append(HRFlowable(width="100%", thickness=0.6, color=colors.HexColor("#1F4E79"), spaceBefore=2, spaceAfter=6))
    story.append(_paragraph(
        "Obrigatório para conferência dos julgamentos. Lista-se cada execução marcada como inadequada "
        "pelo avaliador automático: critério da tarefa, solicitação, trecho da resposta e motivo "
        "declarado pelo avaliador quando a resposta é INADEQUADA. "
        "O arquivo resultados/revisao_humana.csv contém o texto integral da resposta e colunas vazias "
        "humano_adequada (sim/não ou 1/0) e observacao_humana para registro de um revisor humano.",
        styles["BodyTextDoc"],
    ))

    if not inadequate:
        story.append(_paragraph("Nenhuma execução foi marcada como inadequada nesta rodada.", styles["BodyTextDoc"]))
        return

    story.append(_paragraph(
        "Total de registros inadequados nesta rodada: " + str(len(inadequate)) + ".",
        styles["NoteDoc"],
    ))

    for record in inadequate:
        title = (
            record["task_code"]
            + " — "
            + NAMES[record["strategy"]]
            + " ("
            + LEVEL_LABELS.get(record["true_complexity"], record["true_complexity"])
            + ")"
        )
        story.append(_paragraph(title, styles["AnnexCase"]))
        story.append(_paragraph(
            "Critério: " + record.get("task_criterion", ""),
            styles["AnnexBody"],
        ))
        story.append(_paragraph(
            "Solicitação: " + _trunc(record.get("task_prompt", ""), 500),
            styles["AnnexBody"],
        ))
        answer = record.get("answer", "")
        if not answer.strip():
            answer = "(resposta vazia)"
        story.append(_paragraph(
            "Resposta (trecho): " + _trunc(answer, 900),
            styles["AnnexBody"],
        ))
        story.append(_paragraph("Veredito do avaliador: INADEQUADA", styles["AnnexBody"]))
        motive = (record.get("judge_justification") or "").strip()
        if not motive:
            motive = (record.get("judge_raw") or "").strip() or "Motivo não registrado nesta execução."
        story.append(_paragraph(
            "Motivo: " + motive,
            styles["AnnexBody"],
        ))
        story.append(Spacer(1, 6))


def export_results(result):
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    CHART_DIR.mkdir(parents=True, exist_ok=True)
    executions_path, summary_path, review_path = _save_csv(result)
    charts = save_charts(result)
    pdf_path = OUTPUT_DIR / "relatorio_resultados.pdf"
    font, bold = _register_fonts()
    _build_pdf(result, charts, pdf_path, font, bold)
    return {
        "pdf": str(pdf_path),
        "executions": str(executions_path),
        "summary": str(summary_path),
        "human_review": str(review_path),
        "charts": [str(path) for path in charts],
    }
