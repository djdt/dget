import logging
import re
import sys
from pathlib import Path
from types import TracebackType

import numpy as np
import pyqtgraph
from PySide6 import QtCore, QtGui, QtWidgets
from spcal.gui.log import LoggingDialog

import dget.io.shimadzu
import dget.io.text
from dget import DGet

logger = logging.getLogger(__name__)


class DGetFormulaValidator(QtGui.QValidator):
    element_symbols = [
        "H",
        "D",
        "He",
        "Li",
        "Be",
        "B",
        "C",
        "N",
        "O",
        "F",
        "Ne",
        "Na",
        "Mg",
        "Al",
        "Si",
        "P",
        "S",
        "Cl",
        "Ar",
        "K",
        "Ca",
        "Sc",
        "Ti",
        "V",
        "Cr",
        "Mn",
        "Fe",
        "Co",
        "Ni",
        "Cu",
        "Zn",
        "Ga",
        "Ge",
        "As",
        "Se",
        "Br",
        "Kr",
        "Rb",
        "Sr",
        "Y",
        "Zr",
        "Nb",
        "Mo",
        "Tc",
        "Ru",
        "Rh",
        "Pd",
        "Ag",
        "Cd",
        "In",
        "Sn",
        "Sb",
        "Te",
        "I",
        "Xe",
        "Cs",
        "Ba",
        "La",
        "Ce",
        "Pr",
        "Nd",
        "Pm",
        "Sm",
        "Eu",
        "Gd",
        "Tb",
        "Dy",
        "Ho",
        "Er",
        "Tm",
        "Yb",
        "Lu",
        "Hf",
        "Ta",
        "W",
        "Re",
        "Os",
        "Ir",
        "Pt",
        "Au",
        "Hg",
        "Tl",
        "Pb",
        "Bi",
        "Po",
        "At",
        "Rn",
        "Fr",
        "Ra",
        "Ac",
        "Th",
        "Pa",
        "U",
        "Np",
        "Pu",
        "Am",
        "Cm",
        "Bk",
        "Cf",
        "Es",
        "Fm",
        "Md",
        "No",
        "Lr",
        "Rf",
        "Db",
        "Sg",
        "Bh",
        "Hs",
        "Mt",
        "Ds",
        "Rg",
        "Cn",
        "Nh",
        "Fl",
        "Mc",
        "Lv",
        "Ts",
        "Og",
    ]
    re_token = re.compile(r"(\[\d+)?([a-zA-Z][a-z]?)\]?\d*")

    def __init__(self, le: QtWidgets.QLineEdit, parent: QtCore.QObject | None = None):
        super().__init__(parent)
        self.le = le

    def validate(self, input: str, pos: int) -> QtGui.QValidator.State:
        if "D" not in input:
            return QtGui.QValidator.State.Intermediate
        tokens = self.re_token.findall(input)
        for _, token in tokens:
            if token not in self.element_symbols:
                return QtGui.QValidator.State.Intermediate
        return QtGui.QValidator.State.Acceptable

    def fixup(self, input: str) -> None:
        upper_idx = []
        for m in self.re_token.finditer(input):
            token = m.group(2)
            if token not in self.element_symbols:
                if token.capitalize() in self.element_symbols:
                    upper_idx.append(m.start(2))
                elif (
                    len(token) == 2
                    and token[0].upper() in self.element_symbols
                    and token[1].upper() in self.element_symbols
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

    def __init__(self, parent: QtWidgets.QWidget | None = None):
        super().__init__("Controls", parent)

        self.dockLocationChanged.connect(self.changeLayout)

        self.formula = QtWidgets.QLineEdit()
        self.formula.setValidator(DGetFormulaValidator(self.formula))

        self.adduct = QtWidgets.QComboBox()
        self.adduct.addItems(DGet.common_adducts)
        self.adduct.setEditable(True)

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
        layout_formula.addRow("Formula", self.formula)
        layout_formula.addRow("Adduct", self.adduct)

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

    @property
    def ms_loadtxt_kws(self) -> dict:
        return {
            "delimiter": self.delimiter_names[self.ms_delimiter.currentText()],
            "skiprows": self.ms_skiprows.value(),
            "usecols": (self.ms_mass_col.value() - 1, self.ms_signal_col.value() - 1),
        }

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


class LimitBoundViewBox(pyqtgraph.ViewBox):
    """Viewbox that autoRanges to any set limits."""

    def childrenBounds(self, frac=None, orthoRange=(None, None), items=None):
        bounds = super().childrenBounds(frac=frac, orthoRange=orthoRange, items=items)
        limits = self.state["limits"]["xLimits"], self.state["limits"]["yLimits"]
        for i in range(2):
            if bounds[i] is not None:
                if limits[i][0] != -1e307:  # and limits[i][0] < bounds[i][0]:
                    bounds[i][0] = limits[i][0]
                if limits[i][1] != +1e307:  # and limits[i][1] > bounds[i][1]:
                    bounds[i][1] = limits[i][1]
        return bounds


class ViewBoxForceScaleAtZero(LimitBoundViewBox):
    """Viewbox that forces the bottom to be 0."""

    def scaleBy(
        self,
        s: list[float] | None = None,
        center: QtCore.QPointF | None = None,
        x: float | None = None,
        y: float | None = None,
    ) -> None:
        if center is not None:
            center.setY(0.0)
        super().scaleBy(s, center, x, y)

    def translateBy(
        self,
        t: QtCore.QPointF | None = None,
        x: float | None = None,
        y: float | None = None,
    ) -> None:
        if t is not None:
            t.setY(0.0)
        if y is not None:
            y = 0.0
        super().translateBy(t, x, y)


class DGetMSGraph(pyqtgraph.GraphicsView):
    def __init__(self, parent: QtWidgets.QWidget | None = None):
        super().__init__(background="white", parent=parent)

        pen = QtGui.QPen(QtCore.Qt.black, 1.0)
        pen.setCosmetic(True)

        self.xaxis = pyqtgraph.AxisItem("bottom", pen=pen, textPen=pen, tick_pen=pen)
        self.xaxis.setLabel("m/z")

        self.yaxis = pyqtgraph.AxisItem("left", pen=pen, textPen=pen, tick_pen=pen)
        self.yaxis.setLabel("Reponse")

        self.plot = pyqtgraph.PlotItem(
            # title=title,
            name="central_plot",
            axisItems={"bottom": self.xaxis, "left": self.yaxis},
            viewBox=ViewBoxForceScaleAtZero(),
            parent=parent,
        )
        # Common options
        self.plot.setMenuEnabled(False)
        self.plot.hideButtons()

        self.ms_series = pyqtgraph.PlotCurveItem(
            pen=pen, connect="all", skipFiniteCheck=True
        )
        self.plot.addItem(self.ms_series)

        self.setCentralWidget(self.plot)

    def drawMSData(self, x: np.ndarray, y: np.ndarray) -> None:
        self.ms_series.setData(x=x, y=y)
        self.plot.setLimits(xMin=x.min(), xMax=x.max(), yMin=0.0, yMax=y.max() * 1.2)


class DGetMainWindow(QtWidgets.QMainWindow):
    def __init__(self, parent: QtWidgets.QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle("DGet!")
        self.resize(1280, 800)

        self.dget = None

        self.log = LoggingDialog()
        self.log.setWindowTitle("SPCal Log")

        data = np.loadtxt("/home/tom/Downloads/NDF-A-009.txt")
        self.controls = DGetControls()
        self.results = DGetResults()
        self.graph = DGetMSGraph()
        self.graph.drawMSData(data[:, 0], data[:, 1])

        self.addDockWidget(QtCore.Qt.DockWidgetArea.LeftDockWidgetArea, self.controls)
        self.addDockWidget(QtCore.Qt.DockWidgetArea.BottomDockWidgetArea, self.results)
        self.setCentralWidget(self.graph)

        self.createMenus()

    def startHRMSBrowser(self, path: str | None = None) -> None:
        file, ok = QtWidgets.QFileDialog.getOpenFileName(
            self, "Open HRMS data", path, "CSV Documents,*.csv;All files,*"
        )
        if ok:
            if dget.io.shimadzu.is_shimadzu_file(file):
                kws = dget.io.shimadzu.get_loadtxt_kws(file)
                self.controls.setMSOptionsEnabled(False)
            else:
                kws = dget.io.text.guess_loadtxt_kws(
                    file, kws=self.controls.ms_loadtxt_kws
                )
                self.controls.setMSOptionsEnabled(True)
            self.controls.ms_loadtxt_kws = kws

    def loadFile(self, file: Path | str) -> None:
        x, y = np.loadtxt(
            file, unpack=True, dtype=np.float32, **self.controls.ms_loadtxt_kws
        )

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
