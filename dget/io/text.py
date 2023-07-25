from pathlib import Path
from typing import TextIO

delimiters = [";", ",", "\t", " "]

mass_hints = ["mass", "m/z", "thompson"]
signal_hints = ["signal", "intensity", "count", "cps"]


def guess_loadtxt_kws(
    file: str | Path | TextIO, loadtxt_kws: dict | None = None
) -> dict:
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
