import logging
import re
import sys
from importlib.metadata import version
from pathlib import Path
from types import TracebackType

import numpy as np
from PySide6 import QtCore, QtGui, QtWidgets

from dget import DGet
from dget.adduct import Adduct
from dget.gui.colors import dget_state_unused
from dget.gui.docks.controls import DGetControls
from dget.gui.docks.results import DGetResultsGraph, DGetResultsText
from dget.gui.graphs import DGetBarGraph, DGetMSGraph
from dget.gui.importdialog import TextImportDialog
from dget.gui.log import LoggingDialog
from dget.gui.report import DGetReportDialog
from dget.gui.settings import DGetSettingsDialog
from dget.io import shimadzu

logger = logging.getLogger(__name__)


class DGetFormulaSpectra(QtWidgets.QDockWidget):
    def __init__(self, parent: QtWidgets.QWidget | None = None):
        super().__init__("Formula Spectra", parent)
        self.setObjectName("dget-formula-spectra-dock")

        self.graph = DGetBarGraph(
            "m/z",
            "Relative Abundance",
            pen=QtGui.QPen(QtCore.Qt.GlobalColor.black, 0.0),
            brush=QtGui.QBrush(QtGui.QColor.fromString(dget_state_unused)),
        )
        self.setWidget(self.graph)


class DGetMainWindow(QtWidgets.QMainWindow):
    dataLoaded = QtCore.Signal(np.ndarray, np.ndarray)
    max_recent_files = 5

    def __init__(self, parent: QtWidgets.QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle("DGet!")

        self.dget: DGet | None = None

        self.log = LoggingDialog()
        self.log.setWindowTitle("DGet! Log")

        self.controls = DGetControls()

        self.results_text = DGetResultsText()
        self.results_graph = DGetResultsGraph()

        self.graph_ms = DGetMSGraph()
        self.graph_ms.dStateClicked.connect(self.controls.cutoff.setText)

        self.graph_spectra = DGetFormulaSpectra()

        self.controls.adductChanged.connect(self.updateAdduct)
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

        status = self.statusBar()
        status.showMessage(f"Welcome to DGet! version {version('dget')}.")

    def createMenus(self) -> None:
        self.action_open = QtGui.QAction(
            QtGui.QIcon.fromTheme("document-open"), "&Open HRMS Data File"
        )
        self.action_open.setStatusTip("Open an HRMS data file of a deuterated compound")
        self.action_open.setShortcut(QtGui.QKeySequence.StandardKey.Open)
        self.action_open.triggered.connect(self.openFile)

        self.action_open_recent = QtGui.QActionGroup(self)
        self.action_open_recent.triggered.connect(self.openRecentFile)

        self.action_report = QtGui.QAction(
            QtGui.QIcon.fromTheme("office-report"), "Generate &Report"
        )
        self.action_report.setStatusTip(
            "Generate a PDF report for the current compound."
        )
        self.action_report.setShortcut(QtGui.QKeySequence.fromString("Ctrl+R"))
        self.action_report.triggered.connect(self.startReportDialog)
        self.action_report.setEnabled(False)

        self.action_quit = QtGui.QAction(
            QtGui.QIcon.fromTheme("application-exit"), "E&xit"
        )
        self.action_quit.setStatusTip("Quit DGet!")
        self.action_quit.triggered.connect(self.close)

        self.action_settings = QtGui.QAction(
            QtGui.QIcon.fromTheme("settings-configure"), "Settings"
        )
        self.action_settings.setStatusTip("Set plotting and processing options.")
        self.action_settings.triggered.connect(self.startSettingsDialog)

        self.action_layout_default = QtGui.QAction(
            QtGui.QIcon.fromTheme("view-group"), "Restore Default Layout"
        )
        self.action_layout_default.setStatusTip("Restore the default window layout.")
        self.action_layout_default.triggered.connect(self.defaultLayout)

        self.action_about = QtGui.QAction(
            QtGui.QIcon.fromTheme("help-about"), "&About DGet!"
        )
        self.action_about.setStatusTip("Show information about the DGet! GUI.")
        self.action_about.triggered.connect(self.about)

        self.action_help = QtGui.QAction(
            QtGui.QIcon.fromTheme("documentation"), "Online &Documentation"
        )
        self.action_help.setStatusTip("Opens a link to the DGet! documentation.")
        self.action_help.triggered.connect(self.linkToDocumentation)

        self.action_log = QtGui.QAction(
            QtGui.QIcon.fromTheme("dialog-information"), "Show &Log"
        )
        self.action_log.setStatusTip("Open the error log.")
        self.action_log.triggered.connect(self.log.open)

        menu_file = QtWidgets.QMenu("File")
        menu_file.addAction(self.action_open)

        self.menu_recent = menu_file.addMenu("O&pen recent")
        self.menu_recent.setIcon(QtGui.QIcon.fromTheme("document-open-recent"))
        self.menu_recent.setEnabled(False)

        menu_file.addAction(self.action_report)
        menu_file.addAction(self.action_quit)

        menu_edit = QtWidgets.QMenu("Edit")
        menu_edit.addAction(self.action_settings)

        menu_view = QtWidgets.QMenu("View")
        menu_view.addAction(self.action_layout_default)
        menu_view.addSection("Show/hide dock widgets")
        for dock in self.findChildren(QtWidgets.QDockWidget):
            menu_view.addAction(dock.toggleViewAction())

        menu_help = QtWidgets.QMenu("Help")
        menu_help.addAction(self.action_log)
        menu_help.addAction(self.action_help)
        menu_help.addAction(self.action_about)

        self.menuBar().addMenu(menu_file)
        self.menuBar().addMenu(menu_edit)
        self.menuBar().addMenu(menu_view)
        self.menuBar().addMenu(menu_help)

    def createToolBar(self) -> None:
        self.toolbar = QtWidgets.QToolBar("Toolbar")
        self.toolbar.setObjectName("dget-toolbar")
        self.addToolBar(QtCore.Qt.ToolBarArea.RightToolBarArea, self.toolbar)

        self.action_show_deconv = QtGui.QAction(
            QtGui.QIcon.fromTheme("office-chart-line"), "Show Deconvolution Result"
        )
        self.action_show_deconv.setStatusTip(
            "Display the result of deconvolving the spectra from the isotopologues."
        )
        self.action_show_deconv.setCheckable(True)
        self.action_show_deconv.setChecked(self.graph_ms.deconv_series.isVisible())
        self.action_show_deconv.toggled.connect(self.graph_ms.deconv_series.setVisible)

        self.action_show_individual = QtGui.QAction(
            QtGui.QIcon.fromTheme("office-chart-bar"), "Show Isotopologues"
        )
        self.action_show_individual.setStatusTip(
            "Show the contributions of individual isotopologues."
        )
        self.action_show_individual.setCheckable(True)
        self.action_show_individual.toggled.connect(
            self.graph_ms.setStateSpectraVisibility
        )

        self.action_zoom_data = QtGui.QAction(
            QtGui.QIcon.fromTheme("zoom-1-to-2"), "Zoom To D"
        )
        self.action_zoom_data.setStatusTip("Zoom to the deuterated m/z region.")
        self.action_zoom_data.triggered.connect(self.graph_ms.zoomToData)
        self.action_zoom_data.setEnabled(False)

        self.action_zoom_reset = QtGui.QAction(
            QtGui.QIcon.fromTheme("zoom-original"), "Reset Zoom"
        )
        self.action_zoom_data.setStatusTip("Zoom out to show the entire m/z range.")
        self.action_zoom_reset.triggered.connect(self.graph_ms.resetZoom)

        self.toolbar.addAction(self.action_show_deconv)
        self.toolbar.addAction(self.action_show_individual)
        self.toolbar.addAction(self.action_zoom_data)
        self.toolbar.addAction(self.action_zoom_reset)

    # Callbacks
    def about(self) -> None:
        QtWidgets.QMessageBox.about(
            self,
            "About DGet!",
            (
                "DGet! is a deuteration calculator for HRMS data<br><br>"
                f'Version {QtWidgets.QApplication.applicationVersion()} © 2023—2025 <a href="mailto:thomas.lockwood@uts.edu.au">Thomas Lockwood</a><br>'
                "Visit the DGet! <a href=https://github.com/djdt/dget>GitHub</a>"
            ),
        )

    def linkToDocumentation(self) -> None:
        QtGui.QDesktopServices.openUrl("https://dget.readthedocs.io")

    def openFile(self) -> None:
        dir = str(QtCore.QSettings().value("recent files/1/path", ""))
        if dir != "":
            dir = str(Path(dir).parent)
        self.startHRMSBrowser(dir=dir)

    def openRecentFile(self, action: QtGui.QAction) -> None:
        path = Path(re.sub("\\&(?!\\&)", "", action.text()))
        if path.exists():
            self.startHRMSBrowser(path)
        else:
            QtWidgets.QMessageBox.warning(
                self, "File Not Found", f"File '{path}' does not exist."
            )
            self.updateRecentFiles(remove=path)

    def startHRMSBrowser(self, file: str | Path | None = None, dir: str = "") -> None:
        def loadData(path: Path, x: np.ndarray, y: np.ndarray) -> None:
            self.graph_ms.setData(x, y)
            self.graph_ms.plot.setTitle(path.stem)
            self.updateDGet(self.controls.adduct())

            self.updateRecentFiles(path)

        if file is None:
            file, _ = QtWidgets.QFileDialog.getOpenFileName(
                self,
                "Open HRMS Data",
                dir,
                "CSV Documents (*.csv *.text *.txt);;All files (*)",
            )
        if file != "":
            if shimadzu.is_shimadzu_file(file):
                loadtxt_kws = shimadzu.get_loadtxt_kws(file)
                x, y = np.loadtxt(file, unpack=True, dtype=np.float32, **loadtxt_kws)
                loadData(Path(file), x, y)
            else:
                dlg = TextImportDialog(file)
                dlg.dataImported.connect(loadData)
                dlg.exec()

    def startReportDialog(self) -> None:
        dlg = DGetReportDialog(self.dget)
        dlg.exec()

    def startSettingsDialog(self) -> None:
        def updateSettings() -> None:
            self.controls.loadAdducts()
            adduct = self.controls.adduct()
            if adduct is None:
                self.updateDGet()
            else:
                self.updateAdduct(adduct)  # calls updateDGet

        dlg = DGetSettingsDialog(self)
        dlg.accepted.connect(updateSettings)
        dlg.exec()

    def updateAdduct(self, adduct: Adduct) -> None:
        self.graph_ms.setAdductLabel(adduct)

        spectra = adduct.formula.spectrum(min_fraction=DGet.min_fraction_for_spectra)

        # Seperate from DGet so we can plot non-deuterated formula
        x = np.array([s.mz for s in spectra.values()])
        y = np.array([s.fraction for s in spectra.values()])
        y = y / y.max()
        self.graph_spectra.graph.setData(x, y)
        self.graph_spectra.graph.resetZoom()

        self.updateDGet(adduct)

        adduct_list = []
        for i in range(self.controls.cb_adduct.count()):
            try:
                adduct_list.append(
                    Adduct(adduct.base, self.controls.cb_adduct.itemText(i))
                )
            except ValueError:
                pass

        self.graph_ms.labelPossibleAdducts(adduct_list)

    def updateDGet(self, adduct: Adduct | None = None) -> None:
        self.results_text.text.clear()
        self.results_graph.graph.series.setOpts(x=[], height=0)
        self.graph_ms.setDeuterationData(np.array([]), np.array([]), np.array([]), 0)
        self.graph_ms.setDeconvolutionResultData(np.array([]), np.array([]))
        self.graph_ms.setStateSpectraData(np.array([]), np.array([]))
        self.action_zoom_data.setEnabled(False)

        if adduct is None:
            if self.dget is not None:
                adduct = self.dget.adduct
            else:
                return

        if (
            self.graph_ms.ms_series.xData is None
            or self.graph_ms.ms_series.yData is None
            or self.graph_ms.ms_series.yData.size == 0
        ):
            return

        self.graph_ms.setShift(self.controls.mass_shift.value())

        cutoff = self.controls.cutoff.text()
        try:
            cutoff = float(cutoff)
        except ValueError:
            if len(cutoff) == 0 or cutoff[0] != "D":
                cutoff = None

        settings = QtCore.QSettings()
        signal_mode = str(settings.value("dget/signal mode", "peak height"))
        signal_mass_width = float(settings.value("dget/signal mass width", 0.1))  # type: ignore

        try:
            self.dget = DGet(
                adduct.base,
                tofdata=self.graph_ms.ms_series.getData(),  # type: ignore as checked by yData
                adduct=adduct.adduct,
                cutoff=cutoff,
                signal_mode=signal_mode,
                signal_mass_width=signal_mass_width,
            )
            self.action_report.setEnabled(True)
        except ValueError:
            self.action_report.setEnabled(False)
            return

        deuteration = self.dget.deuteration
        used = self.dget.deuteration_states
        probs: np.ndarray = self.dget._probabilities  # type: ignore as can't be None after deuteration

        if used.size == 0:
            return

        # update the text results
        self.results_text.updateText(
            deuteration,
            (self.dget.residual_error or 0.0),
            used,
            probs[used] / probs[used].sum(),
        )
        # update graph results
        self.results_graph.graph.setData(
            used, (probs[used] / probs[used].sum()) * 100.0
        )
        self.results_graph.graph.resetZoom()
        self.action_zoom_data.setEnabled(True)

        # update the central graph
        self.graph_ms.setDeuterationData(
            self.dget.target_masses,
            self.dget.target_signals,
            used,
            self.dget.deuterium_count,
            mode=signal_mode,
            mass_width=signal_mass_width,
        )

        probs = np.concatenate(
            (probs[:-1], np.convolve(probs[-1], self.dget.psf, mode="full"))
        )

        if signal_mode == "peak area":
            # rescale to the peak maxima
            starts = np.searchsorted(
                self.graph_ms.ms_series.xData,
                self.dget.target_masses - signal_mass_width,
                side="right",
            )
            ends = np.searchsorted(
                self.graph_ms.ms_series.xData,
                self.dget.target_masses + signal_mass_width,
                side="left",
            )
            maxes = np.maximum.reduceat(
                self.graph_ms.ms_series.yData, np.stack((starts, ends), axis=1).flat
            )[::2]
            probs = probs * (maxes.mean() / probs.mean())

        self.graph_ms.setDeconvolutionResultData(self.dget.target_masses, probs)

        ys = np.apply_along_axis(
            np.convolve,
            1,
            np.diagflat(probs[: -(self.dget.psf.size - 1)]),
            self.dget.psf,
            mode="full",
        )

        self.graph_ms.setStateSpectraData(self.dget.target_masses, ys)

    def updateRecentFiles(
        self, insert: Path | None = None, remove: Path | None = None
    ) -> None:
        settings = QtCore.QSettings()
        num = settings.beginReadArray("recent files")
        paths = []
        for i in range(num):
            settings.setArrayIndex(i)
            path = Path(settings.value("path"))
            if path not in [insert, remove]:
                paths.append(path)
        settings.endArray()

        if insert is not None:
            paths.insert(0, insert)
            paths = paths[: self.max_recent_files]

            settings.remove("recent files")
            settings.beginWriteArray("recent files", len(paths))
            for i, path in enumerate(paths):
                settings.setArrayIndex(i)
                settings.setValue("path", str(path))
            settings.endArray()

        # Clear old actions
        self.menu_recent.clear()
        for action in self.action_open_recent.actions():
            self.action_open_recent.removeAction(action)

        # Add new
        self.menu_recent.setEnabled(len(paths) > 0)
        for path in paths:
            action = QtGui.QAction(str(path), self)
            action.setIconText("1")
            self.action_open_recent.addAction(action)
            self.menu_recent.addAction(action)

    # Layout
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

    def restoreLayout(self) -> None:
        settings = QtCore.QSettings()
        self.restoreGeometry(settings.value("window/geometry"))
        self.restoreState(settings.value("window/state"))

    # Event overrides
    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        settings = QtCore.QSettings()
        settings.setValue("window/geometry", self.saveGeometry())
        settings.setValue("window/state", self.saveState())
        super().closeEvent(event)

    def dragEnterEvent(self, event: QtGui.QDragEnterEvent) -> None:
        if event.mimeData().hasUrls():
            mime_db = QtCore.QMimeDatabase()
            for url in event.mimeData().urls():
                if mime_db.mimeTypeForUrl(url).name() in ["text/plain", "text/csv"]:
                    event.acceptProposedAction()
        super().dragEnterEvent(event)

    def dropEvent(self, event: QtGui.QDropEvent) -> None:
        if event.mimeData().hasUrls():
            mime_db = QtCore.QMimeDatabase()
            for url in event.mimeData().urls():
                if mime_db.mimeTypeForUrl(url).name() in ["text/plain", "text/csv"]:
                    self.startHRMSBrowser(Path(url.toLocalFile()))
                    event.acceptProposedAction()
                    return
        super().dropEvent(event)

    def exceptHook(
        self, etype: type, value: BaseException, tb: TracebackType | None = None
    ):  # pragma: no cover
        """Redirect errors to the log."""
        if etype is KeyboardInterrupt:
            logger.info("Keyboard interrupt, exiting.")
            sys.exit(1)
        logger.exception("Uncaught exception", exc_info=(etype, value, tb))
        QtWidgets.QMessageBox.critical(self, "Uncaught Exception", str(value))
