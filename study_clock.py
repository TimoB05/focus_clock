import sys
from PySide6.QtCore import Qt, QTimer, QPoint
from PySide6.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton,
    QVBoxLayout, QHBoxLayout
    )
from PySide6.QtGui import QFont

FOCUS_SEC = 50 * 60
BREAK_SEC = 10 * 60
MICROBREAK_SEC = 60

# Reminder-time im Fokus (verbleibende Sekunden)
REMIND_AT = {40 * 60, 20 * 60, 0}


class StudyClock(QWidget):
    def __init__(self):
        super().__init__()

        # Fenster-Setup: Always on top + schlicht
        self.setWindowFlags(
            Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
            )
        self.setAttribute(Qt.WA_TranslucentBackground, False)
        self.setStyleSheet(
            """
                        QWidget { background: #111; border: 1px solid #333; 
                        border-radius: 10px; }
                        QLabel { color: #eee; }
                        QPushButton {
                            background: #222; color: #eee; border: 1px solid 
                            #444;
                            padding: 6px 10px; border-radius: 8px;
                        }
                        QPushButton:hover { background: #2a2a2a; }
                    """
            )

        # State
        self.mode = "focus"  # "focus" oder "break"
        self.remaining = FOCUS_SEC
        self.session_count = 0
        self.session_goal = 7
        self.running = False

        # Microbreak (Bildschirmpause)
        self.microbreak_active = False
        self.microbreak_remaining = 0
        self.reminded_this_focus = set()

        # UI
        self.timer_label = QLabel(self.format_time(self.remaining))
        self.timer_label.setFont(QFont("Segoe UI", 24, QFont.Bold))
        self.timer_label.setAlignment(Qt.AlignCenter)

        self.mode_label = QLabel("FOKUS")
        self.mode_label.setFont(QFont("Segoe UI", 11, QFont.Bold))
        self.mode_label.setAlignment(Qt.AlignCenter)

        self.counter_label = QLabel(self.counter_text())
        self.counter_label.setFont(QFont("Segoe UI", 10))
        self.counter_label.setAlignment(Qt.AlignCenter)

        self.info_label = QLabel("")  # microbreak status / messages
        self.info_label.setFont(QFont("Segoe UI", 9))
        self.info_label.setAlignment(Qt.AlignCenter)
        self.info_label.setStyleSheet("color: #bbb;")

        btn_row = QHBoxLayout()
        self.start_btn = QPushButton("Start")
        self.pause_btn = QPushButton("Pause")
        self.reset_btn = QPushButton("Reset")
        btn_row.addWidget(self.start_btn)
        btn_row.addWidget(self.pause_btn)
        btn_row.addWidget(self.reset_btn)

        layout = QVBoxLayout()
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)
        layout.addWidget(self.mode_label)
        layout.addWidget(self.timer_label)
        layout.addWidget(self.counter_label)
        layout.addWidget(self.info_label)
        layout.addLayout(btn_row)
        self.setLayout(layout)

        # Timer tick (1Hz)
        self.tick_timer = QTimer(self)
        self.tick_timer.setInterval(1000)
        self.tick_timer.timeout.connect(self.on_tick)

        # microbreak countdown (1Hz) läuft über selben Tick

        # Signals
        self.start_btn.clicked.connect(self.start)
        self.pause_btn.clicked.connect(self.pause)
        self.reset_btn.clicked.connect(self.reset_all)

        # Dragging
        self._dragging = False
        self._drag_offset = QPoint(0, 0)

        self.update_ui()
        self.resize(220, 170)

    # ----------------- UI helpers -----------------
    def format_time(self, sec: int) -> str:
        m = sec // 60
        s = sec % 60
        return f"{m:02d}:{s:02d}"

    def counter_text(self) -> str:
        return f"Einheiten: {self.session_count}/{self.session_goal}"

    def update_ui(self):
        self.timer_label.setText(self.format_time(self.remaining))
        self.counter_label.setText(self.counter_text())

        if self.mode == "focus":
            self.mode_label.setText("FOKUS")
            self.mode_label.setStyleSheet("color: #7CFC98;")
        else:
            self.mode_label.setText("PAUSE")
            self.mode_label.setStyleSheet("color: #7CC7FF;")

    def beep(self):
        QApplication.beep()

    # ----------------- Control -----------------
    def start(self):
        if not self.running:
            self.running = True
            self.tick_timer.start()

    def pause(self):
        self.running = False
        self.tick_timer.stop()
        self.info_label.setText("")

    def reset_all(self):
        self.running = False
        self.tick_timer.stop()
        self.mode = "focus"
        self.remaining = FOCUS_SEC
        self.session_count = 0
        self.microbreak_active = False
        self.microbreak_remaining = 0
        self.reminded_this_focus.clear()
        self.info_label.setText("")
        self.update_ui()

    # ----------------- State machine -----------------
    def switch_to_break(self):
        self.mode = "break"
        self.remaining = BREAK_SEC
        self.info_label.setText("Pause gestartet")
        self.beep()

    def switch_to_focus(self):
        self.mode = "focus"
        self.remaining = FOCUS_SEC
        self.reminded_this_focus.clear()
        self.info_label.setText("Fokus gestartet")
        self.beep()

    def start_microbreak(self, reason: str):
        # 60 Sekunden pausieren, Hinweis anzeigen
        self.microbreak_active = True
        self.microbreak_remaining = MICROBREAK_SEC
        self.info_label.setText(
            f"Bildschirmpause: {reason} ({MICROBREAK_SEC}s)"
            )
        self.beep()

    def end_microbreak(self):
        self.microbreak_active = False
        self.microbreak_remaining = 0
        self.info_label.setText("")

    def on_tick(self):
        if not self.running:
            return

        # Microbreak hat Priorität: Countdown pausiert
        if self.microbreak_active:
            self.microbreak_remaining -= 1
            if self.microbreak_remaining <= 0:
                self.end_microbreak()
            else:
                self.info_label.setText(
                    f"Bildschirmpause: noch {self.microbreak_remaining}s"
                    )
            return

        # Fokus/Break Countdown
        self.remaining -= 1

        # Reminder-Logik nur im Fokus
        if (self.mode == "focus" and self.remaining in REMIND_AT and
                self.remaining not in self.reminded_this_focus):
            self.reminded_this_focus.add(self.remaining)
            if self.remaining == 40 * 60:
                self.start_microbreak("20-20-20 Regel")
            elif self.remaining == 20 * 60:
                self.start_microbreak("kurz wegschauen")
            elif self.remaining == 0:
                # Ende Fokus: erst microbreak 60s, danach in Pause wechseln
                self.start_microbreak("Fokus beendet")
                # Markieren, dass nach Microbreak gewechselt wird:
                # Wir lassen remaining bei 0, Wechsel passiert sobald
                # microbreak endet.
            self.update_ui()
            return

        # Ende Phase
        if self.remaining <= 0:
            if self.mode == "focus":
                # Fokus fertig -> Einheit hochzählen und in Pause
                self.session_count += 1
                self.beep()
                self.switch_to_break()
            else:
                # Pause fertig -> wieder Fokus
                self.beep()
                self.switch_to_focus()

        self.update_ui()

    # ----------------- Dragging -----------------
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._dragging = True
            self._drag_offset = (event.globalPosition().toPoint() -
                                 self.frameGeometry().topLeft())
            event.accept()

    def mouseMoveEvent(self, event):
        if self._dragging:
            self.move(event.globalPosition().toPoint() - self._drag_offset)
            event.accept()

    def mouseReleaseEvent(self, event):
        self._dragging = False
        event.accept()


def main():
    app = QApplication(sys.argv)
    w = StudyClock()
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
