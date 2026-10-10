# Concurrent Fetch Engine

A URL-fetching program that starts as a simple sequential application and evolves into a
concurrent, resilient worker system.

**Purpose:** build a practical understanding of Python execution, asynchronous I/O, queues,
concurrency limits, retries, cancellation, and backpressure.

---

## Setup

```bash
uv sync                                      # install dependencies into .venv
uv run python -m fetcher.fetch urls.txt      # run the CLI
uv run pytest -q                             # run tests
```

Add dependencies with `uv add <pkg>` (or `uv add --dev <pkg>` for test-only tools).

---

## Roadmap

| Version | Topic | Status |
|---|---|---|
| 0.1 | Sequential fetcher | ☐ |
| 0.2 | Async fetcher + benchmark | ☐ |
| 0.3 | Bounded concurrency | ☐ |
| 0.4 | Producer / consumer queue | ☐ |
| 0.5 | Timeouts | ☐ |
| 0.6 | Retries with backoff + jitter | ☐ |
| 0.7 | Cancellation + graceful shutdown | ☐ |
| 0.8 | Metrics | ☐ |

---

## v0.1 — Sequential Fetcher

**Input:** a text file with one URL per line.

```text
https://example.com
https://python.org
https://github.com
```

**Requirements**

- Process each URL **sequentially**: one request finishes before the next starts.
- **No asyncio yet.**
- For every request, capture the URL, HTTP status code, request duration, and error (if any).

**Interface**

```python
@dataclass
class FetchResult:
    url: str
    status_code: int | None
    duration_ms: float
    error: str | None

def fetch_url(url: str) -> FetchResult: ...
def fetch_all(urls: list[str]) -> list[FetchResult]: ...
```

**Expected CLI output**

```bash
uv run python -m fetcher.fetch urls.txt
```

```text
[200] https://example.com       183 ms
[200] https://python.org        312 ms
[ERR] https://invalid.test     5011 ms

3 requested
2 succeeded
1 failed

total duration: 5.51 s
```

**Tests (at least three)**

1. **Successful request:** status code is populated, error is `None`, duration ≥ 0.
2. **Failed request** (invalid/unreachable endpoint): status code is `None` (or otherwise
   represents failure), error contains useful information, the program does not crash.
3. **Ordering:** `fetch_all(["url-a", "url-b", "url-c"])` returns results in the same order.

**Questions to answer before moving on**

1. What blocks while the HTTP request is being performed?
2. What is the Python process doing while waiting for the remote server?
3. Why does fetching 20 URLs sequentially take roughly the sum of their individual response times?
4. Is this workload CPU-bound or I/O-bound?
5. Why might concurrency improve this workload?
6. What failure modes already exist before introducing concurrency?

---

## v0.2 — Async Fetcher

Rewrite the implementation using `asyncio`. The goal isn't just async code; it's to
**measure the difference**.

Run the same set of URLs through the sequential and async versions and capture:

- total execution time
- average request duration
- number of requests
- throughput

**Explain:** why does total wall-clock time change even though individual server response
times may not?

---

## v0.3 — Bounded Concurrency

Add a configurable concurrency limit (e.g. with `asyncio.Semaphore`). Never allow unlimited
requests in flight.

```bash
uv run python -m fetcher.fetch urls.txt --concurrency 10
```

**Answer**

- Why is unlimited concurrency dangerous?
- What resources can become exhausted?
- What happens with concurrency = 1?
- What happens with concurrency = 10,000?

---

## v0.4 — Producer / Consumer Queue

Move from one task per URL to a worker architecture. The number of workers controls
concurrency.

```text
URL Producer
     |
     v
asyncio.Queue
     |
+----+----+
|    |    |
v    v    v
W1   W2   W3
```

**Learn:** queues, worker lifecycle, producer/consumer systems, queue depth, task completion.

---

## v0.5 — Timeouts

Add configurable request timeouts. The program must never wait indefinitely for a server.

```bash
--timeout 5
```

**Understand:** connection timeout vs. read timeout vs. total timeout.

---

## v0.6 — Retries

Retry transient failures.

```bash
--retries 3
```

Implement:

- a maximum retry count
- exponential backoff
- jitter (the delays must include randomness)

```text
attempt 1 → ~100 ms delay
attempt 2 → ~200 ms delay
attempt 3 → ~400 ms delay
```

**Understand:** why jitter exists.

---

## v0.7 — Cancellation and Graceful Shutdown

Handle Ctrl+C cleanly:

1. Stop introducing new work.
2. Cancel or finish the appropriate active work.
3. Close HTTP client resources.
4. Preserve completed results.
5. Print partial statistics.
6. Exit cleanly.

**Understand:** cancellation propagation.

---

## v0.8 — Metrics

Report:

- requests attempted, successes, failures
- requests per second
- p50 / p95 / p99 latency
- queue depth
- active workers

At this point the project is a small load-processing system rather than a URL downloader.

---

## Definition of Done

- [ ] Sequential implementation works
- [ ] Async implementation works
- [ ] Concurrency can be bounded
- [ ] Work is processed through a queue
- [ ] Requests support timeouts
- [ ] Failures support controlled retries
- [ ] Ctrl+C shuts down cleanly
- [ ] Metrics are reported
- [ ] Tests cover major behavior
- [ ] Design decisions are documented (below)

> Most importantly: be able to explain **why every mechanism exists**.

---

## Design Notes

_Add a short note per version in your own words: what changed, why the mechanism exists, and
what you measured._
# concurrent_fetcher
