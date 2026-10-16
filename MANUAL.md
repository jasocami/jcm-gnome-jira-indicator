# Jira Indicator: User Manual

For version 1.0.1 · GNOME Shell 46 to 50 (Ubuntu 24.04 LTS or newer)

Jira Indicator keeps a count of the Jira issues that still need you in the GNOME top bar. It refreshes on its own,
marks what changed since you last looked, and opens any issue in your browser with one click. It only reads from Jira;
it never changes anything there.

## Install

You need GNOME Shell 46 to 50 (Ubuntu 24.04 LTS or newer). Nothing else: no extra packages.

Paste one of these lines in a terminal (use `wget` if `curl` is not installed):

```bash
wget -qO- https://raw.githubusercontent.com/jasocami/jcm-gnome-jira-indicator/main/install.sh | bash
curl -fsSL https://raw.githubusercontent.com/jasocami/jcm-gnome-jira-indicator/main/install.sh | bash
```

Or, from a downloaded copy of the source: `./install.sh` (or `make install`).
To install a specific release instead of the latest code, add `REF=v1.0.0` before `bash`.
Running the installer again updates the extension and keeps your settings.

## First setup

1. Create a Jira API token at <https://id.atlassian.com/manage-profile/security/api-tokens>. Copy it; Atlassian shows it
   only once.
2. Open `~/.config/jcm-gnome-jira-indicator/config.ini` and fill in `domain`, `email` and `token`
   (see the reference below).
3. Log out and log back in. GNOME only discovers new extensions at login (first install only).
   Jira Indicator then appears in the top bar.

## Using it

The top bar shows `Jira 28 (2)`:

| Part | Meaning |
| --- | --- |
| `Jira` | The `title` from your config |
| `28` | Issues that match your JQL and are not in a Done status |
| `(2)` | Issues that changed since you last opened the menu (hidden when 0) |
| `⚠` | The last refresh failed. Open the menu to read why; the list shown is the last good one |
| `Jira …` | The first refresh after login has not finished yet |

Click it to open the menu:

- **Issue rows:** `●` when it changed since you last looked, then key, status, summary and time since the last update.
  Click a row to open the issue in your browser. Past `visible_issues` rows (10 by default) the list scrolls, so the
  actions below it stay in view.
- **Nothing needs you right now:** shown instead of rows when your JQL matches no issues.
- **Refresh now:** fetches the list immediately. It also shows when the last check happened.
- **Open Jira:** opens your Jira site (`domain` in `config.ini`) in your browser.
- **Edit settings…:** opens your `config.ini` in the text editor.
- **Help:** opens this manual.

Closing the menu marks every row as seen, so the `(2)` and the dots disappear.
An issue leaves the list only when it reaches a Done status in Jira.

After a failed refresh the next one waits longer (twice as long each time, up to 60 minutes), and goes back to normal
after the first success. If Jira says it is rate limiting, the next refresh waits as long as Jira asks.

## Configuration reference

File: `~/.config/jcm-gnome-jira-indicator/config.ini`. Changes apply on the next refresh, or right away with **Refresh now**.
No restart is needed.

### [jira]

| Key | Required | Default | What it does | Example |
| --- | --- | --- | --- | --- |
| `domain` | Yes | (none) | Your Atlassian site, without `https://` | `your-company.atlassian.net` |
| `email` | Yes | (none) | The email you log in to Jira with | `your.name@example.com` |
| `token` | Yes | (none) | Your Jira API token. It works like a password: keep this file private | `ATATT3x…` |
| `jql` | Yes | (none) | Which issues are counted and listed. Any query valid in Jira's advanced search | see below |
| `max_results` | No | `100` | Upper limit of issues loaded | `200` |
| `page_size` | No | `100` | How many issues each request to Jira asks for. It only changes the number of requests, not which issues you see. Values below 1 count as 1 | `50` |

Useful `jql` values:

| Goal | JQL |
| --- | --- |
| Assigned or mentioned, not done (the default) | `(assignee = currentUser() OR comment ~ currentUser() OR description ~ currentUser()) AND statusCategory != Done ORDER BY updated DESC` |
| Only one project | add `AND project = ABC` before `ORDER BY` |
| Only urgent work | add `AND priority in (High, Highest)` before `ORDER BY` |
| Only issues assigned to me | `assignee = currentUser() AND statusCategory != Done ORDER BY updated DESC` |

### [indicator]

| Key | Required | Default | What it does | Example |
| --- | --- | --- | --- | --- |
| `title` | No | `Jira` | Text before the counter in the top bar. Emoji work. Empty shows only the numbers | `Work`, `📋` |
| `refresh_minutes` | No | `5` | Minutes between automatic refreshes. Values below 1 count as 1 | `10` |
| `summary_max_chars` | No | `60` | Longest summary shown in a menu row before it is cut with `…` | `80` |
| `visible_issues` | No | `10` | How many issues the menu shows before the list scrolls. Values below 1 count as 1 | `15` |
| `help` | No | `online` | What **Help** opens: `online` = this manual on GitHub, for your installed version; `local` = the copy installed with the extension (works offline) | `local` |

### Rules of the file format

- Lines starting with `#` are comments. Put comments on their own line, never after a value.
- A long value continues on the next line if that line is indented (see `jql` in the example config).
- Spaces around `=` are ignored. Do not put quotes around values.
- `%` has no special meaning.

## When something goes wrong

The menu shows the reason next to `⚠`. Every error is also saved, with the time, in
`~/.local/state/jcm-gnome-jira-indicator/error.log` (the last 200 lines), so you can see what happened while you were
away: `tail ~/.local/state/jcm-gnome-jira-indicator/error.log`.

| Message | Fix |
| --- | --- |
| Config file not found | Run the installer again; it creates the file |
| No API token | Set `token` in `config.ini` |
| Jira rejected the login | Wrong email, or the token expired: create a new token and paste it into `config.ini` |
| Jira is rate limiting | Nothing to do now; raise `refresh_minutes` if it happens often |
| Jira answered HTTP 400: … | The JQL has an error; the text after the colon is Jira's reason. Fix `jql` in `config.ini` |
| No section: … / No option … | A section or required key is missing from `config.ini`: compare with `config.example.ini` |
| invalid literal for int() | A number key (`refresh_minutes`, `max_results`, `page_size`, `summary_max_chars`, `visible_issues`) contains text |
| A network or timeout message | Offline, VPN or proxy issue. It recovers on its own at a later refresh |

Nothing in the top bar at all: run `gnome-extensions info jcm-gnome-jira-indicator@jasocami.github.io`.
It should say `ACTIVE`. If not, log out and in, then `gnome-extensions enable jcm-gnome-jira-indicator@jasocami.github.io`.

## Uninstall

```bash
gnome-extensions uninstall jcm-gnome-jira-indicator@jasocami.github.io   # removes the extension
rm -r ~/.config/jcm-gnome-jira-indicator ~/.local/state/jcm-gnome-jira-indicator   # removes your settings, token and error log
```

Revoke the token too, at <https://id.atlassian.com/manage-profile/security/api-tokens>.

## Privacy

Jira Indicator talks only to the Jira site in your config. Your token is stored in plain text in `config.ini`, which the
installer makes readable only by you; never commit or share that file. The list of seen issues is kept in `~/.local/state/jcm-gnome-jira-indicator/seen.json`, and the error log in
`error.log` next to it; the log never contains your token.
