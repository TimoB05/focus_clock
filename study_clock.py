import sys

from PySide6.QtCore import QPoint, QSettings, Qt, QTimer
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QApplication, QDialog, QDialogButtonBox, QFormLayout, QHBoxLayout, QLabel,
    QPushButton, QSpinBox, QVBoxLayout, QWidget
    )
from PySide6.QtWidgets import QSystemTrayIcon, QMenu
from PySide6.QtGui import QIcon, QAction
from PySide6.QtMultimedia import QSoundEffect
from PySide6.QtCore import QUrl


# Reminder-Zeitpunkte im Fokus (verbleibende Sekunden)
DEFAULT_REMIND_AT = {40 * 60, 20 * 60, 0}


class SettingsDialog(QDialog):
    def __init__(self, parent, focus_min, break_min, micro_sec, goal,
                 start_unit):
        super().__init__(parent)
        self.start_units = QSpinBox()
        self.start_units.setRange(0, 50)
        self.start_units.setValue(start_unit)

        self.setWindowTitle("Settings")
        self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)

        self.focus = QSpinBox()
        self.focus.setRange(1, 300)
        self.focus.setValue(focus_min)

        self.brk = QSpinBox()
        self.brk.setRange(1, 120)
        self.brk.setValue(break_min)

        self.micro = QSpinBox()
        self.micro.setRange(10, 600)
        self.micro.setValue(micro_sec)

        self.goal = QSpinBox()
        self.goal.setRange(1, 50)
        self.goal.setValue(goal)

        form = QFormLayout()
        form.addRow("Fokus (Min)", self.focus)
        form.addRow("Pause (Min)", self.brk)
        form.addRow("Bildschirmpause (Sek)", self.micro)
        form.addRow("Ziel-Einheiten", self.goal)
        form.addRow("Start-Einheit", self.start_units)

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
            self.focus.value(), self.brk.value(), self.micro.value(),
            self.goal.value(), self.start_units.value()
            )


class StudyClock(QWidget):
    def __init__(self):
        super().__init__()

        self.qs = QSettings("StudyClock", "StudyClockApp")
        # Persistente Settings
        self.focus_min = int(self.qs.value("focus_min", 50))
        self.break_min = int(self.qs.value("break_min", 10))
        self.micro_sec = int(self.qs.value("micro_sec", 60))
        self.session_goal = int(self.qs.value("session_goal", 7))

        self.mode = self.qs.value("mode", "focus")
        self.remaining = int(
            self.qs.value(
                "remaining",
                self.focus_min * 60 if self.mode == "focus" else self.break_min * 60
                )
            )
        self.session_count = int(self.qs.value("session_count", 0))

        self.tray = QSystemTrayIcon(QIcon())
        menu = QMenu()

        restore_action = QAction("Öffnen")
        quit_action = QAction("Beenden")

        restore_action.triggered.connect(self.showNormal)
        quit_action.triggered.connect(QApplication.quit)

        menu.addAction(restore_action)
        menu.addAction(quit_action)

        self.tray.setContextMenu(menu)
        self.tray.show()

        self.tray.activated.connect(self.on_tray_activated)

        # State
        self.running = False

        # Microbreak (Bildschirmpause)
        self.microbreak_active = False
        self.microbreak_remaining = 0
        self.reminded_this_focus = set()
        self.REMIND_AT = set(DEFAULT_REMIND_AT)

        # Fenster: frameless + always-on-top + runde Ecken über Wrapper
        self.setWindowFlags(
            Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
            )
        self.setAttribute(Qt.WA_TranslucentBackground, True)

        # Wrapper (damit border-radius wirklich sauber ist)
        self.wrapper = QWidget(self)
        self.wrapper.setObjectName("wrapper")
        self.wrapper.setStyleSheet(
            """
                        QWidget#wrapper {
                            background: #111;
                            border: 1px solid #333;
                            border-radius: 14px;
                        }
                        QLabel { color: #eee; }
                        QPushButton {
                            background: transparent;
                            color: #eee;
                            border: none;
                            padding: 2px 6px;
                            border-radius: 6px;
                        }
                        QPushButton:hover { background: #222; }
                    """
            )

        # Mini-Titelleiste (Settings, Minimize, Close)
        self.btn_settings = QPushButton("⚙")
        self.btn_min = QPushButton("—")
        self.btn_close = QPushButton("×")
        self.btn_close.setStyleSheet("color: #ff6b6b;")

        top_row = QHBoxLayout()
        top_row.setContentsMargins(8, 6, 8, 0)
        top_row.setSpacing(4)
        top_row.addWidget(self.btn_settings)
        top_row.addStretch(1)
        top_row.addWidget(self.btn_min)
        top_row.addWidget(self.btn_close)

        # Timer Label
        self.timer_label = QLabel(self.format_time(self.remaining))
        self.timer_label.setFont(QFont("Segoe UI", 26, QFont.Bold))
        self.timer_label.setAlignment(Qt.AlignCenter)

        # Counter
        self.counter_label = QLabel(self.counter_text())
        self.counter_label.setFont(QFont("Segoe UI", 10))
        self.counter_label.setAlignment(Qt.AlignCenter)

        # Info Label (nur sichtbar wenn nötig)
        self.info_label = QLabel("")
        self.info_label.setFont(QFont("Segoe UI", 9))
        self.info_label.setAlignment(Qt.AlignCenter)
        self.info_label.setStyleSheet("color: #bbb;")
        self.info_label.hide()

        self.mode_label = QLabel("FOKUS")
        self.mode_label.setAlignment(Qt.AlignCenter)
        self.mode_label.setFont(QFont("Segoe UI", 9, QFont.Bold))
        self.mode_label.setStyleSheet("color: #888;")

        # Start/Pause/Reset minimal
        self.start_btn = QPushButton("Start")
        self.pause_btn = QPushButton("Pause")
        self.reset_btn = QPushButton("Reset")

        ctrl_row = QHBoxLayout()
        ctrl_row.setContentsMargins(10, 0, 10, 10)
        ctrl_row.setSpacing(8)
        for b in (self.start_btn, self.pause_btn, self.reset_btn):
            b.setStyleSheet(
                """
                                QPushButton {
                                    background: #1a1a1a; border: 1px solid 
                                    #2a2a2a;
                                    padding: 6px 10px; border-radius: 10px;
                                }
                                QPushButton:hover { background: #202020; }
                            """
                )
            ctrl_row.addWidget(b)

        # Wrapper Layout
        wrap_layout = QVBoxLayout(self.wrapper)
        wrap_layout.setContentsMargins(0, 0, 0, 0)
        wrap_layout.setSpacing(8)
        wrap_layout.addLayout(top_row)
        wrap_layout.addWidget(self.timer_label)
        wrap_layout.addWidget(self.counter_label)
        wrap_layout.addWidget(self.info_label)
        wrap_layout.addLayout(ctrl_row)
        wrap_layout.insertWidget(1, self.mode_label)

        # Tick Timer
        self.tick_timer = QTimer(self)
        self.tick_timer.setInterval(1000)
        self.tick_timer.timeout.connect(self.on_tick)

        # Signals
        self.start_btn.clicked.connect(self.start)
        self.pause_btn.clicked.connect(self.pause)
        self.reset_btn.clicked.connect(self.reset_all)

        self.btn_close.clicked.connect(QApplication.quit)
        self.btn_min.clicked.connect(self.hide)
        self.btn_settings.clicked.connect(self.open_settings)

        # Dragging (über gesamte Fläche)
        self._dragging = False
        self._drag_offset = QPoint(0, 0)

        self.resize(220, 220)
        self.update_layout_geometry()
        self.update_ui()

    def update_layout_geometry(self):
        # wrapper füllt das ganze Fenster (für runde Ecken)
        self.wrapper.setGeometry(0, 0, self.width(), self.height())

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.update_layout_geometry()

    # ----------------- Helpers -----------------
    def format_time(self, sec: int) -> str:
        m = sec // 60
        s = sec % 60
        return f"{m:02d}:{s:02d}"

    def counter_text(self) -> str:
        return f"Einheiten: {self.session_count}/{self.session_goal}"

    def set_info(self, text: str):
        if text:
            self.info_label.setText(text)
            self.info_label.show()
        else:
            self.info_label.setText("")
            self.info_label.hide()

    def update_ui(self):
        self.timer_label.setText(self.format_time(self.remaining))
        self.counter_label.setText(self.counter_text())

        self.mode_label.setText("FOKUS" if self.mode == "focus" else "PAUSE")

        # optional: leicht anderer Farbton je Mode (minimal, ohne Text)
        if self.mode == "focus":
            self.timer_label.setStyleSheet("color: #7CFC98;")
        else:
            self.timer_label.setStyleSheet("color: #7CC7FF;")

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
        self.set_info("")

    def reset_all(self):
        self.running = False
        self.tick_timer.stop()
        self.mode = "focus"
        self.remaining = self.focus_min * 60
        self.session_count = 0
        self.microbreak_active = False
        self.microbreak_remaining = 0
        self.reminded_this_focus.clear()
        self.set_info("")
        self.update_ui()

    # ----------------- Settings -----------------
    def open_settings(self):
        dlg = SettingsDialog(
            self, self.focus_min, self.break_min, self.micro_sec,
            self.session_goal, self.session_count
            )
        if dlg.exec() == QDialog.Accepted:
            (
                self.focus_min, self.break_min, self.micro_sec,
                self.session_goal, start_unit
                ) = dlg.values()

            self.session_count = int(start_unit)

            self.qs.setValue("focus_min", self.focus_min)
            self.qs.setValue("break_min", self.break_min)
            self.qs.setValue("micro_sec", self.micro_sec)
            self.qs.setValue("session_goal", self.session_goal)
            self.qs.setValue("session_count", self.session_count)

            # Wenn gerade nicht läuft: direkt auf neue Zeiten setzen
            if not self.running and not self.microbreak_active:
                self.remaining = (
                            self.focus_min * 60) if self.mode == "focus" else (
                            self.break_min * 60)

            self.update_ui()

    # ----------------- State machine -----------------
    def switch_to_break(self):
        self.mode = "break"
        self.remaining = self.break_min * 60
        self.set_info("Pause")
        self.beep()

    def switch_to_focus(self):
        self.mode = "focus"
        self.remaining = self.focus_min * 60
        self.reminded_this_focus.clear()
        self.set_info("")
        self.beep()

    def start_microbreak(self, reason: str):
        self.microbreak_active = True
        self.microbreak_remaining = self.micro_sec
        self.set_info(f"Bildschirmpause: {reason} ({self.micro_sec}s)")
        self.beep()

    def end_microbreak(self):
        self.microbreak_active = False
        self.microbreak_remaining = 0
        self.set_info("")

        # Falls Fokus bereits bei 0 war und wir nur wegen microbreak
        # pausiert haben:
        if self.mode == "focus" and self.remaining <= 0:
            self.session_count += 1
            self.switch_to_break()

    def on_tick(self):
        if not self.running:
            return

        # Microbreak hat Priorität
        if self.microbreak_active:
            self.microbreak_remaining -= 1
            if self.microbreak_remaining <= 0:
                self.end_microbreak()
            else:
                self.set_info(
                    f"Bildschirmpause: noch {self.microbreak_remaining}s"
                    )
            return

        # Normaler Countdown
        self.remaining -= 1

        # Reminder nur im Fokus
        if (self.mode == "focus" and self.remaining in self.REMIND_AT and
                self.remaining not in self.reminded_this_focus):
            self.reminded_this_focus.add(self.remaining)

            if self.remaining == 40 * 60:
                self.start_microbreak("20-20-20")
            elif self.remaining == 20 * 60:
                self.start_microbreak("kurz wegschauen")
            elif self.remaining == 0:
                # Erst microbreak, danach (in end_microbreak) -> Pause
                self.start_microbreak("Fokus beendet")

            self.update_ui()
            return

        # Ende Phase
        if self.remaining <= 0:
            if self.mode == "focus":
                self.session_count += 1
                self.switch_to_break()
            else:
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

    def on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.Trigger:  # Linksklick
            self.showNormal()
            self.raise_()
            self.activateWindow()

    def closeEvent(self, event):
        self.qs.setValue("mode", self.mode)
        self.qs.setValue("remaining", self.remaining)
        self.qs.setValue("session_count", self.session_count)
        event.accept()


def main():
    app = QApplication(sys.argv)
    w = StudyClock()
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
