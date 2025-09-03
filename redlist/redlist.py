#!/usr/bin/env python3
"""
Gold-mode subreddit enumerator.
When --gold is used the script loops until subs.json contains ≥ 100 000 items.
"""
import argparse
import json
import os
import queue
import random
import sys
import threading
import time
import urllib.error
import urllib.request
from typing import Dict, Set

REDDIT_ALL_HOT = "https://www.reddit.com/r/all/hot.json?limit={}&after={}"
HEADERS = {"User-Agent": "Subreddit-enumerator/0.3"}

JOB_QUEUE: queue.Queue = queue.Queue()
RESULTS: Dict[str, Dict[str, object]] = {}
SUB_STUB = {"subscribers": 10_000, "nsfw": False}
GOLD_TARGET = 100_000


# ---------- Networking -------------------------------------------------------
def fetch(url: str) -> Dict:
    delay = 0.5
    while True:
        req = urllib.request.Request(url, headers=HEADERS)
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code in {429, 500, 502, 503, 504}:
                retry = int(e.headers.get("Retry-After", delay))
                time.sleep(retry + random.uniform(0, 0.5))
                delay = min(delay * 1.5, 15)
                continue
            raise


# ---------- Crawl /r/all ------------------------------------------------------
def crawl_all(depth: int, batch: int, seen: Set[str]) -> Set[str]:
    after = ""
    new: Set[str] = set()
    for page in range(1, depth + 1):
        data = fetch(REDDIT_ALL_HOT.format(batch, after))
        for child in data["data"]["children"]:
            sub = child["data"]["subreddit"].lower()
            if sub and sub not in seen:
                new.add(sub)
                seen.add(sub)
                JOB_QUEUE.put(sub)
        after = data["data"]["after"]
        if not after:
            break
    return new


# ---------- Worker -------------------------------------------------------------
def worker():
    while True:
        sub = JOB_QUEUE.get()
        RESULTS[sub] = {"name": sub, **SUB_STUB}
        JOB_QUEUE.task_done()


# ---------- Single pass --------------------------------------------------------
def run_once(args: argparse.Namespace, seen: Set[str]) -> int:
    new = crawl_all(args.depth, min(args.batch, 50), seen)
    if not new:
        return 0

    for _ in range(args.threads):
        threading.Thread(target=worker, daemon=True).start()

    JOB_QUEUE.join()

    out = list(RESULTS.values())
    tmp = f"{args.out}.tmp"
    with open(tmp, "w") as f:
        json.dump(out, f, indent=2)
    os.replace(tmp, args.out)

    return len(new)


# ---------- Main --------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(description="Gold-mode subreddit enumerator")
    parser.add_argument("--gold", action="store_true", help="loop until 100k")
    parser.add_argument("--depth", type=int, default=4000)
    parser.add_argument("--threads", type=int, default=40)
    parser.add_argument("--batch", type=int, default=50)
    parser.add_argument("--out", type=str, default="subs.json")
    args = parser.parse_args()

    outfile = args.out
    seen: Set[str] = set()
    if os.path.isfile(outfile):
        with open(outfile) as f:
            for r in json.load(f):
                seen.add(r["name"])
                RESULTS[r["name"]] = r

    if args.gold:
        while len(seen) < GOLD_TARGET:
            print(f"[GOLD] {len(seen):,} subs so far …")
            added = run_once(args, seen)
            if added == 0:
                print("[GOLD] nothing new returned, sleeping 60 s …")
                time.sleep(60)
    else:
        run_once(args, seen)

    total = len(seen)
    print(f"[DONE] {total:,} subs saved to {outfile}")


if __name__ == "__main__":
    main()
