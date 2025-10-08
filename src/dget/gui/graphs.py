from typing import Any

import numpy as np
import pyqtgraph
from PySide6 import QtCore, QtGui, QtWidgets

from dget.adduct import Adduct
from dget.gui.colors import dget_spectra_series, dget_state_unused, dget_state_used
from dget.gui.npqt import array_to_polygonf

pyqtgraph.setConfigOptions(antialias=True)


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


class DGetAreaGraphicsItem(QtWidgets.QGraphicsObject):
    areaHovered = QtCore.Signal(object, object, object)
    areaClicked = QtCore.Signal(object, object, object)

    data_key = 57473

    def __init__(
        self, fill_base: float = 0.0, parent: QtWidgets.QGraphicsItem | None = None
    ):
        super().__init__(parent)  # type: ignore as different from doc

        self.fill_base = fill_base
        self.hover_size = 10

        self.brush = QtGui.QBrush()
        self.pen = QtGui.QPen(QtCore.Qt.PenStyle.NoPen)

        self.polygons: list[QtGui.QPolygonF] = []
        self.brushes: dict[QtGui.QPolygonF, QtGui.QBrush] = {}
        self.datas: dict[QtGui.QPolygonF, Any] = {}

        self.hovergon: QtGui.QPolygonF | None = None

    def contains(self, point: QtCore.QPointF) -> bool:  # type: ignore
        return self.shape().contains(point)

    def paint(
        self, painter: QtGui.QPainter, options, widget: QtWidgets.QWidget | None = None
    ) -> None:
        painter.setPen(self.pen)
        for poly in self.polygons:
            if poly in self.brushes:
                painter.setBrush(self.brushes[poly])
            else:
                painter.setBrush(self.brush)

            painter.drawConvexPolygon(poly)

    def boundingRect(self) -> QtCore.QRectF:
        if len(self.polygons) == 0:
            return QtCore.QRectF()

        rect = self.polygons[0].boundingRect()
        for poly in self.polygons[1:]:
            rect = rect.united(poly.boundingRect())
        return rect

    def shape(self) -> QtGui.QPainterPath:
        path = QtGui.QPainterPath()
        for poly in self.polygons:
            path.addPolygon(poly)
            path.closeSubpath()
        path.setFillRule(QtCore.Qt.FillRule.WindingFill)
        return path

    def hoverLeaveEvent(self, event: QtWidgets.QGraphicsSceneHoverEvent) -> None:
        self.hovergon = None
        self.areaHovered.emit(None, None, event)

    def mousePressEvent(self, event: QtWidgets.QGraphicsSceneMouseEvent) -> None:
        stroke = QtGui.QPainterPathStroker(QtGui.QPen(self.hover_size))
        for poly in self.polygons:
            path = QtGui.QPainterPath()
            path.addPolygon(poly)
            if stroke.createStroke(path).contains(event.pos()):
                self.areaClicked.emit(poly, self.datas.get(poly, None), event)
                event.accept()
                return
        super().mousePressEvent(event)

    def hoverMoveEvent(self, event: QtWidgets.QGraphicsSceneHoverEvent) -> None:
        stroke = QtGui.QPainterPathStroker(QtGui.QPen(self.hover_size))
        for poly in self.polygons:
            path = QtGui.QPainterPath()
            path.addPolygon(poly)
            if stroke.createStroke(path).contains(event.pos()):
                if poly != self.hovergon:
                    self.hovergon = poly
                    self.areaHovered.emit(poly, self.datas.get(poly, None), event)
                return

        if self.hovergon is not None:
            self.hovergon = None
            self.areaHovered.emit(None, None, event)

    def addArea(
        self,
        x: np.ndarray,
        y: np.ndarray,
        brush: QtGui.QBrush | None = None,
        data: Any | None = None,
    ) -> None:
        points = np.stack(
            (
                np.concatenate(([x[0]], x, [x[-1]])),
                np.concatenate(([self.fill_base], y, [self.fill_base])),
            ),
            axis=1,
        )
        poly = array_to_polygonf(points)
        self.polygons.append(poly)

        item = QtWidgets.QGraphicsPolygonItem(poly)

        if brush is not None:
            self.brushes[poly] = brush
            item.setBrush(brush)
        if data is not None:
            self.datas[poly] = data
            item.setData(DGetAreaGraphicsItem.data_key, data)

        self.prepareGeometryChange()


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
        self.plot.setLimits(xMin=0.0, xMax=100.0, yMin=0.0, yMax=100.0)  # type: ignore

        # Common options
        self.plot.setMenuEnabled(False)
        self.plot.hideButtons()
        self.plot.setContentsMargins(10, 10, 10, 10)

        # Main HRMS data series
        self.ms_shift = 0.0
        self.ms_series = pyqtgraph.PlotCurveItem(
            pen=pen, connect="all", skipFiniteCheck=True
        )
        self.plot.addItem(self.ms_series)

        # Dueteration indicator series
        self.d_count = 0
        self.d_series = pyqtgraph.ScatterPlotItem(
            pxMode=True, size=10, hoverable=True, tip=None
        )
        self.d_series.sigClicked.connect(self.stateScatterClicked)
        self.d_series.sigHovered.connect(self.stateScatterHovered)
        self.plot.addItem(self.d_series)

        self.d_areas = DGetAreaGraphicsItem()
        self.d_areas.setAcceptHoverEvents(True)
        self.d_areas.areaClicked.connect(self.stateAreaClicked)
        self.d_areas.areaHovered.connect(self.stateAreaHovered)
        self.ms_series.sigPlotChanged.connect(self.d_areas.prepareGeometryChange)
        self.plot.addItem(self.d_areas)

        # Result series
        pen = QtGui.QPen(QtGui.QColor.fromString("#a56eff"), 2.0)
        pen.setCosmetic(True)
        self.deconv_series = pyqtgraph.PlotCurveItem(
            pen=pen, connect="all", skipFiniteCheck=True
        )
        self.plot.addItem(self.deconv_series)

        self.spectra_bars = []
        self.spectra_bar_visible = False

        # Texts
        self.hover_text = pyqtgraph.TextItem(
            "", color=QtGui.QColor.fromRgb(0, 0, 0), anchor=(0.5, 1.0)
        )
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
        self,
        x: np.ndarray,
        y: np.ndarray,
        used: np.ndarray,
        dcount: int,
        mode: str = "peak height",
        mass_width: float = 0.1,
    ) -> None:
        self.d_count = dcount
        brush_used = QtGui.QBrush(QtGui.QColor.fromString(dget_state_used))
        brush_unused = QtGui.QBrush(QtGui.QColor.fromString(dget_state_unused))
        dstate = np.arange(x.size)
        brushes = [brush_used if i in used else brush_unused for i in dstate]

        self.d_series.setVisible(mode == "peak height")
        self.d_areas.polygons.clear()
        self.d_series.setData(x=x, y=y, brush=brushes, data=dstate)

        if mode == "peak area":
            if self.ms_series.xData is None or self.ms_series.yData is None:
                return
            idx0 = np.searchsorted(self.ms_series.xData, x - mass_width)
            idx1 = np.searchsorted(self.ms_series.xData, x + mass_width, side="right")

            for center, i0, i1, brush, state in zip(x, idx0, idx1, brushes, dstate):
                x0, x1 = center - mass_width, center + mass_width
                y0 = self.ms_series.yData[i0 - 1] + (
                    x0 - self.ms_series.xData[i0 - 1]
                ) * (self.ms_series.yData[i0] - self.ms_series.yData[i0 - 1]) / (
                    self.ms_series.xData[i0] - self.ms_series.xData[i0 - 1]
                )
                y1 = self.ms_series.yData[i1 - 1] + (
                    x1 - self.ms_series.xData[i1 - 1]
                ) * (self.ms_series.yData[i1] - self.ms_series.yData[i1 - 1]) / (
                    self.ms_series.xData[i1] - self.ms_series.xData[i1 - 1]
                )
                self.d_areas.addArea(
                    np.concatenate(([x0], self.ms_series.xData[i0:i1], [x1])),
                    np.concatenate(([y0], self.ms_series.yData[i0:i1], [y1])),
                    brush=brush,
                    data=state,
                )

    def setDeconvolutionResultData(self, x: np.ndarray, y: np.ndarray) -> None:
        self.deconv_series.setData(x=x, y=y)

    def setStateSpectraData(
        self,
        x: np.ndarray,
        ys: np.ndarray,
    ) -> None:
        for bar in self.spectra_bars:
            self.plot.removeItem(bar)

        y0 = np.zeros(x.shape)
        for i in range(ys.shape[0] - 1, -1, -1):
            bar = pyqtgraph.BarGraphItem(
                x=x,
                y0=y0,
                y1=y0 + ys[i],
                width=0.5,
                pen=QtGui.QPen(QtCore.Qt.GlobalColor.black, 0.0),
                brush=QtGui.QBrush(
                    QtGui.QColor.fromString(
                        dget_spectra_series[i % len(dget_spectra_series)]
                    )
                ),
            )
            bar.setVisible(self.spectra_bar_visible)
            y0 += ys[i]
            self.plot.addItem(bar)
            self.spectra_bars.append(bar)

    def setStateSpectraVisibility(self, visible: bool) -> None:
        self.spectra_bar_visible = visible
        for bar in self.spectra_bars:
            bar.setVisible(visible)

    def setAdductLabel(self, adduct: Adduct) -> None:
        self.adduct_label.setText(
            f"{adduct.base.formula} {adduct.adduct} <br>m/z={adduct.formula.isotope.mz:.4f}"
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
            idx = np.searchsorted(self.ms_series.xData, adduct.formula.isotope.mz)
            if idx == 0 or idx == self.ms_series.xData.size:  # under/oversize
                continue
            if self.ms_series.yData[idx] > min_signal:
                label = pyqtgraph.TextItem(adduct.adduct, anchor=(0.5, 1.5))
                label.setPos(adduct.formula.isotope.mz, self.ms_series.yData[idx])
                label.setVisible(self.possible_adduct_labels_visible)
                self.plot.addItem(label)
                self.possible_adduct_labels.append(label)

    def togglePossibleAdductLabels(self) -> None:
        self.possible_adduct_labels_visible = not self.possible_adduct_labels_visible
        for label in self.possible_adduct_labels:
            label.setVisible(self.possible_adduct_labels_visible)

    def updateStateLabel(self, pos: QtCore.QPointF, state: int) -> None:
        if state <= self.d_count:
            self.hover_text.setText(f"D{state}")
        else:
            self.hover_text.setText(f"D{self.d_count}+{state - self.d_count}")
        self.hover_text.setPos(pos)
        self.hover_text.update()

    def stateAreaClicked(
        self,
        poly: QtGui.QPolygonF,
        state: int,
        event: QtWidgets.QGraphicsSceneMouseEvent,
    ) -> None:
        if state <= self.d_count:
            self.dStateClicked.emit(f"D{state}")

    def stateAreaHovered(
        self,
        poly: QtGui.QPolygonF,
        state: int,
        event: QtWidgets.QGraphicsSceneMouseEvent,
    ) -> None:
        if poly is None:
            self.hover_text.setVisible(False)
        else:
            self.hover_text.setVisible(True)
            rect = poly.boundingRect()
            pos = QtCore.QPointF(rect.center().x(), rect.bottom())
            self.updateStateLabel(pos, state)

    def stateScatterClicked(
        self,
        scatter: pyqtgraph.ScatterPlotItem,
        points: list[pyqtgraph.SpotItem],
        event: QtWidgets.QGraphicsSceneMouseEvent,
    ) -> None:
        state = points[0].data()
        if state <= self.d_count:
            self.dStateClicked.emit(f"D{state}")

    def stateScatterHovered(
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

        if (
            self.d_series.data is None
            or self.ms_series.xData is None
            or self.ms_series.yData is None
        ):
            return

        x, _ = self.d_series.getData()
        i0, i1 = np.searchsorted(self.ms_series.xData, (np.amin(x), np.amax(x)))
        i0 -= 1
        i1 += 1
        x0, x1 = self.ms_series.xData[i0], self.ms_series.xData[i1]
        dx = x1 - x0
        vb.setRange(
            xRange=(x0 - dx * 0.05, x1 + dx * 0.05),
            yRange=(0.0, np.amax(self.ms_series.yData[i0:i1]) * 1.05),
        )


class DGetBarGraph(pyqtgraph.GraphicsView):
    def __init__(
        self,
        xlabel: str,
        ylabel: str,
        pen: QtGui.QPen | None = None,
        brush: QtGui.QBrush | None = None,
        parent: QtWidgets.QWidget | None = None,
    ):
        super().__init__(background="white", parent=parent)

        pen = QtGui.QPen(QtCore.Qt.GlobalColor.black, 1.0)
        pen.setCosmetic(True)

        self.xaxis = pyqtgraph.AxisItem("bottom", pen=pen, textPen=pen, tick_pen=pen)
        self.xaxis.setLabel(xlabel)

        self.yaxis = pyqtgraph.AxisItem("left", pen=pen, textPen=pen, tick_pen=pen)
        self.yaxis.setLabel(ylabel)

        self.plot = pyqtgraph.PlotItem(
            name="central_plot",
            axisItems={"bottom": self.xaxis, "left": self.yaxis},
            viewBox=ViewBoxForceScaleAtZero(),
            parent=parent,
        )
        # Common options
        self.plot.setMenuEnabled(False)
        self.plot.hideButtons()

        self.series = pyqtgraph.BarGraphItem(
            x=0, height=0, width=0.33, pen=pen, brush=brush
        )
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
