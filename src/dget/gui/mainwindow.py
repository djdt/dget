import logging
import re
import sys
from pathlib import Path
from types import TracebackType

import numpy as np
from PySide6 import QtCore, QtGui, QtWidgets
from spcal.gui.log import LoggingDialog

from dget import DGet
from dget.adduct import Adduct
from dget.gui.controls import DGetControls
from dget.gui.graphs import DGetBarGraph, DGetMSGraph
from dget.gui.importdialog import TextImportDialog
from dget.gui.report import DGetReportDialog

logger = logging.getLogger(__name__)

re_strip_amp = re.compile("\\&(?!\\&)")


class DGetResultsText(QtWidgets.QDockWidget):
    def __init__(self, parent: QtWidgets.QWidget | None = None):
        super().__init__("Results", parent)
        self.setObjectName("dget-results-text-dock")

        self.text = QtWidgets.QTextBrowser()
        self.text.setFont("courier")

        self.setWidget(self.text)

    def clear(self) -> None:
        self.text.setHtml("")

    def updateText(
        self, deuteration: float, states: np.ndarray, probabilities: np.ndarray
    ) -> None:
        html = f"<p><b>Deuteration: {deuteration * 100.0:.2f} %</b></p>"
        html += "<p>States</p>"
        html += "<table>"
        for state, prob in zip(states, probabilities):
            html += f"<tr><td>D{state}</td><td>{prob * 100.0:.2f} %</td></tr>"
        html += "</table>"
        self.text.setHtml(html)


class DGetResultsGraph(QtWidgets.QDockWidget):
    def __init__(self, parent: QtWidgets.QWidget | None = None):
        super().__init__("Deuteration States", parent)
        self.setObjectName("dget-results-graph-dock")

        self.graph = DGetBarGraph("State", "Percent Abundance")
        self.setWidget(self.graph)


class DGetFormulaSpectra(QtWidgets.QDockWidget):
    def __init__(self, parent: QtWidgets.QWidget | None = None):
        super().__init__("Formula Spectra", parent)
        self.setObjectName("dget-formula-spectra-dock")

        self.graph = DGetBarGraph("m/z", "Relative Abundance")
        self.setWidget(self.graph)


class DGetMainWindow(QtWidgets.QMainWindow):
    dataLoaded = QtCore.Signal(np.ndarray, np.ndarray)
    max_recent_files = 5

    def __init__(self, parent: QtWidgets.QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle("DGet!")
        self.resize(1280, 800)

        self.signal_mode = "peak height"
        self.signal_mass_width = 0.3

        self.dget: DGet | None = None

        self.log = LoggingDialog()
        self.log.setWindowTitle("DGet! Log")

        self.controls = DGetControls()

        self.results_text = DGetResultsText()
        self.results_graph = DGetResultsGraph()

        self.graph_ms = DGetMSGraph()
        self.graph_spectra = DGetFormulaSpectra()

        self.controls.adductChanged.connect(self.onAdductChanged)
        self.controls.processOptionsChanged.connect(self.updateDGet)

        self.addDockWidget(QtCore.Qt.DockWidgetArea.LeftDockWidgetArea, self.controls)
        self.addDockWidget(
            QtCore.Qt.DockWidgetArea.BottomDockWidgetArea, self.results_text
        )
        self.addDockWidget(
            QtCore.Qt.DockWidgetArea.BottomDockWidgetArea, self.results_graph
        )
        self.addDockWidget(
            QtCore.Qt.DockWidgetArea.LeftDockWidgetArea, self.graph_spectra
        )

        self.setCentralWidget(self.graph_ms)

        self.createMenus()
        self.createToolBar()

        self.restoreLayout()
        self.updateRecentFiles()

    def startHRMSBrowser(self, file: str | Path | None = None, dir: str = "") -> None:
        if file is None:
            file, _ = QtWidgets.QFileDialog.getOpenFileName(
                self,
                "Open HRMS data",
                dir,
                "CSV Documents (*.csv *.text *.txt);;All files (*)",
            )
        if file != "":
            dlg = TextImportDialog(file)
            dlg.dataImported.connect(self.loadData)
            dlg.exec()

    def startReportDialog(self) -> None:
        dlg = DGetReportDialog(self.dget)
        dlg.exec()

    def loadData(self, path: Path, x: np.ndarray, y: np.ndarray) -> None:
        self.graph_ms.setData(x, y)
        self.graph_ms.plot.setTitle(path.stem)
        self.updateDGet(self.controls.adduct())

        self.updateRecentFiles(path)

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
        self.graph_spectra.graph.setData(x, y)
        self.graph_spectra.graph.resetZoom()

        self.updateDGet(adduct)

    def updateDGet(self, adduct: Adduct | None = None) -> None:
        self.results_text.clear()
        self.results_graph.graph.series.setOpts(x=[], height=0)
        self.graph_ms.setDeuterationData(np.array([]), np.array([]), np.array([]), 0)
        self.action_zoom_data.setEnabled(False)

        if adduct is None:
            if self.dget is not None:
                adduct = self.dget.adduct
            else:
                return

        if self.graph_ms.ms_series.yData.size == 0:
            return

        self.graph_ms.setShift(self.controls.mass_shift.value())

        cutoff = self.controls.cutoff.text()
        try:
            cutoff = float(cutoff)
        except ValueError:
            if len(cutoff) == 0 or cutoff[0] != "D":
                cutoff = None

        try:
            self.dget = DGet(
                adduct.base,
                tofdata=self.graph_ms.ms_series.getData(),
                adduct=adduct.adduct,
                cutoff=cutoff,
                signal_mode=self.signal_mode,
                signal_mass_width=self.signal_mass_width,
            )
            self.action_report.setEnabled(True)
        except ValueError:
            self.action_report.setEnabled(False)
            return

        used = self.dget.deuteration_states
        probs = self.dget.deuteration_probabilites

        if np.all(np.isnan(probs)):
            return

        self.graph_ms.setDeuterationData(
            self.dget.target_masses,
            self.dget.target_signals,
            used,
            self.dget.deuterium_count,
        )

        self.results_text.updateText(self.dget.deuteration, used, probs)
        self.results_graph.graph.setData(used, probs[used] * 100.0)
        self.results_graph.graph.resetZoom()
        self.action_zoom_data.setEnabled(True)

    def createToolBar(self) -> None:
        self.toolbar = QtWidgets.QToolBar("Toolbar")
        self.toolbar.setObjectName("dget-toolbar")
        self.addToolBar(QtCore.Qt.ToolBarArea.RightToolBarArea, self.toolbar)

        self.action_zoom_data = QtGui.QAction(
            QtGui.QIcon.fromTheme("zoom-2-to-1"), "Zoom To D"
        )
        self.action_zoom_data.triggered.connect(self.graph_ms.zoomToData)
        self.action_zoom_data.setEnabled(False)

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
        self.action_open.setShortcut(QtGui.QKeySequence.StandardKey.Open)
        self.action_open.triggered.connect(self.openFile)

        self.action_open_recent = QtGui.QActionGroup(self)
        self.action_open_recent.triggered.connect(self.openRecentFile)

        self.action_report = QtGui.QAction(
            QtGui.QIcon.fromTheme("office-report"), "Generate &report"
        )
        self.action_report.setStatusTip(
            "Generate a PDF report for the current compound"
        )
        self.action_report.setShortcut(QtGui.QKeySequence.fromString("Ctrl+R"))
        self.action_report.triggered.connect(self.startReportDialog)
        self.action_report.setEnabled(False)

        self.action_log = QtGui.QAction(
            QtGui.QIcon.fromTheme("dialog-information"), "Show &Log"
        )
        self.action_log.setStatusTip("Open the error log.")
        self.action_log.triggered.connect(self.log.open)

        self.action_layout_default = QtGui.QAction(
            QtGui.QIcon.fromTheme("view-group"), "Restore default layout"
        )
        self.action_layout_default.setStatusTip("Restore the default window layout.")
        self.action_layout_default.triggered.connect(self.defaultLayout)

        self.action_quit = QtGui.QAction(
            QtGui.QIcon.fromTheme("application-exit"), "Exit"
        )
        self.action_quit.setStatusTip("Quit DGet!")
        self.action_quit.triggered.connect(self.close)

        menu_file = QtWidgets.QMenu("File")
        menu_file.addAction(self.action_open)

        self.menu_recent = menu_file.addMenu("Open Recent")
        self.menu_recent.setIcon(QtGui.QIcon.fromTheme("document-open-recent"))
        self.menu_recent.setEnabled(False)

        menu_file.addAction(self.action_report)
        menu_file.addAction(self.action_quit)

        menu_view = QtWidgets.QMenu("View")
        menu_view.addAction(self.action_layout_default)
        menu_view.addSection("Show/hide dock widgets")
        for dock in self.findChildren(QtWidgets.QDockWidget):
            menu_view.addAction(dock.toggleViewAction())

        menu_help = QtWidgets.QMenu("Help")
        menu_help.addAction(self.action_log)

        self.menuBar().addMenu(menu_file)
        self.menuBar().addMenu(menu_view)
        self.menuBar().addMenu(menu_help)

    def openFile(self) -> None:
        dir = str(QtCore.QSettings().value("RecentFiles/1/Path", ""))
        if dir != "":
            dir = str(Path(dir).parent)
        self.startHRMSBrowser(dir=dir)

    def openRecentFile(self, action: QtGui.QAction) -> None:
        path = Path(re_strip_amp.sub("", action.text()))
        self.startHRMSBrowser(path)

    def updateRecentFiles(self, new_path: Path | None = None) -> None:
        settings = QtCore.QSettings()
        num = settings.beginReadArray("RecentFiles")
        paths = []
        for i in range(num):
            settings.setArrayIndex(i)
            path = Path(settings.value("Path"))
            if path != new_path:
                paths.append(path)
        settings.endArray()

        if new_path is not None:
            paths.insert(0, new_path)
            paths = paths[: self.max_recent_files]

            settings.remove("RecentFiles")
            settings.beginWriteArray("RecentFiles", len(paths))
            for i, path in enumerate(paths):
                settings.setArrayIndex(i)
                settings.setValue("Path", str(path))
            settings.endArray()

        # Clear old actions
        self.menu_recent.clear()
        for action in self.action_open_recent.actions():
            self.action_open_recent.removeAction(action)

        # Add new
        self.menu_recent.setEnabled(len(paths) > 0)
        for path in paths:
            action = QtGui.QAction(str(path), self)
            self.action_open_recent.addAction(action)
            self.menu_recent.addAction(action)

    def restoreLayout(self) -> None:
        settings = QtCore.QSettings()
        self.restoreGeometry(settings.value("window/geometry"))
        self.restoreState(settings.value("window/state"))

    def defaultLayout(self) -> None:
        self.addToolBar(QtCore.Qt.ToolBarArea.RightToolBarArea, self.toolbar)
        self.addDockWidget(QtCore.Qt.DockWidgetArea.LeftDockWidgetArea, self.controls)
        self.addDockWidget(
            QtCore.Qt.DockWidgetArea.BottomDockWidgetArea, self.results_text
        )
        self.addDockWidget(
            QtCore.Qt.DockWidgetArea.BottomDockWidgetArea, self.results_graph
        )
        self.addDockWidget(
            QtCore.Qt.DockWidgetArea.LeftDockWidgetArea, self.graph_spectra
        )

        size = self.size()
        self.resizeDocks(
            [self.results_text, self.results_graph],
            [size.width() // 3 * 2, size.width() // 3],
            QtCore.Qt.Orientation.Horizontal,
        )
        self.resizeDocks(
            [self.controls, self.graph_spectra, self.results_text],
            [size.height() // 3, size.height() // 3, size.height() // 3],
            QtCore.Qt.Orientation.Vertical,
        )

        for dock in self.findChildren(QtWidgets.QDockWidget):
            dock.show()

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        settings = QtCore.QSettings()
        settings.setValue("window/geometry", self.saveGeometry())
        settings.setValue("window/state", self.saveState())
        super().closeEvent(event)

    def exceptHook(
        self, etype: type, value: BaseException, tb: TracebackType | None = None
    ):  # pragma: no cover
        """Redirect errors to the log."""
        if etype is KeyboardInterrupt:
            logger.info("Keyboard interrupt, exiting.")
            sys.exit(1)
        logger.exception("Uncaught exception", exc_info=(etype, value, tb))
        QtWidgets.QMessageBox.critical(self, "Uncaught Exception", str(value))
