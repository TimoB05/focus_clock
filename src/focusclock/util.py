import sys

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import QApplication


def format_time_mmss(sec: int) -> str:
    sec = max(0, int(sec))
    m = sec // 60
    s = sec % 60
    return f"{m:02d}:{s:02d}"


def format_hm(sec: int) -> str:
    sec = max(0, int(sec))
    h = sec // 3600
    m = (sec % 3600) // 60
    return f"{h:d}:{m:02d}"


def beep():
    if sys.platform == "win32":
        import winsound
        winsound.MessageBeep(winsound.MB_ICONINFORMATION)
    else:
        QApplication.beep()


def tint_icon(
    icon: QIcon, size: int = 18, color: QColor = QColor("white")
    ) -> QIcon:
    pm = icon.pixmap(size, size)
    if pm.isNull():
        return icon

    tinted = QPixmap(pm.size())
    tinted.fill(Qt.transparent)

    painter = QPainter(tinted)
    painter.setCompositionMode(QPainter.CompositionMode_Source)
    painter.drawPixmap(0, 0, pm)
    painter.setCompositionMode(QPainter.CompositionMode_SourceIn)
    painter.fillRect(tinted.rect(), color)
    painter.end()

    return QIcon(tinted)
