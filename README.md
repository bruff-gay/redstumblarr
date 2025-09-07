RedStumblarr

Offline, privacy-first "stumbler" for R*ddit.
What it is

A tiny Firefox WebExtension that opens a random subreddit

Features

    One-click “Random” button on the toolbar
    Works completely offline once the list is cached
    Add favorites with a second click
    Opens links in new tabs; respects old.reddit.com preference
    Zero permissions beyond storage and the Reddit hosts
    < 150 kB packed

Install (production)

    Grab the latest signed .xpi from Releases
    Firefox → Add-ons Manager → Install Add-on From File
    Icon appears in the toolbar—start stumbling.

Install (development)

Bash

git clone https://github.com/bruff-gay/redstumblarr.git
cd redstumblarr
# no build step; pure JS
zip -r pubrelease.zip . -x '*.git*' README.md


Open about:debugging → Load Temporary Add-on → select the zip.

Goal for next milestone (v3.0)

    Chrome-MV3 parity with a single codebase
    Optional custom user lists (JSON drag-and-drop)
    Keyboard shortcut (Ctrl+Shift+S) configurable via UI
    Translations for Spanish

Bug reports

File issues on GitHub:
github.com/bruff-gay/redstumblarr/issues
Please include:

    Firefox version
    Extension version
    Console logs (about:debugging ➜ Inspect)

Release of liability / Terms

This software is provided “as-is” under the MIT License.
By using RedStumblarr you agree that the authors are not responsible for any content you encounter or any damages that may arise.
See LICENSE for full text.
License

MIT © 2025 bruff-gay