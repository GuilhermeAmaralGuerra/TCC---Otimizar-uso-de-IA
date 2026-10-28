"""Aggregate the measured calls, mark latency spikes and write the reading."""

import statistics

from service.strategies_service import CASCADE_THRESHOLDS, LEVELS, LEVEL_LABELS, NAMES, ORDER
from utils.formatting import fmt_ms, fmt_num, fmt_pct, fmt_pp, fmt_usd
from utils.text import compress_prompt, estimate_tokens


def _quartile(values, proportion):
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * proportion
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    weight = position - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


def _mean(values):
    if not values:
        return 0.0
    return sum(values) / len(values)


def mark_latency_outliers(records):
    groups = {}
    for record in records:
        groups.setdefault(record["strategy"], []).append(record)

    for group in groups.values():
        latencies = [record["latency_ms"] for record in group]
        q1 = _quartile(latencies, 0.25)
        q3 = _quartile(latencies, 0.75)
        iqr = q3 - q1
        lower_fence = q1 - 1.5 * iqr
        upper_fence = q3 + 1.5 * iqr
        for record in group:
            outside = record["latency_ms"] < lower_fence or record["latency_ms"] > upper_fence
            record["latency_outlier"] = 1 if outside else 0


def _proportion_se(proportion, count):
    if count <= 0:
        return 0.0
    return (proportion * (1 - proportion) / count) ** 0.5


def _share(records, field):
    if not records:
        return {}
    counts = {}
    for record in records:
        key = record[field]
        counts[key] = counts.get(key, 0) + 1
    shares = {}
    for key, amount in counts.items():
        shares[key] = amount / len(records)
    return shares


def _summarize_strategy(group, projection_requests):
    count = len(group)
    adequate_count = 0
    total_cost = 0.0
    calls = 0
    tokens = 0
    all_latencies = []
    clean_latencies = []

    for record in group:
        adequate_count += record["adequate"]
        total_cost += record["cost_usd"]
        calls += record["call_count"]
        tokens += record["input_tokens"] + record["output_tokens"]
        all_latencies.append(record["latency_ms"])
        if not record["latency_outlier"]:
            clean_latencies.append(record["latency_ms"])

    adequacy = adequate_count / count if count else 0.0
    mean_cost = total_cost / count if count else 0.0
    outlier_count = count - len(clean_latencies)

    if len(clean_latencies) > 1:
        deviation = statistics.stdev(clean_latencies)
        latency_se = deviation / (len(clean_latencies) ** 0.5)
        median_latency = statistics.median(clean_latencies)
    else:
        deviation = 0.0
        latency_se = 0.0
        median_latency = _mean(clean_latencies)

    if adequate_count:
        cost_per_adequate = total_cost / adequate_count
    else:
        cost_per_adequate = None

    return {
        "count": count,
        "outlier_count": outlier_count,
        "outlier_rate": outlier_count / count if count else 0.0,
        "adequacy": adequacy,
        "adequacy_se": _proportion_se(adequacy, count),
        "total_cost": total_cost,
        "mean_cost": mean_cost,
        "projection": mean_cost * projection_requests,
        "cost_per_adequate": cost_per_adequate,
        "mean_latency": _mean(clean_latencies),
        "latency_se": latency_se,
        "median_latency": median_latency,
        "latency_sd": deviation,
        "mean_latency_with_spikes": _mean(all_latencies),
        "mean_calls": calls / count if count else 0.0,
        "mean_tokens": tokens / count if count else 0.0,
        "final_profile_share": _share(group, "final_profile"),
    }


def _summarize_level(group, level):
    cell = []
    clean_latencies = []
    for record in group:
        if record["true_complexity"] != level:
            continue
        cell.append(record)
        if not record["latency_outlier"]:
            clean_latencies.append(record["latency_ms"])

    count = len(cell)
    adequate_count = 0
    cost = 0.0
    for record in cell:
        adequate_count += record["adequate"]
        cost += record["cost_usd"]

    return {
        "count": count,
        "adequacy": adequate_count / count if count else 0.0,
        "mean_cost": cost / count if count else 0.0,
        "mean_latency": _mean(clean_latencies),
    }


def _measure_compression(tasks):
    grouped = {level: [] for level in LEVELS}
    overall = []
    for task in tasks:
        before = estimate_tokens(task["prompt"])
        after = estimate_tokens(compress_prompt(task["prompt"]))
        item = {"before": before, "after": after, "reduction": 1 - (after / before)}
        overall.append(item)
        grouped[task["complexity"]].append(item)

    def summarize(items):
        return {
            "tokens_before": _mean([item["before"] for item in items]),
            "tokens_after": _mean([item["after"] for item in items]),
            "reduction": _mean([item["reduction"] for item in items]),
        }

    measured = {"overall": summarize(overall)}
    for level in LEVELS:
        measured[level] = summarize(grouped[level])
    return measured


def _classifier_error(records, strategy_name):
    selected = []
    errors = 0
    for record in records:
        if record["strategy"] != strategy_name:
            continue
        selected.append(record)
        if record["estimated_complexity"] != record["true_complexity"]:
            errors += 1
    if not selected:
        return 0.0
    return errors / len(selected)


def _interpret(strategies, by_level, compression, checks):
    large = strategies["always_large"]
    small = strategies["always_small"]
    medium = strategies["always_medium"]
    routing = strategies["routing"]
    combined = strategies["compression_routing"]
    lines = []

    lines.append(
        "O perfil grande alcançou adequação de "
        + fmt_pct(large["adequacy"])
        + " (erro padrão "
        + fmt_pct(large["adequacy_se"])
        + "), com custo médio de "
        + fmt_usd(large["mean_cost"])
        + " por solicitação e latência média de "
        + fmt_ms(large["mean_latency"])
        + " depois da exclusão dos picos."
    )
    lines.append(
        "O perfil pequeno ficou com adequação de "
        + fmt_pct(small["adequacy"])
        + " e custo médio de "
        + fmt_usd(small["mean_cost"])
        + ". O perfil médio ficou com adequação de "
        + fmt_pct(medium["adequacy"])
        + " e custo médio de "
        + fmt_usd(medium["mean_cost"])
        + "."
    )

    for level in LEVELS:
        gap = (by_level["always_large"][level]["adequacy"] - by_level["always_small"][level]["adequacy"]) * 100
        lines.append(
            "Nas tarefas de complexidade "
            + LEVEL_LABELS[level].lower()
            + ", a adequação foi "
            + fmt_pct(by_level["always_small"][level]["adequacy"])
            + " no perfil pequeno e "
            + fmt_pct(by_level["always_large"][level]["adequacy"])
            + " no perfil grande. A diferença foi de "
            + fmt_pp(gap)
        )

    low_gap = (by_level["always_large"]["low"]["adequacy"] - by_level["always_small"]["low"]["adequacy"]) * 100
    high_gap = (by_level["always_large"]["high"]["adequacy"] - by_level["always_small"]["high"]["adequacy"]) * 100
    if high_gap > low_gap:
        lines.append(
            "A diferença de adequação entre o perfil grande e o perfil pequeno "
            "é maior nas tarefas altas ("
            + fmt_pp(high_gap)
            + ") do que nas tarefas baixas ("
            + fmt_pp(low_gap)
            + "). O ganho do perfil grande se concentra nas tarefas mais difíceis."
        )

    if large["mean_cost"]:
        routing_savings = (1 - routing["mean_cost"] / large["mean_cost"]) * 100
    else:
        routing_savings = 0.0
    if routing["mean_cost"] < large["mean_cost"]:
        cost_sentence = "O roteamento ficou " + fmt_num(routing_savings, 1) + "% mais barato que o uso exclusivo do perfil grande"
    else:
        cost_sentence = "O roteamento ficou " + fmt_num(-routing_savings, 1) + "% mais caro que o uso exclusivo do perfil grande"
    lines.append(
        cost_sentence
        + ", com adequação de "
        + fmt_pct(routing["adequacy"])
        + ". A diferença de adequação em relação ao perfil grande foi de "
        + fmt_pp((large["adequacy"] - routing["adequacy"]) * 100)
        + " O erro do classificador, medido contra o nível atribuído na coleta, foi "
        + fmt_pct(checks["routing_error"])
        + "."
    )

    for key in CASCADE_THRESHOLDS:
        item = strategies[key]
        stopped_at_small = checks["cascades"][key].get("small", 0)
        lines.append(
            NAMES[key]
            + " usou em média "
            + fmt_num(item["mean_calls"], 2)
            + " chamadas por solicitação e parou no perfil pequeno em "
            + fmt_pct(stopped_at_small)
            + " dos casos. A adequação foi "
            + fmt_pct(item["adequacy"])
            + " e o custo médio foi "
            + fmt_usd(item["mean_cost"])
            + "."
        )
    lines.append(
        "As três cascatas usam a confiança que o próprio modelo escreveu na última linha. "
        "Os limiares são 0,70, 0,80 e 0,90. A confiança observada nesta rodada ficou entre "
        + fmt_num(checks["confidence_min"], 2)
        + " e "
        + fmt_num(checks["confidence_max"], 2)
        + "."
    )

    adequacy_drop = (routing["adequacy"] - combined["adequacy"]) * 100
    if routing["mean_cost"]:
        compression_savings = (1 - combined["mean_cost"] / routing["mean_cost"]) * 100
    else:
        compression_savings = 0.0
    lines.append(
        "A compressão reduziu em média "
        + fmt_pct(compression["overall"]["reduction"])
        + " dos tokens estimados na entrada, antes da contagem da API. "
        "Combinada ao roteamento, a adequação foi "
        + fmt_pct(combined["adequacy"])
        + " e o custo médio foi "
        + fmt_usd(combined["mean_cost"])
        + ". No roteamento sem compressão, a adequação foi "
        + fmt_pct(routing["adequacy"])
        + " e o custo médio foi "
        + fmt_usd(routing["mean_cost"])
        + ". A diferença foi de "
        + fmt_num(compression_savings, 1)
        + "% no custo e de "
        + fmt_pp(adequacy_drop)
        + " na adequação."
    )

    busiest = max(CASCADE_THRESHOLDS, key=lambda key: strategies[key]["mean_calls"])
    if strategies[busiest]["mean_calls"] > 1:
        lines.append(
            NAMES[busiest]
            + " foi a cascata com mais chamadas por solicitação ("
            + fmt_num(strategies[busiest]["mean_calls"], 2)
            + "), porque o limiar mais alto faz a resposta subir de perfil com mais frequência."
        )

    lines.append(
        "Em uma projeção de "
        + fmt_num(checks["projection_requests"], 0)
        + " solicitações, com o mesmo mix da amostra, o perfil grande custaria "
        + fmt_usd(large["projection"])
        + " e o roteamento custaria "
        + fmt_usd(routing["projection"])
        + ". O custo por resposta adequada foi "
        + fmt_usd(large["cost_per_adequate"] or 0)
        + " no perfil grande e "
        + fmt_usd(routing["cost_per_adequate"] or 0)
        + " no roteamento."
    )
    lines.append(
        "A adequação foi julgada por um modelo avaliador, com o critério escrito para cada tarefa. "
        "O custo desse avaliador ficou fora da comparação entre estratégias."
    )
    return lines


def analyze(records, tasks, meta):
    mark_latency_outliers(records)
    projection_requests = meta["projection_requests"]
    groups = {key: [] for key in ORDER}
    for record in records:
        groups[record["strategy"]].append(record)

    strategies = {}
    by_level = {}
    for key in ORDER:
        group = groups[key]
        summary = _summarize_strategy(group, projection_requests)
        summary["name"] = NAMES[key]
        strategies[key] = summary
        by_level[key] = {}
        for level in LEVELS:
            by_level[key][level] = _summarize_level(group, level)

    judge_cost = 0.0
    parsed = 0
    confidences = []
    for record in records:
        judge_cost += record["judge_cost_usd"]
        parsed += record["confidence_parsed"]
        confidences.append(record["confidence"])

    bands = {"below_070": 0, "from_070_to_079": 0, "from_080_to_089": 0, "from_090_to_099": 0, "from_100": 0}
    for value in confidences:
        if value < 0.70:
            bands["below_070"] += 1
        elif value < 0.80:
            bands["from_070_to_079"] += 1
        elif value < 0.90:
            bands["from_080_to_089"] += 1
        elif value <= 0.99:
            bands["from_090_to_099"] += 1
        else:
            bands["from_100"] += 1

    checks = {
        "routing_error": _classifier_error(records, "routing"),
        "compression_routing_error": _classifier_error(records, "compression_routing"),
        "cascades": {key: strategies[key]["final_profile_share"] for key in CASCADE_THRESHOLDS},
        "routing_by_profile": strategies["routing"]["final_profile_share"],
        "projection_requests": projection_requests,
        "judge_cost": judge_cost,
        "confidence_parsed_rate": parsed / len(records) if records else 0.0,
        "confidence_min": min(confidences) if confidences else 0.0,
        "confidence_max": max(confidences) if confidences else 0.0,
        "confidence_bands": bands,
        "confidence_count": len(confidences),
    }
    example = tasks[0]
    compression = _measure_compression(tasks)

    result = {
        "meta": meta,
        "strategies": strategies,
        "by_level": by_level,
        "compression": compression,
        "checks": checks,
        "records": records,
        "example": {
            "code": example["code"],
            "original": example["prompt"],
            "compressed": compress_prompt(example["prompt"]),
            "tokens_before": estimate_tokens(example["prompt"]),
            "tokens_after": estimate_tokens(compress_prompt(example["prompt"])),
        },
    }
    result["reading"] = _interpret(strategies, by_level, compression, checks)
    return result
