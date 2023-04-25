"""Module containing molmass helper functions."""
from typing import Dict, List, Tuple

import numpy as np
from molmass import Formula, Spectrum, SpectrumEntry


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


def spectra_mz_spread(spectra: List[Spectrum], charge: int = 0) -> Spectrum:
    """Calculte the m/z spread of the given spectra.

    Each entry with the same unit mass is averaged, weighted
    by its relative intensity.

    Args:
        spectra: list of Spectrum to combine

    Returns:
        array of mean m/z values
    """

    combined: Dict[int, List[SpectrumEntry]] = {}

    # build a dict of every spectra
    for spectrum in spectra:
        for num, entry in spectrum.items():
            entries = combined.get(num, [])
            entries.append(entry)
            combined[num] = entries

    return np.sort(
        [
            np.average(
                [e.mz for e in entries], weights=[e.fraction for e in entries]
            )
            for entries in combined.values()
        ]
    )

    # total_fraction = sum(e[0].fraction for e in combined.values())
    # return Spectrum(
    #     {
    #         num: [entry[0].mass, entry[0].fraction / total_fraction]
    #         for num, entry in combined.items()
    #     },
    #     charge=charge,
    # )
