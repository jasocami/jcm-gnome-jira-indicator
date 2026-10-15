"""Unit tests for fetch.py. No network: Jira is faked."""
import base64
import configparser
import contextlib
import io
import json
import sys
import tempfile
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


def http_error(code, headers=None, body=None):
    fp = io.BytesIO(json.dumps(body).encode()) if body is not None else None
    return urllib.error.HTTPError('url', code, 'error', headers or {}, fp)


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
        # Never write to the real log
        log_dir = tempfile.TemporaryDirectory()
        self.addCleanup(log_dir.cleanup)
        self.log_path = Path(log_dir.name) / 'state' / 'error.log'
        log_patch = mock.patch('fetch.LOG_PATH', self.log_path)
        log_patch.start()
        self.addCleanup(log_patch.stop)

    @mock.patch('fetch.urllib.request.urlopen')
    def test_prints_issues_and_settings(self, urlopen):
        urlopen.side_effect = [jira_page(['A-1'])]
        output = run_main()
        self.assertIsNone(output['error'])
        self.assertEqual(output['title'], 'Work')
        self.assertEqual(output['refresh_minutes'], 1)  # 0 is raised to the minimum
        self.assertEqual(output['help'], 'online')
        self.assertEqual(output['visible_issues'], 10)  # default when the key is missing
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
    def test_shows_the_reason_jira_gives(self, urlopen):
        urlopen.side_effect = http_error(400, body={'errorMessages': ["Field 'bogus' does not exist."], 'errors': {}})
        output = run_main()
        self.assertEqual(output['error'], "Jira answered HTTP 400: Field 'bogus' does not exist.")

    @mock.patch('fetch.urllib.request.urlopen')
    def test_shows_only_the_status_when_jira_gives_no_reason(self, urlopen):
        urlopen.side_effect = http_error(500)
        output = run_main()
        self.assertEqual(output['error'], 'Jira answered HTTP 500')

    @mock.patch('fetch.urllib.request.urlopen')
    def test_sends_email_and_token_as_basic_auth(self, urlopen):
        urlopen.side_effect = [jira_page([])]
        run_main()
        header = urlopen.call_args.args[0].get_header('Authorization')
        self.assertEqual(header, 'Basic ' + base64.b64encode(b'someone@example.com:secret-token').decode())

    def test_visible_issues_is_at_least_one(self):
        with mock.patch('fetch.load_config', return_value=make_config(CONFIG + 'visible_issues = 0\n')), \
                mock.patch('fetch.urllib.request.urlopen', side_effect=[jira_page([])]):
            output = run_main()
        self.assertEqual(output['visible_issues'], 1)

    def test_reports_a_missing_token(self):
        with mock.patch('fetch.load_config', return_value=make_config(CONFIG.replace('token = secret-token', ''))):
            output = run_main()
        self.assertIn('No API token', output['error'])


    @mock.patch('fetch.urllib.request.urlopen')
    def test_logs_each_error_with_the_time(self, urlopen):
        urlopen.side_effect = http_error(400, body={'errorMessages': ['Bad JQL'], 'errors': {}})
        run_main()
        run_main()
        lines = self.log_path.read_text().splitlines()
        self.assertEqual(len(lines), 2)
        self.assertRegex(lines[0], r'^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}  Jira answered HTTP 400: Bad JQL$')

    @mock.patch('fetch.urllib.request.urlopen')
    def test_does_not_log_a_successful_refresh(self, urlopen):
        urlopen.side_effect = [jira_page(['A-1'])]
        run_main()
        self.assertFalse(self.log_path.exists())

    @mock.patch('fetch.urllib.request.urlopen')
    def test_keeps_only_the_last_lines(self, urlopen):
        self.log_path.parent.mkdir(parents=True)
        self.log_path.write_text(''.join(f'old {n}\n' for n in range(fetch.LOG_MAX_LINES)))
        urlopen.side_effect = http_error(500)
        run_main()
        lines = self.log_path.read_text().splitlines()
        self.assertEqual(len(lines), fetch.LOG_MAX_LINES)
        self.assertEqual(lines[0], 'old 1')
        self.assertIn('Jira answered HTTP 500', lines[-1])

    @mock.patch('fetch.urllib.request.urlopen')
    def test_never_logs_the_token(self, urlopen):
        urlopen.side_effect = http_error(401)
        run_main()
        self.assertNotIn('secret-token', self.log_path.read_text())

    @mock.patch('fetch.urllib.request.urlopen')
    def test_still_reports_the_error_when_the_log_cannot_be_written(self, urlopen):
        urlopen.side_effect = http_error(500)
        with mock.patch('fetch.LOG_PATH', Path('/proc/not-writable/error.log')):
            output = run_main()
        self.assertEqual(output['error'], 'Jira answered HTTP 500')


if __name__ == '__main__':
    unittest.main()
