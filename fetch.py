#!/usr/bin/env python3
"""Fetch the Jira issues that need my attention and print them as JSON.

The GNOME extension runs this script on a timer and reads what it prints.
Test it by hand with:  python3 fetch.py | python3 -m json.tool
"""
import base64
import configparser
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path

APP_NAME = 'jcm-gnome-jira-indicator'
CONFIG_PATH = Path.home() / '.config' / APP_NAME / 'config.ini'
# Same folder as the extension's seen.json (GLib.get_user_state_dir())
LOG_PATH = Path(os.environ.get('XDG_STATE_HOME') or Path.home() / '.local' / 'state') / APP_NAME / 'error.log'
LOG_MAX_LINES = 200
PAGE_SIZE = 100
TIMEOUT_SECONDS = 20


def load_config():
    # interpolation=None: a '%' in the JQL is plain text, not a configparser variable
    config = configparser.ConfigParser(interpolation=None)
    if not config.read(CONFIG_PATH):
        raise RuntimeError(f'Config file not found: {CONFIG_PATH}')
    return config


def get_token(config):
    """The API token from config.ini. It sits there in plain text, so the file must stay readable only by you."""
    token = config.get('jira', 'token', fallback='').strip()
    if not token:
        raise RuntimeError(f'No API token: set token in {CONFIG_PATH}')
    return token


def search(domain, email, token, jql, max_results):
    """Run the JQL search, following pages until there are no more or max_results is reached."""
    auth = base64.b64encode(f'{email}:{token}'.encode()).decode()
    headers = {'Authorization': f'Basic {auth}', 'Accept': 'application/json'}
    issues, page_token = [], None
    while len(issues) < max_results:
        params = {'jql': jql, 'fields': 'summary,status,updated', 'maxResults': PAGE_SIZE}
        if page_token:
            params['nextPageToken'] = page_token
        url = f'https://{domain}/rest/api/3/search/jql?{urllib.parse.urlencode(params)}'
        request = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            data = json.load(response)
        issues.extend(data.get('issues', []))
        page_token = data.get('nextPageToken')
        if not page_token:  # no token = last page
            break
    return issues[:max_results]


def retry_minutes(error, default=10):
    """Minutes to wait after a 429, from the Retry-After header (in seconds) when Jira sends one."""
    try:
        return max(1, -(-int(error.headers['Retry-After']) // 60))
    except (TypeError, KeyError, ValueError):
        return default


def jira_message(error):
    """The reason Jira gives in the error body (errorMessages and field errors), or None when there is none."""
    try:
        body = json.loads(error.read())
        messages = body.get('errorMessages', []) + list(body.get('errors', {}).values())
    except Exception:  # empty or non-JSON body: fall back to the bare status code
        return None
    return ' '.join(str(message) for message in messages) or None


def log_error(message):
    """Append the error to error.log with the time, keeping only the last LOG_MAX_LINES lines."""
    try:
        lines = LOG_PATH.read_text().splitlines() if LOG_PATH.exists() else []
        lines.append(f'{datetime.now():%Y-%m-%d %H:%M:%S}  {" ".join(message.split())}')
        LOG_PATH.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        LOG_PATH.write_text('\n'.join(lines[-LOG_MAX_LINES:]) + '\n')
    except OSError:  # a log that cannot be written must not hide the error from the top bar
        pass


def main():
    output = {
        'title': 'Jira', 'refresh_minutes': 5, 'summary_max_chars': 60, 'help': 'online',
        'error': None, 'retry_after_minutes': None, 'issues': [],
    }
    try:
        config = load_config()
        output['title'] = config.get('indicator', 'title', fallback='Jira')
        output['refresh_minutes'] = max(1, config.getint('indicator', 'refresh_minutes', fallback=5))
        output['summary_max_chars'] = config.getint('indicator', 'summary_max_chars', fallback=60)
        if config.get('indicator', 'help', fallback='online') == 'local':
            output['help'] = 'local'
        domain = config.get('jira', 'domain')
        email = config.get('jira', 'email')
        token = get_token(config)
        jql = config.get('jira', 'jql')
        max_results = config.getint('jira', 'max_results', fallback=100)
        output['issues'] = [
            {
                'key': issue['key'],
                'summary': issue['fields']['summary'],
                'status': issue['fields']['status']['name'],
                'updated': issue['fields']['updated'],
                'url': f'https://{domain}/browse/{issue["key"]}',
            }
            for issue in search(domain, email, token, jql, max_results)
        ]
    except urllib.error.HTTPError as error:
        if error.code in (401, 403):
            output['error'] = 'Jira rejected the login: check the email and the API token'
        elif error.code == 429:
            output['error'] = 'Jira is rate limiting: the next refresh waits'
            output['retry_after_minutes'] = retry_minutes(error)
        else:
            message = jira_message(error)
            output['error'] = f'Jira answered HTTP {error.code}' + (f': {message}' if message else '')
    except Exception as error:  # any other failure is shown in the top bar instead of crashing
        output['error'] = str(error) or type(error).__name__
    if output['error']:
        log_error(output['error'])
    print(json.dumps(output))


if __name__ == '__main__':
    main()
