import argparse
import re
from pathlib import Path

import numpy as np

from dget.dget import DGet


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
        m = re.match("M([+-][A-Z][A-Za-z0-9]*)?", args.species)
        if m is None:
            parser.error("--species must have the form M<+-><formula>.")
        args.species = m[1]

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
    dget = DGet.from_formula(args.formula, args.species, args.charge)

    data = read_ms_data_file(
        args.tofdata,
        delimiter=args.delimiter,
        skiprows=args.skiprows,
        mass_column=args.columns[0],
        signal_column=args.columns[1],
    )

    deuteration = dget.deuteration_from_tofdata(data["mass"], data["signal"])

    print(f"Formula: {args.formula}")
    print(f"M/Z    : {dget.average_mass()}")
    print(f"%D     : {deuteration * 100.0:.2f}")

    if args.plot:
        import matplotlib.pyplot as plt

        fig, axes = plt.subplots(1, 1)
        dget.plot_predicted_spectra(axes, data["mass"], data["signal"])
        plt.show()


if __name__ == "__main__":
    main()
