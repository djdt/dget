import logging
import sys
from pathlib import Path
from types import TracebackType

import numpy as np
from molmass import GROUPS, Formula, FormulaError
from molmass.elements import ELEMENTS
from PySide6 import QtCore, QtGui, QtWidgets
from spcal.gui.log import LoggingDialog

from dget import DGet
from dget.adduct import Adduct
from dget.gui.graphs import DGetMSGraph, DGetSpectraGraph
from dget.gui.importdialog import TextImportDialog

logger = logging.getLogger(__name__)


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
                        print("accepted token", token)
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

        self.realign = QtWidgets.QCheckBox("Re-align HRMS data")
        self.subtract_bg = QtWidgets.QCheckBox("Subtract HRMS baseline")
        self.cutoff = QtWidgets.QLineEdit()

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
        self.signal_mode = "peak height"
        self.signal_mass_width = 0.3

        self.dget: DGet | None = None
        self.hrms_file: Path | None = None

        self.log = LoggingDialog()
        self.log.setWindowTitle("SPCal Log")

        self.controls = DGetControls()
        self.controls.setEnabled(False)

        self.results = DGetResults()

        self.graph_ms = DGetMSGraph()
        # self.graph_ms_toolbar = DGetGraphToolbar(self.graph_ms)
        dock = QtWidgets.QDockWidget("Formula Spectra")
        self.graph_spectra = DGetSpectraGraph()
        dock.setWidget(self.graph_spectra)
        dock.setShortcutAutoRepeat

        self.controls.adductChanged.connect(self.onAdductChanged)

        self.addDockWidget(QtCore.Qt.DockWidgetArea.LeftDockWidgetArea, self.controls)
        self.addDockWidget(QtCore.Qt.DockWidgetArea.BottomDockWidgetArea, self.results)
        self.addDockWidget(QtCore.Qt.DockWidgetArea.LeftDockWidgetArea, dock)
        #
        # widget = QtWidgets.QWidget()
        # widget.setLayout(QtWidgets.QVBoxLayout())
        # widget.layout().addWidget(self.graph_ms, 1)
        # widget.layout().addWidget(self.graph_ms_toolbar, 0)

        self.setCentralWidget(self.graph_ms)

        self.createMenus()
        self.createToolBar()

    def startHRMSBrowser(self, file: str | Path | None = None) -> None:
        if file is None:
            file, _ = QtWidgets.QFileDialog.getOpenFileName(
                self,
                "Open HRMS data",
                "",
                "CSV Documents (*.csv *.text *.txt);;All files (*)",
            )
        if file != "":
            dlg = TextImportDialog(file)
            dlg.dataImported.connect(self.loadData)
            dlg.exec()

    def loadData(self, path: Path, x: np.ndarray, y: np.ndarray) -> None:
        self.controls.setEnabled(True)
        self.graph_ms.setData(x, y)
        self.graph_ms.plot.setTitle(path.stem)

    def onAdductChanged(self, adduct: Adduct) -> None:
        self.graph_ms.setAdductLabel(adduct)
        adducts = []
        for ad in DGet.common_adducts:
            try:
                adducts.append(Adduct(adduct.base, ad))
            except ValueError:
                pass
        self.graph_ms.labelAdducts(adducts)

        spectra = adduct.formula.spectrum(min_fraction=DGet.min_fraction_for_spectra)

        # Seperate from DGet so we can plot non-deuterated formula
        x = np.array([s.mz for s in spectra.values()])
        y = np.array([s.fraction for s in spectra.values()])
        y = y / y.max()
        self.graph_spectra.setData(x, y)

        self.updateDGet(adduct)

    def updateDGet(self, adduct: Adduct) -> None:
        try:
            cutoff = self.controls.cutoff.text()
            self.dget = DGet(
                adduct.base,
                tofdata=self.graph_ms.ms_series.getData(),
                adduct=adduct.adduct,
                cutoff=cutoff if len(cutoff) > 0 else None,
                signal_mode=self.signal_mode,
                signal_mass_width=self.signal_mass_width,
            )
        except ValueError:
            self.dget = None
            return

        x = self.dget.target_masses
        y = self.dget.target_signals

        used = self.dget.deuteration_states
        # used = np.append(used, np.arange(used[-1] + 1, x.size))
        # not_used = np.flatnonzero(~np.in1d(np.arange(x.size), used))

        # xs = self.target_masses
        # ys = self.target_signals
        # if self._deconv_residuals is not None:
        #     ys -= self._deconv_residuals
        # ys[ys < 0.0] = 0.0

        self.graph_ms.setDeuterationData(x, y, used)

    def createToolBar(self) -> None:
        self.toolbar = self.addToolBar("Toolbar")

        self.action_zoom_data = QtGui.QAction(
            QtGui.QIcon.fromTheme("zoom-2-to-1"), "Zoom To D"
        )
        self.action_zoom_data.triggered.connect(self.graph_ms.zoomToData)

        self.action_zoom_reset = QtGui.QAction(
            QtGui.QIcon.fromTheme("zoom-reset"), "Reset Zoom"
        )
        self.action_zoom_reset.triggered.connect(self.graph_ms.zoomReset)
        self.toolbar.addAction(self.action_zoom_data)
        self.toolbar.addAction(self.action_zoom_reset)

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
