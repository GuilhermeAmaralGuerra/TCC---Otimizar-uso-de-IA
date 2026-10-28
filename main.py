"""
TCC experiment: cost, model selection and performance.

Fill in .env (see .env.template), then run:

    venv\\Scripts\\python main.py

The run calls the OpenAI API through LangChain. Results are printed and saved in resultados/.
"""

import sys

from controller.experiment_controller import run_experiment


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    run_experiment()


if __name__ == "__main__":
    main()
