from PySide6 import QtCore, QtGui, QtWidgets

from dget.adduct import Adduct
from dget.dget import DGet


class DGetAdductsTextEdit(QtWidgets.QPlainTextEdit):
    def __init__(self, number_lines: int = 4, parent: QtWidgets.QWidget | None = None):
        super().__init__(parent)

        height = (
            self.fontMetrics().lineSpacing() * number_lines
            + (self.document().documentMargin() + self.frameWidth()) * 2
            + self.contentsMargins().bottom()
            + self.contentsMargins().top()
        )
        self.setMaximumHeight(int(height))

    def hasAcceptableInput(self) -> bool:
        for token in self.toPlainText().replace(" ", "").split(";"):
            if not Adduct.is_valid_adduct(token):
                return False

        return True


class DGetSettingsDialog(QtWidgets.QDialog):
    def __init__(self, parent: QtWidgets.QWidget | None = None):
        super().__init__(parent)

        self.setWindowTitle("DGet! Settings")

        self.adducts = DGetAdductsTextEdit()
        self.adducts.textChanged.connect(self.completeChanged)
        self.adducts.textChanged.connect(self.setAdductsColor)

        adduct_box = QtWidgets.QGroupBox("DGet! Defaults")
        adduct_layout = QtWidgets.QFormLayout()
        adduct_layout.addRow("Adducts:", self.adducts)
        adduct_box.setLayout(adduct_layout)

        self.signal_mode_area = QtWidgets.QRadioButton("Peak area")
        self.signal_mode_height = QtWidgets.QRadioButton("Peak height")

        self.signal_mass_width = QtWidgets.QDoubleSpinBox()
        self.signal_mass_width.setDecimals(4)
        self.signal_mass_width.setRange(1e-4, 1.0)
        self.signal_mass_width.setStepType(
            QtWidgets.QAbstractSpinBox.StepType.AdaptiveDecimalStepType
        )
        self.signal_mass_width.setSuffix(" m/z")

        mode_box = QtWidgets.QGroupBox()
        mode_layout = QtWidgets.QHBoxLayout()
        mode_layout.addWidget(self.signal_mode_area)
        mode_layout.addWidget(self.signal_mode_height)
        mode_box.setLayout(mode_layout)

        signal_box = QtWidgets.QGroupBox("Peak detection options")
        signal_layout = QtWidgets.QFormLayout()
        signal_layout.addRow("Signal mode:", mode_box)
        signal_layout.addRow("Mass width:", self.signal_mass_width)
        signal_box.setLayout(signal_layout)

        self.button_box = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Reset
            | QtWidgets.QDialogButtonBox.StandardButton.Ok
            | QtWidgets.QDialogButtonBox.StandardButton.Cancel
        )
        self.button_box.clicked.connect(self.buttonPressed)

        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(adduct_box)
        layout.addWidget(signal_box)
        layout.addWidget(self.button_box)
        self.setLayout(layout)

        self.loadSettings()

    def isComplete(self) -> bool:
        return self.adducts.hasAcceptableInput()

    def completeChanged(self) -> None:
        self.button_box.button(QtWidgets.QDialogButtonBox.StandardButton.Ok).setEnabled(
            self.isComplete()
        )

    def accept(self) -> None:
        self.saveSettings()
        super().accept()

    def buttonPressed(self, button: QtWidgets.QAbstractButton) -> None:
        sb = self.button_box.standardButton(button)
        if sb == QtWidgets.QDialogButtonBox.StandardButton.Reset:
            self.restoreDefaults()
        elif sb == QtWidgets.QDialogButtonBox.StandardButton.Ok:
            self.accept()
        else:
            self.reject()

    def setAdductsColor(self) -> None:
        palette = self.adducts.palette()
        if self.adducts.hasAcceptableInput():
            color = self.palette().text().color()
            palette.setColor(QtGui.QPalette.ColorRole.Text, color)
        else:
            palette.setColor(QtGui.QPalette.ColorRole.Text, QtCore.Qt.GlobalColor.red)
        self.adducts.setPalette(palette)

    def loadSettings(self) -> None:
        settings = QtCore.QSettings()
        if settings.contains("dget/adducts/size"):
            adducts = []
            size = settings.beginReadArray("dget/adducts")
            for i in range(size):
                settings.setArrayIndex(i)
                adducts.append(str(settings.value("adduct")))
            settings.endArray()
        else:
            adducts = DGet.common_adducts

        self.adducts.setPlainText("; ".join(adducts))

        mode = settings.value("dget/signal mode", "peak height")
        if mode == "peak area":
            self.signal_mode_area.setChecked(True)
        else:
            self.signal_mode_height.setChecked(True)

        self.signal_mass_width.setValue(
            float(settings.value("dget/signal mass width", 0.1))  # type: ignore
        )

    def restoreDefaults(self) -> None:
        settings = QtCore.QSettings()
        settings.remove("dget")
        self.loadSettings()

    def saveSettings(self) -> None:
        settings = QtCore.QSettings()

        settings.beginWriteArray("dget/adducts")
        adducts = self.adducts.toPlainText().replace(" ", "").split(";")
        for i, adduct in enumerate(adducts):
            settings.setArrayIndex(i)
            settings.setValue("adduct", adduct)
        settings.endArray()

        mode = "peak area" if self.signal_mode_area.isChecked() else "peak height"
        settings.setValue("dget/signal mode", mode)

        settings.setValue("dget/signal mass width", self.signal_mass_width.value())


if __name__ == "__main__":
    app = QtWidgets.QApplication()

    dlg = DGetSettingsDialog()

    dlg.show()
    app.exec()
