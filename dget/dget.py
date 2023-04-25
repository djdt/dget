from pathlib import Path
from typing import List, Tuple

import numpy as np
from molmass import ELEMENTS, Formula, Spectrum

from dget.adduct import adduct_from_formula, formula_from_adduct
from dget.convolve import deconvolve


class DGet(object):
    """Deuteration calculation class.

    This class contains functions for calculating deuteration from
    a molecular formula and mass spectra.

    Mass spectra is expected to be in a delimited text file with at least 2 columns,
    for mass and signals. Specify columns using the keyword 'usecols' in `loadtxt_kws`,
    a (zero indexed) tuple of ints for (mass, signal) columns. The deilimter can be
    specified using the 'delimiter' keyword.

    Uses formulas and calculations from `molmass <https://github.com/cgohlke/molmass>`_

    Attributes:
        formula: formula of expected deuterated molecule
        tofdata: path to mass spectra text file
        adduct: form of adduct ion, see `dget.adduct`
        loadtxt_kws: parameters passed to `numpy.loadtxt`,
            defaults to {'delimiter': ',', 'usecols': (0, 1)}
    """

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
        formula: str | Formula,
        tofdata: str | Path,
        adduct: str = "[M]+",
        mass_width: float = 0.5,
        loadtxt_kws: dict | None = None,
    ):
        if isinstance(formula, str):
            formula = Formula(formula)

        _loadtxt_kws = {"delimiter": ",", "usecols": (0, 1)}
        if loadtxt_kws is not None:
            _loadtxt_kws.update(loadtxt_kws)

        self.mass_width = mass_width
        self.offset_mz: float | None = None

        self._targets: np.ndarray | None = None
        self._probabilities: np.ndarray | None = None
        self._probability_remainders: np.ndarray | None = None

        self.base = formula  # store original for adduct calcs
        self.formula = formula_from_adduct(formula, adduct)

        if self.deuterium_count == 0:
            raise ValueError(
                f"formula: {self.formula.formula} does not contain deuterium"
            )

        self.x, self.y = self._read_tofdata(tofdata, **_loadtxt_kws)

    @property
    def adduct(self) -> str:
        """Get the adduct as a string."""
        return adduct_from_formula(self.formula, self.base)

    @property
    def deuterium_count(self) -> int:
        """The number of deuterium atoms in the molecule."""
        comp = self.formula.composition()
        if "2H" not in comp:
            return 0
        return comp["2H"].count

    @property
    def deuteration(self) -> float:
        """The deuteration of the molecule.

        Deuteration is calculated as the fraction of deuterium in the molecular
        formula that have been dueterated successfully.

        For Example: 60% C2H5D1, 40% C2H6 would give a deuteration of 0.6.
        """
        prob = self.deuteration_probabilites
        return np.sum(prob * np.arange(prob.size)) / self.deuterium_count

    @property
    def deuteration_probabilites(self) -> np.ndarray:
        """The deuteration fraction of each possible deuteration.

        Probabilities are listed in order of D=0 to N, where N is the number of
        deuterium in the original molecular formula. Probabilites will sum to 1.0.
        """
        if self._probabilities is None:
            starts = np.searchsorted(self.x, self.targets - self.mass_width / 2.0)
            ends = np.searchsorted(self.x, self.targets + self.mass_width / 2.0)

            areas = np.array(
                [np.trapz(self.y[s:e], x=self.x[s:e]) for s, e in zip(starts, ends)]
            )
            areas = areas / areas.sum()

            self._probabilities, self._probability_remainders = deconvolve(
                areas, self.psf
            )
            self._probabilities = self._probabilities / self._probabilities.sum()

        return self._probabilities  # type: ignore

    @property
    def psf(self) -> np.ndarray:  # type: ignore
        """The point spread function used for (de)convolution."""
        fractions = np.array([i.fraction for i in self.spectrum.values()])
        return fractions / fractions.sum()

    @property
    def spectrum(self) -> Spectrum:
        """Formula spectrum, see `molmass.Spectrum`.

        A minimum intensity of 1% is used.
        """
        return self.formula.spectrum(min_intensity=0.01)

    @property
    def targets(self) -> np.ndarray:
        """The m/z of each possible deuteration.

        In order of D=0 to N, where N is the number of deuterium in the original
        molecular formula.
        """
        if self._targets is None:
            diff_HD = ELEMENTS["H"].isotopes[2].mass - ELEMENTS["H"].isotopes[1].mass
            smin, smax = self.spectrum.range
            self._targets = np.arange(
                self.spectrum[smin].mz - (self.deuterium_count * diff_HD),
                self.spectrum[smax].mz + diff_HD,
                diff_HD,
            )
        return self._targets

    def __str__(self) -> str:
        return f"DGet({self.formula.formula})"

    def _read_tofdata(
        self, path: str | Path, **kwargs
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Internal helper to read mass spectra data."""

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
        Sets the `offset_mz` attribute to the offset used to shift.
        """
        mz = self.formula.isotope.mz
        start, onmass, end = np.searchsorted(
            self.x, [mz - self.mass_width, mz, mz + self.mass_width]
        )
        self.offset_mz = self.x[start + np.argmax(self.y[start:end])] - self.x[onmass]
        if abs(self.offset_mz) > 1.0:  # type: ignore
            print("warning: calculated alignment offset greater than 0.5 Da!")
        self.x -= self.offset_mz

    def guess_adduct_from_base_peak(
        self,
        adducts: List[Formula] | None = None,
        mass_range: Tuple[float, float] | None = None,
    ) -> Tuple[Formula, float]:
        """Finds the adduct closest to the m/z of the largest tof peak.

        This function will work best with highly deuterated samples.

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
                formulas.append(formula_from_adduct(self.base, adduct))
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
        return formulas[best], diffs[best]

    def plot_predicted_spectra(
        self, ax: "matplotlib.axes.Axes", pad_mz: float = 2.0  # noqa: F821
    ) -> None:
        """Plot spectra over mass spectra on `ax`.

        Args:
            ax: matplotlib axes to plot on
            pad_mz: window around targets to show
        """

        def scale_spectra(x, y, spectra_x, spectra):
            max = spectra_x[np.argmax(spectra)]
            start, end = np.searchsorted(x, [max - 0.5, max + 0.5])
            return spectra * np.amax(y[start:end]) / spectra.max()

        targets = self.targets
        start, end = np.searchsorted(
            self.x, [targets[0] - pad_mz, targets[-1] + pad_mz]
        )
        x, y = self.x[start:end], self.y[start:end]

        prediction = np.convolve(self.deuteration_probabilites, self.psf, mode="full")

        # Data
        ax.plot(x, y, color="black")

        # Scaled prediction
        if prediction.size == 0:
            return

        ax.stem(
            targets,
            scale_spectra(x, y, targets, prediction),
            markerfmt=" ",
            basefmt=" ",
            linefmt="red",
            label="Predicted Specta",
        )

        # Scaled PSF
        masses = [i.mass for i in self.spectrum.values()]
        ax.stem(
            masses,
            scale_spectra(x, y, masses, self.psf),
            markerfmt=" ",
            basefmt=" ",
            linefmt="blue",
            label="Formula Spectra",
        )
        ax.set_title(self.formula.formula)
        ax.set_xlabel("Mass")
        ax.set_ylabel("Signal")
        ax.legend()

    def print_results(self) -> None:
        """Print results to stdout."""

        print(f"Formula          : {self.base.formula}")
        print(f"Adduct           : {self.adduct}")
        print(f"M/Z              : {self.formula.mz}")
        print(f"Monoisotopic M/Z : {self.formula.isotope.mz}")
        print(f"%D               : {self.deuteration * 100.0:.2f} %")
        print()
        print("Deuteration Ratio Spectra")
        for i, p in enumerate(self.deuteration_probabilites):
            print(f"D{i:<2}              : {p * 100.0:5.2f} %")
