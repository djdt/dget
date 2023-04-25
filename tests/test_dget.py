from pathlib import Path

import numpy as np
from molmass import Formula

from dget import DGet

data_path = Path(__file__).parent.joinpath("data")


def test_dget_know_data():
    formulas = {
        "C12HD8N": ("[M-H]-", 94.4),
        "C42H69D13NO8P": ("[M+H]+", 99.0),
        "C16H11D7N2O4S": ("[M-H]-", 95.4),
        "C57H3D101O6": ("[M+Na]+", 95.1),
        "C13H9D7N2O2": ("[M+Na]+", 94.9),
    }

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
    assert np.isclose(dget.deuteration, 0.5)
    dget._probabilities = np.array([0.1, 0.1, 0.2, 0.2, 0.4])
    assert np.isclose(dget.deuteration, 0.675)


def test_targets():
    dget = DGet("C20D6", tofdata=(np.array([0.0, 999.0]), np.array([0.0, 0.0])))
    formulas = ["C20H6", "C20H5D", "C20H4D2", "C20H3D3", "C20H2D4", "C20HD5", "C20D6"]

    assert np.allclose(dget.targets[:7], [Formula(f).isotope.mz for f in formulas])
    assert np.allclose(
        dget.targets[6:],
        [s.mz for s in dget.formula.spectrum().values()],
    )
