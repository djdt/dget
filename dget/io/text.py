# from pathlib import Path
from typing import List

delimiters = [";", ",", "\t", " "]


def guess_loadtxt_kws(header: List[str], loadtxt_kws: dict | None = None) -> dict:
    if loadtxt_kws is None:
        loadtxt_kws = {}

    for delim in delimiters:
        if all(delim in line for line in header):
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
        for i, text in enumerate(last_text_line):
            masscol, signalcol = -1, -1
            if any(x in text.lower() for x in ["mass", "m/z"]):
                masscol = i
            if any(x in text.lower() for x in ["signal", "intensity", "counts"]):
                signalcol = i
        if masscol is not None and signalcol is not None:
            loadtxt_kws["usecols"] = (masscol, signalcol)

    return loadtxt_kws
