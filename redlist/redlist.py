#!/usr/bin/env python3
"""
Multi-threaded subreddit enumerator.

Usage:
    python scrape_subs.py --depth 500 --threads 50 --out subs.json
"""
import argparse
import json
import os
import queue
import threading
import time
import urllib.error
import urllib.request
from typing import Dict, Set

REDDIT_ALL_HOT = "https://www.reddit.com/r/all/hot.json?limit={}&after={}"
SUB_ABOUT      = "https://www.reddit.com/r/{}/about.json"
HEADERS = {"User-Agent": "Subreddit-enumerator/0.3"}

JOB_QUEUE = queue.Queue()
RESULTS_LOCK = threading.Lock()
RESULTS: Dict[str, Dict[str, object]] = {}
ERRORS = 0


# ---------- Networking -------------------------------------------------------
def fetch(url: str) -> Dict:
    req = urllib.request.Request(url, headers=HEADERS)
    while True:
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code == 429:
                retry = int(e.headers.get("Retry-After", 1))
                time.sleep(retry)
                continue
            raise


# ---------- Crawl /r/all --------------------------------------------------------
def crawl_all(depth: int, batch: int) -> Set[str]:
    seen: Set[str] = set()
    after = ""
    for page in range(1, depth + 1):
        data = fetch(REDDIT_ALL_HOT.format(batch, after))
        for child in data["data"]["children"]:
            sub = child["data"]["subreddit"].lower()
            if sub and sub not in seen:
                seen.add(sub)
                JOB_QUEUE.put(sub)
        after = data["data"]["after"]
        if not after:
            break
    return seen


# ---------- Worker -------------------------------------------------------------
def worker():
    global ERRORS
    while True:
        sub = JOB_QUEUE.get()
        try:
            data = fetch(SUB_ABOUT.format(sub))["data"]
            meta = {
                "name": sub,
                "nsfw": bool(data.get("over18", False)),
                "subscribers": int(data.get("subscribers", 0)),
            }
            with RESULTS_LOCK:
                RESULTS[sub] = meta
        except Exception:
            pass
        finally:
            JOB_QUEUE.task_done()


# ---------- Main --------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(description="Enumerate subreddits from /r/all")
    parser.add_argument("--depth", type=int, default=200, help="Pages to fetch")
    parser.add_argument("--threads", type=int, default=20, help="About fetchers")
    parser.add_argument("--batch", type=int, default=100, help="Posts per /r/all call")
    parser.add_argument("--out", type=str, default="subs.json", help="Output JSON")
    parser.add_argument("--resume", type=str, help="Resume from partial list")
    parser.add_argument("-q", "--quiet", action="store_true", help="Quiet mode")
    args = parser.parse_args()

    # Resume or fresh start
    existing: Set[str] = set()
    if args.resume and os.path.isfile(args.resume):
        with open(args.resume) as f:
            for r in json.load(f):
                RESULTS[r["name"]] = r
                existing.add(r["name"])

    # Phase 1: crawl /r/all
    if not args.quiet:
        print("[1] Crawling /r/all ...")
    names = crawl_all(args.depth, min(args.batch, 100))
    names |= existing  # union with resume list
    if not args.quiet:
        print(f"   Found {len(names)} unique subs")

    # Phase 2: fetch metadata in parallel
    for _ in range(args.threads):
        threading.Thread(target=worker, daemon=True).start()

    if not args.quiet:
        print("[2] Fetching subreddit metadata ...")
    JOB_QUEUE.join()

    # Save
    out = list(RESULTS.values())
    with open(args.out, "w") as f:
        json.dump(out, f, indent=2)
    if not args.quiet:
        print(f"[DONE] {len(out)} subs saved to {args.out}")


if __name__ == "__main__":
    main()
