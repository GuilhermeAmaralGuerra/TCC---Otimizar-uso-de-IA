"""Experiment settings loaded from the .env file."""

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = ROOT / ".env"

load_dotenv(ENV_PATH)

PRICE_SOURCE = "https://developers.openai.com/api/docs/pricing"
PRICE_DATE = "28/10/2026"


def _text(name):
    return os.getenv(name, "").strip()


def _required(name):
    value = _text(name)
    if not value:
        raise SystemExit(
            "Preencha " + name + " no arquivo .env. O modelo dos campos está em .env.template."
        )
    return value


def _number(name):
    raw = _required(name).replace(",", ".")
    return float(raw)


def load_settings():
    api_key = _text("OPENAI_API_KEY")
    if not api_key:
        raise SystemExit(
            "Preencha OPENAI_API_KEY no arquivo .env. Use .env.template como modelo."
        )

    profiles = {
        "small": {
            "label": "Perfil pequeno",
            "model": _required("OPENAI_MODEL_SMALL"),
            "input_price": _number("PRICE_SMALL_INPUT_PER_1M"),
            "output_price": _number("PRICE_SMALL_OUTPUT_PER_1M"),
        },
        "medium": {
            "label": "Perfil médio",
            "model": _required("OPENAI_MODEL_MEDIUM"),
            "input_price": _number("PRICE_MEDIUM_INPUT_PER_1M"),
            "output_price": _number("PRICE_MEDIUM_OUTPUT_PER_1M"),
        },
        "large": {
            "label": "Perfil grande",
            "model": _required("OPENAI_MODEL_LARGE"),
            "input_price": _number("PRICE_LARGE_INPUT_PER_1M"),
            "output_price": _number("PRICE_LARGE_OUTPUT_PER_1M"),
        },
        "judge": {
            "label": "Avaliador",
            "model": _required("OPENAI_MODEL_JUDGE"),
            "input_price": _number("PRICE_JUDGE_INPUT_PER_1M"),
            "output_price": _number("PRICE_JUDGE_OUTPUT_PER_1M"),
        },
    }

    return {
        "api_key": api_key,
        "profiles": profiles,
        "repetitions": int(_number("EXPERIMENT_REPETITIONS")),
        "seed": int(_number("EXPERIMENT_SEED")),
        "projection_requests": int(_number("PROJECTION_REQUESTS")),
    }
