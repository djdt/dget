import argparse
import re
from pathlib import Path

import numpy as np
from masscalc import calculate_masses_and_ratios, sum_unique_masses_and_ratios
from masscalc.parser import parse_formula_string

from dget.convolve import deconvolve


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser("DGet")
    parser.add_argument("formula", help="Molecular formula of the compound.")
    parser.add_argument("--species", help="Adduct or loss as M<+-><formula>.")
    parser.add_argument("--charge", type=int, default=0, help="Compound charge.")
    parser.add_argument("tofdata", type=Path, help="Path to mass spec data file.")
    parser.add_argument("--delimiter", default="\t", help="MS data file delimiter.")
    parser.add_argument(
        "--columns",
        metavar=("MASS", "SIGNAL"),
        type=int,
        default=(0, 1),
        nargs=2,
        help="Columns used in the MS data file.",
    )
    parser.add_argument(
        "--skiprows",
        type=int,
        default=1,
        help="Number of header rows to skip in data file.",
    )
    parser.add_argument(
        "--plot",
        action="store_true",
        help="Plot the convolved match against the MS data.",
    )

    args = parser.parse_args()

    if "D" not in args.formula:
        parser.error("--formula, must contain at least one D atom.")

    if args.species is not None:
        m = re.match("M([+-])([A-Z][A-Za-z0-9]*)?", args.species)
        if m is None:
            parser.error("--species must have the form M<+-><formula>.")
        args.species = m[2], 1 if m[1] == "+" else -1

    return args


def read_ms_data_file(
    path: Path,
    delimiter: str = "\t",
    skiprows: int = 0,
    mass_column: int = 0,
    signal_column: int = 1,
) -> np.ndarray:
    return np.loadtxt(
        path,
        delimiter=delimiter,
        skiprows=skiprows,
        usecols=(mass_column, signal_column),
        dtype=[("mass", np.float32), ("signal", np.float32)],
    )


def ms_peak_areas(
    x: np.ndarray, y: np.ndarray, targets: np.ndarray, mass_width: float = 0.4
) -> np.ndarray:
    starts = np.searchsorted(x, targets - mass_width / 2.0)
    ends = np.searchsorted(x, targets + mass_width / 2.0)
    return np.array([np.trapz(y[s:e], x=x[s:e]) for s, e in zip(starts, ends)])


def targets_for_masses(masses: np.ndarray, num_D: int) -> np.ndarray:
    mdiff_HD = 2.01410177812 - 1.00782503223
    return np.arange(masses[0] - (num_D * mdiff_HD), masses[-1] + mdiff_HD, mdiff_HD)


def main():
    args = parse_args()
    atoms = parse_formula_string(args.formula)

    if args.species:
        species_atoms = parse_formula_string(args.species[0])
        atoms = {
            key: atoms.get(key, 0) + species_atoms.get(key, 0) * args.species[1]
            for key in set(atoms) | set(species_atoms)
        }
    for k, v in atoms.items():
        if v < 0:
            raise ValueError(f"Invalid number of {k}, {k} = {v}.")

    data = read_ms_data_file(
        args.tofdata,
        delimiter=args.delimiter,
        skiprows=args.skiprows,
        mass_column=args.columns[0],
        signal_column=args.columns[1],
    )

    masses, ratios = calculate_masses_and_ratios(atoms, charge=args.charge)
    masses, ratios = sum_unique_masses_and_ratios(
        masses, ratios, decimals=0, sort_ratio=False
    )
    psf = ratios / ratios.sum()

    targets = targets_for_masses(masses, atoms["D"])
    areas = ms_peak_areas(data["mass"], data["signal"], targets)
    areas /= areas.sum()

    prob = deconvolve(areas, psf, mode="same")[: atoms["D"] + 1]
    deuteration = 1.0 - np.sum(prob * np.arange(prob.size)[::-1]) / prob.size

    print(f"Formula: {args.formula}")
    print(f"M/Z    : {np.average(masses, weights=ratios)}")
    print(f"%D     : {deuteration * 100.0:.2f}")

    if args.plot:
        import matplotlib.pyplot as plt

        s, e = np.searchsorted(data["mass"], [targets[0] - 5.0, targets[-1] + 5.0])
        x, y = data["mass"][s:e], data["signal"][s:e]

        prediction = np.convolve(prob, psf, mode="full")

        prediction *= y.max() / prediction.max()

        plt.plot(x, y, color="black")
        plt.stem(
            targets,
            prediction,
            markerfmt=" ",
            basefmt=" ",
            linefmt="red",
            label="prediction",
        )
        plt.xlabel("mass")
        plt.ylabel("signal")
        plt.show()


if __name__ == "__main__":
    main()
