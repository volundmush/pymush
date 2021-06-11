import math
from typing import Optional

from rich.text import Text

from mudstring.encodings.pennmush import ansi_fun, ansi_fun_style

from rich import box, table, columns


class BaseFormatter:
    def __init__(self):
        # if this is true, then .send() will ONLY send OOB data if the connection supports OOB - text will not be sent.
        self.prefer_oob = False

    def text(
        self,
        formatter,
        conn: "Connection",
        user: Optional["User"] = None,
        character: Optional["GameObject"] = None,
    ):
        """
        All formatters must implement text.
        """
        pass

    def oob(
        self,
        formatter,
        conn: "Connection",
        user: Optional["User"] = None,
        character: Optional["GameObject"] = None,
    ):
        """
        All formatters must implement data.
        This function returns data that will be sent over OOB to the client.
        """
        pass

    def send(
        self,
        formatter,
        conn: "Connection",
        user: Optional["User"] = None,
        character: Optional["GameObject"] = None,
    ):
        oob = conn.details.oob

        if oob:
            self.oob(formatter, conn, user, character)
            if self.prefer_oob:
                return

        self.text(formatter, conn, user, character)


class BaseHeader(BaseFormatter):
    mode = "header"

    def __init__(
        self,
        text="",
        fill_character=None,
        edge_character=None,
        color=True,
        color_category="system",
    ):
        if isinstance(text, Text):
            self.contained_text = text.plain
        else:
            self.contained_text = text
        if self.contained_text is None:
            self.contained_text = ""
        self.fill_character = fill_character
        self.edge_character = edge_character
        self.color = color
        self.color_category = color_category

    def text(
        self,
        formatter,
        conn: "Connection",
        user: Optional["User"] = None,
        character: Optional["GameObject"] = None,
    ):
        colors = dict()
        styler = formatter.style
        colors["border"] = styler.get(self.color_category, "border_color")
        colors["headertext"] = styler.get(
            self.color_category, f"{self.mode}_text_color"
        )
        colors["headerstar"] = styler.get(
            self.color_category, f"{self.mode}_star_color"
        )
        width = conn.details.width
        if self.edge_character:
            width -= 2

        contained_text = self.contained_text.strip()
        if contained_text:
            if self.color:
                header_text = ansi_fun(colors["headertext"], contained_text)
            if self.mode == "header":
                col_star = ansi_fun(colors["headerstar"], "*")
                begin_center = ansi_fun(colors["border"], "<") + col_star
                end_center = col_star + ansi_fun(colors["border"], ">")
                center_string = begin_center + " " + header_text + " " + end_center
            else:
                center_string = (
                    ansi_fun(None, " ")
                    + ansi_fun(colors["headertext"], header_text)
                    + " "
                )
        else:
            center_string = ansi_fun(None, "")

        fill_character = styler.get(self.color_category, f"{self.mode}_fill")

        remain_fill = width - len(center_string)
        if remain_fill % 2 == 0:
            right_width = remain_fill / 2
            left_width = remain_fill / 2
        else:
            right_width = math.floor(remain_fill / 2)
            left_width = math.ceil(remain_fill / 2)
        right_fill = ansi_fun(colors["border"], fill_character * int(right_width))
        left_fill = ansi_fun(colors["border"], fill_character * int(left_width))

        if self.edge_character:
            edge_fill = ansi_fun(colors["border"], self.edge_character)
            main_string = center_string
            final_send = edge_fill + left_fill + main_string + right_fill + edge_fill
        else:
            final_send = left_fill + center_string + right_fill
        conn.print(final_send)


class Header(BaseHeader):
    mode = "header"


class Subheader(BaseHeader):
    mode = "subheader"


class Separator(BaseHeader):
    mode = "separator"


class Footer(BaseHeader):
    mode = "footer"


class Line(BaseFormatter):
    """
    Just a line of text to display. Nothing fancy about this one!
    """

    def __init__(self, text):
        super().__init__()
        self.data = text

    def text(
        self,
        formatter,
        conn: "Connection",
        user: Optional["User"] = None,
        character: Optional["GameObject"] = None,
    ):
        if self.data:
            conn.print(self.data)


class PyDebug(Line):
    def text(
        self,
        formatter,
        conn: "Connection",
        user: Optional["User"] = None,
        character: Optional["GameObject"] = None,
    ):
        if self.data:
            conn.print_python(self.data)


class PyException(Line):
    def text(
        self,
        formatter,
        conn: "Connection",
        user: Optional["User"] = None,
        character: Optional["GameObject"] = None,
    ):
        conn.print_exception(self.data)


class OOB(BaseFormatter):
    pass


class TabularTable(BaseFormatter):
    def __init__(self, word_list, field_width: int = 26, equal: bool = False):
        self.columns = columns.Columns(word_list, width=field_width, equal=equal)

    def text(
        self,
        formatter,
        conn: "Connection",
        user: Optional["User"] = None,
        character: Optional["GameObject"] = None,
    ):
        conn.print(self.columns)


class Table(BaseFormatter):
    def __init__(self, title: Optional[str] = None, color_category: str = "system"):
        """
        Create an EvTable styled by user preferences.

        Args:
            *args (str or AnsiString): Column headers. If not colored explicitly, these will get colors
                from user options.

        Kwargs:
            any (str, int or dict): EvTable options, including, optionally a `table` dict
                detailing the contents of the table.
        """
        super().__init__()
        self.title = title
        self.rows = list()
        self.columns = list()
        self.color_category = color_category

    def add_row(self, *args):
        self.rows.append(args)

    def add_column(self, title: str, **kwargs):
        self.columns.append((title, kwargs))

    def text(
        self,
        formatter,
        conn: "Connection",
        user: Optional["User"] = None,
        character: Optional["GameObject"] = None,
    ):
        styler = conn.style
        border_style = ansi_fun_style(styler.get(self.color_category, "border_color"))
        column_name_style = ansi_fun_style(
            styler.get(self.color_category, "column_names_color")
        )

        width = conn.details.width

        widths = dict()

        use_box = None if conn.details.screen_reader else box.ASCII

        out_table = table.Table(
            box=use_box, border_style=border_style, width=conn.details.width
        )

        for col in self.columns:
            options = col[1]
            options["style"] = column_name_style
            out_table.add_column(col[0], **options)

        for row in self.rows:
            out_table.add_row(*row)

        conn.print(out_table)


class FormatList:
    __slots__ = ["source", "messages", "relay_chain", "kwargs", "disconnect", "reason"]

    def __init__(self, source, **kwargs):
        self.source = source
        self.messages = list()
        self.relay_chain = list()
        self.kwargs = kwargs
        self.disconnect = False
        self.reason = ""

    @property
    def style(self):
        return self.source.style

    def relay(self, obj):
        c = self.__class__(self.source)
        c.relay_chain = list(self.relay_chain)
        c.messages = list(self.messages)
        c.relay_chain.append(obj)
        return c

    def send(
        self,
        conn: "Connection",
        user: Optional["User"] = None,
        character: Optional["GameObject"] = None,
    ):
        """
        Render the messages in this FormatList for obj.
        """
        for msg in self.messages:
            msg.send(self, conn, user, character)

    def add(self, fmt: BaseFormatter):
        self.messages.append(fmt)

    def data(self, obj):
        return None
