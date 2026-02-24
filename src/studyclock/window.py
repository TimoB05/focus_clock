from __future__ import annotations
import sys

from PySide6.QtCore import QPoint, QSettings, QSize, Qt, QTimer, QEvent
from PySide6.QtGui import QAction, QFont, QIcon, QPalette, QColor
from PySide6.QtWidgets import (
    QApplication, QDialog, QHBoxLayout, QLabel, QMenu, QPushButton, QStyle,
    QSystemTrayIcon, QVBoxLayout, QWidget
    )

from .logic import ClockState, StudyClockLogic
from .settings_dialog import SettingsDialog
from .stats_dialog import \
    StatsDialog
from .util import beep, format_hm, format_time_mmss, tint_icon


class StudyClockWindow(QWidget):
    def __init__(self):
        super().__init__()
        self._ui_ready = False
        self._icon_color = QColor("#eee")  # Default bis apply_theme läuft

        flags = Qt.Window | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint

        if sys.platform == "darwin":
            flags |= Qt.Window
        else:
            flags |= Qt.Tool

        self.setWindowFlags(flags)

        # ---------- Settings store ----------
        self.qs = QSettings("StudyClock", "StudyClockApp")

        # ---------- Load persistent config ----------
        focus_min = int(self.qs.value("focus_min", 50))
        break_min = int(self.qs.value("break_min", 10))
        micro_sec = int(self.qs.value("micro_sec", 60))
        goal = int(self.qs.value("session_goal", 7))

        # ---------- Load runtime state ----------
        mode = self.qs.value("mode", "focus")
        remaining = int(
            self.qs.value(
                "remaining",
                focus_min * 60 if mode == "focus" else break_min * 60
                )
            )

        completed_units = int(self.qs.value("completed_units", 0))
        microbreak_active = bool(int(self.qs.value("microbreak_active", 0)))
        microbreak_remaining = int(self.qs.value("microbreak_remaining", 0))
        after_micro = self.qs.value("after_micro", "")
        finished = bool(int(self.qs.value("finished", 0)))

        total_open_sec = int(self.qs.value("total_open_sec", 0))
        paused_sec = int(self.qs.value("paused_sec", 0))
        microbreak_sec = int(self.qs.value("microbreak_sec", 0))
        focus_work_sec = int(self.qs.value("focus_work_sec", 0))

        # ---------- Build state + logic ----------
        state = ClockState(
            focus_min=focus_min,
            break_min=break_min,
            micro_sec=micro_sec,
            session_goal=goal,
            mode=mode,
            remaining=remaining,
            completed_units=completed_units,
            microbreak_active=microbreak_active,
            microbreak_remaining=microbreak_remaining,
            after_micro=after_micro,
            finished=finished,
            running=False,  # start paused
            total_open_sec=total_open_sec,
            paused_sec=paused_sec,
            microbreak_sec=microbreak_sec,
            focus_work_sec=focus_work_sec,
            )

        self.logic = StudyClockLogic(
            state=state, on_change=self.update_ui, on_beep=beep
            )

        # ---------- Window flags / style ----------
        self.setAttribute(Qt.WA_TranslucentBackground, True)

        self.wrapper = QWidget(self)
        self.wrapper.setObjectName("wrapper")

        # ---------- Tray ----------
        self.tray = QSystemTrayIcon(QIcon())
        menu = QMenu()

        restore_action = QAction("Open")
        quit_action = QAction("End")
        restore_action.triggered.connect(self.showNormal)
        quit_action.triggered.connect(QApplication.quit)

        menu.addAction(restore_action)
        menu.addAction(quit_action)

        self.tray.setContextMenu(menu)
        self.tray.show()
        self.tray.activated.connect(self.on_tray_activated)

        # ---------- Title bar ----------
        self.btn_settings = QPushButton("⚙")
        self.btn_stats = QPushButton("📊")
        self.btn_lunch = QPushButton("L")
        self.btn_lunch.setToolTip("Lunch Break (60 Min)")

        self.btn_min = QPushButton("—")
        self.btn_close = QPushButton("×")
        self.btn_close.setStyleSheet("color: #ff6b6b;")

        top_row = QHBoxLayout()
        top_row.setContentsMargins(8, 6, 8, 0)
        top_row.setSpacing(4)
        top_row.addWidget(self.btn_settings)
        top_row.addWidget(self.btn_stats)
        top_row.addWidget(self.btn_lunch)
        top_row.addStretch(1)
        top_row.addWidget(self.btn_min)
        top_row.addWidget(self.btn_close)

        # ---------- Labels ----------
        self.studytime_label = QLabel("")
        self.studytime_label.setFont(QFont("Segoe UI", 9))
        self.studytime_label.setAlignment(Qt.AlignCenter)
        self.studytime_label.setStyleSheet("color: #bbb;")

        self.mode_label = QLabel("")
        self.mode_label.setAlignment(Qt.AlignCenter)
        self.mode_label.setFont(QFont("Segoe UI", 9, QFont.Bold))
        self.mode_label.setStyleSheet("color: #888;")

        self.timer_label = QLabel("")
        self.timer_label.setFont(QFont("Segoe UI", 26, QFont.Bold))
        self.timer_label.setAlignment(Qt.AlignCenter)

        self.counter_label = QLabel("")
        self.counter_label.setFont(QFont("Segoe UI", 10))
        self.counter_label.setAlignment(Qt.AlignCenter)

        # (Info label remains optional, but invisible by default)
        self.info_label = QLabel("")
        self.info_label.setFont(QFont("Segoe UI", 9))
        self.info_label.setAlignment(Qt.AlignCenter)
        self.info_label.setStyleSheet("color: #bbb;")
        self.info_label.hide()

        # ---------- Controls ----------
        self.play_pause_btn = QPushButton()
        self.rewind_btn = QPushButton()
        self.skip_btn = QPushButton()
        self.reset_btn = QPushButton()

        self.play_pause_btn.setIcon(
            tint_icon(self.style().standardIcon(QStyle.SP_MediaPlay), color=self._icon_color)
            )
        self.rewind_btn.setIcon(
            tint_icon(self.style().standardIcon(QStyle.SP_MediaSeekBackward), color=self._icon_color)
            )
        self.skip_btn.setIcon(
            tint_icon(self.style().standardIcon(QStyle.SP_MediaSeekForward), color=self._icon_color)
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
                                    color: white;
                                }
                                QPushButton:hover { background: #2f2f2f; 
                                border: 1px solid #4a4a4a; }
                                QPushButton:pressed { background: #1f1f1f; }
                            """
                )

        self.play_pause_btn.setToolTip("Start / Pause")
        self.rewind_btn.setToolTip("Back (Phase)")
        self.skip_btn.setToolTip("Skip (Phase)")
        self.reset_btn.setToolTip("Reset")

        ctrl_row = QHBoxLayout()
        ctrl_row.setContentsMargins(10, 4, 10, 14)
        ctrl_row.setSpacing(8)
        ctrl_row.addWidget(self.play_pause_btn)
        ctrl_row.addWidget(self.rewind_btn)
        ctrl_row.addWidget(self.skip_btn)
        ctrl_row.addWidget(self.reset_btn)

        # ---------- Wrapper layout ----------
        wrap_layout = QVBoxLayout(self.wrapper)
        wrap_layout.setContentsMargins(0, 0, 0, 0)
        wrap_layout.setSpacing(6)
        wrap_layout.addLayout(top_row)
        wrap_layout.addWidget(self.studytime_label)
        wrap_layout.addWidget(self.mode_label)
        wrap_layout.addWidget(self.timer_label)
        wrap_layout.addWidget(self.counter_label)
        wrap_layout.addWidget(self.info_label)
        wrap_layout.addLayout(ctrl_row)

        # ---------- Timers ----------
        self.tick_timer = QTimer(self)
        self.tick_timer.setInterval(1000)
        self.tick_timer.timeout.connect(self.logic.on_tick)

        self.pause_count_timer = QTimer(self)
        self.pause_count_timer.setInterval(1000)
        self.pause_count_timer.timeout.connect(self.logic.on_pause_count_tick)
        self.pause_count_timer.start()

        # ---------- Signals ----------
        self.btn_close.clicked.connect(QApplication.quit)
        self.btn_min.clicked.connect(self.showMinimized)
        self.btn_settings.clicked.connect(self.open_settings)
        self.btn_stats.clicked.connect(self.open_stats)
        self.btn_lunch.clicked.connect(self.on_lunch)

        self.play_pause_btn.clicked.connect(self.on_toggle_play_pause)
        self.rewind_btn.clicked.connect(self.logic.rewind_phase)
        self.skip_btn.clicked.connect(self.logic.skip_phase)
        self.reset_btn.clicked.connect(self.on_reset)

        # ---------- Dragging ----------
        self._dragging = False
        self._drag_offset = QPoint(0, 0)

        # Size
        self.resize(200, 200)
        self.update_layout_geometry()

        # initial UI
        self._ui_ready = True
        self.apply_theme()
        self.update_ui()

    # ---------- Geometry ----------
    def update_layout_geometry(self):
        self.wrapper.setGeometry(0, 0, self.width(), self.height())

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.update_layout_geometry()

    # ---------- UI update ----------
    def update_ui(self):
        s = self.logic.s

        # progress
        done, left, total, pct = self.logic.calc_focus_progress()
        self.studytime_label.setText(
            f"{format_hm(done)}/{format_hm(total)} ({pct}%)"
            )
        self.counter_label.setText(
            f"Unit: {self.logic.current_unit()}/{s.session_goal}"
            )

        # finished
        if s.finished:
            self.mode_label.setText("Finished")
            self.mode_label.setStyleSheet("color: #7CFC98;")
            self.timer_label.setText("Finished")
            self.timer_label.setStyleSheet("color: #7CFC98;")
            self.play_pause_btn.setIcon(
                tint_icon(self.style().standardIcon(QStyle.SP_MediaPlay), color=self._icon_color)
                )
            if self.tick_timer.isActive():
                self.tick_timer.stop()
            return

        # microbreak display (optional)
        if s.microbreak_active:
            self.mode_label.setText("SCREEN BREAK")
            # Basisfarbe nicht hart setzen (kommt aus apply_theme),
            # nur die Timer-Farbe bleibt "warm".
            self.timer_label.setText(
                format_time_mmss(max(1, s.microbreak_remaining))
                )
            self.timer_label.setStyleSheet("color: #FFD27C;")

            if s.running:
                self.play_pause_btn.setIcon(
                    tint_icon(
                        self.style().standardIcon(QStyle.SP_MediaPause),
                        color=self._icon_color
                        )
                    )
                if not self.tick_timer.isActive():
                    self.tick_timer.start()
            else:
                self.play_pause_btn.setIcon(
                    tint_icon(
                        self.style().standardIcon(QStyle.SP_MediaPlay),
                        color=self._icon_color
                        )
                    )
                if self.tick_timer.isActive():
                    self.tick_timer.stop()

            return

        # timer text
        self.timer_label.setText(format_time_mmss(s.remaining))

        # running visuals
        if not s.running:
            self.mode_label.setText("PAUSED")
            self.mode_label.setStyleSheet("color: #ff6b6b;")
            self.timer_label.setStyleSheet("color: #ff6b6b;")
            self.play_pause_btn.setIcon(
                tint_icon(self.style().standardIcon(QStyle.SP_MediaPlay), color=self._icon_color)
                )
            if self.tick_timer.isActive():
                self.tick_timer.stop()
        else:
            if s.mode == "focus":
                self.mode_label.setText("FOCUS")
                self.timer_label.setStyleSheet("color: #7CFC98;")
            elif s.mode == "break":
                self.mode_label.setText("PAUSE")
                self.timer_label.setStyleSheet("color: #7CC7FF;")
            else:
                self.mode_label.setText("LUNCH")
                self.timer_label.setStyleSheet("color: #7CC7FF;")

            self.mode_label.setStyleSheet("color: #888;")
            self.play_pause_btn.setIcon(
                tint_icon(self.style().standardIcon(QStyle.SP_MediaPause), color=self._icon_color)
                )
            if not self.tick_timer.isActive():
                self.tick_timer.start()

    def changeEvent(self, event):
        super().changeEvent(event)
        if not getattr(self, "_ui_ready", False):
            return

        t = event.type()
        if t in (
                QEvent.Type.PaletteChange, QEvent.Type.ApplicationPaletteChange
        ):
            self.apply_theme()
            self.update_ui()
            return

        if hasattr(
                QEvent.Type, "ThemeChange"
                ) and t == QEvent.Type.ThemeChange:
            self.apply_theme()
            self.update_ui()

    def apply_theme(self):
        app = QApplication.instance()
        pal = app.palette()
        bg = pal.color(QPalette.Window)
        dark = bg.lightness() < 128

        if dark:
            muted = "#bbb"
            subtle = "#888"
            wrapper_css = """
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
            ctrl_css = """
                QPushButton {
                    background: #262626;
                    border: 1px solid #3a3a3a;
                    border-radius: 10px;
                    color: #eee;
                }
                QPushButton:hover { background: #2f2f2f; border: 1px solid #4a4a4a; }
                QPushButton:pressed { background: #1f1f1f; }
            """
            icon_color = QColor("#eee")

        else:
            muted = "#444"
            subtle = "#666"
            wrapper_css = """
                QWidget#wrapper {
                    background: #f5f5f5;
                    border: 1px solid #cfcfcf;
                    border-radius: 14px;
                }
                QLabel { color: #111; }
                QPushButton {
                    background: transparent;
                    color: #111;
                    border: none;
                    padding: 2px 6px;
                    border-radius: 6px;
                }
                QPushButton:hover { background: #e9e9e9; }
            """
            ctrl_css = """
                QPushButton {
                    background: #ffffff;
                    border: 1px solid #cfcfcf;
                    border-radius: 10px;
                    color: #111;
                }
                QPushButton:hover { background: #f0f0f0; border: 1px solid #bdbdbd; }
                QPushButton:pressed { background: #e2e2e2; }
            """
            icon_color = QColor("#111")

        self._icon_color = icon_color

        self.wrapper.setStyleSheet(wrapper_css)

        self.studytime_label.setStyleSheet(f"color: {muted};")
        self.mode_label.setStyleSheet(f"color: {subtle};")
        self.info_label.setStyleSheet(f"color: {muted};")

        for b in (
                self.play_pause_btn, self.rewind_btn, self.skip_btn,
                self.reset_btn
        ):
            b.setStyleSheet(ctrl_css)

        # Standard-Icons passend einfärben
        self.rewind_btn.setIcon(
            tint_icon(
                self.style().standardIcon(QStyle.SP_MediaSeekBackward),
                color=self._icon_color
                )
            )
        self.skip_btn.setIcon(
            tint_icon(
                self.style().standardIcon(QStyle.SP_MediaSeekForward),
                color=self._icon_color
                )
            )

    def showEvent(self, event):
        super().showEvent(event)
        if not getattr(self, "_ui_ready", False):
            return
        self.apply_theme()
        self.update_ui()

    # ---------- Button handlers ----------
    def on_toggle_play_pause(self):
        self.logic.toggle_play_pause()
        # update_ui is already called via on_change, but it's okay here.
        # redundant:
        self.update_ui()

    def on_reset(self):
        self.logic.reset_all()
        self.update_ui()

    def on_lunch(self):
        self.logic.start_lunch_break()
        self.update_ui()

    # ---------- Dialogs ----------
    def open_settings(self):
        s = self.logic.s
        dlg = SettingsDialog(
            self,
            s.focus_min,
            s.break_min,
            s.micro_sec,
            s.session_goal,
            self.logic.current_unit(),
            )
        if dlg.exec() == QDialog.Accepted:
            focus_min, break_min, micro_sec, goal, start_unit = dlg.values()
            self.logic.apply_settings(
                focus_min, break_min, micro_sec, goal, start_unit
                )

            # persist config immediately
            self.qs.setValue("focus_min", self.logic.s.focus_min)
            self.qs.setValue("break_min", self.logic.s.break_min)
            self.qs.setValue("micro_sec", self.logic.s.micro_sec)
            self.qs.setValue("session_goal", self.logic.s.session_goal)
            self.qs.setValue("start_unit", int(start_unit))

            self.update_ui()

    def open_stats(self):
        s = self.logic.s
        dlg = StatsDialog(
            self,
            focus_work_sec=s.focus_work_sec,
            paused_sec=s.paused_sec,
            microbreak_sec=s.microbreak_sec,
            total_open_sec=s.total_open_sec,
            )
        dlg.exec()

    # ---------- Tray ----------
    def on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.Trigger:
            self.showNormal()
            self.raise_()
            self.activateWindow()

    # ---------- Close: persist state ----------
    def closeEvent(self, event):
        s = self.logic.s
        self.qs.setValue("mode", s.mode)
        self.qs.setValue("remaining", s.remaining)
        self.qs.setValue("completed_units", s.completed_units)
        self.qs.setValue("finished", int(s.finished))

        self.qs.setValue("microbreak_active", int(s.microbreak_active))
        self.qs.setValue("microbreak_remaining", s.microbreak_remaining)
        self.qs.setValue("after_micro", s.after_micro)

        self.qs.setValue("total_open_sec", s.total_open_sec)
        self.qs.setValue("paused_sec", s.paused_sec)
        self.qs.setValue("microbreak_sec", s.microbreak_sec)
        self.qs.setValue("focus_work_sec", s.focus_work_sec)

        event.accept()

    # ---------- Dragging ----------
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
