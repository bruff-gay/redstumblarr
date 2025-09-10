const DB_URL = 'https://raw.githubusercontent.com/bruff-gay/redlistjson/refs/heads/main/all.ndjson';
const STORE_KEY = 'favorites';
let lastUpdate = 0;
const CACHE_DURATION = 5 * 60 * 1000; // 5 minutes in milliseconds

// ---------- helpers ----------
async function updateCounter() {
  const el = document.getElementById('count');
  try {
    const now = Date.now();
    if (now - lastUpdate < CACHE_DURATION) return;

    const lines = (await (await fetch(DB_URL)).text())
      .trim().split('\n').filter(Boolean);
    el.textContent = `(${lines.length})`;
    lastUpdate = now;
  } catch {
    el.textContent = '(?)';
  }
}

async function getCurrentSub() {
  const tabs = await browser.tabs.query({ active: true, currentWindow: true });
  const tab = tabs[0];
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

// Add this new function
async function removeFavorite(name) {
  const favs = await loadFavorites();
  const idx = favs.indexOf(name);
  if (idx > -1) {
    favs.splice(idx, 1);
    await saveFavorites(favs);
    await refreshFavList();
  }
}

async function refreshFavList() {
  const ul = document.getElementById('favList');
  const favs = await loadFavorites();
  ul.innerHTML = '';
  
  favs.forEach(name => {
    const li = document.createElement('li');
    li.style.display = 'flex';
    li.style.alignItems = 'center';
    li.style.gap = '5px';
    
    const a = document.createElement('a');
    a.href = `https://reddit.com/r/${name}`;
    a.textContent = `r/${name}`;
    a.target = '_blank';
    a.style.flex = '1';
    
    const removeBtn = document.createElement('button');
    removeBtn.textContent = '✕';
    removeBtn.style.padding = '2px 6px';
    removeBtn.style.fontSize = '10px';
    removeBtn.style.cursor = 'pointer';
    removeBtn.onclick = (e) => {
      e.preventDefault();
      e.stopPropagation();
      removeFavorite(name);
    };
    
    li.appendChild(a);
    li.appendChild(removeBtn);
    ul.appendChild(li);
  });
  
  ul.style.display = favs.length ? 'block' : 'none';
}

// ---------- dark mode -------
document.addEventListener('DOMContentLoaded', async () => {
  // Load saved preferences including dark mode
  const { darkMode = false, reuseTab = false, lastMode = 'all' } = await browser.storage.sync.get(['darkMode', 'reuseTab', 'lastMode']);

  // Apply dark mode preference
  if (darkMode) {
    document.body.classList.add('dark-mode');
  }

  // Set checkbox states
  document.getElementById('useCurrentTab').checked = reuseTab;
  document.getElementById('darkModeToggle').checked = darkMode;
  
  // Restore dropdown selection
  document.getElementById('mode').value = lastMode;

  // Save preferences when changed
  document.getElementById('useCurrentTab').addEventListener('change', async (e) => {
    await browser.storage.sync.set({ reuseTab: e.target.checked });
  });

  document.getElementById('darkModeToggle').addEventListener('change', async (e) => {
    const darkMode = e.target.checked;
    await browser.storage.sync.set({ darkMode });
    // Apply immediately
    if (darkMode) {
      document.body.classList.add('dark-mode');
    } else {
      document.body.classList.remove('dark-mode');
    }
  });
  
  // Save dropdown selection when changed
  document.getElementById('mode').addEventListener('change', async (e) => {
    await browser.storage.sync.set({ lastMode: e.target.value });
  });

  // ---------- init ----------
  updateCounter();
  setInterval(updateCounter, 21600000);
  refreshFavList();

  // random
  document.getElementById('stumble').addEventListener('click', () => {
    const mode = document.getElementById('mode').value;
    // Save the selected mode for persistence
    browser.storage.sync.set({ lastMode: mode });
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

  // show / hide favorites list
  document.getElementById('showFavs').addEventListener('click', () => {
    const ul = document.getElementById('favList');
    ul.style.display = ul.style.display === 'none' ? 'block' : 'none';
  });
});