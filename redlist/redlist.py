#!/usr/bin/env python3
"""
Ultra-verbose, zero-redundancy crawler
Writes every new subreddit immediately so you can tail -f subs.ndjson
"""
import argparse
import itertools
import json
import os
import random
import re
import signal
import sys
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime

HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:125.0) Gecko/20100101 Firefox/125.0"
}
GOLD_TARGET = 100_000
STOP = False

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

# ---------- LIVE NSFW CHECK --------------------------------------------------
def fetch_nsfw_flag(sub_name: str) -> bool:
    """
    Query Reddit /about.json for the *live* NSFW flag.
    Very verbose: shows every request and result.
    """
    url = f"https://www.reddit.com/r/{sub_name}/about.json"
    log(f"[NSFW_CHECK] Starting NSFW check for /r/{sub_name}")
    log(f"[NSFW_CHECK] URL: {url}")
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw = resp.read().decode("utf-8", errors="ignore")
            j = json.loads(raw)
            nsfw = bool(
                j.get("data", {}).get("over18", False) or
                j.get("data", {}).get("subreddit_over_18", False)
            )
            log(f"[NSFW_CHECK] /r/{sub_name}  NSFW={nsfw}")
            return nsfw
    except Exception as e:
        log(f"[NSFW_CHECK] ERROR for /r/{sub_name}: {e}")
        return False

# ---------- NETWORK ---------------------------------------------------------
def fetch(url: str) -> str:
    """
    Verbose fetcher with retry/back-off.
    """
    delay = 5.0
    fetch.last = getattr(fetch, "last", 0.0)
    while not STOP:
        sleep_time = max(0, delay - (time.time() - fetch.last)) + random.uniform(0.1, 0.4)
        log(f"[FETCH] Sleeping {sleep_time:.2f}s before GET {url}")
        time.sleep(sleep_time)
        fetch.last = time.time()
        req = urllib.request.Request(url, headers=HEADERS)
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                log(f"[FETCH] HTTP {resp.status} for {url}")
                return resp.read().decode("utf-8", errors="ignore")
        except urllib.error.HTTPError as e:
            if e.code == 429:
                sleep = int(e.headers.get("Retry-After", 60))
                log(f"[FETCH] 429 -> sleeping {sleep}s")
                time.sleep(sleep)
                delay = min(delay * 2, 1800)
                continue
            elif e.code in {500, 502, 503, 504}:
                log("[FETCH] 5xx -> sleeping 30s")
                time.sleep(30)
                continue
            raise
    sys.exit(0)

# ---------- EXTRACTION -------------------------------------------------------
def extract_subs(html: str) -> set[str]:
    """
    Pull /r/ names from HTML with verbose counts.
    """
    subs = {s.lower() for s in re.findall(r'/r/([A-Za-z0-9_]{3,21})(?:/|")', html)}
    log(f"[EXTRACT] Found {len(subs)} unique subreddits")
    return subs

# ---------- LOAD EXISTING NAMES (no NSFW check) -----------------------------
def load_existing(outfile: str) -> set[str]:
    """
    Load only the names of subreddits already on disk.
    """
    if not os.path.isfile(outfile):
        log("[LOAD_EXISTING] No file yet, returning empty set")
        return set()
    subs = set()
    with open(outfile, "r", encoding="utf-8") as f:
        for lineno, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                subs.add(json.loads(line)["name"].lower())
            except Exception as e:
                log(f"[LOAD_EXISTING] Bad line {lineno}: {e}")
    log(f"[LOAD_EXISTING] Loaded {len(subs)} subreddit names")
    return subs

# ---------- APPEND NEW SUB (live check + flush) -----------------------------
def append_new(new_subs: set[str], outfile: str) -> int:
    """
    For every new subreddit:
      1. Live NSFW check.
      2. Write JSON line.
      3. Flush + fsync so tail -f shows it instantly.
    """
    existing = load_existing(outfile)
    really_new = new_subs - existing
    log(f"[APPEND_NEW] {len(really_new)} truly new subreddits")
    with open(outfile, "a", encoding="utf-8") as f:
        for s in sorted(really_new):
            nsfw = fetch_nsfw_flag(s)
            stub = {
                "name": s,
                "subscribers": 10_000,
                "verified_nsfw": nsfw,
                "nsfw": nsfw,
            }
            line = json.dumps(stub, ensure_ascii=False)
            f.write(line + "\n")
            f.flush()
            os.fsync(f.fileno())
            log(f"[APPEND_NEW] Flushed /r/{s}  NSFW={nsfw}")
    log(f"[APPEND_NEW] {len(really_new)} lines written")
    return len(really_new)

# ---------- STATUS PRINTER ---------------------------------------------------
def printer(outfile: str):
    while not STOP:
        total = sum(1 for _ in open(outfile, "r", encoding="utf-8")) if os.path.isfile(outfile) else 0
        log(f"[STATUS] {total:,} subreddits in {outfile}")
        time.sleep(5)

# ---------- CRAWL ------------------------------------------------------------
def crawl(outfile: str) -> None:
    AGGREGATORS = [
        "AskReddit", "funny", "pics", "todayilearned", "science", "aww",
        "worldnews", "technology", "gaming", "movies", "books", "space",
        "gonewild", "nsfw", "realgirls", "holdthemoan", "nsfw_gif", "porn",
    ]
    seen = load_existing(outfile)
    log("[CRAWL] Starting scrape loop")

    # build the full aggregator list once
    aggregator_list = list(load_existing(outfile)) or AGGREGATORS
    agg_cycle = itertools.cycle(aggregator_list)
    fetch_count = 0

    while len(seen) < GOLD_TARGET and not STOP:
        # pick source
        if fetch_count % 4 == 3:
            # every 4th fetch is /r/all/new
            source = "all"
            url = "https://www.reddit.com/r/all/new/"
        else:
            source = next(agg_cycle)
            url = f"https://www.reddit.com/r/{source}/new/"

        html = fetch(url)
        fresh = extract_subs(html) - seen
        if fresh:
            added = append_new(fresh, outfile)
            seen |= fresh
            log(f"[CRAWL] ADDED +{added}  (total seen {len(seen)})")
        else:
            log("[CRAWL] No new subreddits on this page")
        fetch_count += 1
        time.sleep(0.5)

# ---------- MAIN ------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="Ultra-verbose live crawler")
    parser.add_argument("--gold", action="store_true", help="loop forever")
    parser.add_argument("--out", type=str, default="subs.ndjson", help="output file")
    args = parser.parse_args()

    # no repair_file call – start crawling immediately
    threading.Thread(target=printer, args=(args.out,), daemon=True).start()

    if args.gold:
        while not STOP:
            crawl(args.out)
            log("[MAIN] Sleeping 5 min before next cycle")
            time.sleep(300)
    else:
        crawl(args.out)

    total = sum(1 for _ in open(args.out, "r", encoding="utf-8")) if os.path.isfile(args.out) else 0
    log(f"[MAIN] FINISHED with {total:,} total subreddits in {args.out}")

if __name__ == "__main__":
    main()
