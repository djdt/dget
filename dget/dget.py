from typing import Dict

import numpy as np
from masscalc import calculate_masses_and_ratios, sum_unique_masses_and_ratios
from masscalc.parser import parse_formula_string

from dget.convolve import deconvolve

mass_D = 2.01410177812
mass_H = 1.00782503223


class DGet(object):
    def __init__(self, atoms: Dict[str, int], charge: int = 0):
        self.atoms = atoms
        self.charge = charge

        masses, ratios = calculate_masses_and_ratios(self.atoms, charge=self.charge)
        self.masses, self.ratios = sum_unique_masses_and_ratios(
            masses, ratios, decimals=0, sort_ratio=False
        )
        diff_HD = mass_D - mass_H
        self.targets = np.arange(
            self.masses[0] - (self.nD * diff_HD), self.masses[-1] + diff_HD, diff_HD
        )
        self.probabilites = np.array([])

    @property
    def nD(self) -> int:
        return self.atoms["D"]

    @property
    def psf(self) -> np.ndarray:
        return self.ratios / self.ratios.sum()

    def average_mass(self) -> float:
        return np.average(self.masses, weights=self.ratios)

    def deuteration_from_tofdata(
        self, x: np.ndarray, y: np.ndarray, mass_width: float = 0.5
    ) -> float:
        starts = np.searchsorted(x, self.targets - mass_width / 2.0)
        ends = np.searchsorted(x, self.targets + mass_width / 2.0)

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

        start, end = np.searchsorted(
            x, [self.targets[0] - pad_mz, self.targets[-1] + pad_mz]
        )
        x, y = x[start:end], y[start:end]

        prediction = np.convolve(self.probabilites, self.psf, mode="full")

        ax.plot(x, y, color="black")
        # Scaled prediction
        prediction *= y.max() / prediction.max()
        ax.stem(
            self.targets,
            prediction,
            markerfmt=" ",
            basefmt=" ",
            linefmt="red",
            label="prediction",
        )
        # Scaled PSF
        psf = self.ratios / self.ratios.max() * y.max()
        ax.stem(
            self.masses, psf, markerfmt=" ", basefmt=" ", linefmt="blue", label="PSF"
        )
        ax.set_xlabel("mass")
        ax.set_ylabel("signal")

    @classmethod
    def from_formula(
        cls, formula: str, adduct: str | None = None, charge: int = 0
    ) -> "DGet":
        atoms = parse_formula_string(formula)

        if adduct is not None:
            print(adduct)
            adduct_atoms = parse_formula_string(adduct[1:])
            print(atoms, adduct_atoms)
            atoms = {
                key: atoms.get(key, 0)
                + adduct_atoms.get(key, 0) * (1 if adduct[0] == "+" else -1)
                for key in set(atoms) | set(adduct_atoms)
            }
            print(atoms)
        for k, v in atoms.items():
            if v < 0:
                raise ValueError(f"Invalid number of {k}, {k} = {v}.")
        return DGet(atoms, charge=charge)
