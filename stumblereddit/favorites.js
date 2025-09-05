const STORE_KEY = 'favorites';

async function load() {
  const { [STORE_KEY]: fav = { list: [] } } = await chrome.storage.local.get(STORE_KEY);
  const ul = document.getElementById('list');
  ul.innerHTML = '';
  fav.list.forEach(name => {
    const li = document.createElement('li');
    li.innerHTML = `<a href="https://reddit.com/r/${name}" target="_blank">r/${name}</a>`;
    ul.appendChild(li);
  });
}

window.addEventListener('DOMContentLoaded', load);
chrome.storage.onChanged.addListener(load);

