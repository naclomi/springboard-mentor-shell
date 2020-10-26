import time

import urwid


def spinner():
    frames = r"/-\|/-\|"
    idx = 0
    while True:
        yield " "+frames[idx]+" "
        idx += 1
        if idx >= len(frames):
            idx = 0


class PopupDialog(urwid.Overlay):
    def __init__(self, loop, internal_widget, attach, width=None, height=None, cancelable=True):
        self.loop = loop
        self.original_widget = loop.widget
        self.internal_widget = internal_widget
        self.cancelable = cancelable
        if width is None:
            width = 'pack'
        if width is None:
            height = 'pack'
        super().__init__(urwid.LineBox(internal_widget), self.original_widget, 'center', width, 'middle', height)
        if attach:
            self.attach()

    def attach(self):
        if self.loop.widget is not self:
            if isinstance(self.loop.widget, PopupDialog):
                self.loop.widget.detach()
            self.original_widget = self.loop.widget
            self.loop.widget = self
            return True
        return False

    def detach(self):
        if self.loop.widget is self:
            self.loop.widget = self.original_widget
            return True
        return False


    def selectable(self):
        return True

    def keypress(self, size, key):
        if self.cancelable:
        
            if key in ('esc', 'ctrl w'):
                self.detach()
                return None
        super().keypress(size, key)
        return None


class WaitDialog(PopupDialog):
    ANIMATION_SPEED = 0.1
    SPINNER = r"/-\|/-\|"
    def __init__(self, loop, text, attach=True):
        self.spinner = spinner()
        self.spinner_widget = urwid.Text(next(self.spinner))
        self.label = urwid.Text(text)
        dialog = urwid.Filler(urwid.Columns((
            ('pack',self.spinner_widget),
            self.label
        )), 'middle')
        super().__init__(loop, dialog, attach, 40, 4, cancelable=False)

    def get_text(self, *args, **kwargs):
        return self.label.get_text(*args, **kwargs)

    def set_text(self, *args, **kwargs):
        return self.label.set_text(*args, **kwargs)

    def attach(self):
        if super().attach():
            self.animation_alarm = self.loop.set_alarm_in(
                self.ANIMATION_SPEED, self.update_animation, None)

    def detach(self):
        if super().detach():
            self.loop.remove_alarm(self.animation_alarm)

    def update_animation(self, loop, unused=None):
        self.spinner_widget.set_text(next(self.spinner))
        self.animation_alarm = loop.set_alarm_in(self.ANIMATION_SPEED, self.update_animation, unused)

    def keypress(self, size, key):
        super().keypress(size, key)
        return None


class DoubleClickable(object):
    DOUBLE_CLICK_SPEED = 0.3

    def __init__(self, *args, **kwargs):
        self.last_click = 0
        return super().__init__(*args, **kwargs)

    def mouse_event(self, size, event, button, col, row, focus):
        if event == "mouse press" and button == 1:
            now = time.time()
            delta = now - self.last_click
            self.last_click = now
            if delta < self.DOUBLE_CLICK_SPEED:
                urwid.emit_signal(self, "doubleclick")
                return True
        try:
            return super().mouse_event(size, event, button, col, row, focus)
        except AttributeError:
            return True


class HighlightableListRow(DoubleClickable, urwid.WidgetWrap):
    __metaclass__ = urwid.MetaSignals
    signals = ["doubleclick", "click"]

    def __init__(self, base_widget):
        return super().__init__(urwid.AttrMap(
            base_widget,
            attr_map={None: 'list_entry'},
            focus_map={None: 'list_selected'}
        ))

    def selectable(self):
        return True

    def keypress(self, size, key):
        if key in (" ", "enter"):
            urwid.emit_signal(self, "click")
            return None
        return key


class MouseWheelListBox(urwid.ListBox):
    def mouse_event(self, size, event, button, col, row, focus):
        try:
            if event.endswith("mouse press"):
                if button == 5:
                    self.set_focus(self.body.get_prev(self.focus_position)[1])
                    return True
                elif button == 4:
                    self.set_focus(self.body.get_next(self.focus_position)[1])
                    return True
        except Exception:
            pass
        return super().mouse_event(size, event, button, col, row, focus)

class SelectorCarousel(HighlightableListRow):
    __metaclass__ = urwid.MetaSignals
    signals = ["doubleclick", "click"]

    def __init__(self, entries, focus_position=0):
        self.entries = entries
        self.position = focus_position
        self.label_widget = urwid.Text("")
        super().__init__(self.label_widget)
        self.label_widget.set_text(self.carouselText(self.position))


    def carouselText(self, position):
        prev_entries = "." * self.position
        post_entries = "." * (len(self.entries) - self.position - 1)
        return (prev_entries + self.entries[self.position] +
                post_entries)

    def cycle(self, clockwise):
        if clockwise:
            self.position += 1
            if self.position >= len(self.entries):
                self.position = 0
        else:
            self.position -= 1
            if self.position < 0:
                self.position = len(self.entries) - 1
        self.label_widget.set_text(self.carouselText(self.position))
        urwid.emit_signal(self, "click")

    def mouse_event(self, size, event, button, col, row, focus):
        if button == 0:
            self.cycle(True)
            return True
        return False

    def keypress(self, size, key):
        if key in ("enter", " "):
            self.cycle(True)
            return None
        elif key == "left":
            self.cycle(False)
            return None
        elif key == "right":
            self.cycle(True)
            return None
        return key


class FormatEdit(urwid.Text):
    def __init__(self, format_string, background_text, initial_value=None):
        # TODO initial value
        super().__init__(background_text)
        self.format_string = format_string
        self.backgroundWidget = self
        self.editWidget = urwid.Edit()
        self.composeWidget = urwid.Overlay(
            self.editWidget, self.backgroundWidget,
            'left', len(background_text), 'middle', 1)

    def render(self, size, focus):
        return self.composeWidget.render((size[0],1), focus)

class DateEdit(urwid.SelectableIcon):
    def __init__(self, initial_value=None):
        # TODO initial value
        self.sep = "/"
        self.internal_text = ""
        super().__init__("MM/DD/YYYY")

    def selectable(self):
        return True

    def updateText(self):
        month = self.internal_text[:2].ljust(2, "M")
        day = self.internal_text[2:4].ljust(2, "D")
        year = self.internal_text[4:].ljust(4, "Y")
        self.set_text(
            month+self.sep+day+self.sep+year
        )

    def keypress(self, size, key):
        if key in "0123456789":
            if len(self.internal_text) < 8:
                self.internal_text += key
                self.updateText()
                if len(self.internal_text) == 8:
                    return 'right'
            return None
        elif key == "backspace":
            if len(self.internal_text) == 0:
                return 'left'
            self.internal_text = self.internal_text[:-1]
            self.updateText()
            return None
        return key

    def get_cursor_coords(self, size):
        if self._cursor_position > len(self.text):
            return None
        (maxcol,) = size
        trans = self.get_line_translation(maxcol)
        cursor_position = len(self.internal_text)
        if cursor_position >= 2:
            cursor_position += 1
        if cursor_position >= 5:
            cursor_position += 1
        if cursor_position > 9:
            cursor_position = 9
        x, y = urwid.text_layout.calc_coords(self.text, trans, cursor_position)
        if maxcol <= x:
            return None
        return x, y