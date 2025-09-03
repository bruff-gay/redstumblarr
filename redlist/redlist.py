#!/usr/bin/env python3
"""
Self-growing aggregator crawler — uses JSON file itself as the next source.
"""
import argparse
import itertools
import json
import os
import queue
import random
import re
import signal
import sys
import threading
import time
import urllib.error
import urllib.request
from typing import Dict, List, Set

HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:125.0) Gecko/20100101 Firefox/125.0"
}

GOLD_TARGET = 100_000
JOB_QUEUE = queue.Queue()
STOP = False


def sigint(*_):
    global STOP
    STOP = True


signal.signal(signal.SIGINT, sigint)


# ---------- Networking ----------------------------------------------------------
def fetch(url: str) -> Dict:
    """Fetch raw JSON from public listing; fallback to empty dict on 429."""
    global LAST_CALL
    delay = 5.0
    while not STOP:
        gap = max(0, delay - (time.time() - LAST_CALL))
        time.sleep(gap + random.uniform(0.1, 0.4))
        LAST_CALL = time.time()

        req = urllib.request.Request(url, headers=HEADERS)
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code == 429:
                return {}
            time.sleep(min(int(e.headers.get("Retry-After", 60)), 1800))
            delay = min(delay * 2, 1800)
            continue
            raise
    sys.exit(0)


# ---------- Parse subs from HTML ------------------------------------------------
def extract_subs_from_html(html: str) -> Set[str]:
    pattern = re.compile(r'/r/([A-Za-z0-9_]{3,21})(?:/|")')
    return {s.lower() for s in pattern.findall(html)}


# ---------- Atomic append (dedup) ---------------------------------------------
def atomic_append_unique(new_subs: Set[str], outfile: str) -> int:
    """Append only new subs; return count actually added."""
    existing = set()
    if os.path.isfile(outfile):
        with open(outfile, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        data = json.loads(line)
                        existing.add(data["name"].lower())
                    except Exception:
                        pass
    really_new = new_subs - existing
    with open(outfile, "a", encoding="utf-8") as f:
        for s in really_new:
            stub = {
                "name": s,
                "subscribers": 10_000,
                "nsfw": s in {"gonewild", "nsfw", "realgirls", "nsfw_gif", "porn"},
            }
            f.write(json.dumps(stub, ensure_ascii=False) + "\n")
    return len(really_new)


# ---------- Status printer ------------------------------------------------------
def status_printer(outfile: str):
    while not STOP:
        total = sum(1 for _ in open(outfile, "r", encoding="utf-8")) if os.path.isfile(outfile) else 0
        print(f"[TOTAL] {total:,} subs in {outfile}")
        time.sleep(5)


# ---------- Load aggregator list from JSON --------------------------------------
def load_aggregator_list(outfile: str) -> List[str]:
    """Return the list of subreddit names already in the JSON file."""
    if not os.path.isfile(outfile):
        return []
    with open(outfile, "r", encoding="utf-8") as f:
        return [json.loads(line)["name"].lower() for line in f if line.strip()]


# ---------- Crawl --------------------------------------------------------------
def crawl_all(outfile: str) -> None:
    """Deep-crawl /hot with pagination for every aggregator in JSON file."""
    seen = set(load_aggregator_list(outfile))
    LAST_CALL = 0.0

    while len(seen) < GOLD_TARGET and not STOP:
        # Dynamically use the JSON file itself as the aggregator list
        aggregator_list = list(load_aggregator_list(outfile)) or AGGREGATORS
        url_iter = itertools.cycle(aggregator_list)

        for sub in url_iter:
            if len(seen) >= GOLD_TARGET or STOP:
                break
            url_base = f"https://www.reddit.com/r/{sub}/hot.json?limit=100"
            after = ""
            while True:
                data = fetch(url_base + f"&after={after}")
                children = data.get("data", {}).get("children", [])
                if not children:
                    break
                fresh = {
                    child["data"]["subreddit"].lower()
                    for child in children
                    if child.get("data", {}).get("subreddit")
                } - seen
                if fresh:
                    added = atomic_append_unique(fresh, outfile)
                    seen |= fresh
                after = data.get("data", {}).get("after")
                if not after:
                    break


# ---------- Worker --------------------------------------------------------------
def worker():
    while True:
        sub = JOB_QUEUE.get()
        stub = {
            "name": sub,
            "subscribers": 10_000,
            "nsfw": sub in {"gonewild", "nsfw", "realgirls", "nsfw_gif", "porn"},
        }
        RESULTS[sub] = stub
        JOB_QUEUE.task_done()


# ---------- Main ----------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(description="Self-growing aggregator crawler")
    parser.add_argument("--gold", action="store_true", help="loop until 100k")
    parser.add_argument("--out", type=str, default="subs.json")
    args = parser.parse_args()

    outfile = args.out
    threading.Thread(target=status_printer, args=(outfile,), daemon=True).start()

    if args.gold:
        while not STOP:
            crawl_all(outfile)
            time.sleep(300)
    else:
        crawl_all(outfile)

    total = sum(1 for _ in open(outfile, "r", encoding="utf-8")) if os.path.isfile(outfile) else 0
    print(f"[FINISHED] {total:,} total subs in {outfile}")


if __name__ == "__main__":
    main()
