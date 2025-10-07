from pathlib import Path

import numpy as np
from PySide6 import QtCore, QtGui, QtWidgets

from dget.io.text import guess_loadtxt_kws


class TextImportDialog(QtWidgets.QDialog):
    dataImported = QtCore.Signal(Path, np.ndarray, np.ndarray)

    def __init__(self, path: str | Path, parent: QtWidgets.QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle("DGet! Text Import")
        self.file_path = Path(path)

        header_row_count = 100

        self.file_header = [
            x for _, x in zip(range(header_row_count), self.file_path.open("r"))
        ]

        # Guess the delimiter, skip rows and count from header
        loadtxt_kws = guess_loadtxt_kws(
            self.file_path, {"deilimiter": ",", "usecols": (0, 1), "skiprows": 0}
        )

        column_count = (
            max([line.count(loadtxt_kws["delimiter"]) for line in self.file_header]) + 1
        )

        with self.file_path.open("rb") as fp:
            line_count = 0
            buffer = bytearray(4086)
            while fp.readinto(buffer):
                line_count += buffer.count(b"\n")

        self.table = QtWidgets.QTableWidget()
        self.table.setFont(QtGui.QFont("Courier"))
        self.table.setColumnCount(column_count)
        self.table.setRowCount(header_row_count)
        self.table.itemChanged.connect(self.completeChanged)

        self.combo_delimiter = QtWidgets.QComboBox()
        self.combo_delimiter.addItems([",", ";", "Space", "Tab"])
        self.combo_delimiter.setCurrentIndex(
            [",", ";", " ", "\t"].index(loadtxt_kws["delimiter"])
        )
        self.combo_delimiter.currentIndexChanged.connect(self.fillTable)

        self.spinbox_first_line = QtWidgets.QSpinBox()
        self.spinbox_first_line.setRange(1, header_row_count - 1)
        self.spinbox_first_line.setValue(loadtxt_kws["skiprows"] + 1)
        self.spinbox_first_line.valueChanged.connect(self.updateTableIgnores)

        self.spinbox_mass_column = QtWidgets.QSpinBox()
        self.spinbox_mass_column.setRange(1, column_count)
        self.spinbox_mass_column.setValue(loadtxt_kws["usecols"][0] + 1)
        self.spinbox_mass_column.valueChanged.connect(self.updateTableIgnores)

        self.spinbox_signal_column = QtWidgets.QSpinBox()
        self.spinbox_signal_column.setRange(1, column_count)
        self.spinbox_signal_column.setValue(loadtxt_kws["usecols"][1] + 1)
        self.spinbox_signal_column.valueChanged.connect(self.updateTableIgnores)

        box_options = QtWidgets.QGroupBox("Import options")
        box_options.setLayout(QtWidgets.QFormLayout())

        box_options.layout().addRow("Delimiter:", self.combo_delimiter)
        box_options.layout().addRow("First data line:", self.spinbox_first_line)
        box_options.layout().addRow("Mass column:", self.spinbox_mass_column)
        box_options.layout().addRow("Signal column:", self.spinbox_signal_column)

        self.button_box = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Ok
            | QtWidgets.QDialogButtonBox.StandardButton.Cancel
        )
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)

        box_info = QtWidgets.QGroupBox("File info")
        box_info.setLayout(QtWidgets.QFormLayout())
        box_info.layout().addRow("Name:", QtWidgets.QLabel(self.file_path.name))
        box_info.layout().addRow("No. lines:", QtWidgets.QLabel(str(line_count)))

        boxes_layout = QtWidgets.QVBoxLayout()
        boxes_layout.addWidget(box_info, 0)
        boxes_layout.addWidget(box_options, 1)
        content_layout = QtWidgets.QHBoxLayout()
        content_layout.addLayout(boxes_layout, 0)
        content_layout.addWidget(self.table, 1)

        layout = QtWidgets.QVBoxLayout()
        layout.addLayout(content_layout, 1)
        layout.addWidget(self.button_box)

        self.fillTable()
        self.setLayout(layout)

    def completeChanged(self) -> None:
        complete = self.isComplete()
        self.button_box.button(QtWidgets.QDialogButtonBox.StandardButton.Ok).setEnabled(
            complete
        )

    def isComplete(self) -> bool:
        if self.table.columnCount() < 2:
            return False
        if self.spinbox_mass_column.value() == self.spinbox_signal_column.value():
            return False
        try:
            tokens = self.file_header[self.spinbox_first_line.value()].split(
                self.delimiter()
            )
            float(tokens[self.usecols()[0]])
            float(tokens[self.usecols()[1]])
        except ValueError:
            return False
        return True

    def delimiter(self) -> str:
        delimiter = self.combo_delimiter.currentText()
        if delimiter == "Space":
            delimiter = " "
        elif delimiter == "Tab":
            delimiter = "\t"
        return delimiter

    def usecols(self) -> tuple[int, int]:
        return (
            self.spinbox_mass_column.value() - 1,
            self.spinbox_signal_column.value() - 1,
        )

    def skiprows(self) -> int:
        return self.spinbox_first_line.value() - 1

    def fillTable(self) -> None:
        lines = [line.split(self.delimiter()) for line in self.file_header]
        col_count = max(len(line) for line in lines)

        self.table.blockSignals(True)
        self.table.setColumnCount(col_count)

        for row, line in enumerate(lines):
            line.extend([""] * (col_count - len(line)))
            for col, text in enumerate(line):
                item = QtWidgets.QTableWidgetItem(text.strip().replace(" ", "_"))
                self.table.setItem(row, col, item)
        self.table.blockSignals(False)

        self.updateTableIgnores()
        self.table.resizeColumnsToContents()

    def updateTableIgnores(self) -> None:
        self.table.blockSignals(True)
        header_row = self.skiprows()
        for row in range(self.table.rowCount()):
            for col in range(self.table.columnCount()):
                item = self.table.item(row, col)
                if item is None:
                    continue
                if row != header_row:
                    item.setFlags(item.flags() & ~QtCore.Qt.ItemFlag.ItemIsEditable)
                else:
                    item.setFlags(item.flags() | QtCore.Qt.ItemFlag.ItemIsEditable)
                if row < header_row or col not in self.usecols():
                    item.setFlags(item.flags() & ~QtCore.Qt.ItemFlag.ItemIsEnabled)
                else:
                    item.setFlags(item.flags() | QtCore.Qt.ItemFlag.ItemIsEnabled)
        self.table.blockSignals(False)
        self.completeChanged()

    def accept(self, loadtxt_kws: dict | None = None) -> None:
        if loadtxt_kws is None:
            loadtxt_kws = {
                "delimiter": self.delimiter(),
                "skiprows": self.skiprows(),
                "usecols": self.usecols(),
            }
        x, y = np.loadtxt(self.file_path, unpack=True, dtype=np.float32, **loadtxt_kws)
        self.dataImported.emit(self.file_path, x, y)
        super().accept()
