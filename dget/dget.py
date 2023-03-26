import numpy as np
from molmass import Formula, ELEMENTS

from dget.convolve import deconvolve


class DGet(object):
    def __init__(
        self, formula: str, adduct: str | None = None, loss: str | None = None
    ):

        self.formula = Formula(formula)
        if adduct is not None:
            self.formula += Formula(adduct)
        if loss is not None:
            self.formula -= Formula(loss)

        self.spectrum = self.formula.spectrum(min_intensity=0.01)

        self.probabilites = np.array([])

    @property
    def nD(self) -> int:
        return self.formula.composition()["2H"].count

    @property
    def psf(self) -> np.ndarray:
        fractions = np.array([i.fraction for i in self.spectrum.values()])
        return fractions / fractions.sum()

    def targets(self) -> np.ndarray:
        diff_HD = ELEMENTS["H"].isotopes[2].mass - ELEMENTS["H"].isotopes[1].mass
        smin, smax = self.spectrum.range
        return np.arange(
            self.spectrum[smin].mass - (self.nD * diff_HD),
            self.spectrum[smax].mass + diff_HD,
            diff_HD,
        )

    def deuteration_from_tofdata(
        self, x: np.ndarray, y: np.ndarray, mass_width: float = 0.5
    ) -> float:
        targets = self.targets()
        starts = np.searchsorted(x, targets - mass_width / 2.0)
        ends = np.searchsorted(x, targets + mass_width / 2.0)

        areas = np.array([np.trapz(y[s:e], x=x[s:e]) for s, e in zip(starts, ends)])
        areas = areas / areas.sum()

        self.probabilites = deconvolve(areas, self.psf, mode="same")[: self.nD + 1]

        return (
            1.0
            - np.sum(self.probabilites * np.arange(self.probabilites.size)[::-1])
            / self.probabilites.size
        )

    def plot_predicted_spectra(
        self,
        ax: "matplotlib.axes.Axes",
        x: np.ndarray,
        y: np.ndarray,
        pad_mz: float = 5.0,
    ) -> None:
        if self.probabilites.size == 0:
            raise ValueError(
                "plot_predicted_spectra: must run `deuteration_from_tofdata` first."
            )
        targets = self.targets()

        start, end = np.searchsorted(x, [targets[0] - pad_mz, targets[-1] + pad_mz])
        x, y = x[start:end], y[start:end]

        prediction = np.convolve(self.probabilites, self.psf, mode="full")

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
            label="prediction",
        )
        # Scaled PSF
        psf = self.psf * y.max()
        masses = [i.mass for i in self.spectrum.values()]
        ax.stem(masses, psf, markerfmt=" ", basefmt=" ", linefmt="blue", label="PSF")
        ax.set_xlabel("mass")
        ax.set_ylabel("signal")
