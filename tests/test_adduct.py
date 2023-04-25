import pytest
from molmass import Formula

from dget.adduct import adduct_from_formula, formula_from_adduct


def test_formula_from_adduct():
    formula = "C6H6"

    adduct = formula_from_adduct(formula, "[M]+")
    assert adduct.formula == "[C6H6]+"
    adduct = formula_from_adduct(formula, "[M]-")
    assert adduct.formula == "[C6H6]-"
    adduct = formula_from_adduct(formula, "[M+H]+")
    assert adduct.formula == "[C6H7]+"
    adduct = formula_from_adduct(formula, "[M-H]-")
    assert adduct.formula == "[C6H5]-"
    adduct = formula_from_adduct(formula, "[2M+H]+")
    assert adduct.formula == "[C12H13]+"
    adduct = formula_from_adduct(formula, "[M+H2]2+")
    assert adduct.formula == "[C6H8]2+"
    adduct = formula_from_adduct(formula, "[2M-H]-")
    assert adduct.formula == "[C12H11]-"

    with pytest.raises(ValueError):
        formula_from_adduct(formula, "M+")
    with pytest.raises(ValueError):
        formula_from_adduct(formula, "[MNa]+")
    with pytest.raises(ValueError):
        formula_from_adduct(formula, "[M+Na]")
    with pytest.raises(ValueError):
        formula_from_adduct(formula, "[M-Na]+")


def test_adduct_from_formula():
    formula = "C6H6"

    adduct = adduct_from_formula("[C6H6]+", formula)
    assert adduct == "[M]+"
    adduct = adduct_from_formula("[C6H6]-", formula)
    assert adduct == "[M]-"
    adduct = adduct_from_formula("[C6H7]+", formula)
    assert adduct == "[M+H]+"
    adduct = adduct_from_formula("[C6H5]-", formula)
    assert adduct == "[M-H]-"
    adduct = adduct_from_formula("[C12H13]+", formula)
    assert adduct == "[2M+H]+"
    adduct = adduct_from_formula("[C6H8]2+", formula)
    assert adduct == "[M+H2]2+"
    adduct = adduct_from_formula("[C12H11]-", formula)
    assert adduct == "[2M-H]-"
    adduct = adduct_from_formula("[CHNa]+", "CH")
    assert adduct == "[M+Na]+"
    adduct = adduct_from_formula("[C54H13D24N4]+", "C27H6D12N2")
    assert adduct == "[2M+H]+"

    with pytest.raises(ValueError):
        formula_from_adduct("[C2H2]+", "Na")
    with pytest.raises(ValueError):
        formula_from_adduct("[C2H2]+", "[C2H2]+")
