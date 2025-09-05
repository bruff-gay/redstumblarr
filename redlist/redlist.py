#!/usr/bin/env python3
"""
Zero-JSON live crawler
* never calls /about.json
* scrapes NSFW flag + subscriber count from public HTML
* writes one NDJSON line per subreddit, flush + fsync on every new record
"""
import argparse, os, re, json, time, random, signal, sys, threading, itertools, urllib.request, urllib.error
from datetime import datetime

HEADERS = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:125.0) Gecko/20100101 Firefox/125.0"}
GOLD_TARGET = 100_000
STOP = False

# ---------- UTILS -----------------------------------------------------------
def log(msg, *a, **kw):
    print(f"[{datetime.now():%H:%M:%S}] {msg}", *a, **kw)
def sigint(*_):
    global STOP; log("SIGINT caught — shutting down gracefully..."); STOP = True
signal.signal(signal.SIGINT, sigint)

# ---------- NETWORK ---------------------------------------------------------
def fetch(url: str) -> str:
    delay = 5.0
    while not STOP:
        time.sleep(max(0, delay - (time.time() - getattr(fetch, "last", 0))) + random.uniform(0.1, 0.4))
        fetch.last = time.time()
        req = urllib.request.Request(url, headers=HEADERS)
        try:
            with urllib.request.urlopen(req, timeout=15) as r:
                return r.read().decode("utf-8", errors="ignore")
        except urllib.error.HTTPError as e:
            if e.code == 429:
                time.sleep(int(e.headers.get("Retry-After", 30)))
                continue
            if 500 <= e.code < 600:
                time.sleep(30)
                continue
            raise
    sys.exit(0)

# ---------- EXTRACTION -------------------------------------------------------
def extract_subs(html: str) -> set[str]:
    return {s.lower() for s in re.findall(r'/r/([A-Za-z0-9_]{3,21})(?:/|")', html)}

def extract_meta(html: str) -> tuple[bool, int] | None:
    """
    Scrape NSFW flag and subscriber count from a normal subreddit front page.
    Returns (nsfw, subscribers) or None on parse failure.
    """
    # 1. NSFW
    nsfw = bool(re.search(r'"over18":\s*true|nsfw.*?community', html, flags=re.I))
    # 2. Subscribers
    m = re.search(r'"subscribers":\s*(\d+)', html)
    if not m:
        m = re.search(r'(\d[\d,]*)\s*(?:members?|subscribers?)', html, flags=re.I)
    if not m:
        return None
    subs = int(m.group(1).replace(",", ""))
    return nsfw, subs

# ---------- LOAD + SAVE ------------------------------------------------------
def load_names(outfile: str) -> set[str]:
    if not os.path.isfile(outfile):
        return set()
    names = set()
    with open(outfile, encoding="utf-8") as f:
        for ln in f:
            try:
                names.add(json.loads(ln)["name"].lower())
            except Exception:
                pass
    return names

def append_new(new: set[str], outfile: str) -> int:
    existing = load_names(outfile)
    todo = new - existing
    log(f"[append] {len(todo)} candidates after fast filter")
    written = 0
    with open(outfile, "a", encoding="utf-8") as f:
        for sub in sorted(todo):
            if sub in load_names(outfile):   # race-safe double check
                continue
            url = f"https://www.reddit.com/r/{sub}/"
            html = fetch(url)
            meta = extract_meta(html)
            if meta is None:
                continue
            nsfw, subs = meta
            line = json.dumps({"name": sub, "subscribers": subs, "nsfw": nsfw}, ensure_ascii=False)
            f.write(line + "\n")
            f.flush(); os.fsync(f.fileno())
            written += 1
            log(f"[append] flushed /r/{sub}  NSFW={nsfw}  subs={subs:,}")
    return written

# ---------- STATUS ----------------------------------------------------------
def printer(outfile: str):
    while not STOP:
        total = sum(1 for _ in open(outfile, encoding="utf-8")) if os.path.isfile(outfile) else 0
        log(f"[status] {total:,} subreddits in {outfile}")
        time.sleep(5)

# ---------- CRAWL -----------------------------------------------------------
AGGREGATORS = [
    "AskReddit", "funny", "pics", "todayilearned", "science", "aww",
    "worldnews", "technology", "gaming", "movies", "books", "space",
    "gonewild", "nsfw", "realgirls", "holdthemoan", "nsfw_gif", "porn",
]

def crawl(outfile: str):
    seen = load_names(outfile)
    agg_cycle = itertools.cycle(load_names(outfile) or AGGREGATORS)
    fetch_count = 0
    while len(seen) < GOLD_TARGET and not STOP:
        if fetch_count % 4 == 3:
            url = "https://www.reddit.com/r/all/new/"
        else:
            sub = next(agg_cycle)
            url = f"https://www.reddit.com/r/{sub}/new/"
        html = fetch(url)
        fresh = extract_subs(html) - seen
        if fresh:
            added = append_new(fresh, outfile)
            seen |= fresh
            log(f"[crawl] +{added} new subs  (total {len(seen)})")
        fetch_count += 1
        time.sleep(0.5)

# ---------- MAIN ------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--gold", action="store_true")
    ap.add_argument("--out", default="subs.ndjson")
    args = ap.parse_args()

    threading.Thread(target=printer, args=(args.out,), daemon=True).start()
    if args.gold:
        while not STOP:
            crawl(args.out)
            log("[main] sleeping 5 min before next cycle")
            time.sleep(300)
    else:
        crawl(args.out)

    total = sum(1 for _ in open(args.out, encoding="utf-8")) if os.path.isfile(args.out) else 0
    log(f"[main] finished with {total:,} subreddits in {args.out}")

if __name__ == "__main__":
    main()
