from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QDialog, QDialogButtonBox, QLabel, QVBoxLayout

from .util import format_hm


class StatsDialog(QDialog):
    def __init__(self, parent, focus_work_sec: int, paused_sec: int, microbreak_sec: int, total_open_sec: int):
        super().__init__(parent)
        self.setWindowTitle("Statistiken")
        self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)

        total = max(1, int(total_open_sec))
        eff = int(round((int(focus_work_sec) / total) * 100))

        text = (
            f"Fokus aktiv: {format_hm(focus_work_sec)}\n"
            f"Pausiert: {format_hm(paused_sec)}\n"
            f"Bildschirmpause: {format_hm(microbreak_sec)}\n"
            f"\nEffizienz: {eff}%"
        )

        lbl = QLabel(text)
        lbl.setFont(QFont("Segoe UI", 10))
        lbl.setStyleSheet("color: #eee;")

        btns = QDialogButtonBox(QDialogButtonBox.Ok)
        btns.accepted.connect(self.accept)

        lay = QVBoxLayout(self)
        lay.addWidget(lbl)
        lay.addWidget(btns)
