from molmass import GROUPS, Formula, FormulaError
from molmass.elements import ELEMENTS
from PySide6 import QtCore, QtGui, QtWidgets

from dget.adduct import Adduct
from dget.dget import DGet


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


class DGetControls(QtWidgets.QDockWidget):
    delimiter_names = {"Comma": ",", "Semicolon": ";", "Tab": "\t", "Space": " "}
    adductChanged = QtCore.Signal(Adduct)
    processOptionsChanged = QtCore.Signal()

    def __init__(self, parent: QtWidgets.QWidget | None = None):
        super().__init__("Controls", parent)
        self.setObjectName("dget-controls-dock")

        self.dockLocationChanged.connect(self.changeLayout)

        self.le_formula = QtWidgets.QLineEdit()
        self.le_formula.setValidator(DGetFormulaValidator())
        self.le_formula.textChanged.connect(self.onFormulaChange)

        self.cb_adduct = QtWidgets.QComboBox()
        self.loadAdducts()

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

        self.main_layout = QtWidgets.QVBoxLayout()
        self.main_layout.addLayout(layout_formula)
        self.main_layout.addWidget(gbox_proc)
        self.main_layout.addStretch(1)

        widget = QtWidgets.QWidget()
        widget.setLayout(self.main_layout)

        self.setWidget(widget)

    def loadAdducts(self) -> None:
        current = self.cb_adduct.currentText()
        index = 0
        self.cb_adduct.blockSignals(True)
        self.cb_adduct.clear()
        settings = QtCore.QSettings()
        if settings.contains("dget/adducts/size"):
            size = settings.beginReadArray("dget/adducts")
            for i in range(size):
                settings.setArrayIndex(i)
                adduct = str(settings.value("adduct"))
                self.cb_adduct.addItem(adduct)
                if adduct == current:
                    index = i
            settings.endArray()
        else:
            self.cb_adduct.addItems(DGet.common_adducts)
        self.cb_adduct.setCurrentIndex(index)
        self.cb_adduct.blockSignals(False)

    def onFormulaChange(self) -> None:
        adduct = self.adduct()
        if adduct is not None:
            self.adductChanged.emit(adduct)

    def adduct(self) -> Adduct | None:
        adduct = self.cb_adduct.currentText()
        formula = Formula(self.le_formula.text())
        try:
            _ = formula.monoisotopic_mass
            return Adduct(formula, adduct)
        except (FormulaError, ValueError):
            return None

    def changeLayout(self, area: QtCore.Qt.DockWidgetArea) -> None:
        if area in [
            QtCore.Qt.DockWidgetArea.LeftDockWidgetArea,
            QtCore.Qt.DockWidgetArea.RightDockWidgetArea,
        ]:
            self.main_layout.setDirection(QtWidgets.QBoxLayout.Direction.TopToBottom)
        else:
            self.main_layout.setDirection(QtWidgets.QBoxLayout.Direction.LeftToRight)
