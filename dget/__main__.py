import argparse
from pathlib import Path

from dget import DGet


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser("dget")
    parser.add_argument(
        "formula", help="Molecular formula of the compound, see molmass."
    )
    parser.add_argument(
        "--adduct",
        help="Formula of adduct, see molmass. Treated as a mass loss if "
        " there is a leading '-' otherwise, a mass addition.",
    )
    parser.add_argument(
        "--autoadduct",
        action="store_true",
        help="Guess the adduct from the mass spectra base peak. Overrides --adduct.",
    )
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
    parser.add_argument(
        "--masswidth",
        type=float,
        default=0.5,
        help="Window for integration of MS data.",
    )
    parser.add_argument(
        "--realign",
        action="store_true",
        help="Force alignment of MS data with predicted spectra, "
        "please just calibrate your MS.",
    )

    args = parser.parse_args()

    if args.autoadduct:
        args.adduct = None

    if "D" not in args.formula:
        parser.error("--formula, must contain at least one D atom.")

    return args


def main():
    args = parse_args()
    loadtxt_kws = {
        "delimiter": args.delimiter,
        "skiprows": args.skiprows,
        "usecols": args.columns,
    }
    dget = DGet(
        args.formula,
        args.tofdata,
        adduct=args.adduct,
        loss=args.loss,
        loadtxt_kws=loadtxt_kws,
    )
    if args.autoadduct:
        adduct, diff = dget.guess_adduct_from_base_peak()
        dget.formula = adduct
        print(f"Adduct difference from base peak m/z: {diff:.4f}")
        print()

    dget.mass_width = args.masswidth
    if args.realign:
        dget.align_tof_with_spectra()

    print(f"Formula          : {dget._formula}")
    print(f"Adduct           : {dget.adduct}")
    print(f"M/Z              : {dget.formula.mz}")
    print(f"Monoisotopic M/Z : {dget.formula.isotope.mz}")
    print(f"%D               : {dget.deuteration * 100.0:.2f}")
    print()
    print("Deuteration Ratio Spectra")
    for i, p in enumerate(dget.deuteration_probabilites):
        print(f"D{i:<2}              : {p:.4f}")

    if args.plot:
        import matplotlib.pyplot as plt

        fig, axes = plt.subplots(1, 1)
        dget.plot_predicted_spectra(axes)
        plt.show()


if __name__ == "__main__":
    main()
