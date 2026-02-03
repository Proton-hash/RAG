#!/usr/bin/env python3
"""Wait for Elasticsearch to be reachable, then exec the given command."""

import os
import sys
import time
import urllib.request
import urllib.error


def main() -> int:
    es_host = os.getenv("ES_HOST", "http://localhost:9200").rstrip("/")
    url = f"{es_host}/_cluster/health"
    max_wait = 30
    interval = 2
    elapsed = 0

    while elapsed < max_wait:
        try:
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=5) as resp:
                if 200 <= resp.status < 400:
                    break
        except (urllib.error.URLError, OSError):
            pass

        time.sleep(interval)
        elapsed += interval

    if elapsed >= max_wait:
        print("Elasticsearch not ready after 30s", file=sys.stderr)
        return 1

    time.sleep(5)

    args = sys.argv[1:]
    if not args:
        return 0
    os.execvp(args[0], args)
    return 1


if __name__ == "__main__":
    sys.exit(main())
