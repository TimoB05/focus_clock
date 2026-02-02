from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QDialogButtonBox, QFormLayout, QSpinBox, QVBoxLayout
)


class SettingsDialog(QDialog):
    def __init__(self, parent, focus_min: int, break_min: int, micro_sec: int, goal: int, start_unit: int):
        super().__init__(parent)

        self.setWindowTitle("Settings")
        self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)

        self.focus = QSpinBox()
        self.focus.setRange(1, 300)
        self.focus.setValue(focus_min)

        self.brk = QSpinBox()
        self.brk.setRange(1, 120)
        self.brk.setValue(break_min)

        self.micro = QSpinBox()
        self.micro.setRange(0, 600)  # 0 = microbreak deaktivieren
        self.micro.setValue(micro_sec)

        self.goal = QSpinBox()
        self.goal.setRange(1, 50)
        self.goal.setValue(goal)

        self.start_units = QSpinBox()
        self.start_units.setRange(1, 50)
        self.start_units.setValue(start_unit)

        form = QFormLayout()
        form.addRow("Fokus (Min)", self.focus)
        form.addRow("Pause (Min)", self.brk)
        form.addRow("Bildschirmpause (Sek)", self.micro)
        form.addRow("Ziel-Einheiten", self.goal)
        form.addRow("Start-Einheit", self.start_units)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
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
