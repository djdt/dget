import logging
import re
import sys
from pathlib import Path
from types import TracebackType

import numpy as np
from molmass import Formula, FormulaError
from molmass.elements import ELEMENTS
from PySide6 import QtCore, QtGui, QtWidgets
from spcal.gui.log import LoggingDialog

import dget.io.shimadzu
import dget.io.text
from dget import DGet
from dget.adduct import Adduct
from dget.gui.graphs import DGetMSGraph

logger = logging.getLogger(__name__)


class DGetFormulaValidator(QtGui.QValidator):
    re_token = re.compile(r"(\[\d+)?([a-zA-Z][a-z]?)\]?\d*")

    def __init__(self, le: QtWidgets.QLineEdit, parent: QtCore.QObject | None = None):
        super().__init__(parent)
        self.le = le
        self.symbols = [element.symbol for element in ELEMENTS]
        self.symbols.append("D")

    def validate(self, input: str, pos: int) -> QtGui.QValidator.State:
        if "D" not in input or "[2H]" not in input:
            return QtGui.QValidator.State.Intermediate
        tokens = self.re_token.findall(input)
        for _, token in tokens:
            if token not in self.symbols:
                return QtGui.QValidator.State.Intermediate
        return QtGui.QValidator.State.Acceptable

    def fixup(self, input: str) -> None:
        upper_idx = []
        for m in self.re_token.finditer(input):
            token = m.group(2)
            if token not in self.symbols:
                if token.capitalize() in self.symbols:
                    upper_idx.append(m.start(2))
                elif (
                    len(token) == 2
                    and token[0].upper() in self.symbols
                    and token[1].upper() in self.symbols
                ):
                    upper_idx.append(m.start(2))
                    upper_idx.append(m.start(2) + 1)

        if len(upper_idx) > 0:
            new_input = "".join(
                x.upper() if i in upper_idx else x for i, x in enumerate(input)
            )
            self.le.setText(new_input)


class DGetControls(QtWidgets.QDockWidget):
    delimiter_names = {"Comma": ",", "Semicolon": ";", "Tab": "\t", "Space": " "}
    adductChanged = QtCore.Signal(Adduct)

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

        self.ms_delimiter = QtWidgets.QComboBox()
        self.ms_delimiter.addItems(list(self.delimiter_names.keys()))
        self.ms_skiprows = QtWidgets.QSpinBox()
        self.ms_skiprows.setRange(0, 99)
        self.ms_skiprows.setValue(0)
        self.ms_mass_col = QtWidgets.QSpinBox()
        self.ms_mass_col.setRange(1, 99)
        self.ms_mass_col.setValue(1)
        self.ms_signal_col = QtWidgets.QSpinBox()
        self.ms_signal_col.setRange(1, 99)
        self.ms_signal_col.setValue(2)

        self.realign = QtWidgets.QCheckBox("Re-align HRMS data")
        self.subtract_bg = QtWidgets.QCheckBox("Subtract HRMS baseline")
        self.cutoff = QtWidgets.QLineEdit()

        gbox_ms = QtWidgets.QGroupBox("HRMS options")
        gbox_ms.setLayout(QtWidgets.QFormLayout())
        # gbox_ms.layout().addWidget(self.ms_button_open)
        gbox_ms.layout().addRow("Delimiter", self.ms_delimiter)
        gbox_ms.layout().addRow("Skip rows", self.ms_skiprows)
        gbox_ms.layout().addRow("Mass column", self.ms_mass_col)
        gbox_ms.layout().addRow("Signal column", self.ms_signal_col)

        gbox_proc = QtWidgets.QGroupBox("Proccessing options")
        gbox_proc.setLayout(QtWidgets.QFormLayout())
        gbox_proc.layout().addWidget(self.realign)
        gbox_proc.layout().addWidget(self.subtract_bg)
        gbox_proc.layout().addRow("Calc. cutoff", self.cutoff)

        layout_formula = QtWidgets.QFormLayout()
        layout_formula.addRow("Formula", self.le_formula)
        layout_formula.addRow("Adduct", self.cb_adduct)

        self.layout = QtWidgets.QVBoxLayout()
        self.layout.addLayout(layout_formula)
        self.layout.addWidget(gbox_ms)
        self.layout.addWidget(gbox_proc)
        self.layout.addStretch(1)

        widget = QtWidgets.QWidget()
        widget.setLayout(self.layout)

        self.setWidget(widget)

    def setMSOptionsEnabled(self, enabled: bool) -> None:
        self.ms_delimiter.setEnabled(enabled)
        self.ms_skiprows.setEnabled(enabled)
        self.ms_mass_col.setEnabled(enabled)
        self.ms_signal_col.setEnabled(enabled)

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
        print("emitting adduct", adduct)
        self.adductChanged.emit(adduct)

    # @property
    # def formula(self) -> Formula | None:
    #     if not self.le_formula.hasAcceptableInput():
    #         return None
    #     try:
    #         formula = Formula(self.le_formula.text())
    #         formula.monoisotopic_mass
    #     except ValueError:
    #         return None
    #     return formula

    @property
    def ms_loadtxt_kws(self) -> dict:
        return {
            "delimiter": self.delimiter_names[self.ms_delimiter.currentText()],
            "skiprows": self.ms_skiprows.value(),
            "usecols": (self.ms_mass_col.value() - 1, self.ms_signal_col.value() - 1),
        }

    @ms_loadtxt_kws.setter
    def ms_loadtxt_kws(self, kws: dict) -> None:
        if "delimiter" in kws:
            delimiter = next(
                k for k, v in self.delimiter_names.items() if v == kws["delimiter"]
            )
            self.ms_delimiter.setCurrentText(delimiter)
        if "skiprows" in kws:
            self.ms_skiprows.setValue(kws["skiprows"])
        if "usecols" in kws:
            self.ms_mass_col.setValue(kws["usecols"][0] + 1)
            self.ms_signal_col.setValue(kws["usecols"][1] + 1)

    def changeLayout(self, area: QtCore.Qt.DockWidgetArea) -> None:
        if area in [
            QtCore.Qt.DockWidgetArea.LeftDockWidgetArea,
            QtCore.Qt.DockWidgetArea.RightDockWidgetArea,
        ]:
            self.layout.setDirection(QtWidgets.QBoxLayout.Direction.TopToBottom)
        else:
            self.layout.setDirection(QtWidgets.QBoxLayout.Direction.LeftToRight)


class DGetResults(QtWidgets.QDockWidget):
    def __init__(self, parent: QtWidgets.QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle("Results")

        self.text = QtWidgets.QTextBrowser()

        self.setWidget(self.text)


class DGetMainWindow(QtWidgets.QMainWindow):
    dataLoaded = QtCore.Signal(np.ndarray, np.ndarray)

    def __init__(self, parent: QtWidgets.QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle("DGet!")
        self.resize(1280, 800)

        # self.dataLoaded.connect(self.updateMSGraph)

        self.dget: DGet | None = None
        self.hrms_file: Path | None = None
        self.hrms_data: tuple[np.ndarray, np.ndarray] | None = None

        self.log = LoggingDialog()
        self.log.setWindowTitle("SPCal Log")

        self.controls = DGetControls()
        self.controls.setEnabled(False)

        self.results = DGetResults()

        self.graph = DGetMSGraph()

        self.controls.adductChanged.connect(self.onAdductChanged)

        self.addDockWidget(QtCore.Qt.DockWidgetArea.LeftDockWidgetArea, self.controls)
        self.addDockWidget(QtCore.Qt.DockWidgetArea.BottomDockWidgetArea, self.results)
        self.setCentralWidget(self.graph)

        self.createMenus()
        self.loadFile("/home/tom/Downloads/NDF-A-009.txt")

    def startHRMSBrowser(self) -> None:
        ok, file = QtWidgets.QFileDialog.getOpenFileName(
            self, "Open HRMS data", "", "CSV Documents (*.csv *.txt);;All files (*)"
        )
        if ok:
            self.loadFile(file)

    def loadFile(self, file: Path | str) -> None:
        if isinstance(file, str):
            file = Path(file)

        if dget.io.shimadzu.is_shimadzu_file(file):
            loadtxt_kws = dget.io.shimadzu.get_loadtxt_kws(file)
            self.controls.setMSOptionsEnabled(False)
        else:
            loadtxt_kws = dget.io.text.guess_loadtxt_kws(
                file, loadtxt_kws=self.controls.ms_loadtxt_kws
            )
            self.controls.setMSOptionsEnabled(True)
        self.controls.ms_loadtxt_kws = loadtxt_kws

        self.hrms_file = file

        x, y = np.loadtxt(file, unpack=True, dtype=np.float32, **loadtxt_kws)
        self.hrms_data = (x, y)
        self.dataLoaded.emit(x, y)

        self.controls.setEnabled(True)
        self.graph.drawMSData(x, y)

    def onAdductChanged(self, adduct: Adduct) -> None:
        self.graph.plot.setTitle(
            f"{adduct.base.formula} {adduct.adduct} \nm/z={adduct.formula.monoisotopic_mass:.4f}"
        )
        adducts = []
        for ad in DGet.common_adducts:
            try:
                adducts.append(Adduct(adduct.base, ad))
            except ValueError:
                pass
        self.graph.labelAdducts(adducts)

    # def updateDGet(self) -> None:
    #     if self.hrms_data is None:
    #         return
    #
    #     self.dget = DGet(
    #         self.controls.formula.text(),
    #         tofdata=self.hrms_data,
    #         adduct=self.controls.adduct.currentText(),
    #         cutoff=self.controls.cutoff.text(),
    #         signal_mode=self.signal_mode,
    #         signal_mass_width=self.signal_mass_width,
    #     )

    def createMenus(self) -> None:
        self.action_open = QtGui.QAction(
            QtGui.QIcon.fromTheme("document-open"), "Open HRMS data file"
        )
        self.action_open.setStatusTip("Open an HRMS data file of a deuterated compound")
        self.action_open.triggered.connect(self.startHRMSBrowser)

        self.action_quit = QtGui.QAction(
            QtGui.QIcon.fromTheme("application-exit"), "Exit"
        )
        self.action_quit.setStatusTip("Quit DGet!")
        self.action_quit.triggered.connect(self.close)

        menu_file = QtWidgets.QMenu("File")
        menu_file.addAction(self.action_open)
        menu_file.addAction(self.action_quit)

        menu_view = QtWidgets.QMenu("View")
        menu_view.addSection("Show/hide dock widgets")
        for dock in self.findChildren(QtWidgets.QDockWidget):
            menu_view.addAction(dock.toggleViewAction())

        menu_help = QtWidgets.QMenu("Help")

        self.menuBar().addMenu(menu_file)
        self.menuBar().addMenu(menu_view)
        self.menuBar().addMenu(menu_help)

    def exceptHook(
        self, etype: type, value: BaseException, tb: TracebackType | None = None
    ):  # pragma: no cover
        """Redirect errors to the log."""
        if etype == KeyboardInterrupt:
            logger.info("Keyboard interrupt, exiting.")
            sys.exit(1)
        logger.exception("Uncaught exception", exc_info=(etype, value, tb))
        QtWidgets.QMessageBox.critical(self, "Uncaught Exception", str(value))
