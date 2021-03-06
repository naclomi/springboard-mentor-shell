#!/usr/bin/env python3
import argparse
import os
import sys

import urwid

import mentor_dashboard
import shell_integration
import generic_widgets

import gdrive
import github

DEFAULT_PALETTE = (
    ('titlebar', urwid.BLACK, urwid.LIGHT_GRAY),
    ('list_entry', urwid.DEFAULT, urwid.DEFAULT),
    ('list_selected', urwid.BLACK, urwid.LIGHT_GRAY)
)

class InitializeGdriveClient(generic_widgets.PopupDialog):
    def __init__(self, loop, client, completionCallback=None, failureCallback=None):
        self.completionCallback = completionCallback
        self.failureCallback = failureCallback
        if not client.initialized():
            if not client.initialize(attemptAuthorization=False):
                self.client = client

                continue_button = generic_widgets.HighlightableListRow(urwid.Text("[Continue]"))
                urwid.connect_signal(continue_button, 'click', self.begin)
                urwid.connect_signal(continue_button, 'doubleclick', self.begin)

                cancel_button = generic_widgets.HighlightableListRow(urwid.Text("[Cancel]"))
                urwid.connect_signal(cancel_button, 'click', self.detach)
                urwid.connect_signal(cancel_button, 'doubleclick', self.detach)
                
                self.label = urwid.Text(
                    "To download files from your Google Drive, you "
                    "must first authorize this application to access "
                    "your account. Select 'continue' to begin this "
                    "authorization process.\n")

                self.buttons = urwid.Columns((continue_button, cancel_button))

                widget = urwid.Pile((
                    self.label,
                    self.buttons
                ))
                super().__init__(loop, widget, True, 65)
            else:
                if self.completionCallback is not None:
                    self.completionCallback()
        else:
            if self.completionCallback is not None:
                self.completionCallback()

    def fail(self, failure_text):
        self.label.set_text(failure_text)
        ok_button = generic_widgets.HighlightableListRow(urwid.Text("[Ok]"))
        urwid.connect_signal(ok_button, 'click', self.detach)
        urwid.connect_signal(ok_button, 'doubleclick', self.detach)
        self.buttons.contents = ((ok_button, self.buttons.options('pack')),)
        if self.failureCallback is not None:
            self.failureCallback()

    def begin(self):
        try:
            self.loop.stop()
            self.client.initialize()
            self.loop.start()
            self.detach()
            if self.completionCallback is not None:
                self.completionCallback()
        except FileNotFoundError:
            self.fail(
                "Could not find credentials file in:\n\n%s\n\n"
                "Please put your Google Cloud API credentials "
                "in this location and try again.\n" % self.client.credentials_file)

class FilterDialog(generic_widgets.PopupDialog):
    def __init__(self, loop, initial_filter, set_filter_callback, attach=True):
        self.filter = initial_filter
        self.set_filter_callback = set_filter_callback

        # filter_button = generic_widgets.ToolbarButton("Filter")
        filter_button = generic_widgets.HighlightableListRow(urwid.Text("[Filter]"))
        urwid.connect_signal(filter_button, 'click', self.filter_callback)
        urwid.connect_signal(filter_button, 'doubleclick', self.filter_callback)

        # cancel_button = generic_widgets.ToolbarButton("Cancel")
        cancel_button = generic_widgets.HighlightableListRow(urwid.Text("[Cancel]"))
        urwid.connect_signal(cancel_button, 'click', self.detach)
        urwid.connect_signal(cancel_button, 'doubleclick', self.detach)

        filter_group = []
        self.radios = {
            "show all": urwid.RadioButton(filter_group, "Show all"),
            "hide relative": urwid.RadioButton(filter_group, "Hide submissions")
        }
        self.days_ago_entry = urwid.IntEdit(default=7 )

        # TODO: load from current settings
        widget = urwid.Pile((
            self.radios["show all"],
            self.radios["hide relative"],
            urwid.Columns((
                ('pack', urwid.Text("      more than ")),
                (3, self.days_ago_entry),
                ('pack', urwid.Text("days old")),
            )),
            # TODO:
            # urwid.RadioButton(filter_group, "Show submissions from"),
            # urwid.Columns((
            #     ('pack', urwid.Text('      ')),
            #     ('pack', generic_widgets.FormatEdit("##_##_####", "MM/DD/YYYY")),
            #     ('pack', urwid.Text(' to ')),
            #     # ('pack', generic_widgets.DateEdit())
            # )),
            urwid.Columns((filter_button, cancel_button))
        ))

        self.set_defaults()
        super().__init__(loop, widget, attach, 40)

    def set_defaults(self):
        self.radios["show all"].set_state(
            type(self.filter) is mentor_dashboard.ProjectFilter, do_callback=False)
        self.radios["hide relative"].set_state(
            type(self.filter) is mentor_dashboard.RelativeProjectFilter, do_callback=False)
        if self.radios["hide relative"].state is True:
            self.days_ago_entry.set_edit_text(str(self.filter.days_ago))

    def filter_callback(self):
        new_filter = mentor_dashboard.ProjectFilter()
        if self.radios["show all"].state is True:
            pass
        elif self.radios["hide relative"].state is True:
            new_filter = mentor_dashboard.RelativeProjectFilter(self.days_ago_entry.value())
        self.set_filter_callback(new_filter)
        self.detach()


class OperationsPopup(generic_widgets.PopupDialog):
    def __init__(self, loop, project, attach=True):
        self.project = project
        self.operations = [
            ("Open local folder", self.openLocalUris),
            ("Copy local path to clipboard", self.uriToClipboard),
            ("Open assignment page", self.openAssignmentPage),
            ("Open submission links", self.openWorkLinks)
        ]
        if len(project.solution) > 0:
            self.operations.append(("Open solution", self.openSolution))
        if len(project.rubric) > 0:
            self.operations.append(("Open rubric", self.openRubric))
        option_widgets = []
        for option_name, option_callback in self.operations:
            option_widget = generic_widgets.HighlightableListRow(urwid.Text(option_name))
            urwid.connect_signal(option_widget, 'click', option_callback)
            urwid.connect_signal(option_widget, 'doubleclick', option_callback)
            option_widgets.append(option_widget)
        options_list = urwid.BoxAdapter(generic_widgets.MouseWheelListBox(
            urwid.SimpleFocusListWalker(option_widgets)), len(self.operations))
        super().__init__(loop, options_list, attach, 30)

    def keypress(self, size, key):
        if key in "123456789":
            selection = int(key) - 1
            if selection < len(self.operations):
                self.operations[selection][1]()
            return None
        return super().keypress(size, key)

    def openAssignmentPage(self, *args, **kwargs):
        for link in self.project.projectLinks.values():
            shell_integration.openLink(link)
        self.detach()

    def openSolution(self, *args, **kwargs):
        for link in self.project.solution.values():
            shell_integration.openLink(link)
        self.detach()

    def openRubric(self, *args, **kwargs):
        for link in self.project.rubric.values():
            shell_integration.openLink(link)
        self.detach()

    def openWorkLinks(self, *args, **kwargs):
        for link in self.project.work.values():
            shell_integration.openLink(link)
        self.detach()

    def openLocalUris(self, *args, **kwargs):
        def completion():
            for uri in self.project.getLocalURIs().values():
                shell_integration.openFolder(uri)
        self.detach()
        InitializeGdriveClient(
            self.loop, self.project.download_clients["gdrive"],
            completionCallback=completion)

    def uriToClipboard(self, *args, **kwargs):
        def completion():
            uris = []
            for uri in self.project.getLocalURIs().values():
                uris.append(uri)
            uris = ";".join(uris)
            shell_integration.copyText(uris)
        self.detach()
        InitializeGdriveClient(
            self.loop, self.project.download_clients["gdrive"],
            completionCallback=completion)


class ProjectRow(generic_widgets.HighlightableListRow):
    DATE_FORMAT = "%b %-d %Y"
    HOTKEYS = {
        "detail": ("tab", "right"),
    }

    def __init__(self, project, loop):
        self.project = project
        self.loop = loop
        self.selected_indicator_widget = urwid.Text("")
        self.set_selected(False)
        cells = urwid.Columns([
            ('pack', self.selected_indicator_widget),
            ('pack', urwid.Text(project.unit.ljust(5))),
            ('weight', 70, urwid.Text(project.name)),
            ('pack', urwid.Text(project.date.strftime(self.DATE_FORMAT)))
        ], dividechars=1)
        super().__init__(cells)

    def keypress(self, size, key):
        if key in self.HOTKEYS["detail"]:
            OperationsPopup(self.loop, self.project)
            return None
        return super().keypress(size, key)

    def set_selected(self, value):
        self.selected = value
        self.selected_indicator_widget.set_text("[%s]" % ("*" if value else " "))
        if value is True:
            def completion():
                self.project.open()
            InitializeGdriveClient(
                self.loop, self.project.download_clients["gdrive"],
                completionCallback=completion)
        else:
            self.project.close()


class RadioListbox(generic_widgets.MouseWheelListBox):
    def __init__(self, *args, **kwargs):
        self.cur_selected = None
        super().__init__(*args, **kwargs)

    def update_selected(self, *args, **kwargs):
        if self.cur_selected is not None:
            self.cur_selected.set_selected(False)
        self.cur_selected = self.focus
        self.cur_selected.set_selected(True)

    def keypress(self, size, key):
        if key in (" ", "enter"):
            self.update_selected()
            self.focus.keypress(size, key)
            return None
        return super().keypress(size, key)

class BrowserApplication(object):
    CLIPBOARD_POLL_SPEED = .5
    HOTKEYS = {
        "reload": ("ctrl r",),
        "filter": ("ctrl f",),
        "quit": ("q", "Q")
    }

    def __init__(self, palette, working_dir, download_clients, project_filter, data_source):
        self.data_source = data_source
        self.palette = palette
        self.working_dir = working_dir
        self.download_clients = download_clients

        if self.working_dir is None:
            self.working_dir = os.path.join(os.getcwd(), "downloads")
        self.loop = urwid.MainLoop(None, self.palette,
                                   unhandled_input=self.global_input)
        title_bar = urwid.AttrMap(urwid.Filler(urwid.Padding(urwid.Text("Projects")),'top'),'titlebar')

        if project_filter is None:
            self.project_filter = mentor_dashboard.ProjectFilter()
        else:
            self.project_filter = project_filter

        hotkeys = list(self.HOTKEYS.items()) + list(ProjectRow.HOTKEYS.items())
        hotkeys.sort(key=lambda elem: elem[0])
        hotkey_widgets = []

        for action, hotkey in hotkeys:
            toolbar_button = generic_widgets.ToolbarButton(action.capitalize() + "\n" + "/".join(hotkey))
            hotkey_widgets.append(toolbar_button)
            urwid.connect_signal(toolbar_button, 'click', self.handle_toolbar_click, user_args=[hotkey[0]])

        self.project_list_walker = urwid.SimpleFocusListWalker([])
        self.project_list = RadioListbox(self.project_list_walker)
        self.loop.widget = urwid.Pile((
            (1, title_bar),
            self.project_list,
            (4, urwid.Columns(hotkey_widgets))
        ))
        self.waitDialog = None
        self.downloadDialog = generic_widgets.WaitDialog(self.loop, "Downloading project", attach=False, threadable=True)

    def handle_toolbar_click(self, hotkey):
        self.loop.process_input((hotkey,))

    def set_filter(self, new_filter):
        self.project_filter = new_filter
        self.update_project_ui()

    def poll_clipboard(self, loop, unused=None):
        success = False
        clipboard_result = shell_integration.getHTMLFromClipboard()
        if clipboard_result is not None:
            self.projects = mentor_dashboard.getProjectsFromHTML(
                clipboard_result,
                download_clients=self.download_clients,
                working_dir=self.working_dir,
                startCallback=self.startDownloadDialog,
                progressCallback=self.progressDownloadDialog,
                completionCallback=self.completeDownloadDialog
            )
            success = self.update_project_ui()
        if success:
            if self.waitDialog is not None:
                self.waitDialog.detach()
                self.waitDialog = None
        else:
            self.loop.set_alarm_in(self.CLIPBOARD_POLL_SPEED, self.poll_clipboard, unused)
            if self.waitDialog is None:
                self.waitDialog = generic_widgets.WaitDialog(loop, "Waiting for valid dashboard contents in clipboard")

    def reload_projects(self):
        self.project_list_walker.clear()
        if self.data_source is None:
            self.poll_clipboard(self.loop)
        else:
            self.projects = mentor_dashboard.getProjectsFromHTML(
                self.data_source,
                download_clients=self.download_clients,
                working_dir=self.working_dir,
                startCallback=self.startDownloadDialog,
                progressCallback=self.progressDownloadDialog,
                completionCallback=self.completeDownloadDialog
            )
            self.update_project_ui()

    def update_project_ui(self):
        self.project_list_walker.clear()
        self.displayed_projects = self.project_filter.filter(self.projects)
        if len(self.projects) > 0:
            for project in self.displayed_projects:
                project_widget = ProjectRow(project, self.loop)
                self.project_list_walker.append(project_widget)
                urwid.connect_signal(project_widget, 'doubleclick', self.project_list.update_selected)
            return True
        return False

    def startDownloadDialog(self, service):
        self.downloadDialog.service = service
        self.downloadDialog.threaded_set_text("Downloading project ("+self.downloadDialog.service+")\n 0%")
        self.downloadDialog.threadedAttach()

    def progressDownloadDialog(self, metadata, progress):
        self.downloadDialog.threaded_set_text("Downloading project ("+self.downloadDialog.service+")\n" + str(progress*100) + "%")

    def completeDownloadDialog(self):
        self.downloadDialog.threadedDetach()

    def run(self):
        shell_integration.syncShells(self.working_dir)
        self.reload_projects()
        self.loop.run()

    def global_input(self, key):
        if key in self.HOTKEYS["reload"]:
            self.reload_projects()
            return None
        if key in self.HOTKEYS["filter"]:
            FilterDialog(self.loop, self.project_filter, self.set_filter)
            return None
        if key in self.HOTKEYS["quit"]:
            raise urwid.ExitMainLoop()


def main():
    parser = argparse.ArgumentParser(description='workspace switcher for springboard project submissions')
    parser.add_argument("--stdin", action="store_true",
                        help="Read dashboard data from STDIN")
    parser.add_argument("--gdrive-credentials", metavar="CREDENTIALS_JSON_FILE", type=str,
                        default=gdrive.GdriveClient.CREDENTIALS_FILE,
                        help="Path to JSON file containing GDrive API credentials. Default is \"%s\"" % gdrive.GdriveClient.CREDENTIALS_FILE)
    parser.add_argument("--gdrive-token", metavar="TOKEN_FILE", type=str,
                        default=gdrive.GdriveClient.TOKEN_FILE,
                        help="Path to GDrive API token file. Default is \"%s\"" % gdrive.GdriveClient.TOKEN_FILE)
    parser.add_argument("--hide-older-than", metavar="DAYS", type=int,
                        help="Hide submissions older than DAYS old")
    parser.add_argument("--working-dir", metavar="DOWNLOADS_DIR", type=str,
                        help="Directory to use for downloads and settings")

    args = parser.parse_args()

    palette = DEFAULT_PALETTE
    if args.stdin:
        data_source = sys.stdin.read()
        sys.stdin = open('/dev/tty')
        os.dup2(sys.stdin.fileno(), 0)
    else:
        data_source = None

    if args.hide_older_than:
        project_filter = mentor_dashboard.RelativeProjectFilter(
            days_ago=args.hide_older_than)
    else:
        project_filter = None

    if args.working_dir is not None:
        args.working_dir = os.path.abspath(args.working_dir)

    download_clients = {
        "gdrive": gdrive.GdriveClient(
                    token_file=args.gdrive_token,
                    credentials_file=args.gdrive_credentials),
        "github": github.GithubClient()
    }

    app = BrowserApplication(
        palette,
        download_clients=download_clients,
        project_filter=project_filter,
        working_dir=args.working_dir,
        data_source=data_source)

    try:
        app.run()
    except KeyboardInterrupt:
        pass
    shell_integration.syncShells("")


if __name__ == "__main__":
    main()
    sys.exit(0)
