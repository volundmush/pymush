from rich.text import Text
from ..utils.evtable import EvTable as _EvTable
from ..utils.text import tabular_table
import math


class BaseFormatter:

    def render(self, formatter, obj):
        """
        All formatters must implement render.

        Args:
            obj (TypedObject): A TypedObject / GameObject. This will generally be a connection.

        Returns:
            output (AnsiString): The formatted text, as an AnsiString.
        """
        return Text('')

    def data(self, formatter, obj):
        """
        All formatters must implement data.
        This function returns data that will be sent over OOB to the client.

        Args:
            formatter:
            obj:

        Returns:

        """
        return None


class BaseHeader(BaseFormatter):
    mode = "header"

    def __init__(self, text='', fill_character=None, edge_character=None, color=True, color_category='system'):
        if isinstance(text, AnsiString):
            self.text = text.clean
        else:
            self.text = text
        if self.text is None:
            self.text = ''
        self.fill_character = fill_character
        self.edge_character = edge_character
        self.color = color
        self.color_category = color_category

    def render(self, formatter, obj):
        colors = dict()
        styler = obj.style
        colors["border"] = styler.get(self.color_category, "border_color")
        colors["headertext"] = styler.get(self.color_category, f"{self.mode}_text_color")
        colors["headerstar"] = styler.get(self.color_category, f"{self.mode}_star_color")
        width = obj.get_width()
        if self.edge_character:
            width -= 2

        header_text = self.text.strip()
        if self.text:
            if self.color:
                header_text = AnsiString.from_args(colors['headertext'], self.text)
            if self.mode == "header":
                col_star = AnsiString.from_args(colors['headerstar'], '*')
                begin_center = AnsiString.from_args(colors['border'], '<') + col_star
                end_center = col_star + AnsiString.from_args(colors['border'], '>')
                center_string = begin_center + ' ' + header_text + ' ' + end_center

            else:
                center_string = " " + AnsiString.from_args(colors['headertext'], header_text) + " "
        else:
            center_string = ""

        fill_character = styler.get(self.color_category, f"{self.mode}_fill")

        remain_fill = width - len(center_string)
        if remain_fill % 2 == 0:
            right_width = remain_fill / 2
            left_width = remain_fill / 2
        else:
            right_width = math.floor(remain_fill / 2)
            left_width = math.ceil(remain_fill / 2)
        right_fill = AnsiString.from_args(colors["border"], fill_character * int(right_width))
        left_fill = AnsiString.from_args(colors["border"], fill_character * int(left_width))

        if self.edge_character:
            edge_fill = AnsiString.from_args(colors["border"], self.edge_character)
            main_string = center_string
            final_send = edge_fill + left_fill + main_string + right_fill + edge_fill
        else:
            final_send = left_fill + center_string + right_fill
        return final_send


class Header(BaseHeader):
    mode = "header"


class Subheader(BaseHeader):
    mode = "subheader"


class Separator(BaseHeader):
    mode = "separator"


class Footer(BaseHeader):
    mode = "footer"


class Text(BaseFormatter):
    """
    Just a line of text to display. Nothing fancy about this one!
    """
    
    def __init__(self, text):
        self.text = text
        
    def render(self, formatter, obj):
        return self.text


class OOB(BaseFormatter):
    pass


class TabularTable(BaseFormatter):

    def __init__(self, word_list, field_width: int = 26, output_separator: str = ' ', truncate_elements: bool = True):
        self.word_list = word_list
        self.field_width = field_width
        self.output_separator = output_separator
        self.truncate_elements = truncate_elements

    def render(self, formatter, obj):
        return tabular_table(self.word_list, field_width=self.field_width, line_length=obj.get_width(),
                             output_separator=self.output_separator, truncate_elements=self.truncate_elements)



class Table(BaseFormatter):

    def __init__(self, *args, **kwargs):
        """
        Create an EvTable styled by user preferences.

        Args:
            *args (str or AnsiString): Column headers. If not colored explicitly, these will get colors
                from user options.

        Kwargs:
            any (str, int or dict): EvTable options, including, optionally a `table` dict
                detailing the contents of the table.
        """
        self.args = args
        self.kwargs = kwargs
        self.rows = list()
        self.color_category = self.kwargs.pop('color_category', 'system')
        self.h_line_char = self.kwargs.pop("header_line_char", "~")
        self.c_char = self.kwargs.pop("corner_char", "+")
        self.b_left_char = self.kwargs.pop("border_left_char", "|")
        self.b_right_char = self.kwargs.pop("border_right_char", "|")
        self.b_bottom_char = self.kwargs.pop("border_bottom_char", "-")
        self.b_top_char = self.kwargs.pop("border_top_char", "-")

    def add_row(self, *args):
        self.rows.append(args)

    def render(self, formatter, obj):
        styler = obj.style
        border_color = styler.get(self.color_category, "border_color")
        column_color = styler.get(self.color_category, "column_names_color")

        header_line_char = AnsiString.from_args(border_color, self.h_line_char)
        corner_char = AnsiString.from_args(border_color, self.c_char)
        border_left_char = AnsiString.from_args(border_color, self.b_left_char)
        border_right_char = AnsiString.from_args(border_color, self.b_right_char)
        border_bottom_char = AnsiString.from_args(border_color, self.b_bottom_char)
        border_top_char = AnsiString.from_args(border_color, self.b_top_char)

        width = obj.get_width()
        column_names = list()
        widths = dict()
        for i, arg in enumerate(self.args):
            if isinstance(arg, str):
                column_names.append(arg)
            else:
                column_names.append(arg[0])
                widths[i] = arg[1]

        column_names = [AnsiString.from_args(column_color, c) for c in column_names]

        #header_line_char = self.h_line_char
        #corner_char = self.c_char
        #border_left_char = self.b_left_char
        #border_right_char = self.b_right_char
        #border_top_char = self.b_top_char

        table = _EvTable(
            *column_names,
            header_line_char=header_line_char,
            corner_char=corner_char,
            border_left_char=border_left_char,
            border_right_char=border_right_char,
            border_top_char=border_top_char,
            border_bottom_char=border_bottom_char,
            **self.kwargs,
            maxwidth=width,
            width=width,
        )
        for row in self.rows:
            table.add_row(*row)

        for i, w in widths.items():
            table.reformat_column(i, width=w)

        return table.to_ansistring()


class FormatList:
    __slots__ = ["source", "messages", "relay_chain", "kwargs", 'disconnect', 'reason']

    def __init__(self, source, **kwargs):
        self.source = source
        self.messages = list()
        self.relay_chain = list()
        self.kwargs = kwargs
        self.disconnect = False
        self.reason = ''

    def relay(self, obj):
        c = self.__class__(self.source)
        c.relay_chain = list(self.relay_chain)
        c.messages = list(self.messages)
        c.relay_chain.append(obj)
        return c

    def send(self, obj):
        """
        Render the messages in this FormatList for obj.
        """
        text = AnsiString('\n').join([m.render(self, obj) for m in self.messages])
        out = dict()
        c = obj.connection
        if text:
            out['text'] = text.render(ansi=c.ansi, xterm256=c.xterm256, mxp=c.mxp)
        if self.disconnect:
            out['disconnect'] = self.reason
        c.msg(out)

    def add(self, fmt: BaseFormatter):
        self.messages.append(fmt)

    def data(self, obj):
        return None
