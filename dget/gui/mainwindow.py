import logging
import sys
from types import TracebackType

from PySide6 import QtCore, QtGui, QtWidgets
from spcal.gui.log import LoggingDialog

logger = logging.getLogger(__name__)


class DGetControls(QtWidgets.QDockWidget):
    def __init__(self, parent: QtWidgets.QWidget | None = None):
        super().__init__("Controls", parent)

        self.dockLocationChanged.connect(self.changeLayout)

        self.formula = QtWidgets.QLineEdit()
        self.adduct = QtWidgets.QComboBox()

        self.ms_button_open = QtWidgets.QPushButton("Open")

        self.ms_delimiter = QtWidgets.QComboBox()
        self.ms_skiprows = QtWidgets.QSpinBox()
        self.ms_mass_col = QtWidgets.QSpinBox()
        self.ms_signal_col = QtWidgets.QSpinBox()

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
        layout_formula.addRow("Formula", self.formula)
        layout_formula.addRow("Adduct", self.adduct)
        layout_formula.addRow("HRMS Data", self.ms_button_open)

        self.layout = QtWidgets.QVBoxLayout()
        self.layout.addLayout(layout_formula)
        self.layout.addWidget(gbox_ms)
        self.layout.addWidget(gbox_proc)
        self.layout.addStretch(1)

        widget = QtWidgets.QWidget()
        widget.setLayout(self.layout)

        self.setWidget(widget)

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
    def __init__(self, parent: QtWidgets.QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle("DGet!")
        self.resize(1280, 800)

        self.log = LoggingDialog()
        self.log.setWindowTitle("SPCal Log")

        self.controls = DGetControls()
        self.results = DGetResults()
        self.graphics = QtWidgets.QGraphicsView()

        layout = QtWidgets.QHBoxLayout()
        layout_left = QtWidgets.QFormLayout()

        layout_right = QtWidgets.QVBoxLayout()
        layout_bottom_bar = QtWidgets.QHBoxLayout()
        layout_right.addWidget(self.graphics)
        layout_right.addLayout(layout_bottom_bar, 0)

        layout.addWidget(self.controls, 1)
        layout.addLayout(layout_right, 1)

        self.addDockWidget(QtCore.Qt.DockWidgetArea.LeftDockWidgetArea, self.controls)
        self.addDockWidget(QtCore.Qt.DockWidgetArea.BottomDockWidgetArea, self.results)
        self.setCentralWidget(self.graphics)

        self.createMenus()

    def startHRMSBrowser(self, path: str | None = None) -> None:
        file, ok = QtWidgets.QFileDialog.getOpenFileName(
            self, "Open HRMS data", path, "CSV Documents,*.csv;All files,*"
        )
        if ok:
            # loadfile
            pass

    def toggleControls(self, checked: bool) -> None:
        print(self.controls.isVisible())

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

        # view
        self.action_toggle_controls = QtGui.QAction(
            QtGui.QIcon.fromTheme("show"), "Show/hide controls"
        )
        self.action_toggle_controls.setCheckable(True)
        self.action_toggle_controls.setChecked(True)
        self.action_toggle_controls.triggered.connect(self.toggleControls)

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
