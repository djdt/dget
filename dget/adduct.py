"""Adduct calculations for DGet.

This module contains classes and functions for transforming adduct strings
to and from molmass.Formula classes.

Adduct strings are in the form [M+X-X]+, where 'M' represents the base formula,
Some valid examples are: [M]+, [M+H]+, [M-H]-, [M+Cl]-, [2M+Na]+, [M+H2]2+, [M+K-H2]-.
"""

import re

from molmass import Composition, Formula, Spectrum, format_charge

from dget.formula import divide_formulas, formula_in_formula


class Adduct(object):
    """Class for creating adduct formulas.

    Attributes:
        adduct: adduct string
        base: formula of the base molecule, represented by M in adduct
        num_base: number of base molecules in adduct
        formula: formula of the adduct
    """

    regex = re.compile("\\[(\\d*)M(.*)\\](\\d+)?([+-])")
    regex_split = re.compile("([+-])(\\w+)")

    def __init__(self, base: Formula, adduct: str):
        """Initialiation function.

        Args:
            base: formula of the base molecule, represented by M in adduct
            adduct: adduct string
        """
        match = Adduct.regex.match(adduct)

        if match is None:
            raise ValueError("adduct must be in the format [xM<+-><formula>]x<+->")

        self.adduct = adduct
        self.base = base
        self.num_base = int(match.group(1) or 1)

        self.formula = base * self.num_base

        for adduct_type, formula in Adduct.regex_split.findall(match.group(2)):
            if adduct_type == "-":
                self.formula -= Formula(formula)
            else:
                self.formula += Formula(formula)

        self.formula._charge = (1 if match.group(4) == "+" else -1) * int(
            match.group(3) or 1
        )

    @property
    def composition(self) -> Composition:
        """Return the adduct composition."""
        return self.formula.composition()

    @property
    def spectrum(self) -> Spectrum:
        """Return the adduct spectrum."""
        return self.formula.spectrum()

    def __str__(self) -> str:
        return f"{self.adduct}, M={self.base.formula}"

    def __repr__(self) -> str:
        return f"Adduct({self.adduct!r}, M={self.base.formula!r})"


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

    match = re.match("\\[(\\d*)M(?:([+-])(.+))?\\](\\d*[+-])", adduct)
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
