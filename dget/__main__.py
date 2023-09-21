import argparse
from pathlib import Path

from dget import DGet, __version__
from dget.io import shimadzu, text


def generate_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        "dget",
        description="DGet! uses deconvolution of high-resolution mass spectrometry "
        "data to calculate molecular deuteration.",
    )
    parser.add_argument(
        "formula", help="Molecular formula of the compound, see molmass."
    )
    parser.add_argument(
        "--adduct",
        default="[M]+",
        help="Type of adduct in form [xM<+-><adduct>]x<+->. Valid examples are [M]-, "
        "[M+H]+, [2M+Na2]2+, [M-2H]2-. To guess pass 'Auto'. Defaults to [M]+.",
    )

    parser.add_argument("tofdata", type=Path, help="Path to mass spec data file.")
    parser.add_argument("--delimiter", help="MS data file delimiter.")
    parser.add_argument(
        "--columns",
        metavar=("MASS", "SIGNAL"),
        type=int,
        nargs=2,
        help="Columns used in the MS data file.",
    )
    parser.add_argument(
        "--skiprows",
        type=int,
        help="Number of header rows to skip in data file.",
    )

    parser.add_argument(
        "--plot",
        nargs="?",
        const="targets",
        help="Plot the convolved match against the MS data, "
        "use '--plot full' to show the entire mass range.",
    )
    parser.add_argument(
        "--cutoff",
        type=str,
        help="Mass <float> or deuterium D<int> cutoff to calculate, "
        "defaults to first 2 points < 1%%.",
    )
    parser.add_argument(
        "--masswidth",
        type=float,
        default=0.5,
        help="Window for integration of MS data.",
    )
    parser.add_argument(
        "--baseline",
        action="store_true",
        help="Subtract the 'baseline' from the spectra.",
    )
    parser.add_argument(
        "--realign",
        action="store_true",
        help="Force alignment of MS data with predicted spectra, "
        "please just calibrate your MS.",
    )
    parser.add_argument("--version", action="version", version=__version__)

    return parser


def guess_loadtxt_kws(path: Path):
    if shimadzu.is_shimadzu_file(path):
        return shimadzu.get_loadtxt_kws(path)
    return text.guess_loadtxt_kws(
        path, {"delimiter": "\t", "usecols": (0, 1), "skiprows": 1}
    )


def main():
    parser = generate_parser()
    args = parser.parse_args()

    args.auto_adduct = False
    if args.adduct == "Auto":
        args.auto_adduct = True
        args.adduct = "[M]+"

    if args.cutoff:
        try:
            args.cutoff = float(args.cutoff)
        except ValueError:
            pass

    if "D" not in args.formula:
        parser.error("--formula, must contain at least one D atom.")

    loadtxt_kws = guess_loadtxt_kws(args.tofdata)
    if args.delimiter is not None:
        loadtxt_kws["delimiter"] = args.delimiter
    if args.columns is not None:
        loadtxt_kws["usecols"] = args.columns
    if args.skiprows is not None:
        loadtxt_kws["delimiter"] = args.skiprows

    dget = DGet(
        args.formula,
        args.tofdata,
        adduct=args.adduct,
        cutoff=args.cutoff,
        loadtxt_kws=loadtxt_kws,
        signal_mass_width=args.masswidth,
    )
    if args.auto_adduct:
        adduct, diff = dget.guess_adduct_from_base_peak()
        dget.adduct = adduct
        print(f"Adduct difference from adduct base peak m/z: {diff:.4f}")
        print()

    if args.realign:
        offset = dget.align_tof_with_spectra()
        print(f"Re-aligned ToF data by shifting {offset:.2f} m/z")
        print()

    if args.baseline:
        baseline = dget.subtract_baseline()
        print(f"Subtracting baseline of {baseline:.2f}")
        print()

    dget.print_results()

    if args.plot:
        import matplotlib.pyplot as plt

        fig, axes = plt.subplots(1, 1)
        dget.plot_predicted_spectra(axes, mass_range=args.plot)
        plt.show()


if __name__ == "__main__":
    main()
