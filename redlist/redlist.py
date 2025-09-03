#!/usr/bin/env python3
"""
Polite HTML crawler for SFW + NSFW subreddits
with live status & atomic ND-JSON append.
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

# Curated list — SFW & NSFW
AGGREGATORS: List[str] = [
    # SFW
    "AskReddit", "funny", "pics", "todayilearned", "science", "aww",
    "worldnews", "technology", "gaming", "movies", "books", "space",
    # NSFW
    "gonewild", "nsfw", "realgirls", "holdthemoan", "nsfw_gif", "porn",
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64; rv:125.0) "
        "Gecko/20100101 Firefox/125.0"
    )
}

JOB_QUEUE: queue.Queue = queue.Queue()
RESULTS: Dict[str, Dict[str, object]] = {}
SUB_STUB = {"subscribers": 10_000, "nsfw": False}
GOLD_TARGET = 100_000

# Rate-limit globals
LAST_CALL = 0.0
MIN_GAP = 6.0           # ~0.17 req/sec
STOP = False


def sigint(*_):
    global STOP
    STOP = True


signal.signal(signal.SIGINT, sigint)


# ---------- Networking ----------------------------------------------------------
def fetch(url: str) -> str:
    global LAST_CALL
    delay = MIN_GAP
    while not STOP:
        gap = max(0, delay - (time.time() - LAST_CALL))
        time.sleep(gap + random.uniform(0.1, 0.3))
        LAST_CALL = time.time()

        req = urllib.request.Request(url, headers=HEADERS)
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                return resp.read().decode("utf-8", errors="ignore")
        except urllib.error.HTTPError as e:
            if e.code == 429:
                sleep = min(int(e.headers.get("Retry-After", 60)), 600)
                print(f"[429] sleeping {sleep}s")
                time.sleep(sleep)
                delay = min(delay * 2, 600)
                continue
            elif e.code in {500, 502, 503, 504}:
                print("[5xx] sleeping 30s")
                time.sleep(30)
                continue
            raise
    sys.exit(0)


# ---------- Regex extractor ------------------------------------------------------
def extract_subs_from_html(html: str) -> Set[str]:
    pattern = re.compile(r'/r/([A-Za-z0-9_]{3,21})(?:/|")')
    return {s.lower() for s in pattern.findall(html)}


# ---------- Atomic append (ND-JSON) ----------------------------------------------
def atomic_append(new_subs: Set[str], outfile: str):
    with open(outfile, "a", encoding="utf-8") as f:
        for s in new_subs:
            stub = {"name": s, **SUB_STUB, "nsfw": s in {"gonewild", "nsfw", "realgirls", "nsfw_gif", "porn"}}
            f.write(json.dumps(stub, ensure_ascii=False) + "\n")


# ---------- Status printer -------------------------------------------------------
def status_printer(seen: Set[str]):
    while not STOP:
        print(f"[STATUS] {len(seen):,} unique subs collected …")
        time.sleep(5)


# ---------- Crawl ----------------------------------------------------------------
def crawl_all(depth: int, seen: Set[str], outfile: str) -> Set[str]:
    new_total: Set[str] = set()
    url_iter = itertools.cycle(AGGREGATORS)
    for page in range(1, depth + 1):
        if STOP:
            break
        sub = next(url_iter)
        url = f"https://www.reddit.com/r/{sub}/new/"
        html = fetch(url)
        fresh = extract_subs_from_html(html) - seen
        if fresh:
            atomic_append(fresh, outfile)
            new_total |= fresh
            seen |= fresh
        if len(seen) >= GOLD_TARGET:
            break
    return new_total


# ---------- Worker ---------------------------------------------------------------
def worker():
    while True:
        sub = JOB_QUEUE.get()
        stub = {"name": sub, **SUB_STUB, "nsfw": sub in {"gonewild", "nsfw", "realgirls", "nsfw_gif", "porn"}}
        RESULTS[sub] = stub
        JOB_QUEUE.task_done()


# ---------- Main -----------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(description="SFW+NSFW raw-HTML crawler")
    parser.add_argument("--gold", action="store_true", help="loop until 100k")
    parser.add_argument("--out", type=str, default="subs.json")
    args = parser.parse_args()

    outfile = args.out
    seen: Set[str] = set()

    # safely load existing ND-JSON file
    if os.path.isfile(outfile):
        with open(outfile, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        data = json.loads(line)
                        seen.add(data["name"])
                        RESULTS[data["name"]] = data
                    except json.JSONDecodeError:
                        continue  # skip malformed lines

    threading.Thread(target=status_printer, args=(seen,), daemon=True).start()

    if args.gold:
        while len(seen) < GOLD_TARGET and not STOP:
            crawl_all(4000, seen, outfile)
            time.sleep(300)
    else:
        crawl_all(4000, seen, outfile)

    total = len(seen)
    print(f"[FINISHED] {total:,} subs saved to {outfile}")


if __name__ == "__main__":
    main()
