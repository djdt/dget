"""Class for deuteration calculations."""

from pathlib import Path
from typing import Generator, List, Tuple

import numpy as np
from molmass import Formula, Spectrum

from dget.adduct import Adduct
from dget.convolve import deconvolve
from dget.formula import spectra_mz_spread


class DGet(object):
    """Deuteration calculation class.

    This class contains functions for calculating deuteration from
    a molecular formula and mass spectra.

    Mass spectra files are expected to be a delimited text file with at least 2 columns,
    one for mass and one for signals. Specify columns using the keyword 'usecols' in
    `loadtxt_kws`, a (zero indexed) tuple of ints for (mass, signal) columns.
    The deilimter can be specified using the 'delimiter' keyword.
    Mass spectra can also be passed as a tuple of numpy arrays, (masses, signals).

    Attributes:
        deuterated_formula: formula of fully deuterated molecule
        tofdata: path to mass spectra text file, or tuple of masses, signals
        adduct: form of adduct ion, see `dget.adduct`
        signal_mass_width: range around each m/z to search for maxima or integrate
        signal_method: detection mode, valid values are 'peak area', 'peak height'
        spectrum_min_fraction: limit spectra to entries with at least this fraction
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
        "[M-H3O]-",
    ]

    def __init__(
        self,
        deuterated_formula: str | Formula,
        tofdata: str | Path | Tuple[np.ndarray, np.ndarray],
        adduct: str = "[M]+",
        signal_mass_width: float = 0.5,
        signal_mode: str = "peak height",
        spectrum_min_fraction: float = 0.01,
        loadtxt_kws: dict | None = None,
    ):
        if isinstance(deuterated_formula, str):
            deuterated_formula = Formula(deuterated_formula)

        _loadtxt_kws = {"delimiter": ",", "usecols": (0, 1)}
        if loadtxt_kws is not None:
            _loadtxt_kws.update(loadtxt_kws)

        self.offset_mz: float | None = None

        self._targets: np.ndarray | None = None
        self._probabilities: np.ndarray | None = None
        self._probability_remainders: np.ndarray | None = None

        self.adduct = Adduct(deuterated_formula, adduct)

        if self.deuterium_count == 0:
            raise ValueError(
                f"formula: {self.adduct.base.formula} does not contain deuterium"
            )

        self.mass_width = signal_mass_width
        if signal_mode not in ["peak area", "peak height"]:
            raise ValueError("signal_mode must be one of 'peak area', 'peak height'.")
        self.signal_mode = signal_mode
        self.spectra_min_fraction = spectrum_min_fraction

        if isinstance(tofdata, (str | Path)):
            self.x, self.y = self._read_tofdata(tofdata, **_loadtxt_kws)
        else:
            self.x, self.y = tofdata[0], tofdata[1]

    @property
    def deuterium_count(self) -> int:
        """The number of deuterium atoms in the adduct."""
        comp = self.formula.composition()
        if "2H" not in comp:
            return 0
        return comp["2H"].count

    @property
    def deuteration(self) -> float:
        """The deuteration of the *base molecule*.

        Deuteration is calculated as the fraction of deuterium in the molecular
        formula that have been deuterated successfully.

        For example: 60% C2H5D1, 40% C2H6 would give a deuteration of 0.6.
        """
        prob = self.deuteration_probabilites
        return (
            np.sum(prob * np.arange(prob.size))
            / self.deuterium_count
            / self.adduct.num_base
        )

    @property
    def deuteration_probabilites(self) -> np.ndarray:
        """The deuteration fraction of each possible deuteration.

        Probabilities are listed in order of D=0 to N, where N is the number of
        deuterium in the original molecular formula. Probabilites will sum to 1.0.
        """
        if self._probabilities is None:
            starts = np.searchsorted(self.x, self.targets - self.mass_width / 2.0)
            ends = np.searchsorted(self.x, self.targets + self.mass_width / 2.0)

            valid = (starts < ends) & (ends < self.x.size - 1)
            if np.any(~valid):
                print("warning: some m/z targets fall outside of mass spectrum")

            counts = np.zeros(self.targets.size)

            if self.signal_mode == "peak area":
                counts[valid] = [
                    np.trapz(self.y[s:e], x=self.x[s:e])
                    for s, e in zip(starts[valid], ends[valid])
                ]
            else:  # self.signal_mode == "peak height"
                counts[valid] = np.maximum.reduceat(
                    self.y, np.stack((starts[valid], ends[valid]), axis=1).flat
                )[::2]
            counts = counts / counts.sum()

            self._probabilities, self._probability_remainders = deconvolve(
                counts, self.psf
            )
            self._probabilities = self._probabilities / self._probabilities.sum()

        return self._probabilities  # type: ignore

    @property
    def formula(self) -> Formula:
        """The adduct formula."""
        return self.adduct.formula

    @property
    def psf(self) -> np.ndarray:  # type: ignore
        """The point spread function used for (de)convolution.

        This is the normalised spectrum of the adduct."""
        fractions = np.array([i.fraction for i in self.spectrum.values()])
        return fractions / fractions.sum()

    @property
    def spectrum(self) -> Spectrum:
        """The adduct spectrum."""
        return self.formula.spectrum()

    @property
    def targets(self) -> np.ndarray:
        """The m/z of every possible spectrum.

        A new spectrum is created by combining the spectra of every possible
        deuteration state."""
        if self._targets is None:
            self._targets = spectra_mz_spread(list(self.spectra()))
        return self._targets

    def __str__(self) -> str:
        return f"DGet({self.adduct})"

    def __repr__(self) -> str:
        return f"DGet({self.adduct!r})"

    def _read_tofdata(
        self, path: str | Path, **kwargs
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Internal helper to read mass spectra data.

        kwargs are forwarded to ``numpy.loadtxt``.
Formula          : C12H[2H]8N
Adduct           : [M-H]-
M/Z              : 175.12371326162
Adduct M/Z       : 174.11643680929907
%D               : 93.66 %

Deuteration Ratio Spectra
D0               :  0.15 %
D1               :  0.18 %
D2               :  0.20 %
D3               :  0.26 %
D4               :  0.39 %
D5               :  1.41 %
D6               :  6.05 %
D7               : 27.79 %
D8               : 63.56 %

        Args:
            path: path to file

        Returns:
            masses
            signals
        """

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
        Sets the ``DGet.offset_mz`` attribute as the shift use dto align.
        """
        mz = self.formula.isotope.mz
        start, onmass, end = np.searchsorted(
            self.x, [mz - self.mass_width, mz, mz + self.mass_width]
        )
        if start == 0 or end == self.x.size:
            raise ValueError("unable to align, m/z falls outside of mass spectra")

        self.offset_mz = self.x[start + np.argmax(self.y[start:end])] - self.x[onmass]
        if abs(self.offset_mz) > 1.0:  # type: ignore
            print("warning: calculated alignment offset greater than 0.5 Da!")
        self.x -= self.offset_mz

    def guess_adduct_from_base_peak(
        self,
        adducts: List[Formula] | None = None,
        mass_range: Tuple[float, float] | None = None,
    ) -> Tuple[Adduct, float]:
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
                formulas.append(Adduct(self.adduct.base, adduct))
            except ValueError:
                pass

        masses = np.array([f.formula.isotope.mz for f in formulas])

        if mass_range is not None:
            start, stop = np.searchsorted(self.x, mass_range)
        else:
            start, stop = 0, self.x.size

        base = self.x[start:stop][np.argmax(self.y[start:stop])]
        diffs = base - masses
        best = np.argmin(np.abs(diffs))
        return formulas[best], diffs[best]

    def plot_predicted_spectra(
        self,
        ax: "matplotlib.axes.Axes",
        mass_range: Tuple[float, float] | str = "targets",  # noqa: F821
    ) -> None:
        """Plot spectra over mass spectra on `ax`.

        `mass_range` can be passed as a tuple of floats (start m/z, end m/z),
        'full' to plot the entire mass range or 'targets' to plot the region around
        the predicted spectra.

        Args:
            ax: matplotlib axes to plot on
            mass_range: range to plot
        """

        def scale_spectra(x, y, spectra_x, spectra):
            max = spectra_x[np.argmax(spectra)]
            start, end = np.searchsorted(
                x, [max - self.mass_width, max + self.mass_width]
            )
            if start == end:
                return spectra
            return spectra * np.amax(y[start:end]) / spectra.max()

        targets = self.targets

        if isinstance(mass_range, str):
            if mass_range == "full":
                mass_range = self.x.min(), self.x.max()
            elif mass_range == "targets":
                mass_range = targets.min() - 5.0, targets.max() + 5.0
            else:
                raise ValueError("'mass_range' must be one of 'full', 'targets'.")

        start, end = np.searchsorted(self.x, mass_range)
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
            label="Deconvolved Spectra",
        )

        # Scaled PSF
        masses = [i.mz for i in self.spectrum.values()]
        ax.stem(
            masses,
            scale_spectra(x, y, masses, self.psf),
            markerfmt=" ",
            basefmt=" ",
            linefmt="blue",
            label=f"{self.adduct.formula.formula} Spectra",
        )
        ax.set_title(f"{self.adduct.base.formula} {self.adduct.adduct}")
        ax.set_xlabel("Mass")
        ax.set_ylabel("Signal")
        ax.legend()

    def print_results(self) -> None:
        """Print results to stdout."""
        pd = self.deuteration  # ensure calculated

        print(f"Formula          : {self.adduct.base.formula}")
        print(f"Adduct           : {self.adduct.adduct}")
        print(f"M/Z              : {self.adduct.base.isotope.mz}")
        print(f"Adduct M/Z       : {self.formula.isotope.mz}")
        print(f"%Deuteration     : {pd * 100.0:.2f} %")
        print()
        print("Deuteration Ratio Spectra")
        for i, p in enumerate(self.deuteration_probabilites):
            print(f"D{i:<2}              : {p * 100.0:5.2f} %")

    def spectra(self, **kwargs) -> Generator[Spectrum, None, None]:
        """Spectrum of all compounds from non to fully deuterated.

        kwargs are passed to molmass.Formula.spectrum()
        """

        for i in range(self.deuterium_count, 0, -1):
            yield (self.formula - Formula("D") * i + Formula("H") * i).spectrum(
                **kwargs
            )
        yield self.formula.spectrum(**kwargs)
