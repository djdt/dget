from pathlib import Path
from typing import Tuple

import numpy as np
from molmass import ELEMENTS, Formula

from dget.convolve import deconvolve


class DGet(object):
    def __init__(
        self,
        formula: str,
        tofdata: Path,
        adduct: str | None = None,
        loss: str | None = None,
        loadtxt_kws: dict | None = None,
    ):
        _loadtxt_kws = {"delimiter": ",", "usecols": (0, 1)}
        if loadtxt_kws is not None:
            _loadtxt_kws.update(loadtxt_kws)

        self.mass_width = 0.5
        self._targets: np.ndarray | None = None
        self._probabilities: np.ndarray | None = None

        self.formula = Formula(formula)
        if adduct is not None:
            self.formula += Formula(adduct)
        if loss is not None:
            self.formula -= Formula(loss)

        self.spectrum = self.formula.spectrum(min_intensity=0.01)  # min 1%
        self.x, self.y = self.read_tofdata(tofdata, **_loadtxt_kws)

    @property
    def deuterium_count(self) -> int:
        return self.formula.composition()["2H"].count

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

            self._probabilities = deconvolve(areas, self.psf, mode="same")[
                : self.deuterium_count + 1
            ]
        return self._probabilities

    @property
    def psf(self) -> np.ndarray:
        fractions = np.array([i.fraction for i in self.spectrum.values()])
        return fractions / fractions.sum()

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

    def align_tof_with_spectra(self) -> None:
        """Shifts ToF data to better align with monoisotopic m/z.
        Please calibrate your MS instead of using this.
        """
        mz = self.formula.monoisotopic_mass
        start, onmass, end = np.searchsorted(
            self.x, [mz - self.mass_width, mz, mz + self.mass_width]
        )
        offset = self.x[start + np.argmax(self.y[start:end])] - self.x[onmass]
        if abs(offset) > 1.0:
            print("warning: calculated alignment offset greater than 1 Da!")
        self.x -= offset

    def plot_predicted_spectra(
        self, ax: "matplotlib.axes.Axes", pad_mz: float = 5.0  # noqa: F821
    ) -> None:
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

    def read_tofdata(self, path: Path, **kwargs) -> Tuple[np.ndarray, np.ndarray]:
        if len(kwargs["usecols"]) != 2:
            raise ValueError(
                "exactly two columns (mass, signal) must be specified by 'usecols'"
            )
        for kw in ["unpack", "dtype"]:
            if kw in kwargs:
                kwargs.pop(kw)
                print(f"warning: removing loadtxt keyword '{kw}'")
        return np.loadtxt(path, unpack=True, dtype=np.float32, **kwargs)  # type: ignore
