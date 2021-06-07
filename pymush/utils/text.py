import re
from mudstring.patches.text import MudText, OLD_TEXT
from typing import Optional, Union, List, Tuple, Set, Dict


def tabular_table(word_list=None, field_width=26, line_length=78, output_separator=" ", truncate_elements=True):
    """
    This function returns a tabulated string composed of a basic list of words.
    """
    if not word_list:
        word_list = list()
    elements = word_list
    if truncate_elements:
        elements = [entry[:field_width] for entry in elements]
    elements = [entry.ljust(field_width) for entry in elements]
    separator = AnsiString(output_separator)
    lines = list()
    line = AnsiString()
    start = True
    for elem in elements:
        if start:
            line += elem
            start = False
        else:
            if len(line) + field_width + len(separator) <= line_length:
                line += separator
                line += elem
            else:
                lines.append(line)
                line = AnsiString()
                line += elem
    if line:
        lines.append(line)
    return AnsiString('\n').join(lines)


def dramatic_capitalize(capitalize_string=''):
    if isinstance(capitalize_string, AnsiString):
        capitalize_string = capitalize_string.clean
    capitalize_string = re.sub(r"(?i)(?:^|(?<=[_\/\-\|\s()\+]))(?P<name1>[a-z]+)",
                               lambda find: find.group('name1').capitalize(), capitalize_string.lower())
    capitalize_string = re.sub(r"(?i)\b(of|the|a|and|in)\b", lambda find: find.group(1).lower(), capitalize_string)
    capitalize_string = re.sub(r"(?i)(^|(?<=[(\|\/]))(of|the|a|and|in)",
                               lambda find: find.group(1) + find.group(2).capitalize(), capitalize_string)
    return capitalize_string


SYSTEM_CHARACTERS = ('/', '|', '=', ',')


class Speech:
    """
    This class is used for rendering an entity's speech to other viewers.
    It is meant to render speech from a player or character. The output replicates MUSH-style
    speech from varying input. Intended output:

    If input = ':blah.', output = 'Character blah.'
    If input = ';blah.', output = 'Characterblah.'
    If input = |blah', output = 'blah'
    If input = 'blah.', output = 'Character says, "Blah,"'

    """
    re_speech = re.compile(r'(?s)"(?P<found>.*?)"')
    re_name = re.compile(r"\^\^\^(?P<thing_id>\d+)\:(?P<thing_name>[^^]+)\^\^\^")
    speech_dict = {':': 1, ';': 2, '^': 3, '"': 0, "'": 0}

    def __init__(self, speaker=None, speech_text=None, alternate_name=None, title=None, mode='ooc', targets=None,
                 rendered_text=None, action_string="says", controller="character", color_mode='channel'):

        self.controller = athanor.CONTROLLER_MANAGER.get(controller)
        if targets:
            self.targets = [f'^^^{char.id}:{char.key}^^^' for char in targets]
        else:
            self.targets = []
        self.mode = mode
        self.color_mode = color_mode
        self.title = title
        self.speaker = speaker
        self.action_string = action_string

        if alternate_name:
            self.alternate_name = alternate_name
            self.display_name = alternate_name
            self.markup_name = alternate_name
        else:
            self.display_name = str(speaker)
            self.alternate_name = False
            self.markup_name = f'^^^{speaker.id}:{speaker.key}^^^'

        speech_first = speech_text[:1]
        if speech_first in self.speech_dict:
            special_format = self.speech_dict[speech_first]
            speech_string = speech_text[1:]
        else:
            special_format = 0
            speech_string = speech_text

        self.special_format = special_format
        self.speech_string = speech_string

        if rendered_text:
            self.markup_string = rendered_text
        else:
            self.markup_string = self.controller.reg_names.sub(self.markup_names, self.speech_string)

    def markup_names(self, match):
        found = match.group('found')
        return f'^^^{self.controller.name_map[found.upper()].id}:{found}^^^'

    def __str__(self):
        str(self.demarkup())

    def monitor_display(self, viewer=None):
        if not viewer:
            return self.demarkup()
        if not self.alternate_name:
            return self.render(viewer)
        return_string = None
        if self.special_format == 0:
            return_string = f'({self.markup_name}){self.alternate_name} {self.action_string}, "{self.markup_string}"'
        elif self.special_format == 1:
            return_string = f'({self.markup_name}){self.alternate_name} {self.markup_string}'
        elif self.special_format == 2:
            return_string = f'({self.markup_name}){self.alternate_name}{self.markup_string}'
        elif self.special_format == 3:
            return_string = f'({self.markup_name}){self.markup_string}'
        if self.title:
            return_string = f'{self.title} {return_string}'

        return self.colorize(return_string, viewer)

    def render(self, viewer=None):
        if not viewer:
            return ANSIString(self.demarkup())
        return_string = None
        if self.special_format == 0:
            return_string = f'{self.markup_name} {self.action_string}, "{self.markup_string}|n"'
        elif self.special_format == 1:
            return_string = f'{self.markup_name} {self.markup_string}'
        elif self.special_format == 2:
            return_string = f'{self.markup_name}{self.markup_string}'
        elif self.special_format == 3:
            return_string = self.markup_string
        if self.title:
            return_string = f'{self.title} {return_string}'
        if self.mode == 'page' and len(self.targets) > 1:
            pref = f'(To {", ".join(self.targets)})'
            return_string = f'{pref} {return_string}'

        return self.colorize(return_string, viewer)

    def log(self):
        return_string = None
        if self.special_format == 0:
            return_string = f'{self.markup_name} {self.action_string}, "{self.markup_string}|n"'
        elif self.special_format == 1:
            return_string = f'{self.markup_name} {self.markup_string}'
        elif self.special_format == 2:
            return_string = f'{self.markup_name}{self.markup_string}'
        elif self.special_format == 3:
            return_string = self.markup_string
        if self.title:
            return_string = f'{self.title} {return_string}'
        if self.mode == 'page' and len(self.targets) > 1:
            pref = f'(To {", ".join(self.targets)}'
            return_string = f'{pref} {return_string}'
        return return_string

    def demarkup(self):
        return_string = None
        if self.special_format == 0:
            return_string = f'{self.display_name} {self.action_string}, "{self.speech_string}|n"'
        elif self.special_format == 1:
            return_string = f'{self.display_name} {self.speech_string}'
        elif self.special_format == 2:
            return_string = f'{self.display_name}{self.speech_string}'
        elif self.special_format == 3:
            return_string = self.speech_string
        if self.title:
            return_string = f'{self.title} {return_string}'
        return ANSIString(return_string)

    def colorize(self, message, viewer):
        viewer = viewer.get_account() if viewer and hasattr(viewer, 'get_account') else None
        colors = dict()
        styler = viewer.styler if viewer else athanor.STYLER(None)
        for op in ("quotes", "speech", "speaker", "self", 'other'):
            colors[op] = styler.options.get(f"{op}_{self.color_mode}", '')
            if colors[op] == 'n':
                colors[op] = ''

        quote_color = colors["quotes"]
        speech_color = colors["speech"]

        def color_speech(found):
            if not quote_color and not speech_color:
                return f'"{found.group("found")}"'
            if quote_color and not speech_color:
                return f'|{quote_color}"|n{found.group("found")}|n|{quote_color}"|n'
            if speech_color and not quote_color:
                return f'"|n|{speech_color}{found.group("found")}|n"'
            if quote_color and speech_color:
                return f'|{quote_color}"|n|{speech_color}{found.group("found")}|n|{quote_color}"|n'

        def color_names(found):
            data = found.groupdict()
            thing_name = data["thing_name"]
            if not viewer:
                return thing_name
            thing_id = int(data["thing_id"])
            if not (obj := self.controller.id_map.get(thing_id, None)):
                return thing_name
            custom = viewer.colorizer.get(obj, None)
            if custom and custom != 'n':
                return f"|n|{custom}{thing_name}|n"
            if obj == viewer and colors["self"]:
                return f"|n|{colors['self']}{thing_name}|n"
            if obj == self.speaker and colors['speaker']:
                return f"|n|{colors['speaker']}{thing_name}|n"
            return thing_name

        colorized_string = self.re_speech.sub(color_speech, message)
        colorized_string = self.re_name.sub(color_names, colorized_string)
        return colorized_string


def iter_to_string(iter):
    return ', '.join(str(i) for i in iter)


def duration_format(duration: int, width: int = 999999999):
    years = duration // 31536000
    if years:
        duration -= years * 31536000

    weeks = duration // 604800
    if weeks:
        duration -= weeks * 604800

    days = duration // 86400
    if days:
        duration -= days * 86400

    hours = duration // 3600
    if hours:
        duration -= hours * 3600

    minutes = duration // 60
    if minutes:
        duration -= minutes * 60

    seconds = duration

    out_list = list()
    if years:
        out_list.append(f"{years}y")
    if weeks:
        out_list.append(f"{weeks}w")
    if days:
        out_list.append(f"{days}d")
    if hours:
        out_list.append(f"{hours}h")
    if minutes:
        out_list.append(f"{minutes}m")
    if seconds or not out_list:
        out_list.append(f"{seconds}s")

    remaining = width

    out = ''
    for i, section in enumerate(out_list):
        if i == 0:
            out = section
            remaining -= len(section)
        else:
            if len(section)+1 <= remaining:
                out += f" {section}"
                remaining -= len(section)+1
            else:
                break
    return out


def red_yellow_green(number: int = 0):
    blue = 0

    if number > 50:
        red = 255
        green = (255 * 2) - int(255 * ((number * 2) / 100))
    else:
        red = int(255 * ((number * 2) / 100))
        green = 255

    return f"<{red} {green} {blue}>"


def percent_cap(number: int = 0, of: int = 0):
    div = number / of
    if div >= 1:
        return 100
    return int(div * 100)


def find_matching(text: str, start: int, opening: str, closing: str):
    escaped = False
    depth = 0
    i = start
    while i < len(text):
        if escaped:
            pass
        else:
            c = text[i]
            if c == '\\':
                escaped = True
            elif c == opening:
                depth += 1
            elif c == closing and depth:
                depth -= 1
                if not depth:
                    return i
        i += 1
    return None


def find_notspace(text: str, start: int):
    i = start
    while i < len(text):
        if text[i] != ' ':
            return i
        i += 1
    return None


def truthy(test_str: MudText) -> bool:
    test_str = test_str.squish_spaces()
    if not test_str:
        return False
    if test_str.startswith("#-"):
        return False
    number = to_number(test_str)
    if number is not None:
        return bool(number)
    return True


_RE_NUMERIC = re.compile(r"^(?P<neg>-)?(?P<value>\d+(?P<dec>\.\d+)?)$")


def to_number(test_str: MudText) -> Optional[Union[int, float]]:
    test_str = test_str.squish_spaces()

    if not len(test_str):
        return 0

    try:
        match = _RE_NUMERIC.fullmatch(test_str.plain)
        if match:
            return eval(test_str.plain)
        else:
            return None

    except Exception as e:
        # TODO: Add proper exception value handling
        return None

_RE_COMP = re.compile(r"^(?P<comp>(>|<|>=|<=|==|&|\||~|\^))(?P<num>(?P<neg>-)?(?P<value>\d+(?P<dec>\.\d+)?))$")


def case_match(test_str: MudText, pattern: MudText) -> bool:
    test_str = test_str.squish_spaces()
    pattern = pattern.squish_spaces()

    # first case - if both are numeric, then just let Python handle it with an eval().
    if (num := _RE_NUMERIC.match(test_str.plain)) and (comp := _RE_COMP.match(pattern.plain)):
        return eval(f"{test_str.plain}{pattern.plain}")
    else:
        # nope, we're going to do a string comparison instead. this is case-insensitive.
        return test_str.plain.lower() == pattern.plain.lower()