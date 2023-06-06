import argparse
from pathlib import Path

from dget import DGet, __version__


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
        "[M+H]+, [2M+Na2]2+, [M-H2]2-. Defaults to [M]+.",
    )
    parser.add_argument(
        "--autoadduct",
        action="store_true",
        help="Guess the adduct from the mass spectra. Overrides --adduct.",
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
        nargs="?",
        const="targets",
        help="Plot the convolved match against the MS data, "
        "use '--plot full' to show the entire mass range..",
    )
    parser.add_argument(
        "--nstates",
        type=int,
        help="Maximum number of states to calculate, defaults to first 2 < 0.5%%",
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
    parser.add_argument("--version", action="version", version=__version__)

    return parser


def main():
    parser = generate_parser()
    args = parser.parse_args()

    if args.autoadduct:
        args.adduct = "[M]+"

    if "D" not in args.formula:
        parser.error("--formula, must contain at least one D atom.")

    loadtxt_kws = {
        "delimiter": args.delimiter,
        "skiprows": args.skiprows,
        "usecols": args.columns,
    }
    dget = DGet(
        args.formula,
        args.tofdata,
        adduct=args.adduct,
        number_states=args.nstates,
        loadtxt_kws=loadtxt_kws,
    )
    if args.autoadduct:
        adduct, diff = dget.guess_adduct_from_base_peak()
        dget.adduct = adduct
        print(f"Adduct difference from adduct base peak m/z: {diff:.4f}")
        print()

    dget.mass_width = args.masswidth
    if args.realign:
        offset = dget.align_tof_with_spectra()
        print(f"Re-aligned ToF data by shifting {offset:.2f} m/z")
        print()

    baseline = dget.subtract_baseline((dget.targets[0], dget.targets[-1]))
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
