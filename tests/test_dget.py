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
    dget.number_states = 5
    assert np.all(dget.deuteration_states == [0, 1, 2, 3, 4])
    assert np.isclose(dget.deuteration, 0.5)


def test_number_states():
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
        "CD5", number_states=3, tofdata=(np.array([0.0, 999.0]), np.array([0.0, 0.0]))
    )
    assert np.all(dget.deuteration_states == [3, 4, 5])
    dget = DGet(
        "CD5", number_states=30, tofdata=(np.array([0.0, 999.0]), np.array([0.0, 0.0]))
    )
    assert np.all(dget.deuteration_states == [0, 1, 2, 3, 4, 5])
    with pytest.raises(ValueError):
        dget = DGet(
            "CD5",
            number_states=0,
            tofdata=(np.array([0.0, 999.0]), np.array([0.0, 0.0])),
        )

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
        dget.targets[6:],
        [s.mz for s in dget.formula.spectrum().values()],
    )
