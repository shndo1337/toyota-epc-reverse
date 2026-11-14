import argparse
import json
import statistics
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from time import perf_counter

CASES = {
    "number_prefix": "/api/v1/parts?q=04465&limit=25",
    "part_name": "/api/v1/parts?q=brake+pad&limit=25",
    "frame_lookup": "/api/v1/vehicles/resolve?identifier=ZVW30-5753000",
    "vin_lookup": "/api/v1/vin/MR054RU3008009000",
    "vehicle_parts": "/api/v1/parts?q=04465&vehicle=ZVW30-5753000",
    "full_diagram": "/api/v1/catalogs/EU:101510/diagrams/474512F.png",
    "accessories": "/api/v1/accessories?q=floor+mat&limit=25",
}
CONCURRENCY = 8
ROUNDS = 4


def percentile(samples: list[float], share: float) -> float:
    ordered = sorted(samples)
    return ordered[max(0, int(len(ordered) * share) - 1)]


def summary(samples: list[float]) -> dict[str, float]:
    return {
        "p50_ms": round(statistics.median(samples), 2),
        "p95_ms": round(percentile(samples, 0.95), 2),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Measure loopback HTTP latency of a running catalog.")
    parser.add_argument("--url", default="http://127.0.0.1:8000")
    parser.add_argument("--samples", type=int, default=20)
    parser.add_argument("--output", type=Path, default=Path("docs/benchmark.json"))
    args = parser.parse_args()

    def request(path: str) -> float:
        started = perf_counter()
        with urllib.request.urlopen(args.url + path, timeout=30) as response:
            response.read()
            if response.status != 200:
                raise RuntimeError(f"{path} returned {response.status}")
        return (perf_counter() - started) * 1000

    results: dict[str, dict[str, float]] = {}
    for name, path in CASES.items():
        first = request(path)
        results[name] = {"first_ms": round(first, 2), **summary([request(path) for _ in range(args.samples)])}

    mixed = list(CASES.values()) * ROUNDS
    started = perf_counter()
    with ThreadPoolExecutor(max_workers=CONCURRENCY) as pool:
        latencies = list(pool.map(request, mixed))
    results[f"concurrent_{CONCURRENCY}"] = {
        "requests": len(mixed),
        "seconds": round(perf_counter() - started, 3),
        **summary(latencies),
    }

    report = {
        "transport": "real HTTP on loopback",
        "warm_samples_per_case": args.samples,
        "note": "Local-machine measurements; OS cache was not cleared. Not an external load test.",
        "results": results,
    }
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
