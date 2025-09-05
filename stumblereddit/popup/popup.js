const DB_URL = 'https://arrgregator.bruff.xyz/all.ndjson';
const STORE_KEY = 'favorites';

// ---------- helpers ----------
async function updateCounter() {
  const el = document.getElementById('count');
  try {
    const lines = (await (await fetch(DB_URL)).text())
      .trim().split('\n').filter(Boolean);
    el.textContent = `(${lines.length})`;
  } catch {
    el.textContent = '(?)';
  }
}

async function getCurrentSub() {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  const match = tab.url?.match(/\/r\/([^/?#]+)/);
  return match ? match[1] : null;
}

async function loadFavorites() {
  const { [STORE_KEY]: fav = { list: [] } } = await chrome.storage.local.get(STORE_KEY);
  return fav.list;
}

async function saveFavorites(list) {
  await chrome.storage.local.set({ [STORE_KEY]: { list } });
}

async function refreshFavList() {
  const ul = document.getElementById('favList');
  const favs = await loadFavorites();
  ul.innerHTML = '';
  favs.forEach(name => {
    const li = document.createElement('li');
    li.innerHTML = `<a href="https://reddit.com/r/${name}" target="_blank">r/${name}</a>`;
    ul.appendChild(li);
  });
  ul.style.display = favs.length ? 'block' : 'none';
}

// ---------- init ----------
window.addEventListener('DOMContentLoaded', () => {
  updateCounter();
  setInterval(updateCounter, 5000);
  refreshFavList();

  // random
  document.getElementById('stumble').addEventListener('click', () => {
    const mode = document.getElementById('mode').value;
    chrome.runtime.sendMessage({ action: 'openRandom', mode });
  });

  // add/remove favorite for current tab
  document.getElementById('favToggle').addEventListener('click', async () => {
    const sub = await getCurrentSub();
    if (!sub) return;

    const favs = await loadFavorites();
    const idx = favs.indexOf(sub);
    if (idx > -1) favs.splice(idx, 1);
    else favs.push(sub);

    await saveFavorites(favs);
    await refreshFavList();
  });

  // show / hide favorites list
  document.getElementById('showFavs').addEventListener('click', () => {
    const ul = document.getElementById('favList');
    ul.style.display = ul.style.display === 'none' ? 'block' : 'none';
  });
});

