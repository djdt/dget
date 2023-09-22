"""Class for deuteration calculations."""

from pathlib import Path
from typing import Generator, List, TextIO, Tuple

import numpy as np
from molmass import Formula, Spectrum

from dget.adduct import Adduct
from dget.convolve import deconvolve
from dget.formula import spectra_mz_spread
from dget.plot import scale_to_match, stacked_stem


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
        signal_mass_width: float = 0.5,
        signal_mode: str = "peak height",
        loadtxt_kws: dict | None = None,
    ):
        if isinstance(deuterated_formula, str):
            deuterated_formula = Formula(deuterated_formula)

        _loadtxt_kws = {"delimiter": ",", "usecols": (0, 1)}
        if loadtxt_kws is not None:
            _loadtxt_kws.update(loadtxt_kws)

        self._targets: np.ndarray | None = None
        self._probabilities: np.ndarray | None = None
        self._probability_remainders: np.ndarray | None = None

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

        if signal_mode not in ["peak area", "peak height", "raw"]:
            # pragma: no cover, exception
            raise ValueError(
                "signal_mode must be one of 'peak area', 'peak height', 'raw'"
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
        prob = self.deuteration_probabilites[states]
        prob = prob / prob.sum()  # re-normalise
        return np.sum(prob * states) / self.deuterium_count

    @property
    def deuteration_error(self) -> float:
        """Estimation the error of the deconvolution.

        Provides an estimate of the accuracy of the deuterations calculation,
        based on the deconvolution residuals.
        """
        states = self.deuteration_states
        prob = self.deuteration_probabilites[states].sum()
        prob += self.deuteration_probabilites[states.max() + 1 :].sum()
        assert self._probability_remainders is not None
        err = np.abs(self._probability_remainders[states]).sum()
        err += np.abs(self._probability_remainders[states.max() + 1 :]).sum()
        return err / prob

    @property
    def deuteration_probabilites(self) -> np.ndarray:
        """The deuteration fraction of each possible deuteration.

        Probabilities are listed in order of D=0 to N, where N is the number of
        deuterium in the original molecular formula. Probabilities will sum to 1.0.
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
            elif self.signal_mode in ["peak height", "raw"]:
                counts[valid] = np.maximum.reduceat(
                    self.y, np.stack((starts[valid], ends[valid]), axis=1).flat
                )[::2]
            else:  # pragma: no cover, exception
                raise ValueError(
                    "DGet.signal_mode must be 'peak area', 'peak height', 'raw'"
                )
            counts = counts / counts.sum()
            if self.signal_mode == "raw":  # Skip deconvolution
                self._probabilities = counts
            else:
                self._probabilities, self._probability_remainders = deconvolve(
                    counts, self.psf
                )
                # Remove negative probabilities and normalise
                self._probabilities[self._probabilities < 0.0] = 0.0
                self._probabilities = self._probabilities / self._probabilities.sum()

        return self._probabilities  # type: ignore

    @property
    def deuteration_states(self) -> np.ndarray:
        """Indexes of the valid deuteration states.

        Valid states are those Dx-Dn, where n is the number of deuterium atoms
        in the base molecule as x is inferred from ``self.deuteration_cutoff`` if
        defined or the last 2 consecutive probabilities that are < 1% with an
        accumulative probability of at least 10%.
        """
        if self.deuteration_cutoff is None:
            prob = self.deuteration_probabilites[::-1]
            idx = np.flatnonzero((prob[:-1] < 0.01) & (prob[1:] < 0.01))
            idx = idx[idx > np.argmax(np.cumsum(prob) > 0.1)]
            cutoff = self.deuterium_count - idx[0] if idx.size > 0 else 0
        elif isinstance(self.deuteration_cutoff, str):
            cutoff = int(self.deuteration_cutoff[1:])
        else:  # is float
            cutoff = np.searchsorted(self.targets, self.deuteration_cutoff)
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
    def spectrum(self) -> Spectrum:
        """The adduct spectrum."""
        return self.formula.spectrum(min_fraction=DGet.min_fraction_for_spectra)

    @property
    def targets(self) -> np.ndarray:
        """The m/z of every possible spectrum.

        A new spectrum is created by combining the spectra of every possible
        deuteration state."""
        if self._targets is None:
            spectra = list(self.spectra())
            self._targets = spectra_mz_spread(spectra)
        return self._targets

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
                print(f"warning: removing loadtxt keyword '{kw}'")
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
            print("warning: calculated alignment offset greater than 0.5 Da!")
        self.x += offset
        return offset

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
        ax: "matplotlib.axes.Axes",
        mass_range: Tuple[float, float] | str = "targets",  # noqa: F821
        color_probabilities: bool = False,
    ) -> None:
        """Plot spectra over mass spectra on `ax`.

        `mass_range` can be passed as a tuple of floats (start m/z, end m/z),
        'full' to plot the entire mass range or 'targets' to plot the region around
        the predicted spectra.

        Args:
            ax: matplotlib axes to plot on
            mass_range: range to plot
            color_probabilities: use a colour for each probability
        """
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

        # Data
        ax.plot(x, y, color="black")

        if self.deuteration_probabilites.size == 0:
            return

        if color_probabilities:
            ys = np.zeros(
                (
                    self.deuteration_probabilites.size,
                    self.deuteration_probabilites.size,
                )
            )
            np.fill_diagonal(ys.T, self.deuteration_probabilites)
            ys = np.apply_along_axis(np.convolve, 0, ys, self.psf, mode="full")
            ys = scale_to_match(x, y, targets, ys, width=self.mass_width)

            kws = [{"colors": f"C{i}"} for i in range(ys.shape[1])]

            stacked_stem(ax, targets, ys, stack_kws=kws)
        else:
            # Scaled prediction
            ys = np.convolve(self.deuteration_probabilites, self.psf, mode="full")
            ax.stem(
                targets,
                scale_to_match(x, y, targets, ys, width=self.mass_width),
                markerfmt=" ",
                basefmt=" ",
                linefmt="C1-",
                label="Deconvolved Spectra",
            )

        # Scaled PSF
        masses = np.array([i.mz for i in self.spectrum.values()])
        ax.stem(
            masses,
            scale_to_match(x, y, masses, self.psf, width=self.mass_width),
            markerfmt=" ",
            basefmt=" ",
            linefmt="--",
            label="Adduct Spectra",
        )
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
        err = self.deuteration_error
        states = self.deuteration_states
        prob = self.deuteration_probabilites[states]
        prob = prob / prob.sum()

        print(f"Formula          : {self.base_name}", file=file)
        print(f"Adduct           : {self.adduct.adduct}", file=file)
        print(f"M/Z              : {self.adduct.base.isotope.mz:.4f}", file=file)
        print(f"Adduct M/Z       : {self.formula.isotope.mz:.4f}", file=file)
        print(f"%Deuteration     : {pd * 100.0:.2f} ± {err * 100.0:.2f} %", file=file)
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
