"""Latency benchmark (metric 9): 1000 authorize calls through the real API app.
Reports p50/p95/p99 of the host's end-to-end response time. Runs in-process
(no network), so it measures engine + host + SQLite, not the network."""
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient  # noqa: E402
from services.api import main  # noqa: E402


def main_():
    main.DEMO_MODE = True
    c = TestClient(main.app, headers={"X-Service-Token": main.SERVICE_TOKEN})
    c.post("/v1/demo-reset")
    times = []
    for i in range(1000):
        cid = ["c_marat", "c_gulnar", "c_dana", "c_aigerim"][i % 4]
        body = dict(operation_id=f"b{i}", customer_id=cid, channel="atm", type="cash_withdrawal",
                    amount_kzt=1000)
        t0 = time.perf_counter()
        r = c.post("/mock-host/authorize", json=body)
        times.append((time.perf_counter() - t0) * 1000)
        assert r.status_code == 200
    times.sort()
    q = lambda p: times[int(p * len(times)) - 1]
    print(f"n=1000  mean={statistics.mean(times):.1f} ms  p50={q(.50):.1f}  p95={q(.95):.1f}  p99={q(.99):.1f} ms")
    print("target p95 <= 300 ms, minimum <= 500 ms:", "PASS" if q(.95) <= 300 else "FAIL")


if __name__ == "__main__":
    main_()
