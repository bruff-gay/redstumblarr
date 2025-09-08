const DB_URL = 'https://raw.githubusercontent.com/bruff-gay/redlistjson/refs/heads/main/all.ndjson';
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
  const tabs = await browser.tabs.query({ active: true, currentWindow: true });
  const tab  = tabs[0];
  const match = tab.url?.match(/\/r\/([^/?#]+)/);
  return match ? match[1] : null;
}

async function loadFavorites() {
  const res = await browser.storage.local.get(STORE_KEY);
  return res?.[STORE_KEY]?.list ?? [];
}

async function saveFavorites(list) {
  await browser.storage.local.set({ [STORE_KEY]: { list } });
}

async function refreshFavList() {
  const ul = document.getElementById('favList');
  const favs = await loadFavorites();
  ul.innerHTML = '';
  favs.forEach(name => {
    const li = document.createElement('li');
    const a = document.createElement('a');
    a.href = `https://reddit.com/r/${name}`;
    a.textContent = `r/${name}`;
    a.target = '_blank';
    li.appendChild(a);
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
    browser.runtime.sendMessage({ action: 'openRandom', mode });
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
   //why do you need so many open tabs? use one tab
  document.addEventListener('DOMContentLoaded', async () => {
    const useCurrentTabCheckbox = document.getElementById('useCurrentTab');
    // Load saved preference
    const { reuseTab = false } = await browser.storage.sync.get('reuseTab');
    useCurrentTabCheckbox.checked = reuseTab;
    // Save preference when changed
    useCurrentTabCheckbox.addEventListener('change', async (e) => {
      await browser.storage.sync.set({ reuseTab: e.target.checked });
    });
  });
  // show / hide favorites list
  document.getElementById('showFavs').addEventListener('click', () => {
    const ul = document.getElementById('favList');
    ul.style.display = ul.style.display === 'none' ? 'block' : 'none';
  });
});
