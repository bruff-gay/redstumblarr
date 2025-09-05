let overlayMounted = false;

function createOverlay() {
  const div = document.createElement('div');
  div.id = 'stumble-overlay';
  div.innerHTML = `
    <div class="panel">
      <button id="stumble-btn">🎲 Random</button>
      <button id="fav-btn">⭐</button>
      <button id="close-btn">✖</button>
    </div>`;
  document.body.appendChild(div);
  div.querySelector('#close-btn').onclick = toggleOverlay;
  div.querySelector('#stumble-btn').onclick = () => chrome.runtime.sendMessage({ action: 'stumble' });
  div.querySelector('#fav-btn').onclick   = () => chrome.runtime.sendMessage({ action: 'toggleFavorite' });
}

function toggleOverlay() {
  const el = document.getElementById('stumble-overlay');
  el ? el.remove() : createOverlay();
}

chrome.runtime.onMessage.addListener(msg => {
  if (msg.action === 'toggleOverlay') toggleOverlay();
});
