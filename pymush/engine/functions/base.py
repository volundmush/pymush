from mudstring.patches.text import MudText


class BaseFunction:
    name = None
    aliases = set()
    min_args = None
    max_args = None
    even_args = False
    odd_args = False
    eval_args = True

    def __init__(self, parser, called_as: str, args_data: MudText):
        self.parser = parser
        self.called_as = called_as
        self.args_data = args_data
        self.args = list()
        self.args_eval = list()
        self.args_count = 0
        self.error = False

    def _err_too_many_args(self, num):
        if self.min_args is not None and self.min_args != self.max_args:
            self.output = MudText(
                f"#-1 FUNCTION ({self.name.upper()}) EXPECTS BETWEEN {self.min_args} AND {self.max_args} ARGUMENTS BUT GOT {num}")
        else:
            self.output = MudText(
                f"#-1 FUNCTION ({self.name.upper()}) EXPECTS AT MOST {self.max_args} ARGUMENTS BUT GOT {num}")
        self.error = True

    def _err_too_few_args(self, num):
        if self.max_args is not None and self.min_args != self.max_args:
            self.output = MudText(
                f"#-1 FUNCTION ({self.name.upper()}) EXPECTS BETWEEN {self.min_args} AND {self.max_args} ARGUMENTS BUT GOT {num}")
        else:
            self.output = MudText(
                f"#-1 FUNCTION ({self.name.upper()}) EXPECTS AT LEAST {self.min_args} ARGUMENTS BUT GOT {num}")
        self.error = True

    def _err_uneven_args(self, num):
        self.output = MudText(
            f"#-1 FUNCTION ({self.name.upper()}) EXPECTS EVEN NUMBER OF ARGUMENTS BUT GOT {num}")
        self.error = True

    def _err_even_args(self, num):
        self.output = MudText(
            f"#-1 FUNCTION ({self.name.upper()}) EXPECTS ODD NUMBER OF ARGUMENTS BUT GOT {num}")
        self.error = True

    def split_args(self):
        escaped = False

        remaining = self.args_data
        plain = remaining.plain
        i = -1

        while len(remaining):
            i += 1
            if i > len(remaining):
                break
            c = plain[i]

            if escaped:
                escaped = False
                continue
            else:
                if c == '\\':
                    escaped = True
                elif c == ',':
                    self.args.append(remaining[:i])
                    remaining = remaining[i+1:]
                    plain = remaining.plain

        if remaining:
            self.args.append(remaining)


    def execute(self):
        self.split_args()
        self.args_count = len(self.args)
        c = self.args_count
        if self.max_args is not None and c > self.max_args:
            self._err_too_many_args(c)
            return
        if self.min_args is not None and c < self.min_args:
            self._err_too_few_args(c)
            return
        if self.even_args and c % 2 == 1:
            self._err_uneven_args(c)
            return
        if self.odd_args and c % 2 == 0:
            self._err_even_args(c)
            return
        return self.do_execute()

    def do_execute(self):
        return MudText(f"#-1 FUNCTION {self.name.upper()} IS NOT IMPLEMENTED")


class NotFound(BaseFunction):
    def execute(self):
        return MudText(f"#-1 FUNCTION ({self.called_as.upper()}) NOT FOUND")