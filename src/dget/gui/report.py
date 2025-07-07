import datetime
from importlib.metadata import version
from pathlib import Path
from typing import Sequence

from PySide6 import QtCore, QtGui, QtPrintSupport, QtWidgets

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


class TextEditPartialReadOnly(QtWidgets.QTextEdit):
    def __init__(self, parent: QtWidgets.QWidget | None = None):
        super().__init__(parent)
        self.setReadOnly(True)

        # must implement firstCursorPosition and lastCursorPoisition
        self.editable_regions: list[QtGui.QTextTableCell] = []

        self.cursorPositionChanged.connect(self.updateReadOnly)
        self.selectionChanged.connect(self.updateReadOnly)

    def addEditableRegion(self, region: QtGui.QTextTableCell) -> None:
        format = region.format()
        format = format.toTableCellFormat()
        format.setBorder(1.0)
        region.setFormat(format)
        self.editable_regions.append(region)

    def updateReadOnly(self) -> None:
        if not self.isVisible():
            self.setReadOnly(True)
            return

        cursor = self.textCursor()
        if cursor.hasSelection():
            start, end = cursor.selectionStart(), cursor.selectionEnd()
        else:
            start = end = cursor.position()

        for region in self.editable_regions:
            if (
                start >= region.firstCursorPosition().position()
                and end <= region.lastCursorPosition().position()
            ):
                self.setReadOnly(False)
                return
        self.setReadOnly(True)

    def wheelEvent(self, event: QtGui.QWheelEvent) -> None:
        # remove the control modifier (used for zoom in / out)
        event.setModifiers(
            event.modifiers() & ~QtCore.Qt.KeyboardModifier.ControlModifier
        )
        super().wheelEvent(event)

    def keyPressEvent(self, event: QtGui.QKeyEvent) -> None:
        # make Tab and Shift+Tab cycle through editable regions
        if (
            event.key() == QtCore.Qt.Key.Key_Tab
            or event.key() == QtCore.Qt.Key.Key_Backtab
        ):
            cursor = self.textCursor()
            pos = cursor.position()
            if event.key() == QtCore.Qt.Key.Key_Tab:
                for region in self.editable_regions:
                    if region.firstCursorPosition().position() > pos:
                        pos = region.firstCursorPosition().position()
                        break
                if pos == cursor.position():
                    pos = self.editable_regions[0].firstCursorPosition().position()
            else:
                for region in self.editable_regions:
                    if region.lastCursorPosition().position() < pos:
                        pos = region.firstCursorPosition().position()
                        break
                if pos == cursor.position():
                    pos = self.editable_regions[-1].firstCursorPosition().position()
            cursor.setPosition(pos)
            cursor.select(QtGui.QTextCursor.SelectionType.LineUnderCursor)
            self.setTextCursor(cursor)
            event.accept()
        else:
            super().keyPressEvent(event)


class DGetReportDialog(QtWidgets.QDialog):
    def __init__(
        self, dget: DGet | None = None, parent: QtWidgets.QWidget | None = None
    ):
        super().__init__(parent)

        self.doc = QtGui.QTextDocument()
        self.doc.setDefaultFont(QtGui.QFont("Courier", pointSize=12))
        self.doc.setUndoRedoEnabled(False)

        self.printer = QtPrintSupport.QPrinter(
            QtPrintSupport.QPrinter.PrinterMode.ScreenResolution
        )
        self.restorePageSetup()

        self.edit = TextEditPartialReadOnly()
        self.edit.setDocument(self.doc)
        self.edit.setViewportMargins(
            self.printer.pageLayout().marginsPixels(self.printer.resolution())
        )
        page_rect = self.printer.pageLayout().fullRectPixels(self.printer.resolution())
        self.edit.setBaseSize(
            page_rect.width() + self.edit.verticalScrollBar().width(),
            page_rect.height(),
        )
        self.edit.setMinimumSize(
            page_rect.width() + self.edit.verticalScrollBar().width(),
            page_rect.height() // 2,
        )

        self.button_box = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Save
            | QtWidgets.QDialogButtonBox.StandardButton.Close,
        )
        self.button_box.clicked.connect(self.buttonClicked)

        if dget is not None:
            self.generate(dget)

        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(self.edit, 1)
        layout.addWidget(self.button_box, 0)
        self.setLayout(layout)

    def restorePageSetup(self) -> None:
        settings = QtCore.QSettings()
        self.printer.setResolution(int(settings.value("report/resolution", 96)))  # type: ignore
        self.printer.setPageMargins(
            QtCore.QMarginsF(  # type: ignore
                settings.value(  # type: ignore
                    "report/margins", QtCore.QMarginsF(15.0, 5.0, 15.0, 10.0)
                )
            ),
            QtGui.QPageLayout.Unit.Millimeter,
        )
        self.printer.setPageSize(
            settings.value("report/page size", QtGui.QPageSize.PageSizeId.A4)  # type: ignore
        )

    def buttonClicked(self, button: QtWidgets.QAbstractButton) -> None:
        sb = self.button_box.standardButton(button)
        if sb == QtWidgets.QDialogButtonBox.StandardButton.Save:
            self.accept()
        else:
            self.reject()

    def accept(self) -> None:
        default_path = Path(str(QtCore.QSettings().value("recent files/1/path", "")))
        default_path = str(default_path.with_suffix(".pdf").absolute())

        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Save Report", default_path, "PDF Documents (*.pdf)", ""
        )
        if path == "":
            return

        self.printer.setOutputFormat(QtPrintSupport.QPrinter.OutputFormat.PdfFormat)
        self.printer.setOutputFileName(path)
        self.printReport(self.printer)

        super().accept()

    def _addHeader(self, cursor: QtGui.QTextCursor) -> None:
        update_cursor_style(
            cursor,
            align=QtCore.Qt.AlignmentFlag.AlignRight,
            font_size=8,
        )
        cursor.insertText(f"Report generated using the DGet! v{version('dget')} GUI.\n")
        update_cursor_style(
            cursor,
            align=QtCore.Qt.AlignmentFlag.AlignRight,
            font_size=8,
            bottom_margin_lines=2,
        )
        cursor.insertText("When using DGet! in your research please cite ")
        old_format = cursor.charFormat()
        format = cursor.charFormat()
        format.setAnchor(True)
        format.setAnchorHref("https://doi.org/10.1186/s13321-024-00828-x")
        format.setUnderlineStyle(QtGui.QTextCharFormat.UnderlineStyle.SingleUnderline)
        cursor.insertText("10.1186/s13321-024-00828-x", format)
        cursor.insertText(".", old_format)

    def _addTable(
        self,
        cursor: QtGui.QTextCursor,
        title: str,
        contents: Sequence[tuple[str, ...]],
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

        settings = QtCore.QSettings()

        cursor = QtGui.QTextCursor(self.doc)
        self._addHeader(cursor)
        info = [
            ("Date", datetime.datetime.now().isoformat(sep=" ", timespec="minutes")),
            ("User", str(settings.value("report/user", "---"))),
        ]

        table_format = QtGui.QTextTableFormat()
        table_format.setBorderStyle(QtGui.QTextFrameFormat.BorderStyle.BorderStyle_None)
        table_format.setWidth(
            QtGui.QTextLength(QtGui.QTextLength.Type.PercentageLength, 100.0)
        )
        columns = cursor.insertTable(1, 3, table_format)

        cursor = columns.cellAt(0, 0).lastCursorPosition()
        table = self._addTable(cursor, "Report Information", info)
        self.edit.addEditableRegion(table.cellAt(1, 1))

        cinfo = [
            ("Name / ID", "---"),
            ("Formula", dget.adduct.base.formula),
            ("m/z", f"{dget.adduct.base.isotope.mz:.4f}"),
            ("Adduct", dget.adduct.adduct),
            ("Adduct m/z", f"{dget.adduct.formula.isotope.mz:.4f}"),
        ]

        cursor = columns.cellAt(0, 0).lastCursorPosition()
        table = self._addTable(cursor, "Compound Information", cinfo)
        self.edit.addEditableRegion(table.cellAt(0, 1))

        results = [
            ("Deuteration", f"<b>{dget.deuteration * 100:.2f} %</b>"),
            ("Residual error", f"{(dget.residual_error or 0.0) * 100:.2f} %"),
            ("Deuteration Ratio Spectra", ""),
        ]
        probs = dget.deuteration_probabilities[dget.deuteration_states]
        probs = probs / probs.sum() * 100.0
        for state, prob in zip(dget.deuteration_states, probs):
            results.append((f"D{state}", f"{prob:.2f} %"))

        cursor = columns.cellAt(0, 2).lastCursorPosition()
        results_table = self._addTable(cursor, "Results", results)

        # right align the % column
        for row in range(results_table.rows()):
            cell = results_table.cellAt(row, 1)
            format = cell.lastCursorPosition().blockFormat()
            format.setAlignment(QtCore.Qt.AlignmentFlag.AlignRight)
            cell.lastCursorPosition().setBlockFormat(format)

        image_width = (
            self.printer.pageLayout().paintRectPixels(self.printer.resolution()).width()
        )
        image_size = QtCore.QSize(image_width, int(image_width * 3 / 4))

        graph = DGetMSGraph()
        graph.resize(image_size)
        graph.setData(dget.x, dget.y)
        graph.setDeuterationData(
            dget.target_masses,
            dget.target_signals,
            dget.deuteration_states,
            dget.deuterium_count,
            mode=str(settings.value("dget/signal mode", "peak height")),
            mass_width=float(settings.value("dget/signal mass width", 0.1)),  # type: ignore
        )
        graph.zoomToData()

        pixmap = QtGui.QPixmap(image_size * 2)
        painter = QtGui.QPainter(pixmap)
        graph.render(painter)
        painter.end()
        graph.show()  # required to prevent show crashes

        self.doc.addResource(self.doc.ResourceType.ImageResource, "ms_graph", pixmap)

        cursor.movePosition(cursor.MoveOperation.End, cursor.MoveMode.MoveAnchor)
        cursor.insertBlock()
        update_cursor_style(cursor, align=QtCore.Qt.AlignmentFlag.AlignHCenter)
        image_format = QtGui.QTextImageFormat()
        image_format.setWidth(image_size.width())
        image_format.setHeight(image_size.height())
        image_format.setName("ms_graph")
        cursor.insertImage(image_format)

    def printReport(self, printer: QtPrintSupport.QPrinter) -> None:
        # get rid of editable region boxes
        for region in self.edit.editable_regions:
            format = region.format()
            format = format.toTableCellFormat()
            format.setBorderStyle(QtGui.QTextFrameFormat.BorderStyle.BorderStyle_None)
            region.setFormat(format)

        self.doc.setPageSize(
            self.printer.pageLayout().fullRectPixels(self.printer.resolution()).size()
        )
        self.doc.print_(printer)
