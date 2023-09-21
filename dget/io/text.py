"""Module for importing MS data from delimited text files."""
from pathlib import Path
from typing import TextIO

delimiters = [";", ",", "\t", " "]
"""List[str]: text delimiters"""

mass_hints = ["mass", "m/z", "thompson"]
"""List[str]: strings used guess m/z column from header"""

signal_hints = ["signal", "intensity", "count", "cps"]
"""List[str]: strings used guess signal intensity column from header"""


def guess_loadtxt_kws(
    file: str | Path | TextIO, loadtxt_kws: dict | None = None
) -> dict:
    """Attempt to guess the ``loadtxt_kws`` for a file.

    These keywords are passed to ``np.loadtxt`` during initilisation of a
    ``dget.DGet`` class. Guessed values are 'delimiter', 'usecols' and
    'skiprows'.

    Args:
        file: str, path or file pointer to MS text file
        loadtxt_kws: current keywords, values may be overwritten

    Returns:
        ``loadtxt_kws`` updated with guessed values
    """
    if isinstance(file, (str, Path)):  # pragma: no cover
        file = open(file, "r")
    header = file.readlines(2048)

    if loadtxt_kws is None:
        loadtxt_kws = {}

    for delim in delimiters:
        if all(delim in line for line in header if line[0].isdigit()):
            loadtxt_kws["delimiter"] = delim
            break

    if "delimiter" in loadtxt_kws:
        loadtxt_kws["skiprows"] = 0
        # check for first line able to be parsed
        for line in header:
            try:
                float(line.split(loadtxt_kws["delimiter"])[-1])
                break
            except ValueError:
                pass
            loadtxt_kws["skiprows"] = loadtxt_kws["skiprows"] + 1

        # try to find the signal / mass columns
        last_text_line = header[loadtxt_kws["skiprows"] - 1].split(
            loadtxt_kws["delimiter"]
        )
        masscol, signalcol = None, None
        for i, text in enumerate(last_text_line):
            if masscol is None and any(x in text.lower() for x in mass_hints):
                masscol = i
                continue
            if any(x in text.lower() for x in signal_hints):
                signalcol = i
        if masscol is not None and signalcol is not None:
            loadtxt_kws["usecols"] = (masscol, signalcol)

    return loadtxt_kws
