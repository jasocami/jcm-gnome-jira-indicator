# Changelog

## 1.0.0 (unreleased)

- First version: a top-bar count of the Jira issues that need you, with a menu that opens each one.
- Marks issues that changed since you last opened the menu.
- One-line installer (`install.sh`) that needs no extra packages; the API token lives in `config.ini`.
- Loading and empty states in the menu; slower refreshes after errors and when Jira rate limits.
