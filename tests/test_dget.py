from pathlib import Path

import numpy as np

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
        assert np.isclose(dget.deuteration * 100.0, percent_d, atol=1.0)
