import Clutter from 'gi://Clutter';
import Gio from 'gi://Gio';
import GLib from 'gi://GLib';
import GObject from 'gi://GObject';
import St from 'gi://St';

import {Extension} from 'resource:///org/gnome/shell/extensions/extension.js';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import * as PanelMenu from 'resource:///org/gnome/shell/ui/panelMenu.js';
import * as PopupMenu from 'resource:///org/gnome/shell/ui/popupMenu.js';

const APP_NAME = 'jcm-gnome-jira-indicator';
const APP_TITLE = 'Jira Indicator';
const CONFIG_FILE = GLib.build_filenamev([GLib.get_user_config_dir(), APP_NAME, 'config.ini']);
// Remembers the "updated" date of every issue you have already seen (for the ● dots and the (n) counter).
const SEEN_FILE = GLib.build_filenamev([GLib.get_user_state_dir(), APP_NAME, 'seen.json']);
const MAX_BACKOFF_MINUTES = 60;

// Opens a web address or a local file (file://…) in the app the desktop uses for it.
function openUri(uri) {
    try {
        Gio.AppInfo.launch_default_for_uri(uri, null);
    } catch (e) {
        Main.notifyError(APP_TITLE, `Could not open ${uri}: ${e.message}`);
    }
}

// Jira dates look like "2026-10-13T10:02:42.930+0200"; JavaScript needs the offset as "+02:00".
function timeAgo(jiraDate) {
    const date = new Date(jiraDate.replace(/([+-]\d{2})(\d{2})$/, '$1:$2'));
    const minutes = Math.max(0, Math.floor((Date.now() - date.getTime()) / 60000));
    if (minutes < 60)
        return `${minutes} min ago`;
    if (minutes < 60 * 24)
        return `${Math.floor(minutes / 60)} h ago`;
    return `${Math.floor(minutes / (60 * 24))} d ago`;
}

const JiraIndicator = GObject.registerClass(
class JiraIndicator extends PanelMenu.Button {
    _init(extension) {
        super._init(0.0, APP_TITLE);
        this._extensionPath = extension.path;
        this._metadata = extension.metadata;
        this._scriptPath = GLib.build_filenamev([extension.path, 'fetch.py']);
        this._data = {
            title: 'Jira', refresh_minutes: 5, summary_max_chars: 60, visible_issues: 10, help: 'online',
            issues: [], error: null, retry_after_minutes: null,
        };
        this._loaded = false; // false until the first refresh finishes: the Loading state
        this._failures = 0; // failed refreshes in a row, for the backoff
        this._seen = this._loadSeen();
        this._lastCheck = null;
        this._issueItems = [];
        this._issueScroll = null;
        this._timerId = 0;
        this._cancellable = new Gio.Cancellable();

        this._label = new St.Label({text: 'Jira …', y_align: Clutter.ActorAlign.CENTER});
        this.add_child(this._label);

        // Closing the menu counts as "I have seen everything in it", like reading a notification list.
        this.menu.connect('open-state-changed', (_menu, isOpen) => {
            if (isOpen)
                this._fitIssueList();
            else
                this._markAllSeen();
        });

        this._buildMenu();
        this._refresh();
    }

    // Runs fetch.py without blocking the desktop, then hands its JSON to _onData().
    _refresh() {
        try {
            const proc = Gio.Subprocess.new(['python3', this._scriptPath],
                Gio.SubprocessFlags.STDOUT_PIPE | Gio.SubprocessFlags.STDERR_PIPE);
            proc.communicate_utf8_async(null, this._cancellable, (_proc, result) => {
                try {
                    const [, stdout, stderr] = proc.communicate_utf8_finish(result);
                    if (!stdout)
                        throw new Error(stderr.trim() || 'fetch.py printed nothing');
                    this._onData(JSON.parse(stdout));
                } catch (e) {
                    if (!e.matches?.(Gio.IOErrorEnum, Gio.IOErrorEnum.CANCELLED))
                        this._onData({error: e.message});
                }
            });
        } catch (e) {
            this._onData({error: e.message});
        }
    }

    _onData(data) {
        // On an error, keep showing the last good list with a ⚠ instead of an empty menu.
        const issues = data.error ? this._data.issues : data.issues;
        this._data = {...this._data, ...data, issues};
        this._loaded = true;
        this._failures = data.error ? this._failures + 1 : 0;
        this._lastCheck = new Date();
        if (this._seen === null && !data.error)
            this._markAllSeen(); // very first run: nothing counts as new
        this._update();
        this._scheduleNext();
    }

    // Normal interval; Jira's Retry-After when it sent one; otherwise double the wait after each failure.
    _nextMinutes() {
        const {refresh_minutes: minutes, retry_after_minutes: retryAfter} = this._data;
        if (this._failures > 0 && retryAfter)
            return retryAfter;
        if (this._failures === 0)
            return minutes;
        return Math.max(minutes, Math.min(MAX_BACKOFF_MINUTES, minutes * 2 ** this._failures));
    }

    // A one-shot timer, set again after every refresh, so a changed refresh_minutes applies straight away.
    _scheduleNext() {
        if (this._timerId)
            GLib.Source.remove(this._timerId);
        this._timerId = GLib.timeout_add_seconds(GLib.PRIORITY_DEFAULT, this._nextMinutes() * 60, () => {
            this._timerId = 0;
            this._refresh();
            return GLib.SOURCE_REMOVE;
        });
    }

    _isNew(issue) {
        return this._seen !== null && this._seen[issue.key] !== issue.updated;
    }

    _update() {
        const {title, issues, error} = this._data;
        let text = `${title} …`;
        if (this._loaded) {
            const newCount = issues.filter(issue => this._isNew(issue)).length;
            text = `${title} ${issues.length}`;
            if (newCount > 0)
                text += ` (${newCount})`;
            if (error)
                text += ' ⚠';
        }
        this._label.set_text(text);
        this._buildMenu();
    }

    _buildMenu() {
        const {issues, error, summary_max_chars: maxChars} = this._data;
        this.menu.removeAll();

        if (!this._loaded)
            this._addMenuInfo('Loading…');
        else if (error)
            this._addMenuInfo(`⚠ ${error}`);
        else if (issues.length === 0)
            this._addMenuInfo('Nothing needs you right now');

        // The issue rows sit in their own scrolling list, so a long list never pushes the actions off the screen.
        const list = new PopupMenu.PopupMenuSection();
        this._issueItems = issues.map(issue => {
            const dot = this._isNew(issue) ? '●' : '   ';
            const summary = issue.summary.length > maxChars ? `${issue.summary.slice(0, maxChars)}…` : issue.summary;
            const item = new PopupMenu.PopupMenuItem(
                `${dot} ${issue.key}  [${issue.status}]  ${summary}  · ${timeAgo(issue.updated)}`);
            item.connect('activate', () => {
                openUri(issue.url);
                this.menu.close(); // rows inside the scroll view are not linked to the menu, so close it here
            });
            list.addMenuItem(item);
            return item;
        });
        this._issueScroll = new St.ScrollView({
            style_class: 'vfade',
            hscrollbar_policy: St.PolicyType.NEVER,
            vscrollbar_policy: St.PolicyType.AUTOMATIC,
            child: list.actor,
        });
        const listSection = new PopupMenu.PopupMenuSection();
        listSection.actor.add_child(this._issueScroll);
        this.menu.addMenuItem(listSection);
        this._fitIssueList();

        this.menu.addMenuItem(new PopupMenu.PopupSeparatorMenuItem());
        const lastCheck = this._lastCheck ? this._lastCheck.toLocaleTimeString() : 'never';
        this._addMenuAction(`Refresh now  (last check ${lastCheck})`, () => this._refresh());
        this._addMenuAction('Edit settings…', () => openUri(GLib.filename_to_uri(CONFIG_FILE, null)));
        this._addMenuAction('Help', () => openUri(this._helpUri()));
    }

    // Caps the list at visible_issues rows; the rest is reached by scrolling. Measured from a real row so it
    // follows the font size and display scaling.
    _fitIssueList() {
        if (!this._issueScroll || this._issueItems.length <= this._data.visible_issues)
            return;
        const [, rowHeight] = this._issueItems[0].get_preferred_height(-1);
        if (rowHeight > 0)
            this._issueScroll.height = rowHeight * this._data.visible_issues;
    }

    _addMenuInfo(text) {
        this.menu.addMenuItem(new PopupMenu.PopupMenuItem(text, {reactive: false}));
    }

    _addMenuAction(label, callback) {
        const item = new PopupMenu.PopupMenuItem(label);
        item.connect('activate', callback);
        this.menu.addMenuItem(item);
    }

    // "online": the manual of the installed version, on GitHub (release tag v<version-name>).
    // "local", or no url in metadata.json: the MANUAL.md installed with the extension (works offline).
    _helpUri() {
        const {url, 'version-name': version} = this._metadata;
        if (this._data.help === 'online' && url && version)
            return `${url}/blob/v${version}/MANUAL.md`;
        return GLib.filename_to_uri(GLib.build_filenamev([this._extensionPath, 'MANUAL.md']), null);
    }

    _loadSeen() {
        try {
            const [, bytes] = GLib.file_get_contents(SEEN_FILE);
            return JSON.parse(new TextDecoder().decode(bytes));
        } catch {
            return null; // first run: the file does not exist yet
        }
    }

    _markAllSeen() {
        this._seen = Object.fromEntries(this._data.issues.map(issue => [issue.key, issue.updated]));
        GLib.mkdir_with_parents(GLib.path_get_dirname(SEEN_FILE), 0o700);
        GLib.file_set_contents(SEEN_FILE, JSON.stringify(this._seen));
        this._update();
    }

    destroy() {
        this._cancellable.cancel();
        if (this._timerId)
            GLib.Source.remove(this._timerId);
        this._timerId = 0;
        super.destroy();
    }
});

export default class JiraIndicatorExtension extends Extension {
    enable() {
        this._indicator = new JiraIndicator(this);
        Main.panel.addToStatusArea(this.uuid, this._indicator);
    }

    disable() {
        this._indicator?.destroy();
        this._indicator = null;
    }
}
