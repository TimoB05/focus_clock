import sys

from PySide6.QtCore import QPoint, QSettings, QSize, Qt, QTimer
from PySide6.QtGui import QAction, QFont, QIcon
from PySide6.QtWidgets import (
    QApplication, QDialog, QDialogButtonBox, QFormLayout, QHBoxLayout, QLabel,
    QMenu, QPushButton, QSpinBox, QStyle, QSystemTrayIcon, QVBoxLayout, QWidget
    )
from PySide6.QtGui import QColor, QPainter, QPixmap


# Reminder-Zeitpunkte im Fokus (verbleibende Sekunden)
DEFAULT_REMIND_AT = {40 * 60, 20 * 60, 0}


class SettingsDialog(QDialog):
    def __init__(
        self, parent, focus_min, break_min, micro_sec, goal, start_unit
            ):
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
        self.micro.setRange(10, 600)
        self.micro.setValue(micro_sec)

        self.goal = QSpinBox()
        self.goal.setRange(1, 50)
        self.goal.setValue(goal)

        self.start_units = QSpinBox()
        self.start_units.setRange(0, 50)
        self.start_units.setValue(start_unit)

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
            self.focus.value(),
            self.brk.value(),
            self.micro.value(),
            self.goal.value(),
            self.start_units.value(),
            )


def format_time_mmss(sec: int) -> str:
    sec = max(0, int(sec))
    m = sec // 60
    s = sec % 60
    return f"{m:02d}:{s:02d}"


def format_hm(sec: int) -> str:
    # ohne Sekunden: H:MM (mit führender 0 bei Minuten)
    sec = max(0, int(sec))
    h = sec // 3600
    m = (sec % 3600) // 60
    return f"{h:d}:{m:02d}"


def beep():
    # Wenn du später eigenen Sound willst, hier austauschen
    QApplication.beep()


def tint_icon(icon: QIcon, size: int = 18, color: QColor = QColor("white")) -> QIcon:
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


class StudyClock(QWidget):
    def __init__(self):
        super().__init__()

        self.qs = QSettings("StudyClock", "StudyClockApp")

        # Persistente Settings
        self.focus_min = int(self.qs.value("focus_min", 50))
        self.break_min = int(self.qs.value("break_min", 10))
        self.micro_sec = int(self.qs.value("micro_sec", 60))
        self.session_goal = int(self.qs.value("session_goal", 7))

        # gespeicherter Laufzustand
        self.mode = self.qs.value("mode", "focus")
        self.remaining = int(
            self.qs.value(
                "remaining",
                self.focus_min * 60 if self.mode == "focus" else
                self.break_min * 60
                )
            )
        self.session_count = int(self.qs.value("session_count", 0))

        # Microbreak-State (optional persistiert)
        self.microbreak_active = bool(
            int(self.qs.value("microbreak_active", 0))
            )
        self.microbreak_remaining = int(
            self.qs.value("microbreak_remaining", 0)
            )

        # Tray
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

        # Lernzeit oben: 03:20/05:50 (57%)
        self.studytime_label = QLabel("")
        self.studytime_label.setFont(QFont("Segoe UI", 9))
        self.studytime_label.setAlignment(Qt.AlignCenter)
        self.studytime_label.setStyleSheet("color: #bbb;")

        # Status + Timer
        self.mode_label = QLabel("FOKUS")
        self.mode_label.setAlignment(Qt.AlignCenter)
        self.mode_label.setFont(QFont("Segoe UI", 9, QFont.Bold))
        self.mode_label.setStyleSheet("color: #888;")

        self.timer_label = QLabel(format_time_mmss(self.remaining))
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
        self.info_label.setWordWrap(True)
        self.info_label.hide()

        # Controls: Icons (einheitlich, gut sichtbar)
        self.play_pause_btn = QPushButton()
        self.play_pause_btn.setIcon(
            tint_icon(self.style().standardIcon(QStyle.SP_MediaPlay))
            )
        self.play_pause_btn.setIconSize(QSize(18, 18))
        self.play_pause_btn.setFixedSize(44, 32)
        self.play_pause_btn.setStyleSheet(
            """
            QPushButton {
                background: #262626;
                border: 1px solid #3a3a3a;
                border-radius: 10px;
            }
            QPushButton:hover { background: #2f2f2f; border: 1px solid #4a4a4a; }
        """
            )
        self.play_pause_btn.setToolTip("Start / Pause")

        self.rewind_btn = QPushButton()
        self.skip_btn = QPushButton()
        self.reset_btn = QPushButton()

        # Icons (Qt-Standard). Reset bewusst als "Reload" ODER alternativ
        # Text-Symbol, siehe unten.
        self.rewind_btn.setIcon(
            tint_icon(self.style().standardIcon(QStyle.SP_MediaSeekBackward))
            )
        self.skip_btn.setIcon(
            tint_icon(self.style().standardIcon(QStyle.SP_MediaSeekForward))
            )

        self.reset_btn.setText("⟲")
        self.reset_btn.setFont(QFont("Segoe UI", 12, QFont.Bold))

        for b in (
                self.play_pause_btn, self.rewind_btn, self.skip_btn,
                self.reset_btn
                ):
            b.setIconSize(QSize(18, 18))
            b.setFixedSize(44, 32)
            b.setStyleSheet(
                """
                QPushButton {
                    background: #262626;
                    border: 1px solid #3a3a3a;
                    border-radius: 10px;
                    color: white;              /* ← DAS ist der entscheidende Teil */
                }
                QPushButton:hover { background: #2f2f2f; border: 1px solid #4a4a4a; }
                QPushButton:pressed { background: #1f1f1f; }
            """
                )

        # Falls du Reset als Text-Symbol verwendest (Option 2), dann Schrift
        # einstellen:
        # self.reset_btn.setFont(QFont("Segoe UI", 12, QFont.Bold))

        # Tooltips
        self.rewind_btn.setToolTip("Zurück (Phase)")
        self.skip_btn.setToolTip("Vor (Phase)")
        self.reset_btn.setToolTip("Reset")

        ctrl_row = QHBoxLayout()
        ctrl_row.setContentsMargins(10, 4, 10, 14)
        ctrl_row.setSpacing(8)
        ctrl_row.addWidget(self.play_pause_btn)
        ctrl_row.addWidget(self.rewind_btn)
        ctrl_row.addWidget(self.skip_btn)
        ctrl_row.addWidget(self.reset_btn)

        # Wrapper Layout
        wrap_layout = QVBoxLayout(self.wrapper)
        wrap_layout.setContentsMargins(0, 0, 0, 0)
        wrap_layout.setSpacing(8)
        wrap_layout.addLayout(top_row)
        wrap_layout.addWidget(self.studytime_label)
        wrap_layout.addWidget(self.mode_label)
        wrap_layout.addWidget(self.timer_label)
        wrap_layout.addWidget(self.counter_label)
        wrap_layout.addWidget(self.info_label)
        wrap_layout.addLayout(ctrl_row)

        # Tick Timer
        self.tick_timer = QTimer(self)
        self.tick_timer.setInterval(1000)
        self.tick_timer.timeout.connect(self.on_tick)

        # Signals
        self.play_pause_btn.clicked.connect(self.toggle_play_pause)
        self.rewind_btn.clicked.connect(self.rewind_phase)
        self.skip_btn.clicked.connect(self.skip_phase)
        self.reset_btn.clicked.connect(self.reset_all)

        self.btn_close.clicked.connect(QApplication.quit)
        self.btn_min.clicked.connect(self.hide)
        self.btn_settings.clicked.connect(self.open_settings)

        # Dragging (über gesamte Fläche)
        self._dragging = False
        self._drag_offset = QPoint(0, 0)

        self.resize(260, 240)
        self.update_layout_geometry()
        self.update_ui()

        # Wenn beim Start bereits microbreak_active geladen wurde,
        # Info direkt setzen
        if self.microbreak_active:
            self.set_info(
                f"Bildschirmpause: noch {self.microbreak_remaining}s"
                )

    def update_layout_geometry(self):
        self.wrapper.setGeometry(0, 0, self.width(), self.height())

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.update_layout_geometry()

    # ----------------- Helpers -----------------

    def calc_focus_progress(self):
        focus_block = self.focus_min * 60
        total = self.session_goal * focus_block

        done = self.session_count * focus_block
        if self.mode == "focus":
            done += (focus_block - self.remaining)

        done = min(max(done, 0), total)
        left = total - done
        pct = 0
        if total > 0:
            pct = int(round((done / total) * 100))
        return done, left, total, pct

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
        self.timer_label.setText(format_time_mmss(self.remaining))
        self.counter_label.setText(self.counter_text())

        # Mode-Text / Farben
        if not self.running:
            self.mode_label.setText("PAUSIERT")
            self.mode_label.setStyleSheet("color: #ff6b6b;")
            self.timer_label.setStyleSheet("color: #ff6b6b;")
        else:
            self.mode_label.setText(
                "FOKUS" if self.mode == "focus" else "PAUSE"
                )
            self.mode_label.setStyleSheet("color: #888;")
            if self.mode == "focus":
                self.timer_label.setStyleSheet("color: #7CFC98;")
            else:
                self.timer_label.setStyleSheet("color: #7CC7FF;")

        done, left, total, pct = self.calc_focus_progress()
        self.studytime_label.setText(
            f"{format_hm(done)}/{format_hm(total)} ({pct}%)"
            )

    # ----------------- Control -----------------
    def start(self):
        if not self.running:
            self.running = True
            self.tick_timer.start()
            self.update_play_pause_icon()

            # passenden Infotext wiederherstellen
            if self.microbreak_active:
                self.set_info(
                    f"Bildschirmpause: noch {self.microbreak_remaining}s"
                    )
            else:
                self.set_info("")

            self.update_ui()

    def pause(self):
        self.running = False
        self.tick_timer.stop()
        self.update_play_pause_icon()

        # Info NICHT löschen, wenn Microbreak aktiv ist
        if self.microbreak_active:
            self.set_info(
                f"Bildschirmpause pausiert: noch {self.microbreak_remaining}s"
                )
        else:
            self.set_info("")

        self.update_ui()

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

    def skip_phase(self):
        # 1) Wenn Microbreak aktiv: sofort beenden (und ggf. Phase wechseln)
        if self.microbreak_active:
            self.end_microbreak()
            return

        # 2) Sonst: aktuelle Phase überspringen
        if self.mode == "focus":
            # Fokus sofort beenden: Einheit +1 und Pause starten
            self.session_count += 1
            self.switch_to_break()
        else:
            # Pause sofort beenden: Fokus starten
            self.switch_to_focus()

        self.update_ui()

    def rewind_phase(self):
        # Wenn Microbreak aktiv ist: Zurück = Microbreak abbrechen (zurück
        # in die Phase)
        if self.microbreak_active:
            self.microbreak_active = False
            self.microbreak_remaining = 0
            self.set_info("")
            self.update_ui()
            return

        # Von Pause zurück in Fokus (ohne Einheitenänderung)
        if self.mode == "break":
            self.mode = "focus"
            self.remaining = self.focus_min * 60
            self.set_info("")
            self.update_ui()
            return

        # Von Fokus zurück in Pause: Einheit zurücknehmen (wenn >0)
        if self.mode == "focus":
            if self.session_count > 0:
                self.session_count -= 1
            self.mode = "break"
            self.remaining = self.break_min * 60
            self.set_info("Pause")
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
        beep()

    def switch_to_focus(self):
        self.mode = "focus"
        self.remaining = self.focus_min * 60
        self.reminded_this_focus.clear()
        self.set_info("")
        beep()

    def start_microbreak(self, reason: str):
        self.microbreak_active = True
        self.microbreak_remaining = self.micro_sec
        self.set_info(f"Bildschirmpause: {reason} ({self.micro_sec}s)")
        beep()

    def end_microbreak(self):
        self.microbreak_active = False
        self.microbreak_remaining = 0
        self.set_info("")

        # Wenn Microbreak beim Fokus-Ende gestartet wurde:
        if self.mode == "focus" and self.remaining <= 0:
            self.session_count += 1
            self.switch_to_break()

        self.update_ui()

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
                self.update_ui()
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

    # ----------------- Tray / Window -----------------
    def on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.Trigger:  # Linksklick
            self.showNormal()
            self.raise_()
            self.activateWindow()

    def closeEvent(self, event):
        self.qs.setValue("mode", self.mode)
        self.qs.setValue("remaining", self.remaining)
        self.qs.setValue("session_count", self.session_count)
        self.qs.setValue("microbreak_active", int(self.microbreak_active))
        self.qs.setValue(
            "microbreak_remaining", int(self.microbreak_remaining)
            )
        event.accept()

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

    def toggle_play_pause(self):
        if self.running:
            self.pause()
        else:
            self.start()

        self.update_play_pause_icon()

    def update_play_pause_icon(self):
        if self.running:
            icon = self.style().standardIcon(QStyle.SP_MediaPause)
        else:
            icon = self.style().standardIcon(QStyle.SP_MediaPlay)

        self.play_pause_btn.setIcon(tint_icon(icon))


def main():
    app = QApplication(sys.argv)
    w = StudyClock()
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
