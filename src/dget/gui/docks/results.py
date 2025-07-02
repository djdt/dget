import numpy as np
from PySide6 import QtWidgets

from dget.gui.graphs import DGetBarGraph


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
        self,
        deuteration: float,
        error: float,
        states: np.ndarray,
        probabilities: np.ndarray,
    ) -> None:
        html = f"<p><b>Deuteration: {deuteration * 100.0:.2f} %</b></p>"
        html += f"<p>Residual error: {error * 100.0:.2f} %</p>"
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
