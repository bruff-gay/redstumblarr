// lib/api.js
const DB_URL = 'https://arrgregator.bruff.xyz/all.json';

let db;

export async function loadDatabase() {
  if (db) return db;
  const res = await fetch(DB_URL);
  db = await res.json();
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
