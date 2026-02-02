import sys
from PySide6.QtWidgets import QApplication
from .window import StudyClockWindow

def main():
    app = QApplication(sys.argv)
    w = StudyClockWindow()
    w.show()
    sys.exit(app.exec())
