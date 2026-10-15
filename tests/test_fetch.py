"""Unit tests for fetch.py. No network: Jira is faked."""
import base64
import configparser
import contextlib
import io
import json
import sys
import unittest
import urllib.error
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import fetch  # noqa: E402

CONFIG = """
[jira]
domain = example.atlassian.net
email = someone@example.com
token = secret-token
jql = assignee = currentUser()

[indicator]
title = Work
refresh_minutes = 0
"""


def make_config(text=CONFIG):
    config = configparser.ConfigParser(interpolation=None)
    config.read_string(text)
    return config


def jira_page(keys, next_token=None):
    """A fake Jira search response: one page with the given issue keys."""
    issues = [
        {'key': key, 'fields': {'summary': f'Summary {key}', 'status': {'name': 'TO DO'}, 'updated': '2026-10-13'}}
        for key in keys
    ]
    payload = {'issues': issues}
    if next_token:
        payload['nextPageToken'] = next_token
    return io.BytesIO(json.dumps(payload).encode())


def http_error(code, headers=None):
    return urllib.error.HTTPError('url', code, 'error', headers or {}, None)


def run_main():
    """Run fetch.main() and return what it printed, parsed."""
    stdout = io.StringIO()
    with contextlib.redirect_stdout(stdout):
        fetch.main()
    return json.loads(stdout.getvalue())


class SearchTests(unittest.TestCase):
    @mock.patch('fetch.urllib.request.urlopen')
    def test_follows_pages_until_there_is_no_next_token(self, urlopen):
        urlopen.side_effect = [jira_page(['A-1', 'A-2'], next_token='page2'), jira_page(['A-3'])]
        issues = fetch.search('example.atlassian.net', 'someone@example.com', 'token', 'jql', 100)
        self.assertEqual([issue['key'] for issue in issues], ['A-1', 'A-2', 'A-3'])
        second_url = urlopen.call_args_list[1].args[0].full_url
        self.assertIn('nextPageToken=page2', second_url)

    @mock.patch('fetch.urllib.request.urlopen')
    def test_stops_at_max_results(self, urlopen):
        urlopen.side_effect = [jira_page(['A-1', 'A-2', 'A-3'], next_token='page2')]
        issues = fetch.search('example.atlassian.net', 'someone@example.com', 'token', 'jql', 2)
        self.assertEqual(len(issues), 2)
        self.assertEqual(urlopen.call_count, 1)


class MainTests(unittest.TestCase):
    def setUp(self):
        patch = mock.patch('fetch.load_config', return_value=make_config())
        patch.start()
        self.addCleanup(patch.stop)

    @mock.patch('fetch.urllib.request.urlopen')
    def test_prints_issues_and_settings(self, urlopen):
        urlopen.side_effect = [jira_page(['A-1'])]
        output = run_main()
        self.assertIsNone(output['error'])
        self.assertEqual(output['title'], 'Work')
        self.assertEqual(output['refresh_minutes'], 1)  # 0 is raised to the minimum
        self.assertEqual(output['help'], 'online')
        self.assertEqual(output['issues'][0]['url'], 'https://example.atlassian.net/browse/A-1')

    @mock.patch('fetch.urllib.request.urlopen')
    def test_reports_a_rejected_login(self, urlopen):
        urlopen.side_effect = http_error(401)
        output = run_main()
        self.assertIn('rejected the login', output['error'])
        self.assertEqual(output['issues'], [])

    @mock.patch('fetch.urllib.request.urlopen')
    def test_waits_when_rate_limited(self, urlopen):
        urlopen.side_effect = http_error(429, {'Retry-After': '120'})
        output = run_main()
        self.assertIn('rate limiting', output['error'])
        self.assertEqual(output['retry_after_minutes'], 2)

    @mock.patch('fetch.urllib.request.urlopen')
    def test_rate_limit_without_header_uses_the_default(self, urlopen):
        urlopen.side_effect = http_error(429)
        output = run_main()
        self.assertEqual(output['retry_after_minutes'], 10)

    @mock.patch('fetch.urllib.request.urlopen')
    def test_sends_email_and_token_as_basic_auth(self, urlopen):
        urlopen.side_effect = [jira_page([])]
        run_main()
        header = urlopen.call_args.args[0].get_header('Authorization')
        self.assertEqual(header, 'Basic ' + base64.b64encode(b'someone@example.com:secret-token').decode())

    def test_reports_a_missing_token(self):
        with mock.patch('fetch.load_config', return_value=make_config(CONFIG.replace('token = secret-token', ''))):
            output = run_main()
        self.assertIn('No API token', output['error'])


if __name__ == '__main__':
    unittest.main()
