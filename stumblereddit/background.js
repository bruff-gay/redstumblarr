import { getRandomSubreddit } from './lib/api.js';
import { openSubreddit } from './lib/navigator.js';
import { toggleFavorite } from './lib/favorites.js';

chrome.commands.onCommand.addListener(async (cmd) => {
  switch (cmd) {
    case 'random-subreddit':
      openSubreddit(await getRandomSubreddit());
      break;
    case 'toggle-favorite':
      toggleFavorite();
      break;
    case 'open-favorites':
      chrome.runtime.openOptionsPage();
      break;
    case 'toggle-overlay':
      chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
        chrome.tabs.sendMessage(tabs[0].id, { action: 'toggleOverlay' });
      });
      break;
  }
});

// Context-menu entry
chrome.runtime.onInstalled.addListener(() => {
  chrome.contextMenus.create({ id: 'stumble', title: 'Open random subreddit', contexts: ['all'] });
});
chrome.contextMenus.onClicked.addListener(async () => {
  openSubreddit(await getRandomSubreddit());
});
