// background.js
const DB_URL = 'https://arrgregator.bruff.xyz/all.ndjson';
let db;

/**
 * Load the database from remote URL (cached)
 * Time: O(n)
 * @returns {Promise<Array<Object>>} The database as an array of JSON objects
 */
async function loadDatabase() {
  if (db) return db;                 // return cached db if already loaded
  const res   = await fetch(DB_URL); // fetch the NDJSON file
  const lines = (await res.text())   // get text content
      .trim()                        // remove leading/trailing whitespace
      .split('\n')                   // split into lines
      .filter(Boolean);              // remove empty lines
  db = lines.map(JSON.parse);        // parse each line as JSON object
  return db;                         // The database is an array of JSON objects
}

/**
 * Get a random subreddit from the database
 * Time: O(n) due to filtering
 * @param mode
 * @returns {Promise<Object>} A random subreddit object
 */
async function getRandomSubreddit(mode = 'all') {
  const all = await loadDatabase(); // load the database
  let list;

  /*
     Used a switch statement for better readability and maintainability
        in case more modes are added in the future.

     BigO: O(n) because of the filter operation. This would benefit from a database query
        if the dataset was large enough to warrant it.

     Each filter operation iterates through the entire list of subreddits.
   */
  switch(mode) {

    // safe for work case
    case 'sfw':
      list = all.filter(r => !r.nsfw);
      break;

    // not safe for work case
    case 'nsfw':
      list = all.filter(r => r.nsfw && !r.creator);
      break;

    // creators case
    case 'creators':
      list = all.filter(r => r.creator);
      break;

    // default case (all)
    default:
        list = all;
  }

  const idx = Math.floor(Math.random() * list.length);
  return list[idx];
}

/**
 * Open a subreddit in a new tab.
 * Time: O(1)
 * @param sub
 */
function openSubreddit(sub) {
  chrome.tabs.create({ url: `https://www.reddit.com/r/${sub.name}` });
}

/**
 * UNTESTED IMPLEMENTATION. I will get a test environment set up to try this out.
 * Open a subreddit in the current tab.
 * Time: O(1)
 * @param sub
 */
function openSubredditInCurrentTab(sub) {
    chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
        if (tabs[0]) {
}

// ******** GLOBAL LISTENERS BEYOND THIS POINT ********

/**
 * Message listener for opening a random subreddit
 * @param msg is expected to have an 'action' property and optionally a 'mode' property
 * @param _sender is the sender of the message (not used here)
 * @param _respond is a function to send a response back (not used here)
 */
chrome.runtime.onMessage.addListener((msg, _sender, _respond) => {
  if (msg.action === 'openRandom') {
    getRandomSubreddit(msg.mode).then(openSubreddit);
  }
});

/**
 * optional: context menu / commands
 * Creates a context menu item to open a random subreddit
 * Listens for clicks on the context menu item to open a random subreddit
 */
chrome.runtime.onInstalled.addListener(() => {
  chrome.contextMenus.create({ id: 'stumble', title: 'Open random subreddit', contexts: ['all'] });
});

/**
 * Listener for context menu clicks
 * Opens a random subreddit when the context menu item is clicked
 */
chrome.contextMenus.onClicked.addListener(() => {
  getRandomSubreddit().then(openSubreddit);
});

