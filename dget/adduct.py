"""Class for adduct calculations."""

import re
from typing import Tuple

from molmass import Composition, Formula, Spectrum


class Adduct(object):
    """Class used to create a ``molmass.Formula`` from a base ``molmass.Formula``
    and an adduct string. This string should be in the format *[nM+nX-nY]n+* where
    *M* is the base molecule and *X, Y* are gains / losses.
    Some valid examples are:

    * [M]+
    * [M-H]-
    * [M+Na]+
    * [2M-H]-
    * [M+2H]+
    * [M+K-2H]-


    Attributes:
        adduct: adduct string in the form [nM+nX-nY]n+
        base: formula of the base molecule, represented by M in adduct
        num_base: number of base molecules in adduct
        formula: formula of the adduct
    """

    regex = re.compile("\\[(\\d*)M(.*)\\](\\d+)?([+-])")
    regex_split = re.compile("([+-])(\\d*)(\\w+)")

    def __init__(self, base: Formula, adduct: str):
        """Initialisation function.

        Args:
            base: formula of the base molecule, represented by M in adduct
            adduct: adduct string in the form [nM+nX-nY]n+
        """
        if not Adduct.is_valid_adduct(adduct):
            raise ValueError("adduct must be in the format [nM+X-Y]n+")

        match = Adduct.regex.match(adduct)
        assert match is not None

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
    def composition(self) -> Composition:  # pragma: no cover, pass-through
        """The composition of the adduct."""
        return self.formula.composition()

    @property
    def spectrum(self) -> Spectrum:  # pragma: no cover, pass-through
        """The spectrum of the adduct."""
        return self.formula.spectrum()

    def mz_range(self, min_fraction: float = 0.0) -> Tuple[float, float]:
        """Return the spectrum mz range."""
        mzs = list(
            v.mz for v in self.formula.spectrum(min_fraction=min_fraction).values()
        )
        return min(mzs), max(mzs)

    def __str__(self) -> str:  # pragma: no cover, debug
        return f"{self.adduct}, M={self.base.formula}"

    def __repr__(self) -> str:  # pragma: no cover, debug
        return f"Adduct({self.adduct!r}, M={self.base.formula!r})"

    @staticmethod
    def is_valid_adduct(adduct: str) -> bool:
        """Test to see if adduct string is valid.

        Tests string against ``Adduct.regex`` and makes sure any +/- adducts
        match ``Adduct.regex_split``.

        Args:
            adduct: adduct string in the form [nM+nX-nY]n+
        Returns:
            True if valid
        """
        match = Adduct.regex.fullmatch(adduct)
        if match is None:
            return False
        if len(match.group(2)) > 0:
            return sum(  # check all of group 2 covered by matches
                m.span()[1] - m.span()[0]
                for m in Adduct.regex_split.finditer(match.group(2))
            ) == len(match.group(2))
        return True
