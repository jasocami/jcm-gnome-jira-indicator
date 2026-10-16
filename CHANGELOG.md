# Changelog

All notable changes to Jira Indicator. Versions follow [Semantic Versioning](https://semver.org/).

## 1.0.1 (Unreleased)

### Fixed

- `fetch.py` asks Jira only for the issues still missing to reach `max_results`, instead of a full page of 100. With a
  low `max_results` it no longer downloads issues it then drops.

## 1.0.0 (2026-10-15)

First version: a GNOME Shell top-bar count of the Jira issues that still need you. Works with GNOME Shell 46 to 50
(Ubuntu 24.04 LTS or newer) and Jira Cloud. It only reads from Jira; it never changes anything there.

### Top bar and menu

- The top bar shows `title`, the number of matching issues and, in brackets, how many changed since you last looked:
  `Jira 28 (2)`.
- The menu lists each issue with its key, status, summary (cut at `summary_max_chars`) and time since the last update.
  Clicking a row opens the issue in your browser.
- The menu shows up to `visible_issues` issues (default 10) and scrolls for the rest, so a long list never pushes
  **Refresh now**, **Edit settings…** and **Help** off the screen.
- Changed issues get a `●` dot. Closing the menu marks everything as seen. The list of seen issues is kept in
  `~/.local/state/jcm-gnome-jira-indicator/seen.json` across logins.
- Loading (`Jira …`) and empty (`Nothing needs you right now`) states.
- **Refresh now** with the time of the last check, **Edit settings…** to open `config.ini`, and **Help** to open the
  manual (online, or the local copy with `help = local`).

### Fetching from Jira

- `fetch.py` calls the Jira Cloud search API (`/rest/api/3/search/jql`) with your email and API token. It follows every
  page up to `max_results` and prints one line of JSON. The extension runs it in the background, so the desktop never
  freezes.
- Any JQL valid in Jira's advanced search works. The default shows open issues that are assigned to you or mention you.
- Refreshes every `refresh_minutes` (default 5, minimum 1). Config changes apply on the next refresh.

### Errors

- When a refresh fails, the count gets a `⚠`, the menu shows the reason, and the last good list stays visible.
- HTTP errors show the reason Jira gives, not just the status code. A bad JQL, for example, reads
  `Jira answered HTTP 400: Error in the JQL Query: Expecting ')' but got 'ORDER'.`
- Clear messages for a rejected login (401/403), a missing config file or token, and missing or invalid keys.
- After a failure, each refresh waits twice as long as the one before, up to 60 minutes. The normal interval comes back
  after the first success. On a 429, it waits as long as Jira's `Retry-After` header asks (10 minutes when there is
  none).
- Every error is saved with the time in `~/.local/state/jcm-gnome-jira-indicator/error.log`. Only the last 200 lines
  are kept, and the token is never written to it.

### Install and setup

- One-line installer (`install.sh`) that downloads with `curl` or `wget`, or installs from a local copy. It needs no
  extra packages. Running it again updates the extension and keeps your settings. `REF=v1.0.0` installs a specific
  release.
- Creates `~/.config/jcm-gnome-jira-indicator/config.ini` from `config.example.ini`, readable only by you
  (`chmod 600`), because the API token is stored there in plain text.
- Uninstall steps in the README and the manual. `make uninstall` keeps your config.

### Development

- `make` targets to check the needed tools, link the folder for development, run the tests, call Jira for real and
  build the release zip.
- Unit tests for `fetch.py` that never touch the network or your real log, plus CI and release workflows on GitHub.
- User manual (`MANUAL.md`) with every setting and a troubleshooting table.
