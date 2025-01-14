import datetime
from typing import Sequence

from PySide6 import QtCore, QtGui, QtPrintSupport, QtWidgets

from dget import __version__
from dget.dget import DGet
from dget.gui.graphs import DGetMSGraph


def update_cursor_style(
    cursor: QtGui.QTextCursor,
    align: QtCore.Qt.AlignmentFlag | None = None,
    font_size: int | None = None,
    weight: QtGui.QFont.Weight | None = None,
    bottom_margin_lines: int | None = None,
) -> None:
    char = cursor.blockCharFormat()

    if font_size is not None:
        char.setFontPointSize(font_size)
    if weight is not None:
        char.setFontWeight(weight)

    cursor.setBlockCharFormat(char)

    block = cursor.blockFormat()

    if align is not None:
        block.setAlignment(align)
    if bottom_margin_lines is not None:
        fm = QtGui.QFontMetrics(char.font())
        block.setBottomMargin(fm.lineSpacing() * bottom_margin_lines)

    cursor.setBlockFormat(block)


class TextEditNoZoom(QtWidgets.QTextEdit):
    def wheelEvent(self, event: QtGui.QWheelEvent) -> None:
        # remove the control modifier (used for zoom in / out)
        event.setModifiers(
            event.modifiers() & ~QtCore.Qt.KeyboardModifier.ControlModifier
        )
        super().wheelEvent(event)


class DGetReportDialog(QtWidgets.QDialog):
    def __init__(
        self, dget: DGet | None = None, parent: QtWidgets.QWidget | None = None
    ):
        super().__init__(parent)

        self.doc = QtGui.QTextDocument()
        self.doc.setDefaultFont(QtGui.QFont("Courier", pointSize=12))
        self.doc.setUndoRedoEnabled(False)
        # self.doc.setDocumentMargin(0.0)

        self.edit = TextEditNoZoom()
        self.edit.setReadOnly(True)
        self.edit.setDocument(self.doc)
        self.edit.setBaseSize(794, 1123)
        self.edit.setMinimumSize(794, 1123 // 2)

        self.button_box = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Save
            | QtWidgets.QDialogButtonBox.StandardButton.Close,
        )
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)

        if dget is not None:
            self.generate(dget)

        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(self.edit, 1)
        layout.addWidget(self.button_box, 0)
        self.setLayout(layout)

    def accept(self) -> None:
        # todo: check for last used report dialog
        path, ok = QtWidgets.QFileDialog.getSaveFileName(
            self, "Save Report", "", "PDF Documents (*.pdf)", None
        )
        if not ok:
            return
        self.printReport(path)
        super().accept()

    def _addHeader(self, cursor: QtGui.QTextCursor) -> None:
        # cursor = QtGui.QTextCursor(self.doc)
        # cursor.movePosition(cursor.MoveOperation.End, cursor.MoveMode.MoveAnchor)
        update_cursor_style(
            cursor,
            align=QtCore.Qt.AlignmentFlag.AlignRight,
            font_size=8,
            bottom_margin_lines=2,
        )
        cursor.insertText(f"Report generated using the DGet ({__version__}) GUI")

    def _addTable(
        self, cursor: QtGui.QTextCursor, title: str, contents: Sequence[tuple[str, ...]]
    ) -> QtGui.QTextTable:
        cursor.insertBlock()
        update_cursor_style(
            cursor,
            align=QtCore.Qt.AlignmentFlag.AlignLeft,
            font_size=12,
            weight=QtGui.QFont.Weight.Bold,
            bottom_margin_lines=0,
        )
        cursor.insertText(title)
        cursor.insertBlock()
        update_cursor_style(cursor, font_size=12, weight=QtGui.QFont.Weight.Normal)

        fm = QtGui.QFontMetrics(cursor.charFormat().font())

        table_format = QtGui.QTextTableFormat()
        table_format.setWidth(
            QtGui.QTextLength(QtGui.QTextLength.Type.PercentageLength, 50.0)
        )
        table_format.setBottomMargin(fm.lineSpacing())

        table = cursor.insertTable(len(contents), len(contents[0]), table_format)
        for i in range(len(contents)):
            for j, text in enumerate(contents[i]):
                table.cellAt(i, j).firstCursorPosition().insertHtml(text)
        return table

    def generate(self, dget: DGet) -> None:
        self.doc.clear()

        cursor = QtGui.QTextCursor(self.doc)
        self._addHeader(cursor)
        info = [
            ("Date", datetime.datetime.now().isoformat(sep=" ", timespec="minutes")),
            ("User", ""),
        ]

        table_format = QtGui.QTextTableFormat()
        table_format.setBorderStyle(QtGui.QTextFrameFormat.BorderStyle.BorderStyle_None)
        table_format.setWidth(
            QtGui.QTextLength(QtGui.QTextLength.Type.PercentageLength, 100.0)
        )
        # table_format.setPadding
        columns = cursor.insertTable(1, 2, table_format)

        cursor = columns.cellAt(0, 0).lastCursorPosition()
        self._addTable(cursor, "Report Information", info)
        cinfo = [
            ("Name / ID", ""),
            ("Formula", dget.adduct.base.formula),
            ("m/z", f"{dget.adduct.base.mz:.4f}"),
            ("Adduct", dget.adduct.adduct),
            ("Adduct m/z", f"{dget.adduct.formula.mz:.4f}"),
        ]

        cursor = columns.cellAt(0, 0).lastCursorPosition()
        self._addTable(cursor, "Compound Information", cinfo)
        results = [
            ("Deuteration", f"<b>{dget.deuteration * 100:.2f} %</b>"),
            ("Deuteration Ratio Spectra", ""),
        ]
        probs = dget.deuteration_probabilites[dget.deuteration_states]
        probs = probs / probs.sum() * 100.0
        for state, prob in zip(dget.deuteration_states, probs):
            results.append((f"D{state}", f"{prob:.2f} %"))

        cursor = columns.cellAt(0, 1).lastCursorPosition()
        self._addTable(cursor, "Results", results)

        graph = DGetMSGraph()
        graph.resize(1280, 960)
        graph.setData(dget.x, dget.y)
        graph.setDeuterationData(
            dget.target_masses,
            dget.target_signals,
            dget.deuteration_states,
            dget.deuterium_count,
        )
        graph.zoomToData()

        pixmap = QtGui.QPixmap(QtCore.QSize(1280, 960))
        painter = QtGui.QPainter(pixmap)
        graph.render(painter)
        painter.end()
        graph.show()  # required to prevent show crashes

        self.doc.addResource(self.doc.ResourceType.ImageResource, "ms_graph", pixmap)

        cursor.movePosition(cursor.MoveOperation.End, cursor.MoveMode.MoveAnchor)
        cursor.insertBlock()
        # update_cursor_style(cursor, align=QtCore.Qt.AlignmentFlag.AlignCenter)
        image_format = QtGui.QTextImageFormat()
        image_format.setWidth(640)
        image_format.setHeight(480)
        image_format.setName("ms_graph")
        cursor.insertImage(image_format, QtGui.QTextFrameFormat.Position.FloatRight)

    def printReport(self, path: str) -> None:
        printer = QtPrintSupport.QPrinter(
            QtPrintSupport.QPrinter.PrinterMode.ScreenResolution
        )
        printer.setResolution(96)
        printer.setOutputFormat(QtPrintSupport.QPrinter.OutputFormat.PdfFormat)
        printer.setPageMargins(
            QtCore.QMarginsF(15.0, 5.0, 15.0, 10.0), QtGui.QPageLayout.Unit.Millimeter
        )
        printer.setPageSize(QtGui.QPageSize.PageSizeId.A4)
        printer.setOutputFileName(path)
        self.doc.setPageSize(QtCore.QSizeF(printer.width(), printer.height()))
        self.doc.print_(printer)
