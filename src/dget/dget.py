"""Class for deuteration calculations."""

import logging
from pathlib import Path
from typing import Generator, List, TextIO, Tuple

import numpy as np
from molmass import Formula, Spectrum

from dget.adduct import Adduct
from dget.convolve import deconvolve
from dget.formula import spectra_mz_spread
from dget.gui.colors import dget_spectra, dget_state_unused, dget_state_used

logger = logging.getLogger(__name__)


class DGet(object):
    """Deuteration calculation class.

    This class contains functions for calculating deuteration from
    a molecular formula and mass spectra.

    The lowest deuteration state to include in the calculation can be selected using the
    ``cutoff`` argument. This accepts floats to specify an m/z or a string in the format
    'D<int>' to specify the lowest state. By default the lowest state will be the first
    where 2 consecutive states are < 1% and the accumulated probability is > 10%.

    Signals are read from the data using the ``signal_mode``, 'peak area' will integrate
    the ``signal_mass_width`` region around each m/z, while 'peak height'and 'raw' will
    select the highest peak within this region. If 'raw' is selected, no de-convolution
    is performed.

    Mass spectra files are expected to be a delimited text file with at least 2 columns,
    one for mass and one for signals. Specify columns using the keyword 'usecols' in
    ``loadtxt_kws``, a (zero indexed) tuple of ints for (mass, signal) columns.
    The delimiter can be specified using the 'delimiter' keyword.
    Mass spectra can also be passed as a tuple of numpy arrays, (masses, signals).

    Attributes:
        deuterated_formula: formula of fully deuterated molecule
        tofdata: path to mass spectra text file, or tuple of masses, signals
        adduct: form of adduct ion, see `dget.adduct`
        cutoff: cutoff for calculation as an m/z '123.4' or state 'D<int>'
        signal_mass_width: range around each m/z to search for maxima or integrate
        signal_mode: detection mode, one of 'peak area', 'peak height', 'raw'
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
    min_fraction_for_spectra = 1e-3

    def __init__(
        self,
        deuterated_formula: str | Formula,
        tofdata: str | Path | TextIO | Tuple[np.ndarray, np.ndarray],
        adduct: str = "[M]+",
        cutoff: float | str | None = None,
        signal_mass_width: float = 0.33,
        signal_mode: str = "peak height",
        loadtxt_kws: dict | None = None,
    ):
        if isinstance(deuterated_formula, str):
            deuterated_formula = Formula(deuterated_formula)

        _loadtxt_kws = {"delimiter": ",", "usecols": (0, 1)}
        if loadtxt_kws is not None:
            _loadtxt_kws.update(loadtxt_kws)

        # Parameters generated on first use
        self._target_masses: np.ndarray | None = None
        self._target_signals: np.ndarray | None = None
        self._probabilities: np.ndarray | None = None
        self._deconv_residuals: np.ndarray | None = None

        self.adduct = Adduct(deuterated_formula, adduct)

        if self.deuterium_count == 0:  # pragma: no cover, exception
            raise ValueError(
                f"formula: {self.adduct.base.formula} does not contain deuterium"
            )

        if isinstance(cutoff, str) and cutoff[0] == "D":
            try:
                c = int(cutoff[1:])
            except ValueError:  # pragma: no cover, exception
                raise ValueError("'cutoff' must be a float or str of format D<int>")
            if c < 0:
                raise ValueError("deuterium based 'cutoff' must be greater than 0")
        self.deuteration_cutoff = cutoff

        self.mass_width = signal_mass_width

        if signal_mode not in ["peak area", "peak height"]:
            # pragma: no cover, exception
            raise ValueError(
                "signal_mode must be one of 'peak area',height'"
            )
        self.signal_mode = signal_mode

        if isinstance(tofdata, tuple):
            self.x, self.y = tofdata[0], tofdata[1]
        else:
            self.x, self.y = self._read_tofdata(tofdata, **_loadtxt_kws)

    @property
    def base_name(self) -> str:
        """The name of the base formula, with D instead of [2H]."""
        return self.adduct.base.formula.replace("[2H]", "D")

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

        Deuteration is only calculated for the states above the deuteration cutoff.
        """
        states = self.deuteration_states
        prob = self.deuteration_probabilities[states]
        prob = prob / prob.sum()  # re-normalise
        return np.sum(prob * states) / self.deuterium_count

    @property
    def deuteration_probabilities(self) -> np.ndarray:
        """The deuteration fraction of each possible deuteration.

        Probabilities are listed in order of D=0 to N, where N is the number of
        deuterium in the original molecular formula. Probabilities will sum to 1.0.
        """
        if self._probabilities is None:
            self._probabilities, self._deconv_residuals = deconvolve(
                self.target_signals, self.psf
            )
            # Remove negative probabilities
            self._probabilities[self._probabilities < 0.0] = 0.0

        return self._probabilities / self._probabilities.sum()  # type: ignore

    @property
    def deuteration_states(self) -> np.ndarray:
        """Indexes of the valid deuteration states.

        Valid states are those Dx-Dn, where n is the number of deuterium atoms
        in the base molecule as x is inferred from ``self.deuteration_cutoff`` if
        defined or the last 2 consecutive probabilities that are < 1% with an
        accumulative probability of at least 10%.
        """
        if self.deuteration_cutoff is None:
            prob = self.deuteration_probabilities[::-1]
            idx = np.flatnonzero((prob[:-1] < 0.01) & (prob[1:] < 0.01))
            idx = idx[idx > np.argmax(np.cumsum(prob) > 0.1)]
            cutoff = self.deuterium_count - idx[0] if idx.size > 0 else 0
        elif isinstance(self.deuteration_cutoff, str):
            cutoff = int(self.deuteration_cutoff[1:])
        else:  # is float
            cutoff = np.searchsorted(self.target_masses, self.deuteration_cutoff)

        return np.arange(max(cutoff, 0), self.deuterium_count + 1)

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
    def residual_error(self) -> float | None:
        """The normalised (0.0 - 1.0) sum of deonvolution residuals.

        A high residual error is indicitive of a poor fit between the data and
        isotopic spectra. This can result from an incorrect formula or contaminants
        in the mass spectra."""
        if self._deconv_residuals is None:
            return None
        return np.sum(self._deconv_residuals) / np.sum(self.target_signals)

    @property
    def spectrum(self) -> Spectrum:
        """The adduct spectrum."""
        return self.formula.spectrum(min_fraction=DGet.min_fraction_for_spectra)

    @property
    def target_masses(self) -> np.ndarray:
        """The m/z of every possible spectrum.

        A new spectrum is created by combining the spectra of every possible
        deuteration state."""
        if self._target_masses is None:
            spectra = list(self.spectra())
            self._target_masses = spectra_mz_spread(spectra)
        return self._target_masses

    @property
    def target_signals(self) -> np.ndarray:
        """The signal for every m/z in the possible spectrum.

        The ``mass_width`` area around each of the ``target_masses`` is integrated or
        searched for the maximum peak height, depending on the current ``signal_mode``.
        """
        if self._target_signals is None:
            starts = np.searchsorted(
                self.x, self.target_masses - self.mass_width, side="right"
            )
            ends = np.searchsorted(
                self.x, self.target_masses + self.mass_width, side="left"
            )

            valid = np.logical_and(starts < ends, ends < self.x.size)
            if np.any(~valid):
                logger.warning("some target m/z fall outside of mass spectrum")

            self._target_signals = np.zeros(self.target_masses.size)

            if self.signal_mode == "peak area":
                for i in np.arange(self._target_signals.size)[valid]:
                    xs = np.concatenate(
                        (
                            [self.target_masses[i] - self.mass_width],
                            self.x[starts[i] : ends[i]],
                            [self.target_masses[i] + self.mass_width],
                        )
                    )
                    self._target_signals[i] = np.trapezoid(
                        np.interp(xs, self.x, self.y), x=xs
                    )
            elif self.signal_mode == "peak height":
                self._target_signals[valid] = np.maximum.reduceat(
                    self.y, np.stack((starts[valid], ends[valid]), axis=1).flat
                )[::2]
            else:  # pragma: no cover, exception
                raise ValueError(
                    "DGet.signal_mode must be 'peak area' or 'peak height'"
                )
        return self._target_signals

    def __str__(self) -> str:  # pragma: no cover, debug
        return f"DGet({self.adduct})"

    def __repr__(self) -> str:  # pragma: no cover, debug
        return f"DGet({self.adduct!r})"

    def _read_tofdata(
        self, path: str | Path | TextIO, **kwargs
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Internal helper to read mass spectra data.

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
                logger.warning(f"removing loadtxt keyword '{kw}'")
        return np.loadtxt(path, unpack=True, dtype=np.float32, **kwargs)  # type: ignore

    def align_tof_with_spectra(self, alignment_mz: float | None = None) -> float:
        """Shifts ToF data to better align with monoisotopic m/z.

        Please calibrate your MS instead of using this.

        Args:
            alignment_mz: m/z used for alignment, defaults to monoisotopic m/z

        Returns:
            offset used for alignment
        """
        if alignment_mz is None:
            alignment_mz = self.formula.isotope.mz

        idx = np.searchsorted(
            self.x,
            [
                alignment_mz - self.mass_width,
                alignment_mz,
                alignment_mz + self.mass_width,
            ],
        )
        start, onmass, end = np.clip(idx, 0, self.x.size)
        if start == end:  # pragma: no cover, exception
            raise ValueError("unable to align, m/z falls outside spectra")

        offset = self.x[onmass] - self.x[start + np.argmax(self.y[start:end])]
        if abs(offset) > 0.5:  # pragma: no cover, warning
            logger.warning("calculated alignment offset greater than 0.5 Da!")
        self.x += offset
        return offset

    def guess_adduct_from_base_peak(
        self,
        adducts: List[Formula] | None = None,
    ) -> Tuple[Adduct, float]:
        """Search for the adduct with the highest intensity.

        If multiple adducts have the maximum intensity then the adduct with the
        monoisotopic mass closest to the local base peak is returned.
        This function will work best with highly deuterated samples.

        Args:
            adducts: adducts to try, defaults to DGet.common_adducts

        Returns:
            best adduct
            mass difference from adducts base peak
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
        ranges = np.stack(
            [f.mz_range(min_fraction=DGet.min_fraction_for_spectra) for f in formulas],
            axis=0,
        )
        ranges += np.stack(
            [-masses * 0.01, masses * 0.01], axis=1
        )  # Expand by 1% of mass

        # idx of start - end of each range
        idx = np.searchsorted(self.x, ranges)
        idx = np.clip(idx, 0, self.x.size - 1)

        # max intensity for each adduct
        intensities = np.maximum.reduceat(self.y, idx.flat)[::2]
        max_intenstites = np.flatnonzero(intensities == intensities.max())

        start = np.min(idx[max_intenstites, 0])
        end = np.max(idx[max_intenstites, 1])
        base = self.x[start:end][np.argmax(self.y[start:end])]
        # multiple adducts overlap with base peak
        if max_intenstites.size > 1:
            best = max_intenstites[np.argmin(np.abs(base - masses[max_intenstites]))]
        else:
            best = max_intenstites[0]

        return formulas[best], masses[best] - base

    def plot_predicted_spectra(
        self,
        ax: "matplotlib.axes.Axes",  # noqa: F821
        mass_range: Tuple[float, float] | str = "targets",
    ) -> None:
        """Plot spectra over mass spectra on `ax`.

        `mass_range` can be passed as a tuple of floats (start m/z, end m/z),
        'full' to plot the entire mass range or 'targets' to plot the region around
        the predicted spectra.

        Args:
            ax: matplotlib axes to plot on
            mass_range: range to plot
        """
        xs = self.target_masses
        ys = self.target_signals
        if self._deconv_residuals is not None:
            ys -= self._deconv_residuals
        ys[ys < 0.0] = 0.0

        if isinstance(mass_range, str):
            if mass_range == "full":
                mass_range = self.x.min(), self.x.max()
            elif mass_range == "targets":
                mass_range = xs.min() - 5.0, xs.max() + 5.0
            else:
                raise ValueError("'mass_range' must be one of 'full', 'targets'.")

        start, end = np.searchsorted(self.x, mass_range)
        x, y = self.x[start:end], self.y[start:end]

        # Data
        ax.plot(x, y, color="black", zorder=0)

        if self.deuteration_probabilities.size == 0:
            return

        used = self.deuteration_states
        used = np.append(used, np.arange(used[-1] + 1, xs.size))
        not_used = np.flatnonzero(~np.in1d(np.arange(xs.size), used))

        ax.scatter(xs[used], ys[used], c=dget_state_used, s=24, label="Deconvolution")
        if not_used.size > 0:
            ax.scatter(
                xs[not_used],
                ys[not_used],
                c=dget_state_unused,
                s=24,
                label="Deconvolution (Not included)",
            )

        # Scaled PSF
        masses = np.array([i.mz for i in self.spectrum.values()])
        ax.scatter(
            masses,
            self.psf * ys[self.deuterium_count] / self.psf[0],
            c="none",
            edgecolors=dget_spectra,
            linewidths=2,
            s=48,
            label="Isotope Spectra",
        )

        # Labels
        ax.set_title(f"{self.base_name} {self.adduct.adduct}")
        ax.set_xlabel("M/Z")
        ax.set_ylabel("Signal")
        ax.legend(loc="best", bbox_to_anchor=(0.0, 0.6, 1.0, 0.4))

    def print_results(self, file: TextIO | None = None) -> None:
        """Print results.

        Args:
            file: file to print to, or sys.stdout if None
        """
        pd = self.deuteration  # ensure calculated
        states = self.deuteration_states
        prob = self.deuteration_probabilities[states]
        prob = prob / prob.sum()

        print(f"Formula          : {self.base_name}", file=file)
        print(f"Adduct           : {self.adduct.adduct}", file=file)
        print(f"M/Z              : {self.adduct.base.isotope.mz:.4f}", file=file)
        print(f"Adduct M/Z       : {self.formula.isotope.mz:.4f}", file=file)
        print(f"Deuteration      : {pd * 100.0:5.2f} %", file=file)
        print(file=file)
        print("Deuteration Ratio Spectra", file=file)
        for s, p in zip(states, prob):
            print(f"D{s:<2}              : {p * 100.0:5.2f} %", file=file)

    def spectra(self, **kwargs) -> Generator[Spectrum, None, None]:
        """Spectrum of all compounds from non to fully deuterated.

        kwargs are passed to molmass.Formula.spectrum()
        """
        spectra_kws = {"min_fraction": DGet.min_fraction_for_spectra}
        spectra_kws.update(**kwargs)

        for i in range(self.deuterium_count, 0, -1):
            yield (self.formula - Formula("D") * i + Formula("H") * i).spectrum(
                **spectra_kws
            )
        yield self.formula.spectrum(**spectra_kws)

    def subtract_baseline(
        self, mass_range: Tuple[float, float] | None = None, percentile: float = 25.0
    ) -> float:
        """Subtracts baseline of region.

        Calculates the ``percentile`` percentile of the designated mass region and
        subtracts it from the mass spec signals.

        Args:
            mass_range: region to find baseline
            percentile: percentile to use

        Returns:
            amount subtracted from baseline
        """
        if mass_range is not None:
            idx = np.searchsorted(self.x, mass_range)
            start, end = np.clip(idx, 0, self.x.size)
        else:
            start, end = 0, self.x.size
        if start == end:  # pragma: no cover, Exception
            raise ValueError(
                "unable to subtract baseline, entire m/z range falls outside spectra"
            )

        baseline = np.percentile(self.y[start:end], percentile)
        self.y -= baseline
        return baseline
