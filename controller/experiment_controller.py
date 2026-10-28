"""Run the strategies against the API, then analyze and export."""

from prompts.instructions import JUDGE_SYSTEM, judge_prompt
from prompts.tasks import load_tasks
from service.analysis_service import analyze
from service.llm_service import call_model, get_settings, parse_judge_verdict
from service.report_service import export_results
from service.strategies_service import CASCADE_THRESHOLDS, NAMES, ORDER, run_strategy
from utils.console import print_results


def _judge(task, answer):
    raw = call_model("judge", judge_prompt(task, answer), JUDGE_SYSTEM)
    verdict = parse_judge_verdict(raw["text"])
    return {
        "adequate": verdict["adequate"],
        "judge_raw": raw["text"],
        "judge_justification": verdict["justification"],
        "judge_cost_usd": raw["cost_usd"],
        "judge_latency_ms": raw["latency_ms"],
        "judge_input_tokens": raw["input_tokens"],
        "judge_output_tokens": raw["output_tokens"],
    }


def run_experiment():
    settings = get_settings()
    tasks = load_tasks()
    records = []
    total = len(ORDER) * len(tasks) * settings["repetitions"]
    done = 0

    print("Chamando os modelos pela API. Cada linha abaixo é uma solicitação real.")
    print("Para interromper, use Ctrl+C. O custo já feito não é desfeito.")
    print()

    for strategy_name in ORDER:
        for task in tasks:
            for repetition in range(1, settings["repetitions"] + 1):
                done += 1
                print(
                    "[" + str(done) + "/" + str(total) + "] "
                    + NAMES[strategy_name] + " — " + task["code"]
                )
                try:
                    record = run_strategy(strategy_name, task, repetition)
                    record.update(_judge(task, record["answer"]))
                except Exception as error:
                    raise RuntimeError(
                        "Falha em " + NAMES[strategy_name] + " / " + task["code"] + ": " + str(error)
                    ) from error
                records.append(record)

    meta = {
        "seed": settings["seed"],
        "repetitions": settings["repetitions"],
        "projection_requests": settings["projection_requests"],
        "task_count": len(tasks),
        "confidence_thresholds": list(CASCADE_THRESHOLDS.values()),
        "profiles": settings["profiles"],
    }
    result = analyze(records, tasks, meta)
    result["files"] = export_results(result)
    print_results(result)
    return result
