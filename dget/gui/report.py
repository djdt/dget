import datetime

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


class DGetReportDialog(QtWidgets.QDialog):
    def __init__(
        self, dget: DGet | None = None, parent: QtWidgets.QWidget | None = None
    ):
        super().__init__(parent)

        self.doc = QtGui.QTextDocument()
        self.doc.setDefaultFont(QtGui.QFont("Courier", pointSize=12))
        self.doc.setUndoRedoEnabled(False)
        # self.doc.setDocumentMargin(0.0)

        if dget is not None:
            self.generate(dget)

    def _addHeader(self, cursor: QtGui.QTextCursor) -> None:
        # cursor = QtGui.QTextCursor(self.doc)
        # cursor.movePosition(cursor.MoveOperation.End, cursor.MoveMode.MoveAnchor)
        update_cursor_style(
            cursor,
            align=QtCore.Qt.AlignmentFlag.AlignRight,
            font_size=8,
            bottom_margin_lines=2,
        )
        cursor.insertText(f"Report generated using the DGet ({__version__})")

    def _addTable(
        self, cursor: QtGui.QTextCursor, title: str, contents: list[tuple[str, ...]]
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
        # table_format.setBorderStyle(QtGui.QTextFrameFormat.BorderStyle.BorderStyle_None)
        # table_format.setCellSpacing(fm.averageCharWidth()*2)
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
        cursor = columns.cellAt(0, 0).lastCursorPosition()
        self._addTable(cursor, "Results", results)

        graph = DGetMSGraph()
        graph.resize(1280, 960)
        graph.setData(dget.x, dget.y)
        graph.setDeuterationData(
            dget.target_masses, dget.target_signals, dget.deuteration_states
        )
        graph.zoomToData()

        pixmap = QtGui.QPixmap(QtCore.QSize(1280, 960))
        painter = QtGui.QPainter(pixmap)
        graph.render(painter)
        painter.end()

        self.doc.addResource(self.doc.ResourceType.ImageResource, "ms_graph", pixmap)

        cursor = columns.cellAt(0, 1).lastCursorPosition()
        image_format = QtGui.QTextImageFormat()
        image_format.setWidth(320)
        image_format.setHeight(240)
        image_format.setName("ms_graph")
        cursor.insertImage(image_format, QtGui.QTextFrameFormat.Position.FloatRight)

        # table.cellAt(0, 1).firstCursorPosition().insertText(
        #     f"{datetime.datetime.now().isoformat(sep=' ', timespec='minutes')}"
        # )
        # table.cellAt(1, 0).firstCursorPosition().insertText("Date:")

        # cursor.insertHtml(
        #     'Please cite <a href="https://doi.org/10.1186/s13321-024-00828-x">'
        #     "Lockwood and Angeloski (2024)"
        # )

        #         html = """<!doctype html>
        # <html>
        # <body>
        #     <div class="container">
        #         <div class="row">
        #             <h3>Information</h3>
        #                 <table>
        #                     <tr><td>Date:</td><td>{{ date }}</td></tr>
        #                     <tr><td>Notes:</td><td><input type="text"></input></td></tr>
        #                     <!-- <tr><td>Location:</td><td><input type="text"></input></td></tr> -->
        #                 </table>
        #             <h3>Compound Information</h3>
        #                 <table>
        #                     <tr><td>Name / ID:</td><td><input type="text"></input></td></tr>
        #                     <tr><td>Formula:</td><td>{{ formula }}</td></tr>
        #                     <tr><td>m/z:</td><td>{{ mz|round(4) }}</td></tr>
        #                     <tr><td>Adduct:</td><td>{{ adduct }}</td></tr>
        #                     <tr><td>Adduct m/z:</td><td>{{ adduct_mz|round(4) }}</td></tr>
        #                 </table>
        #         </div>
        #         <div class="row">
        #             <h3>Results</h3>
        #                 <table>
        #                     <tr><td>Deuteration:</td><td><b> {{ deuteration|round(2) }} %</td></b></tr>
        #                     <tr><td>Deuteration Ratio Spectra</td></tr>
        #                     {% for state, perc in ratios.items() %}
        #                     <tr><td>D{{ state }}:</td><td>{{ perc|round(2) }} %</td></tr>
        #                     {% endfor %}
        #                 </table>
        #         </div>
        #         <div class="center">
        #             <h3>Spectra</h3>
        #             <img src={{ image }}></img>
        #         </div>
        #     </div>
        #     <p>Report generated using the DGet ({{ version }}) web application ({{ web_version}}).</p>
        #     <p>Please cite <a href="https://doi.org/10.1186/s13321-024-00828-x">Lockwood and Angeloski (2024)</a>.</p>
        #     <p>For more information see <a href="https://github.com/djdt/dget">https://github.com/djdt/dget</a>.</p>
        # </body>
        # </html>"""
        #         doc.setHtml(html)

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
