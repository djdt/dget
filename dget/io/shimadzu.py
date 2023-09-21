"""Module for importing Shimadzu HRMS exports from LabSolutions."""
from pathlib import Path
from typing import List, TextIO

from dget.io.text import delimiters


def is_shimadzu_header(header: List[str]) -> bool:
    """Check if the header is a Shimdazu spectra export.

    Args:
        header: list of header strings, at least 2 lines

    Returns:
        True if a Shimadzu header
    """
    if header[0].startswith("[Header]") and "LabSolutions" in header[1]:
        return True
    return False


def is_shimadzu_file(file: str | Path | TextIO) -> bool:
    """Check if the file is a Shimdazu spectra export.

    Extracts the header and calls ``is_shimadzu_header``.

    Args:
        file: string, Path or file pointer

    Returns:
        True if a Shimadzu header
    """
    if isinstance(file, (str, Path)):  # pragma: no cover
        file = open(file, "r")
    header = file.readlines(2048)
    return is_shimadzu_header(header)


def get_loadtxt_kws(file: str | Path | TextIO) -> dict:
    """Read the `loadtxt_kws` from the Shimadzu file.

    Shimadzu MS exports may contain more than just the MS profile data,
    so we must find the 'Profile Data' header and skip to that. The delimiter
    can be inferred and the usecols should always be (0, 1).

    Args:
        file: string, Path or file pointer to file

    Returns:
        dict of all keywords required for ``np.loadtxt``
    """
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
