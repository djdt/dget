from io import StringIO
from pathlib import Path

import pytest

from dget.io import shimadzu, text


@pytest.fixture()
def shimadzu_path(tmp_path: Path) -> Path:
    data = (
        "[Header]\n"
        "Application Name\tLabSolutions\n"
        "Version\t5.120\n"
        "Data File Name\tC:\\LabSolutions\\Data\\User\\compound.lcd\n"
        "Output Date\t01/01/2023\n"
        "Output Time\t1:00:00 PM\n"
        "\n"
        "[MS Spectrum]\n"
        "# of Peaks\t6218\n"
        "Raw Spectrum\t[2.958->3.248],(scan:[1776->1950])\n"
        "Background\t[4.248->4.503],(scan:[2550->2703])\n"
        "Base Peak\tm/z 433.186014 (Inten : 88,505)\n"
        "Correction\tNone\n"
        "m/z\tAbsolute Intensity\tRelative Intensity\n"
        "250.122045\t2\t0.00\n"
        "250.153812\t132\t0.1\n"
        "\n"
        "Profile Data\n"
        "# of Points\t28840\n"
        "m/z\tAbsolute Intensity\tRelative Intensity\n"
        "250.000000\t0\t0.0000\n"
        "250.117615\t0\t0.00005\n"
    )
    path = tmp_path.joinpath("shimadzu.csv")
    with path.open("w") as fp:
        fp.write(data)
    return path


text_datas = [
    ("1.0,2.0\n" "3.0,4.0\n" "5.0,6.0\n"),
    ("1.0;2.0\n" "3.0;4.0\n" "5.0;6.0\n"),
    (  # Agilent export
        '#"+ESI Scan (0.157 min) Frag=106.0V CID@6.0 20220214_blank-r002.d "\n'
        "#Point\tX(Thompsons)\tY(Counts)\n"
        "0\t49.9914\t0\n"
        "1\t49.9955\t0.120742501748596\n"
    ),
]
text_result_kws = [
    {"delimiter": ",", "skiprows": 0},
    {"delimiter": ";", "skiprows": 0},
    {"delimiter": "\t", "usecols": (1, 2), "skiprows": 2},
]


def test_text_io(tmp_path: Path):
    for data, result in zip(text_datas, text_result_kws):
        io = StringIO(data)
        loadtxt_kws = text.guess_loadtxt_kws(io)
        for k, v in result.items():
            assert loadtxt_kws[k] == v


def test_shimadzu_io(shimadzu_path):
    assert shimadzu.is_shimadzu_file(shimadzu_path)
    for data in text_datas:
        io = StringIO(data)
        assert not shimadzu.is_shimadzu_file(io)

    loadtxt_kws = shimadzu.get_loadtxt_kws(shimadzu_path)
    assert loadtxt_kws["delimiter"] == "\t"
    assert loadtxt_kws["skiprows"] == 20
    assert loadtxt_kws["usecols"] == (0, 1)
