import re
from pathlib import Path
from typing import List, Tuple

import numpy as np
from molmass import ELEMENTS, Formula, Spectrum, format_charge

from dget.convolve import deconvolve


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


class DGet(object):
    common_adducts = [
        "[M]+",
        "[M+H]+",
        "[M+Na]+",
        "[M+H2]2+",
        "[2M+H]+",
        "[M-H]-",
        "[2M-H]-",
        "[M-H2]2-",
        "[M+Cl]-",
    ]

    def __init__(
        self,
        formula: str,
        tofdata: Path,
        adduct: str | None = None,
        loadtxt_kws: dict | None = None,
    ):
        _loadtxt_kws = {"delimiter": ",", "usecols": (0, 1)}
        if loadtxt_kws is not None:
            _loadtxt_kws.update(loadtxt_kws)

        self.mass_width = 0.5
        self._targets: np.ndarray | None = None
        self._probabilities: np.ndarray | None = None
        self._probability_remainders: np.ndarray | None = None

        self._formula = Formula(formula)  # store original for adduct calcs
        self.formula = Formula(formula)
        if adduct is not None:
            self.formula = formula_from_adduct(formula, adduct)

        if self.deuterium_count == 0:
            raise ValueError(
                f"formula: {self.formula.formula} does not contain deuterium"
            )

        self.x, self.y = self._read_tofdata(tofdata, **_loadtxt_kws)

    @property
    def adduct(self) -> str:
        """Get the adduct as a string.
        Eg [M+H]+, [M+Cl]-, [M-H]-"""
        adduct = "M"
        if self.formula.mass > self._formula.mass:
            gain = (self.formula - self._formula)._formula_nocharge
            if len(gain) > 0:
                adduct += "+" + gain
        elif self.formula.mass < self._formula.mass:
            loss = (self._formula - self.formula)._formula_nocharge
            if len(loss) > 0:
                adduct += "-" + loss
        return "[" + adduct + "]" + format_charge(self.formula.charge)

    @property
    def deuterium_count(self) -> int:
        comp = self.formula.composition()
        if "2H" not in comp:
            return 0
        return comp["2H"].count

    @property
    def deuteration(self) -> float:
        prob = self.deuteration_probabilites
        return 1.0 - np.sum(prob * np.arange(prob.size)[::-1]) / prob.size

    @property
    def deuteration_probabilites(self) -> np.ndarray:
        if self._probabilities is None:
            starts = np.searchsorted(self.x, self.targets - self.mass_width / 2.0)
            ends = np.searchsorted(self.x, self.targets + self.mass_width / 2.0)

            areas = np.array(
                [np.trapz(self.y[s:e], x=self.x[s:e]) for s, e in zip(starts, ends)]
            )
            areas = areas / areas.sum()

            self._probabilities, self._probability_remainders = deconvolve(
                areas, self.psf
            )[: self.deuterium_count + 1]
            self._probabilities = self._probabilities / self._probabilities.sum()

        return self._probabilities  # type: ignore

    @property
    def psf(self) -> np.ndarray:  # type: ignore
        fractions = np.array([i.fraction for i in self.spectrum.values()])
        return fractions / fractions.sum()

    @property
    def spectrum(self) -> Spectrum:
        return self.formula.spectrum(min_intensity=0.01)

    @property
    def targets(self) -> np.ndarray:
        if self._targets is None:
            diff_HD = ELEMENTS["H"].isotopes[2].mass - ELEMENTS["H"].isotopes[1].mass
            smin, smax = self.spectrum.range
            self._targets = np.arange(
                self.spectrum[smin].mz - (self.deuterium_count * diff_HD),
                self.spectrum[smax].mz + diff_HD,
                diff_HD,
            )
        return self._targets

    def _read_tofdata(self, path: Path, **kwargs) -> Tuple[np.ndarray, np.ndarray]:
        if len(kwargs["usecols"]) != 2:
            raise ValueError(
                "exactly two columns (mass, signal) must be specified by 'usecols'"
            )
        for kw in ["unpack", "dtype"]:
            if kw in kwargs:
                kwargs.pop(kw)
                print(f"warning: removing loadtxt keyword '{kw}'")
        return np.loadtxt(path, unpack=True, dtype=np.float32, **kwargs)  # type: ignore

    def align_tof_with_spectra(self) -> None:
        """Shifts ToF data to better align with monoisotopic m/z.
        Please calibrate your MS instead of using this.
        """
        mz = self.formula.isotope.mz
        start, onmass, end = np.searchsorted(
            self.x, [mz - self.mass_width, mz, mz + self.mass_width]
        )
        offset = self.x[start + np.argmax(self.y[start:end])] - self.x[onmass]
        if abs(offset) > 1.0:
            print("warning: calculated alignment offset greater than 0.5 Da!")
        self.x -= offset

    def guess_adduct_from_base_peak(
        self,
        adducts: List[Formula] | None = None,
        mass_range: Tuple[float, float] | None = None,
    ) -> Tuple[Formula, float]:
        """Finds the adduct closest to the m/z of the largest tof peak.

        Args:
            adducts: adducts to try, defaults to DGet.common_adducts
            mass_range: range to search for base peak, defaults to whole spectra

        Returns:
            best adduct
            mass difference from base peak
        """
        if adducts is None:
            adducts = DGet.common_adducts

        formulas = []
        for adduct in adducts:
            try:
                formulas.append(formula_from_adduct(self.formula, adduct))
            except ValueError:
                pass

        masses = np.array([f.isotope.mz for f in formulas])

        if mass_range is not None:
            start, stop = np.searchsorted(self.x, mass_range)
        else:
            start, stop = 0, self.x.size

        base = self.x[start:stop][np.argmax(self.y[start:stop])]
        diffs = np.abs(base - masses)
        best = np.argmin(diffs)
        return adducts[best], diffs[best]

    def plot_predicted_spectra(
        self, ax: "matplotlib.axes.Axes", pad_mz: float = 5.0  # noqa: F821
    ) -> None:
        """Plot spectra over mass spectra on `ax`.

        Args:
            ax: matplotlib axes
            pad_mz: window around targets to show
        """
        targets = self.targets

        start, end = np.searchsorted(self.x, [targets[0], targets[-1]])
        x, y = self.x[start:end], self.y[start:end]

        prediction = np.convolve(self.deuteration_probabilites, self.psf, mode="full")
        # Data
        ax.plot(x, y, color="black")

        # Scaled prediction
        if prediction.size == 0 or y.size == 0:
            return
        prediction *= y.max() / prediction.max()
        ax.stem(
            targets,
            prediction,
            markerfmt=" ",
            basefmt=" ",
            linefmt="red",
            label="Predicted Specta",
        )

        # Scaled PSF
        psf = self.psf * y.max()
        masses = [i.mass for i in self.spectrum.values()]
        ax.stem(
            masses,
            psf,
            markerfmt=" ",
            basefmt=" ",
            linefmt="blue",
            label="Formula Spectra",
        )
        ax.set_title(self.formula.formula)
        ax.set_xlabel("Mass")
        ax.set_ylabel("Signal")
        ax.legend()
