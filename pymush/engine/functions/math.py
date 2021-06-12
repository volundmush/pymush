import math
import operator
import numpy

from typing import Union, List, Optional
from functools import reduce
from scipy import stats

from mudrich.text import Text
from pymush.utils.text import truthy, to_number
from .base import BaseFunction


class _MathFunction(BaseFunction):
    help_category = "math"

    async def do_execute(self):
        try:
            result = self.math_execute()
        except ValueError as err:
            return Text(str(err))
        except ZeroDivisionError:
            return Text("#-1 DIVISION BY ZERO")
        if isinstance(result, float) and int(result) == result:
            return Text(str(int(result)))
        else:
            return Text(str(result))

    def math_execute(self):
        return 0


class _SimpleMathFunction(BaseFunction):
    func = sum
    min_args = 2

    def math_execute(self):
        nums = self.list_to_numbers(self.args)
        return self.func(nums)


class AbsFunction(_MathFunction):
    """
    Function: abs(<number>)

    Returns the absolute value of its argument.
    <number> may be a floating point number, and a floating point result
    is returned.

    Examples:
        > say abs(4)
        You say "4"
        > say abs(-4)
        You say "4"
        > say abs(0)
        You say "0"

    See Also: sign()
    """

    name = "abs"
    exact_args = 1

    def math_execute(self):
        if (num := to_number(await self.parser.evaluate(self.args[0]))) is None:
            raise ValueError("#-1 ARGUMENT MUST BE NUMBER")
        return abs(num)


class AddFunction(_SimpleMathFunction):
    """
    Function: add(<number1>,<number2>[,<numberN>]...)

    Returns the result of adding its arguments together.
    You may add up to 30 numbers in one add() call.

    Numbers may be floating point numbers, and a floating point result
    is returned.

    Example:
        > say add(2,4)
        You say "6"
        > say add(5,3,7,-4)
        You say "11"

    See Also: div(), mod(), mul(), sub()
    """

    name = "add"
    func = sum


class BoundFunction(_MathFunction):
    """
    Function: bound(<number>,<min-value>[,<max-value>])

    This function will return <number> if greater than min-value, else it will
    return min-value.  If max-value exists, and number is greater than max-value
    then max-value is used.

    Example:
        > say bound(8,12)
        You say "12"
        > say bound(8,12,10)
        You say "10"

    See Also: between(), fbetween(), fbound(), gt(), lt(), gte(), lte()
    """

    name = "bound"
    min_args = 2
    max_args = 3

    def math_execute(self):
        out_vals = self.list_to_numbers(self.args)
        min_out = min(out_vals[0], out_vals[1])
        if len(out_vals) == 3:
            return max(out_vals[2], min_out)
        else:
            return min_out


class CeilFunction(_MathFunction):
    """
    Function: ceil(<number>)

    Returns the smallest integer greater than or equal to <number>.  <number>
    may be a floating point number, and an integer result is returned.

    Examples:
        > say ceil(5)
        You say "5"
        > say ceil(5.2)
        You say "6"
        > say ceil(5.8)
        You say "6"
        > say ceil(-5)
        You say "-5"
        > say ceil(-5.2)
        You say "-5"

    See Also: div(), floor(), mod(), round(), trunc()
    """

    name = "ceil"
    exact_args = 1

    def math_execute(self):
        numbers = self.list_to_numbers(self.args)
        return math.ceil(numbers[0])


def _divall(numbers):
    return reduce(operator.idiv, numbers)


def _fdivall(numbers):
    return reduce(operator.div, numbers)


class DivFunction(_SimpleMathFunction):
    """
    Function: div(<number1>,<number2>[,<numberN>]...)

    Returns the integer quotient from dividing <number1> by <number2>.

    For floating point numbers, please use the fdiv() function.

    Example:
        > say div(15,3)
        You say "5"
        > say div(16,3)
        You say "5"
        > say div(17,3)
        You say "5"
        > say div(18,3)
        You say "6"
        > say div(-17,3)
        You say XXXXX

    See Also: add(), fdiv(), mod(), mul(), round(), sub(), trunc()
    """

    name = "div"
    func = _divall


class FDivFunction(_SimpleMathFunction):
    """
    Function: div(<number1>,<number2>[,<numberN>]...)

    Returns the integer quotient from dividing <number1> by <number2>.

    For floating point numbers, please use the fdiv() function.

    Example:
        > say div(15,3)
        You say "5"
        > say div(16,3)
        You say "5"
        > say div(17,3)
        You say "5"
        > say div(18,3)
        You say "6"
        > say div(-17,3)
        You say XXXXX

    See Also: add(), fdiv(), mod(), mul(), round(), sub(), trunc()
    """

    name = "fdiv"
    func = _fdivall


class FloorFunction(_MathFunction):
    """
    Function: ceil(<number>)

    Returns the smallest integer greater than or equal to <number>.  <number>
    may be a floating point number, and an integer result is returned.

    Examples:
        > say ceil(5)
        You say "5"
        > say ceil(5.2)
        You say "6"
        > say ceil(5.8)
        You say "6"
        > say ceil(-5)
        You say "-5"
        > say ceil(-5.2)
        You say "-5"

    See Also: div(), floor(), mod(), round(), trunc()
    """

    name = "floor"
    exact_args = 1

    def math_execute(self):
        out_vals = self.list_to_numbers(self.args)
        return math.floor(out_vals[0])


def _subtract(numbers: List[Union[float, int]]) -> Union[float, int]:
    return reduce(operator.sub, numbers)


class LMathFunction(_MathFunction):
    """
    lmath(<op>, <list>[, <delim>])

    This function performs generic math operations on <list>, returning the
    result. Each element of the list is treated as one argument to an
    operation, so that lmath(<op>, 1 2 3) is equivalent to <op>(1, 2, 3).
    Using @function, one can easily write ladd, lsub, etc as per TinyMUSH.

    Supported <op>'s are:
    add and band bor bxor dist2d dist3d div eq fdiv gt gte lt lte max mean
    median min modulo mul nand neq nor or remainder stddev sub xor

    Examples:
        > think lmath(add, 1|2|3, |)
        6

        > think lmath(max, 1 2 3)
        3

        > &FUN_FACTORIAL me=lmath(mul,lnum(1,%0))
        > think u(fun_factorial,5)
        120

    """

    name = "lmath"
    min_args = 2
    max_args = 3

    ops = {
        "add": sum,
        "max": max,
        "min": min,
        "sub": _subtract,
        "mean": numpy.mean,
        "median": numpy.median,
        "mode": stats.mode,
        "mul": numpy.prod,
        "div": _divall,
        "fdiv": _fdivall,
    }

    def math_execute(self):
        op = await self.parser.evaluate(self.args[0]).plain.lower()
        func = self.ops.get(op, None)
        if not func:
            raise ValueError(f"#-1 UNSUPPORTED OPERATION ({op})")

        delim = await self.parser.evaluate(self.args[2]) if len(self.args) == 3 else Text(" ")
        print(self.args)
        out_vals = self.list_to_numbers(
            await self.parser.evaluate(self.args[1]).split(delim.plain)
        )
        return func(out_vals)


class MaxFunction(_SimpleMathFunction):
    name = "max"
    func = max


class MinFunction(_SimpleMathFunction):
    name = "min"
    func = min


class MeanFunction(_SimpleMathFunction):
    name = "mean"
    func = numpy.mean


class MedianFunction(_SimpleMathFunction):
    name = "median"
    func = numpy.median


class ModeFunction(_SimpleMathFunction):
    name = "mode"
    func = stats.mode


class MulFunction(_SimpleMathFunction):
    name = "mul"
    func = numpy.product


class SubFunction(_SimpleMathFunction):
    name = "sub"
    func = _subtract
