const STORE_KEY = 'favorites';

export async function getFavorites() {
  const { [STORE_KEY]: fav = { list: [] } } = await chrome.storage.local.get(STORE_KEY);
  return fav;
}

export async function toggleFavorite() {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  const match = tab.url.match(/\/r\/([^\/]+)/);
  if (!match) return;
  const subName = match[1];

  const fav = await getFavorites();
  const index = fav.list.indexOf(subName);
  if (index > -1) fav.list.splice(index, 1);
  else fav.list.push(subName);

  await chrome.storage.local.set({ [STORE_KEY]: fav });
}
