"""Adduct calculations for DGet.

This module contains classes and functions for transforming adduct strings
to and from molmass.Formula classes.

Adduct strings are in the form [nM+X-Y]n+, where 'M' represents the base formula,
Some valid examples are: [M]+, [M-H]-, [M+Cl]-, [2M+Na]+, [M+H2]2+, [M+2H]2+, [M+K-H2]-.
"""

import re

from molmass import Composition, Formula, Spectrum


class Adduct(object):
    """Class for creating adduct formulas.

    Attributes:
        adduct: adduct string in the form [nM+nX-nY]n+
        base: formula of the base molecule, represented by M in adduct
        num_base: number of base molecules in adduct
        formula: formula of the adduct
    """

    regex = re.compile("\\[(\\d*)M(.*)\\](\\d+)?([+-])")
    regex_split = re.compile("([+-])(\\d*)(\\w+)")

    def __init__(self, base: Formula, adduct: str):
        """Initialiation function.

        Args:
            base: formula of the base molecule, represented by M in adduct
            adduct: adduct string in the form [nM+nX-nY]n+
        """
        match = Adduct.regex.match(adduct)

        if match is None or (
            len(match.group(2)) > 0
            and Adduct.regex_split.search(match.group(2)) is None
        ):
            raise ValueError("adduct must be in the format [nM+X-Y]n+")

        self.adduct = adduct
        self.base = base
        self.num_base = int(match.group(1) or 1)

        self.formula = base * self.num_base

        for m in Adduct.regex_split.finditer(match.group(2)):
            mult = int(m.group(2) or 1)
            if m.group(1) == "-":
                self.formula -= Formula(m.group(3)) * mult
            else:
                self.formula += Formula(m.group(3)) * mult

        self.formula._charge = (1 if match.group(4) == "+" else -1) * int(
            match.group(3) or 1
        )

    @property
    def composition(self) -> Composition:
        """The composition of the adduct."""
        return self.formula.composition()

    @property
    def spectrum(self) -> Spectrum:
        """The spectrum of the adduct."""
        return self.formula.spectrum()

    def __str__(self) -> str:
        return f"{self.adduct}, M={self.base.formula}"

    def __repr__(self) -> str:
        return f"Adduct({self.adduct!r}, M={self.base.formula!r})"
