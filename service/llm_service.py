"""Calls OpenAI models through LangChain and reads tokens, cost and latency."""

import re
import time

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from service.settings import load_settings

_clients = {}
_warned_missing_usage = False
_settings = None


def get_settings():
    global _settings
    if _settings is None:
        _settings = load_settings()
    return _settings


def _client(profile):
    settings = get_settings()
    model_name = settings["profiles"][profile]["model"]
    if model_name not in _clients:
        _clients[model_name] = ChatOpenAI(
            model=model_name,
            api_key=settings["api_key"],
            temperature=0,
            seed=settings["seed"],
            timeout=120,
            max_retries=2,
        )
    return _clients[model_name]


def _as_dict(value):
    if value is None:
        return {}
    if isinstance(value, dict):
        return value
    if hasattr(value, "items"):
        return dict(value)
    return {}


def _first_int(data, names):
    for name in names:
        if name in data and data[name] is not None:
            return int(data[name])
    return 0


def _read_usage(message):
    usage = _as_dict(getattr(message, "usage_metadata", None))
    input_tokens = _first_int(usage, ("input_tokens", "prompt_tokens"))
    output_tokens = _first_int(usage, ("output_tokens", "completion_tokens"))
    if input_tokens or output_tokens:
        return input_tokens, output_tokens

    metadata = _as_dict(getattr(message, "response_metadata", None))
    token_usage = _as_dict(metadata.get("token_usage") or metadata.get("usage"))
    input_tokens = _first_int(token_usage, ("prompt_tokens", "input_tokens"))
    output_tokens = _first_int(token_usage, ("completion_tokens", "output_tokens"))
    return input_tokens, output_tokens


def _message_text(message):
    content = message.content
    if isinstance(content, str):
        return content
    parts = []
    for block in content:
        if isinstance(block, str):
            parts.append(block)
        elif isinstance(block, dict):
            parts.append(str(block.get("text", "")))
    return "\n".join(parts)


def call_model(profile, user_prompt, system_prompt):
    """One real API call. Cost uses the token counts returned by the provider."""
    global _warned_missing_usage
    settings = get_settings()
    profile_data = settings["profiles"][profile]
    started = time.perf_counter()
    message = _client(profile).invoke([
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_prompt),
    ])
    latency_ms = (time.perf_counter() - started) * 1000

    input_tokens, output_tokens = _read_usage(message)
    if input_tokens == 0 and output_tokens == 0 and not _warned_missing_usage:
        print("Aviso: a API não devolveu a contagem de tokens. O custo dessa chamada ficou zerado.")
        _warned_missing_usage = True

    cost = (
        input_tokens * profile_data["input_price"]
        + output_tokens * profile_data["output_price"]
    ) / 1_000_000

    return {
        "profile": profile,
        "model": profile_data["model"],
        "text": _message_text(message).strip(),
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cost_usd": cost,
        "latency_ms": latency_ms,
    }


def split_answer(text):
    """Separate the answer from the CONFIANCA line the model was asked to write."""
    match = re.search(r"CONFIANCA:\s*([0-9]+(?:[.,][0-9]+)?)", text, re.IGNORECASE)
    if not match:
        return text.strip(), 0.0, 0
    value = float(match.group(1).replace(",", "."))
    value = max(0.0, min(1.0, value))
    kept = []
    for line in text.splitlines():
        if re.search(r"CONFIANCA:\s*[0-9]", line, re.IGNORECASE):
            continue
        kept.append(line)
    return "\n".join(kept).strip(), value, 1


def parse_adequate(text):
    return parse_judge_verdict(text)["adequate"]


def parse_judge_verdict(text):
    """Read ADEQUADA/INADEQUADA and optional MOTIVO line from the judge model."""
    raw = (text or "").strip()
    normalized = raw.upper()
    if "INADEQUADA" in normalized:
        adequate = 0
    elif "ADEQUADA" in normalized:
        adequate = 1
    else:
        adequate = 0

    justification = ""
    if adequate == 0:
        match = re.search(
            r"(?:MOTIVO|JUSTIFICATIVA)\s*:\s*(.+)",
            raw,
            re.IGNORECASE | re.DOTALL,
        )
        if match:
            justification = match.group(1).strip()
            justification = justification.splitlines()[0].strip()
        elif raw:
            lines = [line.strip() for line in raw.splitlines() if line.strip()]
            for line in lines:
                upper = line.upper()
                if upper.startswith("INADEQUADA"):
                    continue
                if upper.startswith("MOTIVO") or upper.startswith("JUSTIFICATIVA"):
                    continue
                justification = line
                break
            if not justification and lines:
                justification = lines[-1]

    return {"adequate": adequate, "justification": justification}


def parse_complexity(text):
    normalized = text.strip().lower()
    if "high" in normalized or "alta" in normalized:
        return "high"
    if "low" in normalized or "baixa" in normalized:
        return "low"
    if "medium" in normalized or "média" in normalized or "media" in normalized:
        return "medium"
    return "medium"
