import datetime
import logging
import sys
from pathlib import Path
from types import TracebackType

import numpy as np
from PySide6 import QtCore, QtGui, QtPrintSupport, QtWidgets
from spcal.gui.log import LoggingDialog

from dget import DGet, __version__
from dget.adduct import Adduct
from dget.gui.controls import DGetControls
from dget.gui.graphs import DGetMSGraph, DGetSpectraGraph
from dget.gui.importdialog import TextImportDialog
from dget.gui.report import DGetReportDialog

logger = logging.getLogger(__name__)


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
        self.controls.processOptionsChanged.connect(self.updateDGet)

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

    def startReportDialog(self) -> None:
        dlg = DGetReportDialog(self.dget)
        dlg.printReport("/home/tom/Downloads/test_report.pdf")

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

    def updateDGet(self, adduct: Adduct | None = None) -> None:
        if adduct is None:
            if self.dget is not None:
                adduct = self.dget.adduct
            else:
                return

        try:
            cutoff = self.controls.cutoff.text()
            try:
                cutoff = float(cutoff)
            except ValueError:
                if len(cutoff) == 0 or cutoff[0] != "D":
                    cutoff = None

            self.dget = DGet(
                adduct.base,
                tofdata=self.graph_ms.ms_series.getData(),
                adduct=adduct.adduct,
                cutoff=cutoff,
                signal_mode=self.signal_mode,
                signal_mass_width=self.signal_mass_width,
            )

            x = self.dget.target_masses
            y = self.dget.target_signals
            used = self.dget.deuteration_states

            self.graph_ms.setDeuterationData(x, y, used)

        except ValueError:
            return

        # used = np.append(used, np.arange(used[-1] + 1, x.size))
        # not_used = np.flatnonzero(~np.in1d(np.arange(x.size), used))

        # xs = self.target_masses
        # ys = self.target_signals
        # if self._deconv_residuals is not None:
        #     ys -= self._deconv_residuals
        # ys[ys < 0.0] = 0.0

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

        self.action_report = QtGui.QAction(
            QtGui.QIcon.fromTheme("office-report"), "Generate report"
        )
        self.action_report.setStatusTip(
            "Generate a PDF report for the current compound"
        )
        self.action_report.triggered.connect(self.startReportDialog)

        self.action_quit = QtGui.QAction(
            QtGui.QIcon.fromTheme("application-exit"), "Exit"
        )
        self.action_quit.setStatusTip("Quit DGet!")
        self.action_quit.triggered.connect(self.close)

        menu_file = QtWidgets.QMenu("File")
        menu_file.addAction(self.action_open)
        menu_file.addAction(self.action_report)
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
