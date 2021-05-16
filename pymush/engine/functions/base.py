from rich.text import Text


class BaseFunction:
    name = None
    aliases = set()
    min_args = None
    max_args = None
    even_args = False
    odd_args = False
    eval_args = True

    def __init__(self, entry, called_as, remaining):
        self.entry = entry
        self.called_as = called_as
        self.output = ''
        self.remaining = remaining
        self.args = list()
        self.args_eval = list()
        self.args_count = 0
        self.error = False

    def _err_too_many_args(self, num):
        if self.min_args is not None and self.min_args != self.max_args:
            self.output = AnsiString(
                f"#-1 FUNCTION ({self.name.upper()}) EXPECTS BETWEEN {self.min_args} AND {self.max_args} ARGUMENTS BUT GOT {num}")
        else:
            self.output = AnsiString(
                f"#-1 FUNCTION ({self.name.upper()}) EXPECTS AT MOST {self.max_args} ARGUMENTS BUT GOT {num}")
        self.error = True

    def _err_too_few_args(self, num):
        if self.max_args is not None and self.min_args != self.max_args:
            self.output = AnsiString(
                f"#-1 FUNCTION ({self.name.upper()}) EXPECTS BETWEEN {self.min_args} AND {self.max_args} ARGUMENTS BUT GOT {num}")
        else:
            self.output = AnsiString(
                f"#-1 FUNCTION ({self.name.upper()}) EXPECTS AT LEAST {self.min_args} ARGUMENTS BUT GOT {num}")
        self.error = True

    def _err_uneven_args(self, num):
        self.output = AnsiString(
            f"#-1 FUNCTION ({self.name.upper()}) EXPECTS EVEN NUMBER OF ARGUMENTS BUT GOT {num}")
        self.error = True

    def _err_even_args(self, num):
        self.output = AnsiString(
            f"#-1 FUNCTION ({self.name.upper()}) EXPECTS ODD NUMBER OF ARGUMENTS BUT GOT {num}")
        self.error = True

    def gather_arg(self, noeval=False):
        data, self.remaining, stopped = self.entry.evaluate(self.remaining, stop_at=[')', ','], noeval=noeval)
        return data, stopped

    def gather_all_args(self, noeval=False):
        stopped = ','
        while stopped == ',':
            data, stopped = self.gather_arg(noeval)
            self.args_eval.append(data)

    def execute(self):
        self.gather_all_args()
        self.args_count = len(self.args_eval)
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
        self.do_execute()

    def do_execute(self):
        self.output = f"#-1 FUNCTION {self.name.upper()} IS NOT IMPLEMENTED"
        self.error = True


class NotFound(BaseFunction):
    def execute(self):
        self.gather_all_args(noeval=True)
        self.output = f"#-1 FUNCTION ({self.called_as.upper()}) NOT FOUND"
        self.error = True