# Jira Indicator

[![CI](https://github.com/your-github-user/jcm-gnome-jira-indicator/actions/workflows/ci.yml/badge.svg)](https://github.com/your-github-user/jcm-gnome-jira-indicator/actions/workflows/ci.yml)

A GNOME Shell top-bar counter of the Jira issues that still need you. It refreshes on its own, marks what changed
since you last looked, and opens any issue in your browser with one click.

![Jira Indicator in the GNOME top bar](docs/screenshot.png)

## Install

Nothing to install first. Paste one line in a terminal (`wget` is on every Ubuntu; `curl` works too):

```bash
wget -qO- https://raw.githubusercontent.com/your-github-user/jcm-gnome-jira-indicator/main/install.sh | bash
```

Then put your Jira site, email and [API token](https://id.atlassian.com/manage-profile/security/api-tokens) in
`~/.config/jcm-gnome-jira-indicator/config.ini`, and log out and back in.

Requires GNOME Shell 46 to 50 (Ubuntu 24.04 LTS or newer). Every setting and troubleshooting: [the user manual](MANUAL.md).

## Uninstall

```bash
gnome-extensions uninstall jcm-gnome-jira-indicator@your-github-user.github.io                # removes the extension
rm -r ~/.config/jcm-gnome-jira-indicator ~/.local/state/jcm-gnome-jira-indicator  # removes your settings and token
```

Then revoke the token at <https://id.atlassian.com/manage-profile/security/api-tokens>.

Developers who linked the folder with `make dev`: use `make uninstall` instead of `gnome-extensions uninstall`, which may
follow the link and delete files in your working copy.

## Development

`make help` lists the developer commands: `make test`, `make dev` (link this folder instead of copying), `make fetch`,
`make pack`.

## License

GPL-2.0-or-later. See [LICENSE](LICENSE).
