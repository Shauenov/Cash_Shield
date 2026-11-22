"""Task runner (replaces `make` on Windows): python tasks.py <task> [args]

  data              generate scenario sets (tune seed 42, holdout seed 2026)
  test              unit tests with coverage of the engine
  eval [--set tune] metrics; default set is holdout (hash-checked, logged)
  tune              grid search on the TUNE set only
  bench             1000 authorize calls, p95 latency
  test-integration  API, decision lifecycle and metrics-parity tests
  demo-check [N]    automated API-level rehearsal of the demo (default 10 runs)
  redteam           scripted red team, writes reports/redteam.md
  usability         score the pause-screen usability test from reports/usability_data.csv
  redteam-blind     summarize the blind red team from reports/redteam_blind_data.csv
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
    elif task == "demo-check":
        run("eval/demo_check.py", *rest)
    elif task == "redteam-blind":
        run("eval/redteam_blind.py", *rest)
    elif task == "usability":
        run("eval/usability.py", *rest)
    elif task == "redteam":
        run("eval/redteam.py")
    elif task == "bench":
        run("eval/bench.py")
    elif task == "test-integration":
        run("-m", "pytest", "services/api", "eval/test_metrics_parity.py", "-q", "-W", "ignore", *rest)
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
