import re
from typing import Tuple

from molmass import Formula, format_charge


def divide_formulas(a: Formula, b: Formula) -> Tuple[int, Formula]:
    divs = 0
    while formula_in_formula(b, a):
        if b.mass == a.mass:  # same formula
            return divs + 1, None
        a -= b
        divs += 1
    return divs, a


def formula_in_formula(a: Formula, b: Formula) -> bool:
    for k, v in a._elements.items():
        if k not in b._elements:
            return False
        for ik, iv in v.items():
            if b._elements[k].get(ik, 0) < iv:
                return False
    return True


def formula_from_adduct(formula: str | Formula, adduct: str) -> Formula:
    if isinstance(formula, str):
        formula = Formula(formula)

    match = re.match("\\[(\\d*)M([+-])?(.*)\\](\\d*[+-])", adduct)
    if match is None:
        raise ValueError("adduct must be in the format [xM<+-><formula>]x<+->")

    formula = int(match.group(1) or 1) * formula
    if match.group(2) is None and match.group(3):
        raise ValueError("adduct must be in the format [xM<+-><formula>]x<+->")

    if match.group(2) == "-":
        formula -= Formula(match.group(3))
    else:
        formula += Formula(match.group(3))
    formula += Formula("_" + match.group(4))
    return formula


def adduct_from_formula(formula: Formula | str, base: Formula | str) -> str:
    """Get the adduct from the original base formula as a string.
    Eg [M+H]+, [M+Cl]-, [M-H]-"""

    if isinstance(formula, str):
        formula = Formula(formula)
    if isinstance(base, str):
        base = Formula(base)

    n, rem = divide_formulas(Formula(formula._formula_nocharge), base)
    print(formula, base, n)

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
