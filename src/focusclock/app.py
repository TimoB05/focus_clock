import os
import sys

from PySide6.QtGui import QIcon, QPalette
from PySide6.QtWidgets import QApplication

if __package__ is None or __package__ == "":
    # Running as a script (e.g., PyInstaller)
    sys.path.insert(
        0, os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..")
            )
        )
    from focusclock.window import FocusClockWindow
else:
    # Running as a package
    from .window import FocusClockWindow


def main():
    app = QApplication(sys.argv)
    app.setWindowIcon(QIcon("icon.png"))

    w = FocusClockWindow()
    w.show()
    sys.exit(app.exec())


def is_dark_mode(app: QApplication) -> bool:
    pal = app.palette()
    bg = pal.color(QPalette.Window)
    return bg.lightness() < 128


if __name__ == "__main__":
    main()
