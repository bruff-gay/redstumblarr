// lib/api.js
const DB_URL = 'https://raw.githubusercontent.com/bruff-gay/redlistjson/refs/heads/main/all.ndjson';


let db = null;

export async function loadDatabase() {
  if (db) return db;
  const res = await fetch(DB_URL);
  const text = await res.text();
  db = text.trim().split('\n').filter(Boolean).map(JSON.parse);
  return db;
}

export async function getRandomSubreddit(mode = 'all') {
  const all = await loadDatabase();
  let list = all;
  if (mode === 'sfw') list = all.filter(r => !r.nsfw);
  if (mode === 'nsfw') list = all.filter(r => r.nsfw && !r.creator);
  if (mode === 'creators') list = all.filter(r => r.creator);
  const idx = Math.floor(Math.random() * list.length);
  return list[idx];
}

export async function searchSubreddits(term, mode = 'all') {
  const all = await loadDatabase();
  let list = all;
  if (mode === 'sfw') list = all.filter(r => !r.nsfw);
  if (mode === 'nsfw') list = all.filter(r => r.nsfw && !r.creator);
  if (mode === 'creators') list = all.filter(r => r.creator);
  return list.filter(r => r.name.toLowerCase().includes(term.toLowerCase()));
}
