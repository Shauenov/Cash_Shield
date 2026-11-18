"""Task runner (replaces `make` on Windows): python tasks.py <task> [args]

  data              generate scenario sets (tune seed 42, holdout seed 2026)
  test              unit tests with coverage of the engine
  eval [--set tune] metrics; default set is holdout (hash-checked, logged)
  tune              grid search on the TUNE set only
"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent
PY = sys.executable


def run(*args):
    sys.exit(subprocess.call([PY, *args], cwd=ROOT))


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return
    task, rest = sys.argv[1], sys.argv[2:]
    if task == "data":
        run("data/generate.py")
    elif task == "test":
        run("-m", "pytest", "engine/tests", "--cov=engine", "--cov-report=term-missing", *rest)
    elif task == "eval":
        run("eval/evaluate.py", *rest)
    elif task == "tune":
        run("eval/tune.py", *rest)
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
