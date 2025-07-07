from io import StringIO
from pathlib import Path

import numpy as np
import pytest
from molmass import Formula

from dget import DGet

data_path = Path(__file__).parent.joinpath("data")


def test_dget_basic():
    with pytest.raises(ValueError):  # No D
        dget = DGet("CH3", data_path)

    dget = DGet(
        "C2HD3O",
        adduct="[M+H]+",
        tofdata=(np.array([0.0, 999.0]), np.array([0.0, 0.0])),
    )
    assert dget.base_name == "C2HD3O"


def test_dget_io():
    dget = DGet(
        "CD4",
        data_path.joinpath("col02_comma_0h.txt"),
        loadtxt_kws={"usecols": (0, 2), "delimiter": ","},
    )
    assert np.all(dget.x == [0, 1, 2])
    assert np.all(dget.y == [0, 2, 4])
    dget = DGet(
        "CD4",
        data_path.joinpath("col21_space_2h.txt"),
        loadtxt_kws={"usecols": (2, 1), "delimiter": " ", "skiprows": 2},
    )
    assert np.all(dget.x == [0, 1, 2])
    assert np.all(dget.y == [0, 2, 4])

    # Exceptions
    with pytest.raises(ValueError):
        dget = DGet(
            "CD4",
            data_path.joinpath("col21_space_2h.txt"),
            loadtxt_kws={"usecols": (0, 1, 2)},
        )
    # Maybe move to actual warnings
    dget = DGet(
        "CD4",
        data_path.joinpath("col21_space_2h.txt"),
        loadtxt_kws={
            "usecols": (2, 1),
            "delimiter": " ",
            "skiprows": 2,
            "unpack": False,
        },
    )


def test_dget_ndf_data():
    path = data_path.joinpath("ndf")
    info = np.loadtxt(
        path.joinpath("info.txt"),
        skiprows=1,
        delimiter=",",
        dtype=[
            ("id", "U9"),
            ("formula", "U32"),
            ("adduct", "U16"),
            ("pd", float),
            ("notes", "U16"),
        ],
    )
    for cmp in info:
        dget = DGet(
            cmp["formula"],
            path.joinpath(f"{cmp['id']}.txt"),
            adduct=cmp["adduct"],
            loadtxt_kws={"delimiter": "\t"},
            cutoff=cmp["notes"][-2:] if cmp["notes"] != "" else None,
        )
        dget.align_tof_with_spectra()
        # This test is too lenient, but best we can do with the data we have
        assert np.isclose(dget.deuteration * 100.0, cmp["pd"], atol=1.2)

    # Adduct at M+Na, peak at M, cut off before
    dget = DGet(
        "C48H18D78NO8P",
        path.joinpath("NDF-E-005.txt"),
        adduct="[M+Na]+",
        loadtxt_kws={"delimiter": "\t"},
    )
    assert np.all(
        dget.deuteration_states == [67, 68, 69, 70, 71, 72, 73, 74, 75, 76, 77, 78]
    )


def test_dget_cholesterol():
    dget = DGet(
        "C27HD45O",
        data_path.joinpath("Cholesterol D45.txt"),
        adduct="[M+H-H2O]-",
        signal_mass_width=0.15,
        loadtxt_kws={"delimiter": "\t"},
    )
    assert np.isclose(dget.deuteration * 100.0, 81.5, atol=0.1)

    dget = DGet(
        "C27HD45O",
        data_path.joinpath("Cholesterol D45.txt"),
        adduct="[M+H-H2O]-",
        loadtxt_kws={"delimiter": "\t"},
    )
    assert np.isclose(dget.deuteration * 100.0, 81.7, atol=0.1)


def test_dget_auto_adduct():
    path = data_path.joinpath("ndf")
    info = np.loadtxt(
        path.joinpath("info.txt"),
        skiprows=1,
        delimiter=",",
        dtype=[
            ("id", "U9"),
            ("formula", "U32"),
            ("adduct", "U16"),
            ("pd", float),
            ("notes", "U16"),
        ],
    )
    for cmp in info:
        dget = DGet(
            cmp["formula"],
            path.joinpath(f"{cmp['id']}.txt"),
            loadtxt_kws={"delimiter": "\t"},
        )
        # One example of each adduct. Adducts like [M-H]- and [M+H]+ only work
        # when there is a high %D, otherwise [M]+ may be picked.
        if cmp["id"] in ["NDF-A-009", "NDF-B-002", "NDF-B-040", "NDF-C-006"]:
            best, _ = dget.guess_adduct_from_base_peak()
            assert best.adduct == cmp["adduct"]


def test_dget_baseline_subtraction():
    x = np.linspace(16.0, 24.0, 1000)
    y = np.random.normal(10.0, 0.1, size=1000)
    y[:100] = 0
    old_y = y.copy()
    dget = DGet("CD4", tofdata=(x, y), adduct="[M]+")
    baseline = dget.subtract_baseline([16.0, 16.1])
    assert baseline == 0.0
    baseline = dget.subtract_baseline()
    assert np.isclose(baseline, np.percentile(old_y, 25))
    assert np.all(old_y - baseline == dget.y)


def test_deuteration():
    dget = DGet("C2H5D1", tofdata=(np.array([0.0, 999.0]), np.array([0.0, 0.0])))
    dget._probabilities = np.array([1.0, 0.0])
    assert np.isclose(dget.deuteration, 0.0)
    dget._probabilities = np.array([0.5, 0.5])
    assert np.isclose(dget.deuteration, 0.5)
    dget._probabilities = np.array([0.0, 1.0])
    assert np.isclose(dget.deuteration, 1.0)

    dget = DGet("C2H4D2", tofdata=(np.array([0.0, 999.0]), np.array([0.0, 0.0])))
    dget._probabilities = np.array([0.6, 0.3, 0.1])
    assert np.isclose(dget.deuteration, 0.25)
    dget._probabilities = np.array([0.1, 0.3, 0.6])
    assert np.isclose(dget.deuteration, 0.75)

    dget = DGet("C2H2D4", tofdata=(np.array([0.0, 999.0]), np.array([0.0, 0.0])))
    dget._probabilities = np.array([0.4, 0.2, 0.2, 0.1, 0.1])
    assert np.isclose(dget.deuteration, 0.325)
    dget._probabilities = np.array([0.5, 0.0, 0.0, 0.0, 0.5])
    assert np.all(dget.deuteration_states == [3, 4])
    assert np.isclose(dget.deuteration, 1.0)
    dget._probabilities = np.array([0.1, 0.1, 0.2, 0.2, 0.4])
    assert np.isclose(dget.deuteration, 0.675)
    dget._probabilities = np.array([0.5, 0.0, 0.0, 0.0, 0.5])
    dget.deuteration_cutoff = 0
    assert np.all(dget.deuteration_states == [0, 1, 2, 3, 4])
    assert np.isclose(dget.deuteration, 0.5)

    # 2 molecules with 0.5, 0.5
    dget = DGet(
        "C2H3D1",
        adduct="[2M+H]+",
        tofdata=(np.array([0.0, 999.0]), np.array([0.0, 0.0])),
    )
    dget._probabilities = np.array([0.25, 0.5, 0.25])
    assert np.isclose(dget.deuteration, 0.5)

    # 2 molecules with 0.6, 0.3, 0.1
    dget = DGet(
        "C2H4D2",
        adduct="[2M+H]+",
        tofdata=(np.array([0.0, 999.0]), np.array([0.0, 0.0])),
    )
    dget._probabilities = np.array(
        [
            0.6 * 0.6,
            0.6 * 0.3 + 0.3 * 0.6,
            0.3 * 0.3 + 0.6 * 0.1 + 0.1 * 0.6,
            0.3 * 0.1 + 0.1 * 0.3,
            0.1 * 0.1,
        ]
    )
    assert np.isclose(dget.deuteration, 0.25)

    # 3 molecules with 0.5, 0.5
    dget = DGet(
        "C2H3D1",
        adduct="[3M+H]+",
        tofdata=(np.array([0.0, 999.0]), np.array([0.0, 0.0])),
    )
    dget._probabilities = np.array(
        [
            0.5 * 0.5 * 0.5,
            (0.5 * 0.5 * 0.5) * 3,
            (0.5 * 0.5 * 0.5) * 3,
            (0.5 * 0.5 * 0.5),
        ]
    )
    assert np.isclose(dget.deuteration, 0.5)


def test_integration():
    centers = [i.mz for i in Formula("CH4").spectrum(min_intensity=1e-3).values()]

    x = np.arange(centers[0] - 1.0, centers[-1] + 3.0, 0.001)
    y = np.zeros_like(x)
    for i, center in enumerate(centers):
        start, end = np.searchsorted(x, [center - 0.1, center + 0.1])
        y[start:end] = np.sin(np.linspace(0.0, np.pi, end - start)) * (i + 1.0) * np.pi

    dget = DGet(
        "CH3D",
        tofdata=(x, y),
        adduct="[M]+",
        signal_mode="peak height",
        signal_mass_width=0.1,
    )
    assert np.allclose(dget.target_signals, [np.pi, 2.0 * np.pi, 0.0], atol=1e-2)
    assert np.allclose(dget.deuteration_probabilities, [0.33, 0.66], atol=1e-2)

    dget = DGet(
        "CH3D",
        tofdata=(x, y),
        adduct="[M]+",
        signal_mode="peak area",
        signal_mass_width=0.1,
    )
    assert np.allclose(dget.target_signals, [0.2 * 2.0, 0.2 * 4.0, 0.0], atol=1e-2)
    assert np.allclose(dget.deuteration_probabilities, [0.33, 0.66], atol=1e-2)

    # Reduced width
    dget = DGet(
        "CH3D",
        tofdata=(x, y),
        adduct="[M]+",
        signal_mode="peak area",
        signal_mass_width=0.05,
    )
    # integral from pi/4 to 3pi/4
    assert np.allclose(
        dget.target_signals,
        [0.2 * np.sqrt(2.0), 0.2 * 2.0 * np.sqrt(2.0), 0.0],
        atol=1e-2,
    )
    assert np.allclose(dget.deuteration_probabilities, [0.33, 0.66], atol=1e-2)


def test_intergral_interpolated():
    centers = [i.mz for i in Formula("CH4").spectrum(min_intensity=1e-3).values()]

    x = np.array(
        [0.0, centers[0] - 0.5, centers[0], centers[0] + 0.5, centers[-1] + 1.0]
    )
    y = np.array([0.0, 1.0, 2.0, 1.0, 0.0])
    dget = DGet(
        "CH3D",
        tofdata=(x, y),
        adduct="[M]+",
        signal_mode="peak area",
        signal_mass_width=0.1,
    )
    assert np.isclose(dget.target_signals[0], 0.38, atol=1e-2)


def test_cutoff():
    # Known previous error
    dget = DGet("C6D6ClN", tofdata=(np.array([0.0, 999.0]), np.array([0.0, 0.0])))
    dget._probabilities = np.array(
        [
            0.0,
            0.0,
            0.00722939,
            0.02384589,
            0.02229065,
            0.19356285,
            0.75307123,
        ]
    )
    assert np.all(dget.deuteration_states == [2, 3, 4, 5, 6])

    dget = DGet(
        "CD5", cutoff="D3", tofdata=(np.array([0.0, 999.0]), np.array([0.0, 0.0]))
    )
    assert np.all(dget.deuteration_states == [3, 4, 5])
    dget = DGet(
        "CD5", cutoff=0.0, tofdata=(np.array([0.0, 999.0]), np.array([0.0, 0.0]))
    )
    assert np.all(dget.deuteration_states == [0, 1, 2, 3, 4, 5])
    with pytest.raises(ValueError):
        dget = DGet(
            "CD5", cutoff="D-1", tofdata=(np.array([0.0, 999.0]), np.array([0.0, 0.0]))
        )

    # Test automatic
    dget = DGet("CD5", tofdata=(np.array([0.0, 999.0]), np.array([0.0, 0.0])))
    dget._probabilities = np.array([0.0, 0.0, 0.0, 0.0, 0.0, 1.0])
    assert np.all(dget.deuteration_states == [4, 5])
    dget._probabilities = np.array([0.0, 0.0, 0.0, 0.0, 0.5, 0.5])
    assert np.all(dget.deuteration_states == [3, 4, 5])
    dget._probabilities = np.array([0.0, 0.0, 0.5, 0.0, 0.0, 0.5])
    assert np.all(dget.deuteration_states == [4, 5])
    dget._probabilities = np.array([0.0, 0.0, 0.0, 0.5, 0.0, 0.5])
    assert np.all(dget.deuteration_states == [2, 3, 4, 5])
    dget._probabilities = np.array([0.0, 0.3, 0.0, 0.4, 0.0, 0.3])
    assert np.all(dget.deuteration_states == [0, 1, 2, 3, 4, 5])
    dget._probabilities = np.array([0.0, 0.0, 0.95, 0.0, 0.0, 0.05])
    assert np.all(dget.deuteration_states == [1, 2, 3, 4, 5])

    # Known previous error
    dget = DGet(
        "C20D24O6",
        data_path.joinpath("C20D24O6.txt"),
        adduct="[M+Na]+",
        loadtxt_kws={"delimiter": "\t"},
    )
    assert dget.deuteration_states.size > 1


def test_targets():
    dget = DGet("C20D6", tofdata=(np.array([0.0, 999.0]), np.array([0.0, 0.0])))
    formulas = ["C20H6", "C20H5D", "C20H4D2", "C20H3D3", "C20H2D4", "C20HD5", "C20D6"]

    assert np.allclose(
        dget.target_masses[:7], [Formula(f).isotope.mz for f in formulas]
    )
    assert np.allclose(
        dget.target_masses[-4:],
        [
            s.mz
            for s in dget.formula.spectrum(
                min_fraction=DGet.min_fraction_for_spectra
            ).values()
        ],
    )


def test_output_results():
    dget = DGet("C2H2D4", tofdata=(np.array([0.0, 999.0]), np.array([0.0, 0.0])))
    dget._probabilities = np.array([0.0, 0.1, 0.2, 0.3, 0.4])

    results = StringIO()
    dget.print_results(file=results)
    assert results.getvalue() == (
        "Formula          : C2H2D4\n"
        "Adduct           : [M]+\n"
        "M/Z              : 34.0721\n"
        "Adduct M/Z       : 34.0715\n"
        "Deuteration      : 75.00 %\n"
        "\n"
        "Deuteration Ratio Spectra\n"
        "D0               :  0.00 %\n"
        "D1               : 10.00 %\n"
        "D2               : 20.00 %\n"
        "D3               : 30.00 %\n"
        "D4               : 40.00 %\n"
    )
