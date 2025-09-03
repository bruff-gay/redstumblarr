#!/usr/bin/env python3
"""
Fast, ultra-verbose, Selenium-free crawler
- Batched NSFW checks (single /about.json call per 50 subs)
- Asyncio + aiohttp for concurrent fetches
- Still live-flushes every JSON line
"""
import argparse
import asyncio
import aiohttp
import itertools
import json
import os
import random
import re
import signal
import sys
import threading
import time
from datetime import datetime
from typing import Set, List, Dict

HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:125.0) Gecko/20100101 Firefox/125.0"
}
GOLD_TARGET = 100_000
STOP = False
BATCH_NSFW = 50          # how many subs to check at once

# ---------- UTILS -----------------------------------------------------------
def log(msg: str, *args, **kwargs):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}", *args, **kwargs)

# ---------- CTRL-C ---------------------------------------------------------
def sigint(*_):
    global STOP
    log("SIGINT caught — shutting down gracefully...")
    STOP = True
signal.signal(signal.SIGINT, sigint)

# ---------- CONCURRENT NSFW CHECK ------------------------------------------
async def fetch_nsfw_batch(session: aiohttp.ClientSession, subs: List[str]) -> Dict[str, bool]:
    """
    Reddit /about.json accepts comma-separated subreddit names (50 max).
    Returns dict {sub_lower: bool}.
    """
    sr = ",".join(subs)
    url = f"https://www.reddit.com/api/info.json?sr_name={sr}"
    try:
        async with session.get(url, headers=HEADERS, timeout=15) as resp:
            data = await resp.json()
            return {item["data"]["name"].lower(): bool(item["data"]["over18"])
                    for item in data.get("data", {}).get("children", [])}
    except Exception as e:
        log("[NSFW_BATCH] ERROR:", e)
        return {s: False for s in subs}

# ---------- ASYNC NETWORK ---------------------------------------------------
async def fetch(session: aiohttp.ClientSession, url: str) -> str:
    while not STOP:
        delay = 5.0 + random.uniform(0.1, 0.4)
        await asyncio.sleep(delay)
        try:
            async with session.get(url, headers=HEADERS, timeout=15) as resp:
                return await resp.text()
        except Exception as e:
            log("[FETCH] ERROR -> retry in 10s", e)
            await asyncio.sleep(10)

# ---------- EXTRACTION ------------------------------------------------------
def extract_subs(html: str) -> Set[str]:
    subs = {s.lower() for s in re.findall(r'/r/([A-Za-z0-9_]{3,21})(?:/|")', html)}
    log(f"[EXTRACT] Found {len(subs)} unique subreddits")
    return subs

# ---------- LOAD EXISTING ---------------------------------------------------
def load_existing(outfile: str) -> Set[str]:
    if not os.path.isfile(outfile):
        return set()
    subs = set()
    with open(outfile, "r", encoding="utf-8") as f:
        for line in f:
            try:
                subs.add(json.loads(line)["name"].lower())
            except Exception:
                pass
    log(f"[LOAD_EXISTING] Loaded {len(subs)} subreddit names")
    return subs

# ---------- APPEND NEW ------------------------------------------------------
async def append_new(session: aiohttp.ClientSession, new_subs: Set[str], outfile: str) -> int:
    existing = load_existing(outfile)
    really_new = list(new_subs - existing)
    if not really_new:
        return 0

    # batch NSFW checks
    nsfw_map = {}
    for i in range(0, len(really_new), BATCH_NSFW):
        chunk = really_new[i:i+BATCH_NSFW]
        nsfw_map.update(await fetch_nsfw_batch(session, chunk))

    with open(outfile, "a", encoding="utf-8") as f:
        for s in really_new:
            nsfw = nsfw_map.get(s, False)
            stub = {"name": s, "subscribers": 10_000, "nsfw": nsfw, "verified_nsfw": nsfw}
            f.write(json.dumps(stub, ensure_ascii=False) + "\n")
            f.flush()
            os.fsync(f.fileno())
            log(f"[APPEND_NEW] Flushed /r/{s}  NSFW={nsfw}")
    log(f"[APPEND_NEW] {len(really_new)} lines written")
    return len(really_new)

# ---------- STATUS PRINTER -------------------------------------------------
def printer(outfile: str):
    while not STOP:
        total = sum(1 for _ in open(outfile, "r", encoding="utf-8")) if os.path.isfile(outfile) else 0
        log(f"[STATUS] {total:,} subreddits in {outfile}")
        time.sleep(5)

# ---------- CRAWL ----------------------------------------------------------
async def crawl(outfile: str) -> None:
    AGGREGATORS = [
        "AskReddit", "funny", "pics", "todayilearned", "science", "aww",
        "worldnews", "technology", "gaming", "movies", "books", "space",
        "gonewild", "nsfw", "realgirls", "holdthemoan", "nsfw_gif", "porn",
    ]
    seen = load_existing(outfile)
    log("[CRAWL] Starting async scrape loop")
    agg_cycle = itertools.cycle(load_existing(outfile) or AGGREGATORS)
    fetch_count = 0

    async with aiohttp.ClientSession() as session:
        while len(seen) < GOLD_TARGET and not STOP:
            source = "all" if fetch_count % 4 == 3 else next(agg_cycle)
            url = f"https://www.reddit.com/r/{source}/new/"
            html = await fetch(session, url)
            fresh = extract_subs(html) - seen
            if fresh:
                added = await append_new(session, fresh, outfile)
                seen |= fresh
                log(f"[CRAWL] ADDED +{added}  (total seen {len(seen)})")
            else:
                log("[CRAWL] No new subreddits on this page")
            fetch_count += 1
            await asyncio.sleep(0.5)

# ---------- MAIN ----------------------------------------------------------
async def main():
    parser = argparse.ArgumentParser(description="Fast async crawler")
    parser.add_argument("--gold", action="store_true")
    parser.add_argument("--out", type=str, default="subs.json")
    args = parser.parse_args()

    threading.Thread(target=printer, args=(args.out,), daemon=True).start()

    if args.gold:
        while not STOP:
            await crawl(args.out)
            log("[MAIN] Sleeping 5 min before next cycle")
            await asyncio.sleep(300)
    else:
        await crawl(args.out)

    total = sum(1 for _ in open(args.out, "r", encoding="utf-8")) if os.path.isfile(args.out) else 0
    log(f"[MAIN] FINISHED with {total:,} total subreddits in {args.out}")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
