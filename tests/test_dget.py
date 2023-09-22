from io import StringIO
from pathlib import Path

import numpy as np
import pytest
from molmass import Formula

from dget import DGet

data_path = Path(__file__).parent.joinpath("data")

formulas = {
    "C12HD8N": ("[M-H]-", 94.4),
    "C42H69D13NO8P": ("[M+H]+", 99.0),
    "C16H11D7N2O4S": ("[M-H]-", 95.4),
    "C57H3D101O6": ("[M+Na]+", 95.1),
    "C13H9D7N2O2": ("[M+Na]+", 94.9),
    "C20D24O6": ("[M+Na]+", 50.0),
    "C48H18D78NO8P": ("[M+Na]+", 94.0),
}


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


def test_dget_know_data():
    for formula, (adduct, percent_d) in formulas.items():
        dget = DGet(
            formula,
            data_path.joinpath(f"{formula}.txt"),
            adduct=adduct,
            loadtxt_kws={"delimiter": "\t"},
        )
        dget.align_tof_with_spectra()
        # This test is too lenient, but best we can do with the data we have
        assert np.isclose(dget.deuteration * 100.0, percent_d, atol=1.6)

    # Known previous error
    dget = DGet(
        "C20D24O6",
        data_path.joinpath("C20D24O6.txt"),
        adduct="[M+Na]+",
        loadtxt_kws={"delimiter": "\t"},
    )
    assert dget.deuteration_states.size > 1
    # Adduct at M+Na, peak at M, cut off before
    dget = DGet(
        "C48H18D78NO8P",
        data_path.joinpath("C48H18D78NO8P.txt"),
        adduct="[M+Na]+",
        loadtxt_kws={"delimiter": "\t"},
    )
    assert np.all(
        dget.deuteration_states == [67, 68, 69, 70, 71, 72, 73, 74, 75, 76, 77, 78]
    )


def test_dget_auto_adduct():
    for formula, (adduct, _) in formulas.items():
        if formula == "C20D24O6":  # Low percent D, skip auto adduct test
            continue
        dget = DGet(
            formula,
            data_path.joinpath(f"{formula}.txt"),
            loadtxt_kws={"delimiter": "\t"},
        )
        best, _ = dget.guess_adduct_from_base_peak()
        if best.adduct != adduct:
            raise ValueError(formula, adduct)
        assert best.adduct == adduct


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


def test_deuteration_error():
    dget = DGet("C2H2D4", tofdata=(np.array([0.0, 999.0]), np.array([0.0, 0.0])))
    dget._probabilities = np.array([0.2, 0.2, 0.2, 0.2, 0.2])
    dget._probability_remainders = np.array([0.0, 0.0, 0.0, 0.0, 0.0])
    assert np.isclose(dget.deuteration_error, 0.0)
    dget._probability_remainders = np.array([0.1, 0.1, 0.1, 0.1, 0.0])
    assert np.isclose(dget.deuteration_error, 0.4)
    dget._probability_remainders = np.array([0.1, 0.1, 0.1, 0.1, 0.1])
    assert np.isclose(dget.deuteration_error, 0.5)
    dget._probability_remainders = np.array([0.2, 0.2, 0.2, 0.2, 0.0])
    assert np.isclose(dget.deuteration_error, 0.8)
    dget._probability_remainders = np.array([0.2, 0.2, 0.2, 0.2, 0.2])
    assert np.isclose(dget.deuteration_error, 1.0)


def test_integration():
    x = np.concatenate(
        [
            np.linspace(16.0, 16.1, 100),
            np.linspace(17.0, 17.1, 100),
            np.linspace(18, 22.1, 100),
        ]
    )
    y = np.concatenate(
        [
            np.sin(np.linspace(0.0, np.pi, 100, endpoint=False)),
            2.0 * np.sin(np.linspace(0.0, np.pi, 100, endpoint=False)),
            np.zeros(100),
        ]
    )
    # Could be better if we could test counts
    dget = DGet("CH3D", tofdata=(x, y), adduct="[M]+", signal_mode="peak height")
    assert np.allclose(dget.deuteration_probabilites, [0.33, 0.66], atol=0.01)

    dget = DGet("CH3D", tofdata=(x, y), adduct="[M]+", signal_mode="peak area")
    assert np.allclose(dget.deuteration_probabilites, [0.33, 0.66], atol=0.01)

    # Test height != area
    y = np.zeros_like(x)
    y[40:60] = 2.0
    y[120:180] = 2.0

    dget = DGet("CH3D", tofdata=(x, y), adduct="[M]+", signal_mode="peak height")
    assert np.allclose(dget.deuteration_probabilites, [0.5, 0.5], atol=0.01)

    dget = DGet("CH3D", tofdata=(x, y), adduct="[M]+", signal_mode="peak area")
    assert np.allclose(dget.deuteration_probabilites, [0.25, 0.75], atol=0.01)


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


def test_targets():
    dget = DGet("C20D6", tofdata=(np.array([0.0, 999.0]), np.array([0.0, 0.0])))
    formulas = ["C20H6", "C20H5D", "C20H4D2", "C20H3D3", "C20H2D4", "C20HD5", "C20D6"]

    assert np.allclose(dget.targets[:7], [Formula(f).isotope.mz for f in formulas])
    assert np.allclose(
        dget.targets[-4:],
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
    dget._probability_remainders = np.array([0.0, 0.1, 0.2, 0.3, 0.4]) / 2.0

    results = StringIO()
    dget.print_results(file=results)
    assert results.getvalue() == (
        "Formula          : C2H2D4\n"
        "Adduct           : [M]+\n"
        "M/Z              : 34.0721\n"
        "Adduct M/Z       : 34.0715\n"
        "%Deuteration     : 75.00 ± 50.00 %\n"
        "\n"
        "Deuteration Ratio Spectra\n"
        "D0               :  0.00 %\n"
        "D1               : 10.00 %\n"
        "D2               : 20.00 %\n"
        "D3               : 30.00 %\n"
        "D4               : 40.00 %\n"
    )
