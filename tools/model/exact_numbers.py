"""Exact rational arithmetic with explicit units and rounding; no float coercion."""
from dataclasses import dataclass
from fractions import Fraction
import re

from validate_model import require

TYPES = {'Money', 'Rate', 'Decimal', 'Integer'}
ROUNDING = {'exact', 'half_up', 'half_even', 'floor', 'ceiling', 'truncate'}


@dataclass(frozen=True)
class Exact:
    value_type: str
    amount: Fraction

    def __post_init__(self):
        require(self.value_type in TYPES and type(self.amount) is Fraction, 'Invalid exact numeric representation')
        require(self.value_type != 'Integer' or self.amount.denominator == 1, 'Integer must be integral')


def parse(value_type, value):
    require(value_type in TYPES, 'Unknown numeric type')
    if value_type == 'Integer':
        require(type(value) is int, 'Integer requires an int, not Boolean or float')
        return Exact(value_type, Fraction(value))
    require(type(value) is str and re.fullmatch(r'-?(0|[1-9][0-9]*)(\.[0-9]+)?', value), 'Exact number requires a decimal string')
    digits = value.partition('.')[2]
    require(value_type != 'Money' or len(digits) == 2, 'Money input requires exactly two decimal places')
    return Exact(value_type, Fraction(value))


def arithmetic(operator, values):
    require(values and all(type(v) is Exact for v in values), 'Arithmetic requires exact values')
    types = [v.value_type for v in values]
    amounts = [v.amount for v in values]
    if operator in {'add', 'subtract', 'min', 'max'}:
        require(len(values) >= 2 and len(set(types)) == 1, 'Arithmetic unit mismatch')
        require(operator != 'subtract' or len(values) == 2, 'Subtract arity')
        result = sum(amounts) if operator == 'add' else (amounts[0]-amounts[1] if operator == 'subtract' else (min(amounts) if operator == 'min' else max(amounts)))
        return Exact(types[0], result)
    require(operator in {'multiply', 'divide'} and len(values) == 2, 'Invalid arithmetic operator/arity')
    left, right = types
    if operator == 'multiply':
        require(not (left == right == 'Money'), 'Money times Money has unsupported dimensions')
        typ = 'Money' if 'Money' in types else ('Integer' if left == right == 'Integer' else 'Decimal')
        result = amounts[0] * amounts[1]
    else:
        require(amounts[1] != 0, 'Division by zero')
        require(right != 'Money' or left == 'Money', 'Unsupported division dimensions')
        typ = 'Rate' if left == right == 'Money' else ('Money' if left == 'Money' else 'Decimal')
        result = amounts[0] / amounts[1]
    return Exact(typ, result)


def quantize(value, scale, mode):
    require(type(value) is Exact and type(scale) is int and 0 <= scale <= 28 and mode in ROUNDING, 'Invalid quantization policy')
    scaled = value.amount * 10**scale
    sign = -1 if scaled < 0 else 1
    magnitude = abs(scaled)
    whole, remainder = divmod(magnitude.numerator, magnitude.denominator)
    if mode == 'exact':
        require(remainder == 0, 'Value needs an explicit rounding decision')
        coefficient = sign * whole
    elif mode in {'half_up', 'half_even'}:
        twice = 2 * remainder
        up = twice > magnitude.denominator or (twice == magnitude.denominator and (mode == 'half_up' or whole % 2 == 1))
        coefficient = sign * (whole + int(up))
    elif mode == 'truncate':
        coefficient = sign * whole
    elif mode == 'floor':
        coefficient = scaled.numerator // scaled.denominator
    else:
        coefficient = -((-scaled.numerator) // scaled.denominator)
    return Exact(value.value_type, Fraction(coefficient, 10**scale))


def render(value, scale=2, mode='exact'):
    rounded = quantize(value, scale, mode)
    coefficient = int(rounded.amount * 10**scale)
    if scale == 0:
        return str(coefficient)
    magnitude = abs(coefficient)
    return ('-' if coefficient < 0 else '') + f'{magnitude//10**scale}.{magnitude%10**scale:0{scale}d}'


def round_line_total(amounts):
    """IRS nonnegative whole-dollar line convention: sum cents, then half-up."""
    require(amounts, 'Line total requires at least one amount')
    require(all(v.value_type == 'Money' and v.amount >= 0 for v in amounts), 'Line rounding accepts nonnegative Money only')
    total = amounts[0] if len(amounts) == 1 else arithmetic('add', amounts)
    return render(total, 0, 'half_up')
