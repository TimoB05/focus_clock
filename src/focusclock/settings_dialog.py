from PySide6.QtCore import Qt
from PySide6.QtGui import QPalette
from PySide6.QtWidgets import (
    QApplication, QDialog, QDialogButtonBox,
    QFormLayout, QSpinBox, QVBoxLayout
    )


class SettingsDialog(QDialog):
    def __init__(
        self, parent, focus_min: int, break_min: int, micro_sec: int,
        goal: int, start_unit: int
        ):
        super().__init__(parent)

        app = QApplication.instance()
        bg = app.palette().color(QPalette.Window)
        dark = bg.lightness() < 128
        self.setStyleSheet("color: #eee;" if dark else "color: #111;")

        self.setWindowTitle("Settings")
        self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)

        self.focus = QSpinBox()
        self.focus.setRange(1, 300)
        self.focus.setValue(focus_min)

        self.brk = QSpinBox()
        self.brk.setRange(1, 120)
        self.brk.setValue(break_min)

        self.micro = QSpinBox()
        self.micro.setRange(0, 600)  # 0 = deactivate microbreak
        self.micro.setValue(micro_sec)

        self.goal = QSpinBox()
        self.goal.setRange(1, 50)
        self.goal.setValue(goal)

        self.start_units = QSpinBox()
        self.start_units.setRange(1, 50)
        self.start_units.setValue(start_unit)

        form = QFormLayout()
        form.addRow("Focus (Min)", self.focus)
        form.addRow("Break (Min)", self.brk)
        form.addRow("Screen Break (Sec)", self.micro)
        form.addRow("Target Units", self.goal)
        form.addRow("Starting Unit", self.start_units)

        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
            )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout()
        layout.addLayout(form)
        layout.addWidget(buttons)
        self.setLayout(layout)

    def values(self):
        return (
            self.focus.value(),
            self.brk.value(),
            self.micro.value(),
            self.goal.value(),
            self.start_units.value(),
            )
