// popup/popup.js
import { getRandomSubreddit } from '../lib/api.js';
import { openSubreddit } from '../lib/navigator.js';   // ← add this line

document.getElementById('stumble').addEventListener('click', async () => {
  const mode = document.getElementById('mode').value;
  openSubreddit(await getRandomSubreddit(mode));
});

document.getElementById('manage').addEventListener('click', () => chrome.runtime.openOptionsPage());
