from molmass import GROUPS, Formula, FormulaError
from molmass.elements import ELEMENTS
from PySide6 import QtCore, QtGui, QtWidgets

from dget.adduct import Adduct
from dget.dget import DGet


class DGetFormulaValidator(QtGui.QValidator):
    def __init__(self, le: QtWidgets.QLineEdit, parent: QtCore.QObject | None = None):
        super().__init__(parent)
        self.le = le
        self.acceptable_tokens = [element.symbol for element in ELEMENTS]
        self.acceptable_tokens.extend([k for k in GROUPS.keys()])
        self.acceptable_tokens.append("D")
        self.acceptable_tokens.sort(key=lambda s: -len(s))

    def validate(self, input: str, pos: int) -> QtGui.QValidator.State:
        if "D" not in input or "[2H]" not in input:
            return QtGui.QValidator.State.Intermediate
        formula = Formula(input, parse_oligos=False)
        try:
            formula.formula
        except FormulaError:
            return QtGui.QValidator.State.Intermediate
        return QtGui.QValidator.State.Acceptable

    def fixup(self, input: str) -> None:
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
        if input != new_input:
            self.le.setText(new_input)


class DGetControls(QtWidgets.QDockWidget):
    delimiter_names = {"Comma": ",", "Semicolon": ";", "Tab": "\t", "Space": " "}
    adductChanged = QtCore.Signal(Adduct)
    processOptionsChanged = QtCore.Signal()

    def __init__(self, parent: QtWidgets.QWidget | None = None):
        super().__init__("Controls", parent)

        self.dockLocationChanged.connect(self.changeLayout)

        self.le_formula = QtWidgets.QLineEdit()
        self.le_formula.setValidator(DGetFormulaValidator(self.le_formula))
        self.le_formula.textChanged.connect(self.onFormulaChange)

        self.cb_adduct = QtWidgets.QComboBox()
        self.cb_adduct.addItems(DGet.common_adducts)
        self.cb_adduct.setEditable(True)
        self.cb_adduct.currentTextChanged.connect(self.onFormulaChange)
        self.cb_adduct.editTextChanged.connect(self.onFormulaChange)

        # self.realign = QtWidgets.QCheckBox("Re-align HRMS data")
        # self.subtract_bg = QtWidgets.QCheckBox("Subtract HRMS baseline")
        self.cutoff = QtWidgets.QLineEdit()
        self.cutoff.setToolTip(
            "Deuteration calculation cutoff as a m/z (e.g., 123.4) or state (e.g., D10)"
        )
        self.cutoff.editingFinished.connect(self.processOptionsChanged)

        self.mass_shift = QtWidgets.QDoubleSpinBox()
        self.mass_shift.setRange(-100.0, 100.0)
        self.mass_shift.setDecimals(4)
        self.mass_shift.setSuffix(" m/z")
        self.mass_shift.setSingleStep(0.01)
        self.mass_shift.valueChanged.connect(self.processOptionsChanged)

        gbox_proc = QtWidgets.QGroupBox("Proccessing options")
        gbox_proc.setLayout(QtWidgets.QFormLayout())
        # gbox_proc.layout().addWidget(self.realign)
        # gbox_proc.layout().addWidget(self.subtract_bg)
        gbox_proc.layout().addRow("Cutoff", self.cutoff)
        gbox_proc.layout().addRow("Mass shift", self.mass_shift)

        layout_formula = QtWidgets.QFormLayout()
        layout_formula.addRow("Formula", self.le_formula)
        layout_formula.addRow("Adduct", self.cb_adduct)

        self.layout = QtWidgets.QVBoxLayout()
        self.layout.addLayout(layout_formula)
        self.layout.addWidget(gbox_proc)
        self.layout.addStretch(1)

        widget = QtWidgets.QWidget()
        widget.setLayout(self.layout)

        self.setWidget(widget)

    def onFormulaChange(self) -> None:
        formula = self.le_formula.text()
        adduct = self.cb_adduct.currentText()
        formula = Formula(self.le_formula.text())
        try:
            formula.monoisotopic_mass
        except FormulaError:
            return
        try:
            adduct = Adduct(formula, adduct)
        except ValueError:
            return
        self.adductChanged.emit(adduct)

    def changeLayout(self, area: QtCore.Qt.DockWidgetArea) -> None:
        if area in [
            QtCore.Qt.DockWidgetArea.LeftDockWidgetArea,
            QtCore.Qt.DockWidgetArea.RightDockWidgetArea,
        ]:
            self.layout.setDirection(QtWidgets.QBoxLayout.Direction.TopToBottom)
        else:
            self.layout.setDirection(QtWidgets.QBoxLayout.Direction.LeftToRight)
