from PySide6 import QtCore, QtGui, QtWidgets

from dget.adduct import Adduct
from dget.dget import DGet
from dget.gui.validators import DGetAdductValidator


class DGetSettingsDialog(QtWidgets.QDialog):
    def __init__(self, parent: QtWidgets.QWidget | None = None):
        super().__init__(parent)

        self.setWindowTitle("DGet! Settings")

        self.adduct_input = QtWidgets.QLineEdit()
        self.adduct_input.setValidator(DGetAdductValidator())
        self.adduct_input.textChanged.connect(self.adductInputChanged)

        self.adduct_add_button = QtWidgets.QToolButton()
        self.adduct_add_button.setIcon(QtGui.QIcon.fromTheme("list-add"))
        self.adduct_add_button.setEnabled(False)

        self.adduct_input.returnPressed.connect(self.adduct_add_button.pressed)
        self.adduct_add_button.pressed.connect(self.adductAddPressed)

        self.adducts = QtWidgets.QComboBox()

        adduct_layout = QtWidgets.QHBoxLayout()
        adduct_layout.addWidget(self.adducts)
        adduct_layout.addWidget(self.adduct_input)
        adduct_layout.addWidget(self.adduct_add_button)

        self.signal_mode_area = QtWidgets.QRadioButton("Peak area")
        self.signal_mode_height = QtWidgets.QRadioButton("Peak height")

        mode_box = QtWidgets.QGroupBox()
        mode_layout = QtWidgets.QHBoxLayout()
        mode_layout.addWidget(self.signal_mode_area)
        mode_layout.addWidget(self.signal_mode_height)
        mode_box.setLayout(mode_layout)

        self.signal_mass_width = QtWidgets.QDoubleSpinBox()
        self.signal_mass_width.setDecimals(4)
        self.signal_mass_width.setRange(1e-4, 1.0)
        self.signal_mass_width.setStepType(
            QtWidgets.QAbstractSpinBox.StepType.AdaptiveDecimalStepType
        )
        self.signal_mass_width.setSuffix(" m/z")

        self.button_box = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Reset
            | QtWidgets.QDialogButtonBox.StandardButton.Ok
            | QtWidgets.QDialogButtonBox.StandardButton.Cancel
        )
        self.button_box.clicked.connect(self.buttonPressed)

        layout = QtWidgets.QFormLayout()
        layout.addRow("Default adducts:", adduct_layout)
        layout.addRow("Signal mode:", mode_box)
        layout.addRow("Mass width:", self.signal_mass_width)
        layout.addRow(self.button_box)
        self.setLayout(layout)

        self.loadSettings()

    def adductInputChanged(self, text: str) -> None:
        self.adduct_add_button.setEnabled(self.adduct_input.hasAcceptableInput())

    def adductAddPressed(self) -> None:
        adduct = self.adduct_input.text()
        if not Adduct.is_valid_adduct(adduct):
            raise ValueError("invalid adduct")  # should not be reachable
        existing_adducts = [
            self.adducts.itemText(i) for i in range(self.adducts.count())
        ]
        if adduct not in existing_adducts:
            self.adducts.insertItem(0, adduct)
            self.adducts.setCurrentIndex(0)
        self.adduct_input.clear()

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

    def loadSettings(self) -> None:
        settings = QtCore.QSettings()
        self.adducts.clear()
        if settings.contains("dget/adducts/size"):
            size = settings.beginReadArray("dget/adducts")
            for i in range(size):
                settings.setArrayIndex(i)
                self.adducts.addItem(str(settings.value("adduct")))
            settings.endArray()
        else:
            self.adducts.addItems(DGet.common_adducts)

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
        for i in range(self.adducts.count()):
            settings.setArrayIndex(i)
            settings.setValue("adduct", self.adducts.itemText(i))
        settings.endArray()

        mode = "peak area" if self.signal_mode_area.isChecked() else "peak height"
        settings.setValue("dget/signal mode", mode)

        settings.setValue("dget/signal mass width", self.signal_mass_width.value())


if __name__ == "__main__":
    app = QtWidgets.QApplication()

    dlg = DGetSettingsDialog()

    dlg.show()
    app.exec()
