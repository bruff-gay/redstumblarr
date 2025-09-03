#!/usr/bin/env python3
"""
Ultra-verbose, **Selenium-free** crawler
Repairs malformed JSON, crawls only *new* subs.
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
from datetime import datetime

import requests

HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:125.0) Gecko/20100101 Firefox/125.0"
}
GOLD_TARGET = 100_000
STOP = False

# ---------- UTILS -----------------------------------------------------------
def log(msg: str):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}")

# ---------- CTRL-C ---------------------------------------------------------
def sigint(*_):
    global STOP
    STOP = True
signal.signal(signal.SIGINT, sigint)

# ---------- REPAIR FILE ----------------------------------------------------
def repair_file(outfile: str) -> None:
    if not os.path.isfile(outfile):
        return
    log("repair_file -> fixing malformed JSON")
    good = []
    try:
        with open(outfile, "rb") as f:
            raw = f.read()
        parts = re.findall(rb'\{.*?\}', raw)
        for p in parts:
            try:
                good.append(json.loads(p.decode("utf-8")))
            except Exception:
                pass
    except Exception as e:
        log(f"repair_file -> ERROR {e}")
    log(f"repair_file -> {len(good)} valid objects")
    with open(outfile, "w", encoding="utf-8") as f:
        for obj in good:
            f.write(json.dumps(obj, ensure_ascii=False) + "\n")

# ---------- NETWORK ---------------------------------------------------------
def fetch(url: str) -> str:
    delay = 5.0
    fetch.last = getattr(fetch, "last", 0.0)
    while not STOP:
        time.sleep(max(0, delay - (time.time() - fetch.last)) + random.uniform(0.1, 0.4))
        fetch.last = time.time()
        try:
            log(f"FETCH -> {url}")
            r = requests.get(url, headers=HEADERS, timeout=15)
            r.raise_for_status()
            log(f"FETCHED {len(r.text)} chars")
            return r.text
        except requests.exceptions.RequestException as e:
            log(f"FETCH error {e} -> retry in 10s")
            time.sleep(10)
    sys.exit(0)

# ---------- EXTRACTION ------------------------------------------------------
def extract_subs(html: str) -> set[str]:
    subs = {s.lower() for s in re.findall(r'/r/([A-Za-z0-9_]{3,21})(?:/|")', html)}
    log(f"extract -> {len(subs)} subs")
    return subs

# ---------- LOAD / APPEND ---------------------------------------------------
def load_existing(outfile: str) -> set[str]:
    if not os.path.isfile(outfile):
        return set()
    subs = set()
    with open(outfile, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                subs.add(json.loads(line)["name"].lower())
            except Exception as e:
                log(f"load_bad_line -> {e}")
    log(f"load_existing -> {len(subs)} subs")
    return subs

def append_new(new_subs: set[str], outfile: str) -> int:
    existing = load_existing(outfile)
    really_new = new_subs - existing
    log(f"append_new -> {len(really_new)} truly new")
    with open(outfile, "a", encoding="utf-8") as f:
        for s in really_new:
            stub = {
                "name": s,
                "subscribers": 10_000,
                "nsfw": s in {"gonewild", "nsfw", "realgirls", "nsfw_gif", "porn"},
            }
            f.write(json.dumps(stub, ensure_ascii=False) + "\n")
    return len(really_new)

# ---------- STATUS PRINTER ----------------------------------------------------
def printer(outfile: str):
    while not STOP:
        total = sum(1 for _ in open(outfile, "r", encoding="utf-8")) if os.path.isfile(outfile) else 0
        log(f"TOTAL {total:,} subs in {outfile}")
        time.sleep(5)

# ---------- CRAWL -----------------------------------------------------------
def crawl(outfile: str) -> None:
    AGGREGATORS = [
        "AskReddit", "funny", "pics", "todayilearned", "science", "aww",
        "worldnews", "technology", "gaming", "movies", "books", "space",
        "gonewild", "nsfw", "realgirls", "holdthemoan", "nsfw_gif", "porn",
    ]
    seen = load_existing(outfile)
    log("Starting crawl...")
    while len(seen) < GOLD_TARGET and not STOP:
        aggregator_list = list(load_existing(outfile)) or AGGREGATORS
        log(f"Using {len(aggregator_list)} aggregators")
        for sub in itertools.cycle(aggregator_list):
            if len(seen) >= GOLD_TARGET or STOP:
                break
            html = fetch(f"https://www.reddit.com/r/{sub}/new/")
            fresh = extract_subs(html) - seen
            if fresh:
                added = append_new(fresh, outfile)
                seen |= fresh
                log(f"ADDED +{added}")
            else:
                log("No new subs")
            time.sleep(0.5)

# ---------- MAIN ------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="Repair + crawl")
    parser.add_argument("--gold", action="store_true")
    parser.add_argument("--out", type=str, default="subs.json")
    args = parser.parse_args()
    repair_file(args.out)

    threading.Thread(target=printer, args=(args.out,), daemon=True).start()
    if args.gold:
        while not STOP:
            crawl(args.out)
            log("Sleeping 5 min before next cycle")
            time.sleep(300)
    else:
        crawl(args.out)

    total = sum(1 for _ in open(args.out, "r", encoding="utf-8")) if os.path.isfile(args.out) else 0
    log(f"FINISHED -> {total:,} total subs in {args.out}")

if __name__ == "__main__":
    main()
