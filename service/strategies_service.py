"""Strategies compared in the experiment. Each one calls the API."""

from prompts.instructions import ANSWER_SYSTEM, CLASSIFIER_SYSTEM
from service.llm_service import call_model, parse_complexity, split_answer
from utils.text import compress_prompt

CASCADE_THRESHOLDS = {
    "cascade_070": 0.70,
    "cascade_080": 0.80,
    "cascade_090": 0.90,
}

ORDER = [
    "always_small",
    "always_medium",
    "always_large",
    "routing",
    "cascade_070",
    "cascade_080",
    "cascade_090",
    "compression_routing",
]

NAMES = {
    "always_small": "Sempre pequeno",
    "always_medium": "Sempre médio",
    "always_large": "Sempre grande",
    "routing": "Roteamento",
    "cascade_070": "Cascata 0,70",
    "cascade_080": "Cascata 0,80",
    "cascade_090": "Cascata 0,90",
    "compression_routing": "Compressão + roteamento",
}

SHORT_NAMES = {
    "always_small": "Pequeno",
    "always_medium": "Médio",
    "always_large": "Grande",
    "routing": "Roteamento",
    "cascade_070": "Casc. 0,70",
    "cascade_080": "Casc. 0,80",
    "cascade_090": "Casc. 0,90",
    "compression_routing": "Comp.+rota",
}

DESCRIPTIONS = {
    "always_small": "Todas as solicitações vão para o perfil pequeno.",
    "always_medium": "Todas as solicitações vão para o perfil médio.",
    "always_large": "Todas as solicitações vão para o perfil grande.",
    "routing": "O perfil pequeno classifica a complexidade e a solicitação vai ao perfil correspondente.",
    "cascade_070": "Começa no pequeno e sobe se a confiança ficar abaixo de 0,70.",
    "cascade_080": "Começa no pequeno e sobe se a confiança ficar abaixo de 0,80.",
    "cascade_090": "Começa no pequeno e sobe se a confiança ficar abaixo de 0,90.",
    "compression_routing": "O prompt é comprimido, classificado e então roteado.",
}

LEVELS = ["low", "medium", "high"]
LEVEL_LABELS = {"low": "Baixa", "medium": "Média", "high": "Alta"}
ROUTE = {"low": "small", "medium": "medium", "high": "large"}


def _request_answer(profile, prompt):
    raw = call_model(profile, prompt, ANSWER_SYSTEM)
    answer, confidence, parsed = split_answer(raw["text"])
    raw["text"] = answer
    raw["confidence"] = confidence
    raw["confidence_parsed"] = parsed
    raw["role"] = "answer"
    return raw


def _request_classification(prompt):
    raw = call_model("small", prompt, CLASSIFIER_SYSTEM)
    raw["role"] = "classifier"
    raw["confidence"] = None
    raw["confidence_parsed"] = 0
    raw["estimated_complexity"] = parse_complexity(raw["text"])
    return raw


def _build_record(strategy_name, task, repetition, calls, estimated, used_compression):
    input_tokens = 0
    output_tokens = 0
    cost = 0.0
    latency = 0.0
    model_names = []
    final_answer = None

    for call in calls:
        input_tokens += call["input_tokens"]
        output_tokens += call["output_tokens"]
        cost += call["cost_usd"]
        latency += call["latency_ms"]
        model_names.append(call["model"])
        if call["role"] == "answer":
            final_answer = call

    return {
        "strategy": strategy_name,
        "task_code": task["code"],
        "true_complexity": task["complexity"],
        "estimated_complexity": estimated,
        "repetition": repetition,
        "final_profile": final_answer["profile"],
        "final_model": final_answer["model"],
        "models_used": " > ".join(model_names),
        "call_count": len(calls),
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cost_usd": cost,
        "latency_ms": latency,
        "answer": final_answer["text"],
        "confidence": final_answer["confidence"],
        "confidence_parsed": final_answer["confidence_parsed"],
        "used_compression": 1 if used_compression else 0,
        "cascade_threshold": CASCADE_THRESHOLDS.get(strategy_name, ""),
        "task_criterion": task["criterion"],
        "task_prompt": task["prompt"],
    }


def _run_fixed(strategy_name, profile, task, repetition):
    answer = _request_answer(profile, task["prompt"])
    return _build_record(strategy_name, task, repetition, [answer], task["complexity"], False)


def _run_routing(strategy_name, task, repetition, compress):
    prompt = task["prompt"]
    if compress:
        prompt = compress_prompt(prompt)
    classification = _request_classification(prompt)
    estimated = classification["estimated_complexity"]
    answer = _request_answer(ROUTE[estimated], prompt)
    return _build_record(
        strategy_name, task, repetition, [classification, answer], estimated, compress
    )


def _run_cascade(strategy_name, task, repetition):
    threshold = CASCADE_THRESHOLDS[strategy_name]
    calls = []
    for profile in ("small", "medium", "large"):
        answer = _request_answer(profile, task["prompt"])
        calls.append(answer)
        if answer["confidence"] >= threshold:
            break
    return _build_record(strategy_name, task, repetition, calls, task["complexity"], False)


def run_strategy(strategy_name, task, repetition):
    if strategy_name == "always_small":
        return _run_fixed(strategy_name, "small", task, repetition)
    if strategy_name == "always_medium":
        return _run_fixed(strategy_name, "medium", task, repetition)
    if strategy_name == "always_large":
        return _run_fixed(strategy_name, "large", task, repetition)
    if strategy_name == "routing":
        return _run_routing(strategy_name, task, repetition, False)
    if strategy_name in CASCADE_THRESHOLDS:
        return _run_cascade(strategy_name, task, repetition)
    if strategy_name == "compression_routing":
        return _run_routing(strategy_name, task, repetition, True)
    raise ValueError("Unknown strategy: " + strategy_name)
