"""Adduct calculations for DGet.

This module contains functions for transforming adduct strings
to and from molmass.Formula classes, and helper functions.

Adduct strings are in the form [M+H]+, where 'M' represents the base formula,
and must match the regex `ADDUCT_REGEX`: "\\[(\\d*)M(?:([+-])(.+))?\\](\\d*[+-])".
"
    [
        number of times base molecule in adduct, (M with optional int prefix)
        optional loss or gain, (+ for gain, - for loss)(Formula of loss of gain)
    ]
    charge of adduct, (+ or - with optional int prefix)
"

Valid examples are:
[M]+, [M]-, [M+H]+, [M-H]-, [2M+H2]2+, [2M-H2O]-

"""
import re
from typing import Tuple

from molmass import Formula, format_charge

ADDUCT_REGEX = re.compile("\\[(\\d*)M(?:([+-])(.+))?\\](\\d*[+-])")


def divide_formulas(a: Formula, b: Formula) -> Tuple[int, Formula]:
    """Divide Formula `a` by `b`.
    Returns the number of times `b` is in `a` and remainder.

    Args:
        a: numerator Formula
        b: divisor Formula

    Returns:
        number of times `b` in `a`
        Formula of remainder
    """
    divs = 0
    while formula_in_formula(b, a):
        if b.mass == a.mass:  # same formula
            return divs + 1, None
        a -= b
        divs += 1
    return divs, a


def formula_in_formula(a: Formula, b: Formula) -> bool:
    """Check if all atoms of `a` are in `b`.

    Returns:
        True if `a` in `b`
    """
    for k, v in a._elements.items():
        if k not in b._elements:
            return False
        for ik, iv in v.items():
            if b._elements[k].get(ik, 0) < iv:
                return False
    return True


def formula_from_adduct(base: str | Formula, adduct: str) -> Formula:
    """Create a Formula an adduct string.

    The `base` Formula is represented in the string by 'M'.

    Args:
        base: Formula of non-adduct molecule
        adduct: adduct string

    Returns:
        Formula of the adduct
    """
    if isinstance(base, str):
        base = Formula(base)

    match = ADDUCT_REGEX.match(adduct)
    if match is None or (match.group(2) is None and match.group(3) is not None):
        raise ValueError("adduct must be in the format [xM<+-><formula>]x<+->")

    formula = int(match.group(1) or 1) * base

    if match.group(2) == "-":
        formula -= Formula(match.group(3))
    elif match.group(2) == "+":
        formula += Formula(match.group(3))

    formula += Formula("_" + match.group(4))
    return formula


def adduct_from_formula(formula: Formula | str, base: Formula | str) -> str:
    """Get the adduct string used to create `formula` from base molecule `base`.

    The `base` Formula is represented in the string by 'M'.

    Args:
        formula: Formula of the adduct
        base: Formula of the base molecule

    Returns:
        adduct string
    """
    if isinstance(formula, str):
        formula = Formula(formula)
    if isinstance(base, str):
        base = Formula(base)

    n, rem = divide_formulas(Formula(formula._formula_nocharge), base)

    if rem is None:
        adduct_str = ""
    elif not formula_in_formula(rem, base) or rem.atoms < (base - rem).atoms:
        # Either the remainder is not part of base (must be adduct) or is simpler
        # than an adduct as a loss
        adduct_str = "+" + rem._formula_nocharge
    else:  # Loss adduct simpler than gain aduct
        adduct_str = "-" + (base - rem)._formula_nocharge
        n += 1
    return f"[{n if n > 1 else ''}M{adduct_str}]{format_charge(formula.charge)}"
