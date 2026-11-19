# Clean-machine check (2026-11-19)

Method: `git clone` of the repository into an empty folder (only committed files), `cp .env.example .env`, then the README steps. Same Windows PC as development, Docker Desktop, Python 3.11, Node 22.

| Step | Result |
|---|---|
| Fresh clone: holdout SHA-256 equals the frozen one | **First attempt FAILED.** Windows `autocrlf` changed the line endings, so the hash differed and `python tasks.py eval` refused to run. Fixed with `.gitattributes` (`* text=auto eol=lf`), commit `5873bb7`. Second clone: hash identical |
| `docker compose build --no-cache` | OK, 196 s |
| `docker compose up -d` | OK, healthy in 9 s |
| `http://localhost:8080`, `/api/healthz` | 200; `rules_version: thresholds-frozen` |
| WebSocket through the nginx proxy | OK (a decision event arrives live) |
| `python tasks.py eval` inside the container | Same scorecard as the original holdout run (recall 78.3%, false interventions 4.2%) |
| `python tasks.py demo-check 10` inside the container | 10 of 10 |
| `python tasks.py bench` inside the container | p95 57 ms (database file in a volume); on the host in-process about 10 ms. Both far under 300 ms |
| No Docker: `python -m venv`, `pip install -r requirements-dev.txt` | OK, 138 s |
| `python tasks.py test` / `test-integration` | 46 / 16 passed, engine coverage 99% |
| `python tasks.py eval` (no Docker) | Same scorecard |
| `python tasks.py data` | Scenario files byte-identical to the committed ones |
| `npm install` and `npm run build` in `web/` | OK, 28 s and 2 s |
| API started from the clone without Docker | OK |

Side effects to expect: every `python tasks.py eval` on the holdout adds a line to `reports/holdout_runs.log` (by design), and `python tasks.py data` rewrites `data/HOLDOUT.sha256` with the same hash.

## What this does not prove

- It is the same machine and the same Windows user. Docker base images (`python:3.11-slim`, `node:22-slim`, `nginx:alpine`) were already pulled and pip/npm may have used local caches, so first-time download time on another PC will be longer.
- Not tested on Linux or macOS, on a PC without Docker Desktop, or on a different network (pip failed once earlier inside a container on a flaky connection; the Dockerfile now retries).
- The screens were not clicked through in the clean stack (the API, proxy and WebSocket were). Rehearse them by hand.
