const STORE_KEY = 'favorites';

async function load() {
  const { [STORE_KEY]: fav = { list: [] } } = await chrome.storage.local.get(STORE_KEY);
  const ul = document.getElementById('list');
  ul.innerHTML = '';
  fav.list.forEach(name => {
    const li = document.createElement('li');
    const a = document.createElement('a');
    a.href = `https://reddit.com/r/${name}`;
    a.textContent = `r/${name}`;
    a.target = '_blank';
    li.appendChild(a);
    ul.appendChild(li);          // <- add the line to the DOM
  });
}

window.addEventListener('DOMContentLoaded', load);
chrome.storage.onChanged.addListener(load);
