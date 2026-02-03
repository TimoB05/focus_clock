import os
import sys

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QIcon

if __package__ is None or __package__ == "":
    # Running as a script (e.g., PyInstaller)
    sys.path.insert(
        0, os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..")
            )
        )
    from studyclock.window import StudyClockWindow
else:
    # Running as a package
    from .window import StudyClockWindow


def main():
    app = QApplication(sys.argv)
    app.setWindowIcon(QIcon("icon.png"))
    w = StudyClockWindow()
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
