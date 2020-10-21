#!/usr/bin/env python3
import argparse
import os
import sys
import time
import urwid

import mentor_dashboard
import shell_integration
import generic_widgets

DEFAULT_PALETTE = (
    ('titlebar', urwid.BLACK, urwid.LIGHT_GRAY),
    ('list_entry', urwid.DEFAULT, urwid.DEFAULT),
    ('list_selected', urwid.BLACK, urwid.LIGHT_GRAY)
)

# TODO: find another way to do this
global_loop = None

class FilterDialog(generic_widgets.PopupDialog):
    def __init__(self, loop, attach=True):
        widget = urwid.Filler(urwid.Padding(urwid.Text("Filter\nShow projects from:\nafter last [Wednsday]")))
        super().__init__(loop, widget, attach, 40, 40)

class OperationsPopup(generic_widgets.PopupDialog):
    def __init__(self, loop, project, attach=True):
        self.project = project
        self.operations = [
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

class ProjectRow(generic_widgets.HighlightableListRow):
    def __init__(self, project):
        self.project = project
        self.selected_indicator_widget = urwid.Text("")
        self.set_selected(False)
        cells = urwid.Columns([
            ('pack', self.selected_indicator_widget),
            ('pack', urwid.Text(project.unit)),
            ('weight', 70, urwid.Text(project.name)),
            ('pack', urwid.Text(project.date))
        ], dividechars=1)
        super().__init__(cells)

    def keypress(self, size, key):
        if key in ("tab", "right"):
            global global_loop
            OperationsPopup(global_loop, self.project)
        return super().keypress(size, key)

    def set_selected(self, value):
        self.selected = value
        self.selected_indicator_widget.set_text("[%s]" % ("*" if value else " "))
        if value is True:
            self.project.open()
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
        "reload": "ctrl r",
        "filter": "ctrl f"
    }

    def __init__(self, palette, data_source=None):
        global global_loop
        self.data_source = data_source
        self.palette = palette
        self.loop = urwid.MainLoop(None, self.palette,
                                   unhandled_input=self.global_input)
        global_loop = self.loop
        title_bar = urwid.AttrMap(urwid.Filler(urwid.Padding(urwid.Text("Projects")),'top'),'titlebar')

        self.project_list_walker = urwid.SimpleFocusListWalker([])
        self.project_list = RadioListbox(self.project_list_walker)
        self.loop.widget = urwid.Pile((
            (1, title_bar),
            self.project_list
        ))
        self.waitDialog = None

    def poll_clipboard(self, loop, unused=None):
        success = False
        clipboard_result = mentor_dashboard.getHTMLFromClipboard()
        if clipboard_result is not None:
            success = self.update_project_ui(clipboard_result)
            self.projects = mentor_dashboard.getProjectsFromHTML(clipboard_result)
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
            self.update_project_ui(self.data_source)

    def update_project_ui(self, html):
        self.projects = mentor_dashboard.getProjectsFromHTML(html)
        if len(self.projects) > 0:
            for project in self.projects:
                # project.startCallback = self.startDownloadDialog
                # project.progressCallback = self.progressDownloadDialog
                # project.completionCallback = self.completeDownloadDialog
                project_widget = ProjectRow(project)
                self.project_list_walker.append(project_widget)
                urwid.connect_signal(project_widget, 'doubleclick', self.project_list.update_selected)
            return True
        return False


    def startDownloadDialog(self):
        self.waitDialog = generic_widgets.WaitDialog(self.loop, "Downloading project")
        self.loop.draw_screen()

    def progressDownloadDialog(self, metadata, progress):
        # self.waitDialog.setText(self.waitDialog.getT)
        pass

    def completeDownloadDialog(self):
        self.waitDialog.detach()
        self.waitDialog = None

    def run(self):
        self.reload_projects()
        self.loop.run()

    def global_input(self, key):
        if key == self.HOTKEYS["reload"]:
            self.reload_projects()
            return None
        if key == self.HOTKEYS["filter"]:
            FilterDialog(self.loop)
        if key in ('q', 'Q'):
            raise urwid.ExitMainLoop()


def main():
    parser = argparse.ArgumentParser(description='workspace switcher for springboard project submissions')
    parser.add_argument("--stdin", action="store_true",
                        help="Read dashboard data from STDIN")
    args = parser.parse_args()

    palette = DEFAULT_PALETTE
    if args.stdin:
        data_source = sys.stdin.read()
        sys.stdin = open('/dev/tty')
        os.dup2(sys.stdin.fileno(), 0)
    else:
        data_source = None
    app = BrowserApplication(palette, data_source)
    app.run()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
    sys.exit(0)
