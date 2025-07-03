import numpy as np
import pyqtgraph
from PySide6 import QtCore, QtGui, QtWidgets

from dget.adduct import Adduct


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
    adductLabelHovered = QtCore.Signal(str)
    dStateClicked = QtCore.Signal(str)

    def __init__(self, parent: QtWidgets.QWidget | None = None):
        super().__init__(background="white", parent=parent)

        pen = QtGui.QPen(QtCore.Qt.GlobalColor.black, 1.0)
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
        )
        # Common options
        self.plot.setMenuEnabled(False)
        self.plot.hideButtons()
        self.plot.setContentsMargins(10, 10, 10, 10)

        self.ms_shift = 0.0
        self.ms_series = pyqtgraph.PlotCurveItem(
            pen=pen, connect="all", skipFiniteCheck=True
        )
        self.plot.addItem(self.ms_series)

        self.d_count = 0
        self.d_series = pyqtgraph.ScatterPlotItem(
            pxMode=True, size=10, hoverable=True, tip=None
        )
        self.d_series.sigHovered.connect(self.updateHoverText)
        self.d_series.sigClicked.connect(self.stateClicked)
        self.plot.addItem(self.d_series)

        self.hover_text = pyqtgraph.TextItem(
            "", color=QtGui.QColor.fromRgb(0, 0, 0), anchor=(0.5, 1.0)
        )
        self.hover_text.setVisible(False)
        self.plot.addItem(self.hover_text)

        self.adduct_label = pyqtgraph.LabelItem("", parent=self.yaxis)
        self.adduct_label.anchor(itemPos=(0, 0), parentPos=(1, 0), offset=(10, 10))

        self.doi_label = pyqtgraph.LabelItem(
            "doi: 10.1186/s13321-024-00828-x", parent=self.plot
        )
        self.doi_label.anchor(itemPos=(1, 0), parentPos=(1, 0), offset=(-10, 10))

        self.possible_adduct_labels: list[pyqtgraph.TextItem] = []
        self.possible_adduct_labels_visible = True

        self.setCentralWidget(self.plot)

    def setShift(self, mz_shift: float) -> None:
        x, y = self.ms_series.getData()
        if x is None:
            return
        x = x - self.ms_shift + mz_shift
        self.ms_series.setData(x, y)
        self.ms_shift = mz_shift

    def setData(self, x: np.ndarray, y: np.ndarray) -> None:
        self.ms_shift = 0.0
        self.ms_series.setData(x=x, y=y)

        vb = self.plot.getViewBox()
        if vb is not None:
            vb.setLimits(xMin=x.min(), xMax=x.max(), yMin=0.0, yMax=y.max() * 1.2)

    def setDeuterationData(
        self, x: np.ndarray, y: np.ndarray, used: np.ndarray, dcount: int
    ) -> None:
        self.d_count = dcount
        brush_used = QtGui.QBrush(QtGui.QColor.fromString("#DB5461"))
        brush_unused = QtGui.QBrush(QtGui.QColor.fromString("#8AA29E"))
        brushes = [brush_used if i in used else brush_unused for i in range(x.size)]
        dstate = np.arange(x.size)
        self.d_series.setData(x=x, y=y, brush=brushes, data=dstate)

    def setAdductLabel(self, adduct: Adduct) -> None:
        self.adduct_label.setText(
            f"{adduct.base.formula} {adduct.adduct} <br>m/z={adduct.formula.mz:.4f}"
        )

    def labelPossibleAdducts(self, adducts: list[Adduct]) -> None:
        # clear any existing
        for label in self.possible_adduct_labels:
            self.plot.removeItem(label)
        self.possible_adduct_labels.clear()

        # no data
        if (
            self.ms_series.yData is None
            or self.ms_series.xData is None
            or self.ms_series.yData.size == 0
        ):
            return

        min_signal = np.percentile(self.ms_series.yData, 50)
        for adduct in adducts:
            idx = np.searchsorted(self.ms_series.xData, adduct.formula.mz)
            if idx == 0 or idx == self.ms_series.xData.size:  # under/oversize
                continue
            if self.ms_series.yData[idx] > min_signal:
                label = pyqtgraph.TextItem(adduct.adduct, anchor=(0.5, 1.5))
                label.setPos(adduct.formula.mz, self.ms_series.yData[idx])
                label.setVisible(self.possible_adduct_labels_visible)
                self.plot.addItem(label)
                self.possible_adduct_labels.append(label)

    def togglePossibleAdductLabels(self) -> None:
        self.possible_adduct_labels_visible = not self.possible_adduct_labels_visible
        for label in self.possible_adduct_labels:
            label.setVisible(self.possible_adduct_labels_visible)

    def stateClicked(
        self,
        scatter: pyqtgraph.ScatterPlotItem,
        points: list[pyqtgraph.SpotItem],
        event: QtWidgets.QGraphicsSceneMouseEvent,
    ) -> None:
        state = points[0].data()
        if state <= self.d_count:
            self.dStateClicked.emit(f"D{state}")

    def updateHoverText(
        self,
        scatter: pyqtgraph.ScatterPlotItem,
        points: list[pyqtgraph.SpotItem],
        event: QtWidgets.QGraphicsSceneHoverEvent,
    ) -> None:
        if len(points) == 0:
            self.hover_text.setVisible(False)
        else:
            pos = points[0].pos()
            self.hover_text.setPos(pos)
            dstate = points[0].data()
            if dstate <= self.d_count:
                self.hover_text.setText(f"D{dstate}")
            else:
                self.hover_text.setText(f"D{self.d_count}+{dstate - self.d_count}")
            self.hover_text.setVisible(True)

    def copyToClipboard(self) -> None:
        pixmap = QtGui.QPixmap(self.viewport().size())
        painter = QtGui.QPainter(pixmap)
        self.render(painter)
        painter.end()
        QtWidgets.QApplication.clipboard().setPixmap(pixmap)  # type: ignore

    def resetZoom(self) -> None:
        vb = self.plot.getViewBox()
        if vb is not None:
            vb.enableAutoRange()

    def zoomToData(self) -> None:
        if self.d_series is None:
            return
        vb = self.plot.getViewBox()
        if vb is None:
            return

        x, y = self.d_series.getData()
        if x.size == 0:
            return

        dx = x.max() - x.min()
        vb.setRange(
            xRange=(x.min() - dx * 0.05, x.max() + dx * 0.05),
            yRange=(0.0, y.max() * 1.05),
        )


class DGetBarGraph(pyqtgraph.GraphicsView):
    def __init__(
        self,
        xlabel: str,
        ylabel: str,
        parent: QtWidgets.QWidget | None = None,
    ):
        super().__init__(background="white", parent=parent)

        pen = QtGui.QPen(QtCore.Qt.GlobalColor.black, 1.0)
        pen.setCosmetic(True)

        self.xaxis = pyqtgraph.AxisItem("bottom", pen=pen, textPen=pen, tick_pen=pen)
        self.xaxis.setLabel("m/z")

        self.yaxis = pyqtgraph.AxisItem("left", pen=pen, textPen=pen, tick_pen=pen)
        self.yaxis.setLabel("Relative Abundance")

        self.plot = pyqtgraph.PlotItem(
            name="central_plot",
            axisItems={"bottom": self.xaxis, "left": self.yaxis},
            viewBox=ViewBoxForceScaleAtZero(),
            parent=parent,
        )
        # Common options
        self.plot.setMenuEnabled(False)
        self.plot.hideButtons()

        self.series = pyqtgraph.BarGraphItem(x=0, height=0, width=0.33)
        self.plot.addItem(self.series)
        self.plot.setLimits(yMin=0.0)  # type: ignore
        self.plot.setContentsMargins(10, 10, 10, 10)

        self.setCentralWidget(self.plot)

    def sizeHint(self) -> QtCore.QSize:
        return QtCore.QSize(100, 200)

    def contextMenuEvent(self, event: QtGui.QContextMenuEvent):
        # make a menu
        action_zoom_reset = QtGui.QAction(
            QtGui.QIcon.fromTheme("zoom-original"), "Reset Zoom"
        )
        action_zoom_reset.triggered.connect(self.resetZoom)

        menu = QtWidgets.QMenu()
        menu.addAction(action_zoom_reset)
        menu.exec(event.globalPos())

    def setData(self, x: np.ndarray, y: np.ndarray) -> None:
        self.series.setOpts(x=x, height=y)
        vb = self.plot.getViewBox()
        if vb is not None:
            vb.setLimits(
                xMin=x.min() - 1.0,
                xMax=x.max() + 1.0,
                yMin=0.0,
                yMax=y.max() * 1.2,
            )

    def resetZoom(self) -> None:
        vb = self.plot.getViewBox()
        if vb is not None:
            vb.enableAutoRange()
