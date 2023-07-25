from pathlib import Path
from typing import List, TextIO

from dget.io.text import delimiters


def is_shimadzu_header(header: List[str]) -> bool:
    if header[0].startswith("[Header]") and "LabSolutions" in header[1]:
        return True
    return False


def is_shimadzu_file(file: str | Path | TextIO) -> bool:
    if isinstance(file, (str, Path)):  # pragma: no cover
        file = open(file, "r")
    header = file.readlines(2048)
    return is_shimadzu_header(header)


def get_loadtxt_kws(file: str | Path | TextIO) -> dict:
    if isinstance(file, (str, Path)):  # pragma: no cover
        file = open(file, "r")

    loadtxt_kws: dict = {"skiprows": 0}
    line = file.readline()
    while not line.startswith("Profile Data"):
        line = file.readline()
        loadtxt_kws["skiprows"] += 1

    file.readline()  # skip '# of Points xxxxxx'
    line = file.readline()
    loadtxt_kws["skiprows"] += 2

    for delim in delimiters:
        if delim in line:
            loadtxt_kws["delimiter"] = delim
            break

    loadtxt_kws["skiprows"] += 1
    loadtxt_kws["usecols"] = (0, 1)

    return loadtxt_kws
