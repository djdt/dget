import pytest
from molmass import Formula

from dget.adduct import Adduct


def test_adduct_class():
    adduct = Adduct(Formula("C12HD8N"), "[M-H]-")
    assert adduct.base.formula == "C12H[2H]8N"
    assert adduct.formula.formula == "[C12[2H]8N]-"
    assert adduct.num_base == 1

    adduct = Adduct(Formula("C49H75N12O12"), "[M+2H]2+")
    assert adduct.base.formula == "C49H75N12O12"
    assert adduct.formula.formula == "[C49H77N12O12]2+"
    assert adduct.num_base == 1

    adduct = Adduct(Formula("C9H8BrNO4"), "[2M+2H]2+")
    assert adduct.base.formula == "C9H8BrNO4"
    assert adduct.formula.formula == "[C18H18Br2N2O8]2+"
    assert adduct.num_base == 2


def test_adducts():
    formula = Formula("C6H6")
    adduct = Adduct(formula, "[M]+")
    assert adduct.formula.formula == "[C6H6]+"
    adduct = Adduct(formula, "[M]-")
    assert adduct.formula.formula == "[C6H6]-"
    adduct = Adduct(formula, "[M+H]+")
    assert adduct.formula.formula == "[C6H7]+"
    adduct = Adduct(formula, "[M-H]-")
    assert adduct.formula.formula == "[C6H5]-"
    adduct = Adduct(formula, "[2M+H]+")
    assert adduct.formula.formula == "[C12H13]+"
    adduct = Adduct(formula, "[M+H2]2+")
    assert adduct.formula.formula == "[C6H8]2+"
    adduct = Adduct(formula, "[M+2H]2+")
    assert adduct.formula.formula == "[C6H8]2+"
    adduct = Adduct(formula, "[M+H+H]2+")
    assert adduct.formula.formula == "[C6H8]2+"
    adduct = Adduct(formula, "[2M-H]-")
    assert adduct.formula.formula == "[C12H11]-"
    adduct = Adduct(formula, "[M+K-H2]-")
    assert adduct.formula.formula == "[C6H4K]-"

    with pytest.raises(ValueError):
        Adduct(formula, "M+")
    with pytest.raises(ValueError):
        a = Adduct(formula, "[MNa]+")
        print(a.formula)
    with pytest.raises(ValueError):
        Adduct(formula, "[M+Na]")
    with pytest.raises(ValueError):
        Adduct(formula, "[M-Na]+")
