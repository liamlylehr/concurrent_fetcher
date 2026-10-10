import time
import sys
import httpx
from dataclasses import dataclass

DEFAULT_TIMEOUT = 5 # Default timeout for httpx requests

@dataclass
class FetchResult:
    url: str
    status_code: int | None
    duration_ms: float
    error: str | None

def fetch_url(url: str) -> FetchResult:
    """
    Time call to passed in url and return result object with metrics
    """
    start = time.perf_counter()
    try:
        resp = httpx.get(url, timeout=DEFAULT_TIMEOUT) 
    except httpx.RequestError as err:
        status = None
        error = f"{type(err).__name__}: {err}"
    else:
        status = resp.status_code
        error = None

    elapsed_ms = (time.perf_counter() - start) * 1000
    res = FetchResult(url=url, status_code=status, duration_ms=elapsed_ms, error=error)
    return res

def fetch_all(urls: list[str]) -> list[FetchResult]:
    """
    Run fetch_url() on each url in passed in list and return list of the result objects
    """
    rv = []
    for url in urls:
        rv.append(fetch_url(url))
    return rv

def read_urls(file_path: str) -> list[str]:
    """ 
    This function takes a file path, reads the contents and returns a list of strings consisting of the file contents split by new line
    """
    with open(file_path) as file:
        # Return list of each line in input file stripped of whitespaces
        return [line.strip() for line in file.read().splitlines() if line.strip()]

def summarize_results(results: list[FetchResult]) -> tuple[int, int]:
    """
    Generate counts for the successful and failed httpx calls
    """
    success, failure = 0, 0
    for result in results:
        if result.error is None:
            success+=1
        else:
            failure+=1
    return success, failure

def print_results(results: list[FetchResult], success: int, fail: int, total_duration: float) -> None:
    """
    Print results for each fetch call with summary of all results
    """
    for result in results:
        status_label = "ERR" if result.status_code is None else result.status_code
        error_msg = "" if result.error is None else " " + result.error
        print(f"[{status_label}] {result.url:<40}{result.duration_ms:>6.0f} ms{error_msg}")

    print(f"\n{len(results)} requested")
    print(f"{success} succeeded")
    print(f"{fail} failed")

    print(f"\ntotal duration: {total_duration:.2f} s")

def main(argv: list[str]) -> int:
    # Check for file input argument then read the file and return split list of urls
    if len(argv) < 2:
        print("""usage: python -m fetcher.fetch URL_FILE
    URL_FILE    text file with one URL per line""", file=sys.stderr)
        return 2

    # Read all the urls from the text file passed in
    urls = read_urls(argv[1])

    # Time the total duration of fetching all urls using fetch_url()
    start = time.perf_counter()
    fetch_res = fetch_all(urls)
    total_duration = (time.perf_counter() - start)

    # Summarize the counts for successful and failed httpx calls in the fetched result list
    success, fail = summarize_results(fetch_res)

    # Print the results for the fetched result list
    print_results(fetch_res, success, fail, total_duration)
    return 0

if __name__ == "__main__":
    sys.exit(main(sys.argv))
