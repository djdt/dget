from molmass import GROUPS, Formula, FormulaError
from molmass.elements import ELEMENTS
from PySide6 import QtCore, QtGui

from dget.adduct import Adduct


class DGetFormulaValidator(QtGui.QValidator):
    def __init__(self, parent: QtCore.QObject | None = None):
        super().__init__(parent)
        self.acceptable_tokens = [element.symbol for element in ELEMENTS]
        self.acceptable_tokens.extend([k for k in GROUPS.keys()])
        self.acceptable_tokens.append("D")
        self.acceptable_tokens.sort(key=lambda s: -len(s))

    def fixup(self, input: str) -> str:
        bad_chars = []
        new_input = ""

        while len(new_input) < len(input):
            pos = len(new_input)
            if not input[pos].isalpha():
                new_input += input[pos]
                continue

            found = False
            for token in self.acceptable_tokens:
                if input[pos:].startswith(token):
                    new_input += token
                    found = True
                    break

            if not found:
                for token in self.acceptable_tokens:
                    if input[pos:].lower().startswith(token.lower()):
                        new_input += token
                        found = True
                        break

            if not found:
                bad_chars.append(pos)
                new_input += input[pos]

        return new_input

    def validate(self, input: str, pos: int) -> QtGui.QValidator.State:
        if "D" not in input and "[2H]" not in input:
            return QtGui.QValidator.State.Intermediate

        try:
            formula = Formula(input, parse_oligos=False)
            formula.formula
        except FormulaError:
            return QtGui.QValidator.State.Intermediate

        return QtGui.QValidator.State.Acceptable


class DGetAdductValidator(QtGui.QValidator):
    def __init__(self, parent: QtCore.QObject | None = None):
        super().__init__(parent)

    def fixup(self, input: str) -> str:
        new_input = input.replace(" ", "")
        return new_input

    def validate(self, input: str, pos: int) -> QtGui.QValidator.State:
        if not Adduct.is_valid_adduct(input):
            return QtGui.QValidator.State.Intermediate

        return QtGui.QValidator.State.Acceptable


class DGetCutOffValidator(QtGui.QValidator):
    def __init__(self, parent: QtCore.QObject | None = None):
        super().__init__(parent)

    def fixup(self, input: str) -> str:
        new_input = input.replace(" ", "")
        return new_input

    def validate(self, input: str, pos: int) -> QtGui.QValidator.State:
        if len(input) == 0:
            return QtGui.QValidator.State.Acceptable

        if input.startswith("D"):
            if len(input) == 1:
                return QtGui.QValidator.State.Intermediate
            try:
                int(input[1:])
            except ValueError:
                return QtGui.QValidator.State.Invalid
        elif input.startswith("-"):
            return QtGui.QValidator.State.Invalid
        else:
            try:
                float(input)
            except ValueError:
                if any(input.endswith(x) for x in "eE+-."):
                    return QtGui.QValidator.State.Intermediate
                return QtGui.QValidator.State.Invalid
        return QtGui.QValidator.State.Acceptable
