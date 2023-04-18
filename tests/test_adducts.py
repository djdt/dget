from molmass import Formula

from dget.adduct import adduct_from_formula, formula_from_adduct, formula_in_formula


def test_formula_in_formula():
    assert formula_in_formula(Formula("H"), Formula("CH"))
    assert formula_in_formula(Formula("CH[2H]"), Formula("C2H4[2H]2"))
    assert not formula_in_formula(Formula("H"), Formula("C[2H]"))
    assert formula_in_formula(Formula("C12H2Cl16"), Formula("C12H4Cl16"))


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


test_formula_in_formula()
test_formula_from_adduct()
test_adduct_from_formula()
