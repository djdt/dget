import numpy as np
from molmass import Formula

from dget.formula import divide_formulas, formula_in_formula


def test_divide_formulas():
    n, r = divide_formulas(Formula("H"), Formula("H"))
    assert n == 1
    assert r is None
    n, r = divide_formulas(Formula("Na"), Formula("H"))
    assert n == 0
    assert r._formula == "Na"
    n, r = divide_formulas(Formula("H5"), Formula("H"))
    assert n == 5
    assert r is None
    n, r = divide_formulas(Formula("C4H8"), Formula("CH"))
    assert n == 4
    assert r._formula == "H4"
    n, r = divide_formulas(Formula("C4H8"), Formula("C2H2"))
    assert n == 2
    assert r._formula == "H4"


def test_formula_in_formula():
    assert formula_in_formula(Formula("H"), Formula("CH"))
    assert formula_in_formula(Formula("CH[2H]"), Formula("C2H4[2H]2"))
    assert not formula_in_formula(Formula("H"), Formula("C[2H]"))
    assert formula_in_formula(Formula("C12H2Cl16"), Formula("C12H4Cl16"))


# def test_combine_spectra():
#     def weighted_average(a, b, wa, wb):
#         return (a * wa + b * wb) / (wa + wb)

#     # fractions calculated correctly
#     na_spec = Formula("Na").spectrum()
#     y_spec = Formula("Y").spectrum()
#     f_spec = Formula("F").spectrum()
#     spectrum = combine_spectra([na_spec, y_spec, f_spec])
#     assert list(spectrum.keys()) == [19, 23, 89]
#     assert spectrum[19].fraction == 0.5
#     assert spectrum[19].fraction == 0.5
#     assert spectrum[23].fraction == 0.5

#     # non-overlapping
#     na_spec = Formula("Na").spectrum()
#     cl_spec = Formula("Cl").spectrum()
#     spectrum = combine_spectra([na_spec, cl_spec])
#     assert list(spectrum.keys()) == [23, 35, 37]
#     for key in ["mass", "mz"]:
#         assert np.allclose(getattr(spectrum[23], key), getattr(na_spec[23], key))
#         assert np.allclose(getattr(spectrum[35], key), getattr(cl_spec[35], key))
#         assert np.allclose(getattr(spectrum[37], key), getattr(cl_spec[37], key))

#     # same (full overlap)
#     spectra = [Formula(f).spectrum() for f in ["C2H2", "C2H2"]]
#     spectrum = combine_spectra(spectra)
#     true_spectrum = Formula("C2H2").spectrum()
#     for key in spectrum:
#         assert np.allclose(spectrum[key].astuple(), true_spectrum[key].astuple())

#     # Partial overlap
#     c2h2_spec = Formula("C2H2").spectrum()
#     c2d2_spec = Formula("C2D2").spectrum()
#     spectrum = combine_spectra([c2h2_spec, c2d2_spec])

#     assert list(spectrum.keys()) == [26, 27, 28, 29, 30]
#     for i in [26, 27]:
#         for key in ["mass", "mz"]:
#             assert np.allclose(getattr(spectrum[i], key), getattr(c2h2_spec[i], key))
#     # first overlap
#     for i in [28, 29, 30]:
#         for key in ["mass", "mz"]:
#             assert np.isclose(
#                 getattr(spectrum[i], key),
#                 weighted_average(
#                     getattr(c2h2_spec[i], key),
#                     getattr(c2d2_spec[i], key),
#                     c2h2_spec[i].fraction,
#                     c2d2_spec[i].fraction,
#                 ),
#             )
