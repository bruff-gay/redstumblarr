#!/usr/bin/env python3
"""
Fast subreddit enumerator (stubbed metadata).

Usage:
    python scrape_subs.py --depth 4000 --threads 80 --out subs.json
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
HEADERS = {"User-Agent": "Subreddit-enumerator/0.3"}

JOB_QUEUE = queue.Queue()
RESULTS: Dict[str, Dict[str, object]] = {}          # no lock needed – single writer
SUB_STUB = {"subscribers": 10_000, "nsfw": False}   # <- stubbed values


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


# ---------- Crawl /r/all ------------------------------------------------------
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


# ---------- Worker ------------------------------------------------------------
def worker():
    while True:
        sub = JOB_QUEUE.get()
        RESULTS[sub] = {"name": sub, **SUB_STUB}
        JOB_QUEUE.task_done()


# ---------- Main --------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(description="Enumerate subreddits from /r/all")
    parser.add_argument("--depth", type=int, default=4000)
    parser.add_argument("--threads", type=int, default=80)
    parser.add_argument("--batch", type=int, default=100)
    parser.add_argument("--out", type=str, default="subs.json")
    args = parser.parse_args()

    print("[1] Crawling /r/all ...")
    names = crawl_all(args.depth, min(args.batch, 100))
    print(f"   Found {len(names)} unique subs")

    for _ in range(args.threads):
        threading.Thread(target=worker, daemon=True).start()

    print("[2] Assembling stub metadata ...")
    JOB_QUEUE.join()

    out = list(RESULTS.values())
    with open(args.out, "w") as f:
        json.dump(out, f, indent=2)
    print(f"[DONE] {len(out)} subs saved to {args.out}")


if __name__ == "__main__":
    main()
