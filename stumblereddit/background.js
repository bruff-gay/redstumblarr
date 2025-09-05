// background.js
const DB_URL = 'https://arrgregator.bruff.xyz/all.ndjson';

let db;
async function loadDatabase() {
  if (db) return db;
  const res   = await fetch(DB_URL);
  const lines = (await res.text()).trim().split('\n').filter(Boolean);
  db = lines.map(JSON.parse);
  return db;
}

async function getRandomSubreddit(mode = 'all') {
  const all = await loadDatabase();
  let list = all;
  if (mode === 'sfw')     list = all.filter(r => !r.nsfw);
  if (mode === 'nsfw')    list = all.filter(r => r.nsfw && !r.creator);
  if (mode === 'creators') list = all.filter(r => r.creator);
  const idx = Math.floor(Math.random() * list.length);
  return list[idx];
}

function openSubreddit(sub) {
  chrome.tabs.create({ url: `https://www.reddit.com/r/${sub.name}` });
}

// ---------- message from popup ----------
chrome.runtime.onMessage.addListener((msg, _sender, _respond) => {
  if (msg.action === 'openRandom') {
    getRandomSubreddit(msg.mode).then(openSubreddit);
  }
});

// ---------- optional: context menu / commands ----------
chrome.runtime.onInstalled.addListener(() => {
  chrome.contextMenus.create({ id: 'stumble', title: 'Open random subreddit', contexts: ['all'] });
});

chrome.contextMenus.onClicked.addListener(() => {
  getRandomSubreddit().then(openSubreddit);
});

