from molmass import Formula, FormulaError
from PySide6 import QtCore, QtGui, QtWidgets

from dget.adduct import Adduct
from dget.dget import DGet

from dget.gui.validators import DGetAdductValidator, DGetFormulaValidator

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
        self.le_formula.textChanged.connect(self.setFormulaColor)

        self.cb_adduct = QtWidgets.QComboBox()
        self.loadAdducts()

        self.cb_adduct.setEditable(True)
        self.cb_adduct.setValidator(DGetAdductValidator())
        self.cb_adduct.currentTextChanged.connect(self.onFormulaChange)
        self.cb_adduct.currentTextChanged.connect(self.setAdductColor)
        self.cb_adduct.editTextChanged.connect(self.onFormulaChange)
        self.cb_adduct.editTextChanged.connect(self.setAdductColor)

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

    def setAdductColor(self) -> None:
        palette = self.cb_adduct.palette()
        print(self.cb_adduct.lineEdit().hasAcceptableInput())
        if self.cb_adduct.lineEdit().hasAcceptableInput():
            color = self.palette().text().color()
            palette.setColor(QtGui.QPalette.ColorRole.Text, color)
        else:
            palette.setColor(QtGui.QPalette.ColorRole.Text, QtCore.Qt.GlobalColor.red)
        self.cb_adduct.lineEdit().setPalette(palette)

    def setFormulaColor(self) -> None:
        palette = self.le_formula.palette()
        if self.le_formula.hasAcceptableInput():
            color = self.palette().text().color()
            palette.setColor(QtGui.QPalette.ColorRole.Text, color)
        else:
            palette.setColor(QtGui.QPalette.ColorRole.Text, QtCore.Qt.GlobalColor.red)
        self.le_formula.setPalette(palette)

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
