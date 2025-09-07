export function openSubreddit(subreddit) {
  const url = `https://www.reddit.com/r/${subreddit.name}`;
  chrome.tabs.create({ url });
}
