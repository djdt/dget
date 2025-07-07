import numpy as np
from PySide6 import QtCore, QtGui, QtWidgets

from dget.gui.colors import dget_state_used
from dget.gui.graphs import DGetBarGraph


class DGetResultsText(QtWidgets.QDockWidget):
    def __init__(self, parent: QtWidgets.QWidget | None = None):
        super().__init__("Results", parent)
        self.setObjectName("dget-results-text-dock")

        self.text = QtWidgets.QPlainTextEdit()
        self.text.setFont("courier")
        self.text.setReadOnly(True)

        self.setWidget(self.text)

    def updateText(
        self,
        deuteration: float,
        error: float,
        states: np.ndarray,
        probabilities: np.ndarray,
    ) -> None:
        self.text.clear()

        cursor = self.text.textCursor()
        format = cursor.charFormat()
        format.setFontWeight(QtGui.QFont.Weight.Bold)
        cursor.setCharFormat(format)

        cursor.insertText(f"Deuteration: {deuteration * 100.0:>10.2f} %")
        cursor.insertBlock()

        format.setFontWeight(QtGui.QFont.Weight.Normal)
        cursor.setCharFormat(format)

        cursor.insertText(f"Residual error: {error * 100.0:>7.2f} %")
        cursor.insertBlock()
        cursor.insertBlock()

        cursor.insertText("Deuteration Ratio Spectra")
        cursor.insertBlock()

        for state, prob in zip(states, probabilities):
            cursor.insertText(f"D{state:>2}: {prob * 100.0:>18.2f} %")
            cursor.insertBlock()


class DGetResultsGraph(QtWidgets.QDockWidget):
    def __init__(self, parent: QtWidgets.QWidget | None = None):
        super().__init__("Deuteration States", parent)
        self.setObjectName("dget-results-graph-dock")

        self.graph = DGetBarGraph(
            "State",
            "Percent Abundance",
            pen=QtGui.QPen(QtCore.Qt.GlobalColor.black, 0.0),
            brush=QtGui.QBrush(QtGui.QColor.fromString(dget_state_used)),
        )
        self.setWidget(self.graph)
