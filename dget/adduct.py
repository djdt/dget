import re

from molmass import Formula, FormulaError, format_charge

# def divide_formulas(a: Formula, b: Formula) -> Tuple[int, Formula]:


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
    charge, formula = formula.charge, Formula(formula._formula_nocharge)
    if isinstance(base, str):
        base = Formula(base)

    multiples = 0
    while formula.nominal_mass > base.nominal_mass:
        try:
            formula -= base
        except (FormulaError, ValueError):
            break
        multiples += 1

    print(formula, base)
    if formula.mass == base.mass:  # formula and base same, no adduct
        adduct = ""
    elif (base - formula).mass > formula.mass:  # simpler will be adduct
        adduct = "+" + formula._formula_nocharge
    else:
        adduct = "-" + (base - formula)._formula_nocharge
        multiples += 1
    return f"[{multiples if multiples > 1 else ''}M{adduct}]{format_charge(charge)}"
