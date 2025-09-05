/* global browser */

const DB_URL      = 'https://raw.githubusercontent.com/bruff-gay/redlistjson/refs/heads/main/all.ndjson';
const STORAGE_KEY = 'offlineDB';
const FAV_KEY     = 'favorites';

/* ---------- 1.  offline-first DB ---------- */
async function getDB() {
  const { [STORAGE_KEY]: store } = await browser.storage.local.get(STORAGE_KEY);
  if (store?.data) return store.data;               // fast path – use local copy
  return fetchAndCacheDB();                         // first ever run / upgrade
}

async function fetchAndCacheDB() {
  try {
    const res   = await fetch(DB_URL);
    if (!res.ok) throw new Error('network');
    const text  = await res.text();
    const data  = text.trim().split('\n').filter(Boolean).map(JSON.parse);
    await browser.storage.local.set({
      [STORAGE_KEY]: { data, etag: res.headers.get('etag') ?? '' }
    });
    return data;
  } catch {
    console.warn('[StumbleReddit] network fetch failed – using bundled snapshot');
    return fetchBundledSnapshot();
  }
}

async function fetchBundledSnapshot() {
  const url = browser.runtime.getURL('_data/snapshot.ndjson');
  const txt = await (await fetch(url)).text();
  const data = txt.trim().split('\n').filter(Boolean).map(JSON.parse);
  await browser.storage.local.set({ [STORAGE_KEY]: { data, etag: '' } });
  return data;
}

/* ---------- 2.  optional daily update (disabled by default) ----------
async function maybeUpdateDB() {
  const { [STORAGE_KEY]: store } = await browser.storage.local.get(STORAGE_KEY);
  const headers = store?.etag ? { 'If-None-Match': store.etag } : {};
  try {
    const res = await fetch(DB_URL, { headers });
    if (res.status === 200) await fetchAndCacheDB();
  } catch {}
}
// setInterval(maybeUpdateDB, 24*60*60*1000); // check once per day
------------------------------------------------------------------------*/

/* ---------- 3.  messaging ---------- */
browser.runtime.onMessage.addListener(async (msg) => {
  if (msg.action === 'openRandom') {
    const db   = await getDB();
    const list = filterDB(db, msg.mode);
    if (!list.length) return;
    const pick = list[Math.floor(Math.random() * list.length)];
    browser.tabs.create({ url: `https://www.reddit.com/r/${pick.name}` });
  }
});

/* ---------- 4.  context-menu fallback ---------- */
browser.runtime.onInstalled.addListener(() => {
  browser.contextMenus.create({ id: 'stumble', title: 'Random subreddit', contexts: ['all'] });
});
browser.contextMenus.onClicked.addListener(async () => {
  const db = await getDB();
  const list = filterDB(db, 'all');
  if (list.length) {
    const pick = list[Math.floor(Math.random() * list.length)];
    browser.tabs.create({ url: `https://www.reddit.com/r/${pick.name}` });
  }
});

/* ---------- 5.  helpers ---------- */
function filterDB(db, mode) {
  if (mode === 'sfw')      return db.filter(r => !r.nsfw);
  if (mode === 'nsfw')     return db.filter(r => r.nsfw && !r.creator);
  if (mode === 'creators') return db.filter(r => r.creator);
  return db;
}
