#!/usr/bin/env python3
"""
Fast NSFW crawler – restart on 10×429, always check DEFAULT_AGGREGATORS first,
accurate NSFW flag via /about.json
"""
import argparse
import concurrent.futures
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

import requests

HEADERS_LIST = [
    {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:125.0) Gecko/20100101 Firefox/125.0"},
    {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0 Safari/537.36"},
    {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 13.5; rv:125.0) Gecko/20100101 Firefox/125.0"},
]

GOLD_TARGET = 100_000
MAX_WORKERS = 30
BATCH_SIZE = 1000
FLUSH_EVERY = 2
MAX_BACKOFF = 600
RESTART_429_COUNT = 10

STOP = False

# ---------- DEFAULT AGGREGATORS (always first)
DEFAULT_AGGREGATORS = [
    "AskReddit", "funny", "pics", "todayilearned", "science", "aww",
    "worldnews", "technology", "gaming", "movies", "books", "space",
    "gonewild", "nsfw", "realgirls", "holdthemoan", "nsfw_gif", "porn",
    "NSFW_GIF", "Amateur", "NSFW_Japan", "GWCouples"
]

class Counters:
    seen = set()
    http_errors = {}
    appended = 0
    start_time = None
    buffer = []
    last_flush = 0
    current_page = ""
    total_429s = 0

# ---------- UTILS -----------------------------------------------------------
def log(msg, *a, **kw):
    print(f"[{datetime.now():%H:%M:%S}] {msg}", *a, **kw, file=sys.stderr)

def fmt_seconds(s):
    m, s = divmod(int(s), 60)
    h, m = divmod(m, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"

def sigint(*_):
    global STOP
    log("SIGINT caught — shutting down...")
    STOP = True
signal.signal(signal.SIGINT, sigint)

# ---------- SESSION ----------------------------------------------------------
session = requests.Session()

def _backoff(attempt: int) -> float:
    return min((2 ** attempt) + random.uniform(0, 1), MAX_BACKOFF)

def fetch(url: str) -> str | None:
    headers = random.choice(HEADERS_LIST)
    try:
        r = session.get(url, headers=headers, timeout=15)
        r.raise_for_status()
        return r.text
    except requests.HTTPError as e:
        Counters.http_errors[e.response.status_code] = Counters.http_errors.get(e.response.status_code, 0) + 1
        if e.response.status_code == 429:
            Counters.total_429s += 1
        return None

def fetch_json(url: str) -> dict | None:
    headers = random.choice(HEADERS_LIST)
    try:
        r = session.get(url, headers=headers, timeout=15)
        r.raise_for_status()
        return r.json()
    except requests.HTTPError as e:
        Counters.http_errors[e.response.status_code] = Counters.http_errors.get(e.response.status_code, 0) + 1
        if e.response.status_code == 429:
            Counters.total_429s += 1
        return None

# ---------- EXTRACTION ------------------------------------------------------
def extract_subs(html: str) -> set[str]:
    return {s.lower() for s in re.findall(r'/r/([A-Za-z0-9_]{3,21})(?:/|")', html)}

def extract_meta(sub: str) -> tuple[bool, int] | None:
    url = f"https://www.reddit.com/r/{sub}/about.json"
    data = fetch_json(url)
    if not data:
        return None
    try:
        return bool(data["data"]["over18"]), int(data["data"]["subscribers"])
    except (KeyError, ValueError):
        return None

# ---------- FILE I/O --------------------------------------------------------
def flush(outfile: str):
    if not Counters.buffer:
        return
    with open(outfile, "a", encoding="utf-8", buffering=1) as f:
        f.write("".join(Counters.buffer))
    Counters.buffer.clear()

def append(rec: dict, outfile: str):
    Counters.buffer.append(json.dumps(rec, ensure_ascii=False) + "\n")
    Counters.appended += 1
    if len(Counters.buffer) >= BATCH_SIZE or time.time() - Counters.last_flush >= FLUSH_EVERY:
        flush(outfile)
        Counters.last_flush = time.time()

# ---------- LOAD ------------------------------------------------------------
def load_seen(outfile: str) -> set[str]:
    if not os.path.isfile(outfile):
        return set()
    seen = set()
    with open(outfile, encoding="utf-8") as f:
        for ln in f:
            try:
                seen.add(json.loads(ln)["name"].lower())
            except Exception:
                pass
    return seen

# ---------- STATUS ----------------------------------------------------------
def printer(outfile: str):
    while not STOP:
        total = len(Counters.seen)
        pct = total / GOLD_TARGET
        filled = int(pct * 40)
        bar = "█" * filled + "░" * (40 - filled)
        errs = ",".join(f"{c}:{n}" for c, n in sorted(Counters.http_errors.items()))
        errs = errs or "0"
        eta = ""
        if Counters.start_time:
            elapsed = time.time() - Counters.start_time
            if total:
                eta = fmt_seconds(elapsed / total * (GOLD_TARGET - total))
        else:
            eta = "--:--:--"
        print(
            f"\rTotal={total:,}  429s={Counters.total_429s}  Errors={errs}  Appended={Counters.appended}  "
            f"Page={Counters.current_page}  "
            f"[{bar}]  {total}/{GOLD_TARGET}  {pct*100:5.1f}%  ETA {eta} ",
            end="", flush=True
        )
        time.sleep(2)

# ---------- CRAWL ----------------------------------------------------------
def crawl(outfile: str):
    Counters.seen = load_seen(outfile)
    Counters.start_time = time.time()
    Counters.total_429s = 0

    # always process default aggregators first
    cycle_list = list(DEFAULT_AGGREGATORS) + list(Counters.seen)
    agg_cycle = itertools.cycle(cycle_list)
    fetch_count = 0

    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        while len(Counters.seen) < GOLD_TARGET and not STOP:
            if Counters.total_429s >= RESTART_429_COUNT:
                log(f"Hit {RESTART_429_COUNT} 429s – restarting")
                os.execv(sys.executable, [sys.executable] + sys.argv)

            if fetch_count % 4 == 3:
                url = "https://www.reddit.com/r/all/new"
            else:
                url = f"https://www.reddit.com/r/{next(agg_cycle)}/new"
            Counters.current_page = url

            html = fetch(url)
            if html is None:
                fetch_count += 1
                time.sleep(_backoff(fetch_count % 10))
                continue

            fresh = extract_subs(html) - Counters.seen
            if not fresh:
                fetch_count += 1
                time.sleep(0.2)
                continue

            fresh_list = list(fresh)
            futures = {pool.submit(extract_meta, s): s for s in fresh_list}

            for fut in concurrent.futures.as_completed(futures):
                if STOP:
                    break
                res = fut.result()
                if res is None:
                    continue
                nsfw, subs = res
                sub = futures[fut]
                rec = {"name": sub, "subscribers": subs, "nsfw": nsfw}
                Counters.seen.add(sub)
                append(rec, outfile)

            flush(outfile)
            fetch_count += 1
            time.sleep(0.2)
    flush(outfile)

# ---------- MAIN ----------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description="Fast NSFW crawler – restart on 429")
    ap.add_argument("--gold", action="store_true", help="loop forever")
    ap.add_argument("--out", type=str, default="all.ndjson", help="output file")
    args = ap.parse_args()

    threading.Thread(target=printer, args=(args.out,), daemon=True).start()
    if args.gold:
        while not STOP:
            crawl(args.out)
            log("sleeping 2 min before next cycle")
            time.sleep(120)
    else:
        crawl(args.out)

    total = len(Counters.seen)
    log(f"\n[main] finished with {total:,} subreddits in {args.out}")

if __name__ == "__main__":
    # pip install requests
    main()
