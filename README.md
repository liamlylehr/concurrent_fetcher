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

| Version | Topic                            | Status |
| ------- | -------------------------------- | ------ |
| 0.1     | Sequential fetcher               | ☐      |
| 0.2     | Async fetcher + benchmark        | ☐      |
| 0.3     | Bounded concurrency              | ☐      |
| 0.4     | Producer / consumer queue        | ☐      |
| 0.5     | Timeouts                         | ☐      |
| 0.6     | Retries with backoff + jitter    | ☐      |
| 0.7     | Cancellation + graceful shutdown | ☐      |
| 0.8     | Metrics                          | ☐      |

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
- [ ] Design decisions are documented (below; v0.1 done)

> Most importantly: be able to explain **why every mechanism exists**.

---

## Design Notes

_Add a short note per version: what changed, why the mechanism exists, and what was measured._

### v0.1 — Sequential Fetcher

#### How it works

```text
main(argv)
 ├─ guard: no file argument → usage on stderr, exit 2
 ├─ read_urls(path)        strip lines, drop blanks (missing file → stderr, exit 1)
 ├─ start wall-clock timer
 ├─ fetch_all(urls)        for each URL, in order:
 │    └─ fetch_url(url)      timer → httpx.get(timeout=5) → status or error → FetchResult
 ├─ stop wall-clock timer
 ├─ summarize_results()    count succeeded / failed (returns numbers, prints nothing)
 └─ print_results()        one line per result, then the summary
```

`fetch_url` structure: start the timer, put **only** the risky call in `try`, have `except`
and `else` set the **same** variables (`status`, `error`), then stop the timer and build one
`FetchResult` after the `try`, so both paths are timed and both return a result.

#### Checkpoint answers

1. **What blocks during a request?** The whole thread, not just the call. Inside httpx the
   thread makes a socket read system call, and the OS parks it until bytes arrive. With one
   thread, nothing else in the program can run.
2. **What is the process doing while it waits?** Nothing: about 0% CPU. A parked thread isn't
   scheduled. Check with `time uv run python -m fetcher.fetch urls.txt`: `real` is much
   larger than `user + sys`.
3. **Why does a sequential run take ≈ the sum of request times?** Request N can't start until
   request N−1 returns. Measured: per-request durations summed to 3261.48 ms against a
   3.2615 s wall-clock total, so the overhead between calls was about 0.04 ms.
4. **CPU-bound or I/O-bound?** I/O-bound. Test: a CPU twice as fast changes almost nothing;
   a network twice as fast halves the runtime.
5. **Why could concurrency help?** The waiting can overlap. Each request takes just as long,
   but total wall-clock time drops from about the sum of request times to about the slowest
   one (limited by how many requests can run at once, which is v0.3).
6. **Failure modes before concurrency:** DNS failure, connection refused, TLS errors,
   timeouts, malformed URLs, 4xx/5xx responses, redirects, slow DNS, servers that trickle
   bytes, huge responses, missing input file, rate limiting (429).

#### Concepts to remember

| Concept                          | Key point                                                                                                                                                                                                      |
| -------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Blocking I/O                     | A blocking call doesn't return control to your code until it's done, so a single-threaded program does one thing at a time                                                                                     |
| Clocks                           | `perf_counter()` for durations (never goes backwards); `time()` for timestamps (can jump); `process_time()` counts CPU time only, so it's wrong for network waits                                              |
| Wall-clock vs. summed time       | Total time must be measured around the whole run. Summing request durations hides any concurrency speedup in v0.2                                                                                              |
| `try / except / else`            | Keep `try` minimal. `else` runs only on success. Each branch must set the names used afterwards (otherwise you get `UnboundLocalError`)                                                                        |
| Catch narrowly                   | Catch `httpx.RequestError`, not `Exception`: expected failures become data, bugs still crash loudly                                                                                                            |
| Exception text                   | `f"{type(err).__name__}: {err}"` stays useful even when the message is empty                                                                                                                                   |
| `__main__` and `-m`              | Code under `if __name__ == "__main__":` runs only when executed, not on import (e.g. by tests)                                                                                                                 |
| CLI conventions                  | `argv[0]` is the program itself. Usage and errors go to stderr. Exit 0 = success, 1 = runtime failure, 2 = usage error. `sys.exit(main(argv))` passes the code to the shell                                    |
| Separate computing from printing | Functions that return values (`summarize_results`) are easy to test; printing goes in one place                                                                                                                |
| Hidden globals                   | A function that reads module-level names it wasn't given works by accident and breaks on import. Pass everything in as parameters                                                                              |
| f-string format specs            | `{x:<40}` left-align, `{x:>6.0f}` right-align with 0 decimals (rounds). Width is a minimum. A spec on `None` raises `TypeError`                                                                                |
| Imports and `sys.path`           | `python -m` adds the current directory, pytest doesn't. `[tool.pytest.ini_options] pythonpath = ["."]` fixes test imports                                                                                      |
| `monkeypatch`                    | Modules are imported once and shared, so `setattr(httpx, "get", fake)` is visible to `fetch.py`. Patch where the name is **looked up**: `from httpx import get` would need `fetcher.fetch.get` patched instead |
| Test design                      | Fake the network so tests are fast and deterministic. `parametrize` covers many cases in one test. `pytest.raises` proves bugs aren't swallowed                                                                |
| Two loops vs. one                | A second pass over in-memory results costs microseconds against seconds of I/O. At scale the real problem is holding everything in a list, so stream results instead (v0.4/v0.8)                               |

#### Design decisions

- **4xx/5xx count as success:** the request completed and the server answered, so it has a
  status code and its latency is real. `[ERR]` means no response at all. Pinned by
  `test_http_error_status_is_not_a_failure`.
- **Catch `httpx.RequestError`:** covers DNS, connect, timeout and protocol errors; anything
  else is a bug and should propagate. Pinned by `test_non_request_errors_are_not_swallowed`.
- **Explicit `DEFAULT_TIMEOUT = 5`:** makes httpx's default visible; becomes `--timeout`
  in v0.5.
- **Blank and whitespace-only lines are skipped** when reading the file, so they don't count
  as failed requests.
- **Exit codes:** 0 = ran (even if some URLs failed), 1 = input file unreadable,
  2 = usage error.
- **Tests never touch the network:** `httpx.get` is replaced with fakes via `monkeypatch`.

#### Known limitations (revisit later)

- **The timeout isn't a total timeout.** httpx's `timeout=5` applies per phase, and DNS lookup
  isn't covered. One run saw `example.com` take **107 s**. → v0.5
- **A server that sends a byte every 4 s** never trips the read timeout. → v0.5
- **Redirects aren't followed** (httpx default), so a redirecting URL shows `[301]` and counts
  as success.
- **`httpx.InvalidURL`** isn't a `RequestError`, so a badly malformed URL can still crash
  the run.
- **The whole response body is read into memory**, and all results are held in a list
  until the end.

#### Mistakes I made (and the lesson)

| Mistake                                          | Lesson                                                                        |
| ------------------------------------------------ | ----------------------------------------------------------------------------- |
| Ran the module, got no output                    | Defining functions doesn't run them; you need a `__main__` block              |
| `except ValueError` copied from an example       | Read the traceback bottom-up and catch what _your_ call raises                |
| `resp` / `status` unassigned on the failure path | Both `except` and `else` must set every name used after the `try`             |
| Dropped `* 1000`, so durations were in seconds   | Variable names (`_ms`) are a contract; check units                            |
| Timed the print loop, then reset the total to 0  | Put the timer tightly around the work, and don't reuse names                  |
| Summed durations for the total                   | Wall-clock time is measured, not calculated                                   |
| `print_results` used globals                     | Pass everything a function needs as parameters                                |
| `len(argv) < 1` guard                            | `argv[0]` is always the program name                                          |
| `[tool.pytest.ini.options]`                      | Read config warnings: `Unknown config option` means the section name is wrong |

#### Self-review questions

- Why would the async version report no speedup if the total were the sum of request times?
- What happens if `fetch_url`'s `except` catches `Exception` and you mistype an attribute name?
- Why does patching `httpx.get` affect `fetch.py`, and when would it not?
- Why is `real` ≫ `user + sys` in `time` output evidence of an I/O-bound workload?
- Why does a 5 s timeout not guarantee a request finishes within 5 s?
