#!/usr/bin/env python3
"""
Weekly Task Monitor - PySide6 (Ultimate with Monthly & Yearly Views)
======================================================================
A feature‑rich task manager with weekly, monthly, and yearly views.

Features:
- Weekly view: Monday–Sunday grid with per‑day task lists
- Monthly view: Weeks of the month as summary cards
- Yearly view: Months of the year as summary cards
- Add, edit, delete, duplicate tasks
- Mark tasks complete (with recurring task generation)
- Tags (colored labels) and drag‑and‑drop reordering
- Week navigation (previous/next/today)
- Dark/light theme toggle (dark by default, remembers choice)
- Status bar with task statistics
- Global search bar (weekly view only)
- Export current week to CSV
- Desktop reminders for upcoming tasks
- Compact/expanded view modes
- Add a task to all days of the week with one click
- Missed tasks tracking
- Weekly report (total, completed, missed, pending, productivity)
- Week comparison (compare any two weeks)
- Persistent SQLite database (handles schema upgrades)
"""

import sys
import sqlite3
import csv
from datetime import datetime, timedelta
from typing import Optional, List, Tuple, Dict
from contextlib import closing

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QGridLayout, QPushButton, QLabel, QListWidget, QListWidgetItem,
    QCheckBox, QDialog, QFormLayout, QLineEdit, QTextEdit,
    QDateEdit, QTimeEdit, QComboBox, QMessageBox, QAbstractItemView,
    QFrame, QToolBar, QSizePolicy, QStatusBar, QFileDialog,
    QSystemTrayIcon, QMenu, QLineEdit as QSearchLine,
    QGroupBox, QGridLayout as QGridLayout2, QDialogButtonBox,
    QScrollArea
)
from PySide6.QtCore import Qt, QDate, QTime, Signal, Slot, QSize, QSettings, QTimer
from PySide6.QtGui import QFont, QAction, QActionGroup, QKeySequence, QPalette, QColor, QIcon

# ----------------------------------------------------------------------
# Database setup with schema upgrades
# ----------------------------------------------------------------------
DB_NAME = "tasks.db"

def init_db():
    """Create or upgrade the tasks table to include all required columns."""
    try:
        with sqlite3.connect(DB_NAME) as conn:
            cursor = conn.cursor()

            # Create table with minimal columns first (if not exists)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    description TEXT,
                    due_date DATE NOT NULL,
                    due_time TEXT,
                    completed BOOLEAN DEFAULT 0,
                    priority INTEGER DEFAULT 0,
                    created TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Check existing columns
            cursor.execute("PRAGMA table_info(tasks)")
            existing_columns = [col[1] for col in cursor.fetchall()]

            # Columns to add (with their SQL definitions)
            new_columns = [
                ("recurrence", "TEXT DEFAULT 'none'"),
                ("tags", "TEXT DEFAULT ''"),
                ("order_index", "INTEGER DEFAULT 0")
            ]

            for col_name, col_def in new_columns:
                if col_name not in existing_columns:
                    try:
                        cursor.execute(f"ALTER TABLE tasks ADD COLUMN {col_name} {col_def}")
                    except sqlite3.OperationalError:
                        # Column might already exist due to race condition; ignore
                        pass

            conn.commit()
    except sqlite3.Error as e:
        QMessageBox.critical(None, "Database Error", f"Cannot initialize database:\n{e}")
        sys.exit(1)

# ----------------------------------------------------------------------
# Helper to generate tag colors (simple hash)
# ----------------------------------------------------------------------
def tag_color(tag: str) -> str:
    """Return a CSS color string based on tag name."""
    colors = ["#e6194b", "#3cb44b", "#ffe119", "#4363d8", "#f58231",
              "#911eb4", "#46f0f0", "#f032e6", "#bcf60c", "#fabebe"]
    return colors[hash(tag) % len(colors)]

# ----------------------------------------------------------------------
# Task item widget (displayed inside each day's list)
# ----------------------------------------------------------------------
class TaskItemWidget(QWidget):
    """A task row with checkbox, title, time, and tag labels."""

    toggled = Signal(int, bool)      # task_id, completed
    double_clicked = Signal(int)      # task_id

    def __init__(self, task_id: int, title: str, due_time: Optional[str],
                 completed: bool, tags: str, parent=None):
        super().__init__(parent)
        self.task_id = task_id
        self.completed = completed
        self.tags = [t.strip() for t in tags.split(',') if t.strip()]

        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(8)

        self.checkbox = QCheckBox()
        self.checkbox.setChecked(completed)
        self.checkbox.stateChanged.connect(self._on_toggled)

        # Title and tags in a vertical layout
        text_layout = QVBoxLayout()
        text_layout.setSpacing(2)

        self.title_label = QLabel(title)
        self.title_label.setWordWrap(True)
        text_layout.addWidget(self.title_label)

        if self.tags:
            tag_widget = QWidget()
            tag_layout = QHBoxLayout(tag_widget)
            tag_layout.setContentsMargins(0, 0, 0, 0)
            tag_layout.setSpacing(4)
            for tag in self.tags:
                lbl = QLabel(tag)
                lbl.setStyleSheet(f"background-color: {tag_color(tag)}; color: white; "
                                  f"padding: 2px 6px; border-radius: 8px; font-size: 8pt;")
                tag_layout.addWidget(lbl)
            tag_layout.addStretch()
            text_layout.addWidget(tag_widget)

        layout.addWidget(self.checkbox)
        layout.addLayout(text_layout, 1)

        if due_time:
            self.time_label = QLabel(due_time)
            self.time_label.setObjectName("taskTime")
            layout.addWidget(self.time_label)

        self._update_style()
        self.setAttribute(Qt.WA_StyledBackground, True)

    def _update_style(self):
        """Apply strikeout and correct text color based on completion state."""
        font = self.title_label.font()
        font.setStrikeOut(self.completed)
        self.title_label.setFont(font)

        pal = self.title_label.palette()
        if self.completed:
            color = pal.color(QPalette.Disabled, QPalette.WindowText)
        else:
            color = pal.color(QPalette.Active, QPalette.WindowText)
        self.title_label.setStyleSheet(f"color: {color.name()};")

        if hasattr(self, 'time_label'):
            mid_color = pal.color(QPalette.Mid)
            self.time_label.setStyleSheet(f"color: {mid_color.name()}; font-size: 0.9em;")

    def _on_toggled(self, state):
        self.completed = (state == Qt.Checked)
        self._update_style()
        self.toggled.emit(self.task_id, self.completed)

    def mouseDoubleClickEvent(self, event):
        self.double_clicked.emit(self.task_id)
        super().mouseDoubleClickEvent(event)

# ----------------------------------------------------------------------
# Add/Edit Task Dialog
# ----------------------------------------------------------------------
class TaskDialog(QDialog):
    """Dialog for creating or editing a task."""

    def __init__(self, parent=None, task_data: Optional[Tuple] = None):
        """
        task_data: (id, title, description, due_date, due_time, completed,
                    priority, recurrence, tags)
        """
        super().__init__(parent)
        self.setWindowTitle("Add Task" if task_data is None else "Edit Task")
        self.setModal(True)
        self.resize(450, 450)
        self.setMinimumSize(400, 400)

        self.task_id = task_data[0] if task_data else None

        layout = QVBoxLayout(self)
        form = QFormLayout()
        form.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)

        # Title
        self.title_edit = QLineEdit()
        if task_data:
            self.title_edit.setText(task_data[1])
        form.addRow("Title:", self.title_edit)

        # Description
        self.desc_edit = QTextEdit()
        self.desc_edit.setMaximumHeight(80)
        self.desc_edit.setPlaceholderText("Optional description...")
        if task_data:
            self.desc_edit.setPlainText(task_data[2] or "")
        form.addRow("Description:", self.desc_edit)

        # Date
        self.date_edit = QDateEdit()
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDate(QDate.currentDate())
        if task_data:
            self.date_edit.setDate(QDate.fromString(task_data[3], "yyyy-MM-dd"))
        form.addRow("Date:", self.date_edit)

        # Time
        self.time_edit = QTimeEdit()
        self.time_edit.setSpecialValueText("--")
        self.time_edit.setTime(QTime(9, 0))
        if task_data and task_data[4]:
            qtime = QTime.fromString(task_data[4], "hh:mm")
            if qtime.isValid():
                self.time_edit.setTime(qtime)
        form.addRow("Time (optional):", self.time_edit)

        # Priority
        self.priority_combo = QComboBox()
        self.priority_combo.addItems(["Low", "Normal", "High"])
        if task_data:
            self.priority_combo.setCurrentIndex(task_data[6])
        form.addRow("Priority:", self.priority_combo)

        # Recurrence
        self.recurrence_combo = QComboBox()
        self.recurrence_combo.addItems(["none", "daily", "weekly", "monthly", "yearly"])
        if task_data:
            idx = self.recurrence_combo.findText(task_data[7])
            if idx >= 0:
                self.recurrence_combo.setCurrentIndex(idx)
        form.addRow("Recurrence:", self.recurrence_combo)

        # Tags
        self.tags_edit = QLineEdit()
        self.tags_edit.setPlaceholderText("Comma‑separated tags")
        if task_data:
            self.tags_edit.setText(task_data[8])
        form.addRow("Tags:", self.tags_edit)

        # Completed checkbox
        self.completed_check = QCheckBox("Completed")
        if task_data:
            self.completed_check.setChecked(task_data[5] == 1)
        form.addRow(self.completed_check)

        # Add to all days checkbox (only for new tasks, not edit)
        self.add_all_check = QCheckBox("Add to all days of this week")
        if task_data is None:
            form.addRow(self.add_all_check)

        layout.addLayout(form)

        # Buttons
        btn_layout = QHBoxLayout()
        self.save_btn = QPushButton("Save")
        self.save_btn.clicked.connect(self.accept)
        self.save_btn.setDefault(True)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addStretch()
        btn_layout.addWidget(self.save_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)

    def get_data(self):
        """
        Return tuple (title, desc, due_date, due_time, completed, priority,
                      recurrence, tags) and a boolean indicating whether
                      "add to all days" was checked.
        Returns (None, False) if validation fails.
        """
        title = self.title_edit.text().strip()
        if not title:
            QMessageBox.warning(self, "Validation", "Task title cannot be empty.")
            return None, False

        desc = self.desc_edit.toPlainText().strip()
        due_date = self.date_edit.date().toString("yyyy-MM-dd")
        qtime = self.time_edit.time()
        due_time = qtime.toString("hh:mm") if (qtime.isValid() and
                     self.time_edit.specialValueText() != qtime.toString()) else None
        completed = 1 if self.completed_check.isChecked() else 0
        priority = self.priority_combo.currentIndex()
        recurrence = self.recurrence_combo.currentText()
        tags = self.tags_edit.text().strip()
        add_all = self.add_all_check.isChecked() if hasattr(self, 'add_all_check') else False
        return (title, desc, due_date, due_time, completed, priority, recurrence, tags), add_all

# ----------------------------------------------------------------------
# Weekly Report Dialog
# ----------------------------------------------------------------------
class WeeklyReportDialog(QDialog):
    """Shows statistics for a selected week."""

    def __init__(self, parent=None, week_start: QDate = None):
        super().__init__(parent)
        self.setWindowTitle("Weekly Report")
        self.setMinimumSize(400, 300)
        self.week_start = week_start if week_start else QDate.currentDate()

        layout = QVBoxLayout(self)

        # Week selector
        selector_layout = QHBoxLayout()
        selector_layout.addWidget(QLabel("Week starting:"))
        self.week_edit = QDateEdit()
        self.week_edit.setDate(self.week_start)
        self.week_edit.setCalendarPopup(True)
        self.week_edit.dateChanged.connect(self._update_report)
        selector_layout.addWidget(self.week_edit)
        selector_layout.addStretch()
        layout.addLayout(selector_layout)

        # Stats display
        self.stats_group = QGroupBox("Statistics")
        stats_layout = QGridLayout2(self.stats_group)

        self.total_label = QLabel()
        stats_layout.addWidget(QLabel("Total tasks:"), 0, 0)
        stats_layout.addWidget(self.total_label, 0, 1)

        self.completed_label = QLabel()
        stats_layout.addWidget(QLabel("Completed:"), 1, 0)
        stats_layout.addWidget(self.completed_label, 1, 1)

        self.missed_label = QLabel()
        stats_layout.addWidget(QLabel("Missed:"), 2, 0)
        stats_layout.addWidget(self.missed_label, 2, 1)

        self.pending_label = QLabel()
        stats_layout.addWidget(QLabel("Pending (future):"), 3, 0)
        stats_layout.addWidget(self.pending_label, 3, 1)

        self.productivity_label = QLabel()
        stats_layout.addWidget(QLabel("Productivity:"), 4, 0)
        stats_layout.addWidget(self.productivity_label, 4, 1)

        layout.addWidget(self.stats_group)

        # Close button
        button_box = QDialogButtonBox(QDialogButtonBox.Ok)
        button_box.accepted.connect(self.accept)
        layout.addWidget(button_box)

        self._update_report()

    def _update_report(self):
        """Fetch and display stats for the selected week."""
        week_start = self.week_edit.date()
        week_end = week_start.addDays(6)
        today = QDate.currentDate()

        try:
            with sqlite3.connect(DB_NAME) as conn:
                cursor = conn.cursor()
                # All tasks in the week
                cursor.execute("""
                    SELECT completed, due_date FROM tasks
                    WHERE due_date BETWEEN ? AND ?
                """, (week_start.toString("yyyy-MM-dd"), week_end.toString("yyyy-MM-dd")))
                rows = cursor.fetchall()

            total = len(rows)
            completed = sum(1 for r in rows if r[0] == 1)
            missed = 0
            pending = 0
            for comp, due_str in rows:
                if comp == 0:
                    due_date = QDate.fromString(due_str, "yyyy-MM-dd")
                    if due_date < today:
                        missed += 1
                    else:
                        pending += 1

            self.total_label.setText(str(total))
            self.completed_label.setText(str(completed))
            self.missed_label.setText(str(missed))
            self.pending_label.setText(str(pending))
            if total > 0:
                productivity = (completed / total) * 100
                self.productivity_label.setText(f"{productivity:.1f}%")
            else:
                self.productivity_label.setText("N/A")

        except sqlite3.Error as e:
            QMessageBox.critical(self, "Database Error", f"Failed to fetch stats:\n{e}")

# ----------------------------------------------------------------------
# Compare Weeks Dialog
# ----------------------------------------------------------------------
class CompareWeeksDialog(QDialog):
    """Compares statistics between two weeks."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Compare Weeks")
        self.setMinimumSize(500, 350)

        layout = QVBoxLayout(self)

        # Week selectors
        selector_layout = QHBoxLayout()
        selector_layout.addWidget(QLabel("Week 1:"))
        self.week1_edit = QDateEdit()
        self.week1_edit.setDate(QDate.currentDate())
        self.week1_edit.setCalendarPopup(True)
        self.week1_edit.dateChanged.connect(self._update_comparison)
        selector_layout.addWidget(self.week1_edit)

        selector_layout.addSpacing(20)

        selector_layout.addWidget(QLabel("Week 2:"))
        self.week2_edit = QDateEdit()
        self.week2_edit.setDate(QDate.currentDate().addDays(-7))
        self.week2_edit.setCalendarPopup(True)
        self.week2_edit.dateChanged.connect(self._update_comparison)
        selector_layout.addWidget(self.week2_edit)

        selector_layout.addStretch()
        layout.addLayout(selector_layout)

        # Comparison table
        self.comp_group = QGroupBox("Comparison")
        comp_layout = QGridLayout2(self.comp_group)

        # Headers
        comp_layout.addWidget(QLabel(""), 0, 0)
        comp_layout.addWidget(QLabel("Week 1"), 0, 1)
        comp_layout.addWidget(QLabel("Week 2"), 0, 2)

        # Rows
        self.total1 = QLabel(); self.total2 = QLabel()
        comp_layout.addWidget(QLabel("Total tasks:"), 1, 0)
        comp_layout.addWidget(self.total1, 1, 1)
        comp_layout.addWidget(self.total2, 1, 2)

        self.completed1 = QLabel(); self.completed2 = QLabel()
        comp_layout.addWidget(QLabel("Completed:"), 2, 0)
        comp_layout.addWidget(self.completed1, 2, 1)
        comp_layout.addWidget(self.completed2, 2, 2)

        self.missed1 = QLabel(); self.missed2 = QLabel()
        comp_layout.addWidget(QLabel("Missed:"), 3, 0)
        comp_layout.addWidget(self.missed1, 3, 1)
        comp_layout.addWidget(self.missed2, 3, 2)

        self.pending1 = QLabel(); self.pending2 = QLabel()
        comp_layout.addWidget(QLabel("Pending (future):"), 4, 0)
        comp_layout.addWidget(self.pending1, 4, 1)
        comp_layout.addWidget(self.pending2, 4, 2)

        self.productivity1 = QLabel(); self.productivity2 = QLabel()
        comp_layout.addWidget(QLabel("Productivity:"), 5, 0)
        comp_layout.addWidget(self.productivity1, 5, 1)
        comp_layout.addWidget(self.productivity2, 5, 2)

        layout.addWidget(self.comp_group)

        # Close button
        button_box = QDialogButtonBox(QDialogButtonBox.Ok)
        button_box.accepted.connect(self.accept)
        layout.addWidget(button_box)

        self._update_comparison()

    def _get_week_stats(self, week_start: QDate) -> Tuple[int, int, int, int]:
        """Return (total, completed, missed, pending) for the week."""
        week_end = week_start.addDays(6)
        today = QDate.currentDate()

        try:
            with sqlite3.connect(DB_NAME) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT completed, due_date FROM tasks
                    WHERE due_date BETWEEN ? AND ?
                """, (week_start.toString("yyyy-MM-dd"), week_end.toString("yyyy-MM-dd")))
                rows = cursor.fetchall()

            total = len(rows)
            completed = sum(1 for r in rows if r[0] == 1)
            missed = 0
            pending = 0
            for comp, due_str in rows:
                if comp == 0:
                    due_date = QDate.fromString(due_str, "yyyy-MM-dd")
                    if due_date < today:
                        missed += 1
                    else:
                        pending += 1
            return total, completed, missed, pending
        except sqlite3.Error as e:
            QMessageBox.critical(self, "Database Error", f"Failed to fetch stats:\n{e}")
            return 0, 0, 0, 0

    def _update_comparison(self):
        week1 = self.week1_edit.date()
        week2 = self.week2_edit.date()

        t1, c1, m1, p1 = self._get_week_stats(week1)
        t2, c2, m2, p2 = self._get_week_stats(week2)

        self.total1.setText(str(t1))
        self.total2.setText(str(t2))
        self.completed1.setText(str(c1))
        self.completed2.setText(str(c2))
        self.missed1.setText(str(m1))
        self.missed2.setText(str(m2))
        self.pending1.setText(str(p1))
        self.pending2.setText(str(p2))

        prod1 = (c1 / t1 * 100) if t1 > 0 else 0
        prod2 = (c2 / t2 * 100) if t2 > 0 else 0
        self.productivity1.setText(f"{prod1:.1f}%")
        self.productivity2.setText(f"{prod2:.1f}%")

# ----------------------------------------------------------------------
# Main Window
# ----------------------------------------------------------------------
class WeeklyTaskMonitor(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Weekly Task Monitor")
        self.setMinimumSize(1200, 750)

        # Database
        init_db()

        # Settings
        self.settings = QSettings("YourCompany", "WeeklyTaskMonitor")
        self.dark_mode = self.settings.value("darkMode", True, type=bool)
        self.compact_mode = self.settings.value("compactMode", False, type=bool)

        # View mode: "weekly", "monthly", "yearly"
        self.view_mode = "weekly"
        self.current_date = QDate.currentDate()  # For monthly/yearly views

        # Apply theme before creating widgets
        self._apply_theme(self.dark_mode)

        # Central widget
        central = QWidget()
        self.setCentralWidget(central)
        self.main_layout = QVBoxLayout(central)
        self.main_layout.setContentsMargins(10, 10, 10, 10)

        # Toolbar
        self._create_toolbar()

        # Search bar (hidden initially, shown only in weekly view)
        self.search_layout = QHBoxLayout()
        self.search_layout.addWidget(QLabel("🔍 Search:"))
        self.search_edit = QSearchLine()
        self.search_edit.setPlaceholderText("Filter tasks by title, description, or tags...")
        self.search_edit.textChanged.connect(self._refresh_view)
        self.search_layout.addWidget(self.search_edit)
        self.main_layout.addLayout(self.search_layout)

        # Navigation bar
        self.nav_layout = QHBoxLayout()
        self.prev_btn = QPushButton("◀ Previous")
        self.prev_btn.clicked.connect(self._navigate_prev)
        self.next_btn = QPushButton("Next ▶")
        self.next_btn.clicked.connect(self._navigate_next)
        self.today_btn = QPushButton("📅 Today")
        self.today_btn.clicked.connect(self._navigate_today)
        self.view_label = QLabel()
        self.view_label.setAlignment(Qt.AlignCenter)
        self.view_label.setStyleSheet("font-weight: bold; font-size: 14px;")

        self.nav_layout.addWidget(self.prev_btn)
        self.nav_layout.addWidget(self.view_label, 1)
        self.nav_layout.addWidget(self.next_btn)
        self.nav_layout.addWidget(self.today_btn)
        self.main_layout.addLayout(self.nav_layout)

        # Container for the current view (weekly grid, monthly cards, etc.)
        self.view_container = QWidget()
        self.view_layout = QVBoxLayout(self.view_container)
        self.view_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.addWidget(self.view_container)

        # Status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_label = QLabel()
        self.status_bar.addWidget(self.status_label)

        # Tray icon for notifications
        self._setup_tray()

        # Notification timer (every 60 seconds)
        self.notification_timer = QTimer(self)
        self.notification_timer.timeout.connect(self._check_reminders)
        self.notification_timer.start(60000)  # 60 seconds
        self._last_notified = set()  # avoid repeating same task

        # Initial display
        self._show_weekly_view()

        # Keyboard shortcuts
        self._setup_shortcuts()

    # ------------------------------------------------------------------
    # View switching
    # ------------------------------------------------------------------
    def _show_weekly_view(self):
        """Switch to weekly view."""
        self.view_mode = "weekly"
        self.weekly_action.setChecked(True)
        self.current_week_start = self._get_monday_of_week(QDate.currentDate())
        self._update_view()

    def _show_monthly_view(self):
        """Switch to monthly view."""
        self.view_mode = "monthly"
        self.monthly_action.setChecked(True)
        self.current_month = QDate.currentDate()
        self._update_view()

    def _show_yearly_view(self):
        """Switch to yearly view."""
        self.view_mode = "yearly"
        self.yearly_action.setChecked(True)
        self.current_year = QDate.currentDate()
        self._update_view()

    def _update_view(self):
        """Rebuild the current view based on view_mode."""
        # Clear container
        for i in reversed(range(self.view_layout.count())):
            widget = self.view_layout.itemAt(i).widget()
            if widget:
                widget.deleteLater()

        # Show/hide search bar
        search_widget = self.search_layout.itemAt(1).widget()
        if self.view_mode == "weekly":
            search_widget.show()
            self._build_weekly_view()
        else:
            search_widget.hide()
            if self.view_mode == "monthly":
                self._build_monthly_view()
            elif self.view_mode == "yearly":
                self._build_yearly_view()

    def _build_weekly_view(self):
        """Create the weekly grid (original view)."""
        # Days grid
        self.days_grid = QGridLayout()
        self.days_grid.setSpacing(12)
        for col in range(7):
            self.days_grid.setColumnStretch(col, 1)
        self.view_layout.addLayout(self.days_grid)

        # Create day panels
        self.day_panels = []  # list of (header_label, date_label, list_widget)
        day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        for col, day_name in enumerate(day_names):
            panel = QFrame()
            panel.setFrameShape(QFrame.StyledPanel)
            panel.setObjectName("dayPanel")
            vbox = QVBoxLayout(panel)
            vbox.setContentsMargins(5, 5, 5, 5)

            header = QLabel(day_name)
            header.setAlignment(Qt.AlignCenter)
            header.setObjectName("dayHeader")
            vbox.addWidget(header)

            date_label = QLabel()
            date_label.setAlignment(Qt.AlignCenter)
            date_label.setObjectName("dayDate")
            vbox.addWidget(date_label)

            task_list = QListWidget()
            task_list.setSelectionMode(QAbstractItemView.SingleSelection)
            task_list.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
            task_list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            task_list.setMinimumHeight(250)
            task_list.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            # Enable drag‑drop for reordering
            task_list.setDragDropMode(QAbstractItemView.InternalMove)
            task_list.model().rowsMoved.connect(self._on_rows_moved)
            vbox.addWidget(task_list)

            self.days_grid.addWidget(panel, 0, col)
            self.day_panels.append((header, date_label, task_list))

        self._update_week_display()

    def _build_monthly_view(self):
        """Create monthly view: cards for each week in the month."""
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        container = QWidget()
        layout = QVBoxLayout(container)

        # Get all weeks in the month
        weeks = self._get_weeks_in_month(self.current_month)
        for week_start in weeks:
            week_end = week_start.addDays(6)
            stats = self._get_week_stats(week_start)
            card = self._create_week_card(week_start, week_end, stats)
            layout.addWidget(card)

        layout.addStretch()
        scroll.setWidget(container)
        self.view_layout.addWidget(scroll)

        # Update navigation label
        self.view_label.setText(self.current_month.toString("MMMM yyyy"))

    def _build_yearly_view(self):
        """Create yearly view: cards for each month in the year."""
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        container = QWidget()
        layout = QGridLayout(container)  # Use grid for months
        layout.setHorizontalSpacing(20)
        layout.setVerticalSpacing(20)

        year = self.current_year.year()
        for month in range(1, 13):
            month_date = QDate(year, month, 1)
            stats = self._get_month_stats(month_date)
            card = self._create_month_card(month_date, stats)
            row = (month - 1) // 3
            col = (month - 1) % 3
            layout.addWidget(card, row, col)

        scroll.setWidget(container)
        self.view_layout.addWidget(scroll)

        # Update navigation label
        self.view_label.setText(str(year))

    def _get_weeks_in_month(self, date: QDate) -> List[QDate]:
        """Return list of Monday start dates for all weeks that intersect the month."""
        first_day = QDate(date.year(), date.month(), 1)
        # Find the Monday of the week containing the first day
        start = self._get_monday_of_week(first_day)
        weeks = []
        while start.month() == date.month() or start.addDays(6).month() == date.month():
            weeks.append(start)
            start = start.addDays(7)
            if start.year() > date.year() or (start.year() == date.year() and start.month() > date.month()):
                break
        return weeks

    def _get_week_stats(self, week_start: QDate) -> Tuple[int, int, int]:
        """Return (total, completed, missed) for the week."""
        week_end = week_start.addDays(6)
        today = QDate.currentDate()
        try:
            with sqlite3.connect(DB_NAME) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT completed, due_date FROM tasks
                    WHERE due_date BETWEEN ? AND ?
                """, (week_start.toString("yyyy-MM-dd"), week_end.toString("yyyy-MM-dd")))
                rows = cursor.fetchall()
            total = len(rows)
            completed = sum(1 for r in rows if r[0] == 1)
            missed = 0
            for comp, due_str in rows:
                if comp == 0:
                    due_date = QDate.fromString(due_str, "yyyy-MM-dd")
                    if due_date < today:
                        missed += 1
            return total, completed, missed
        except sqlite3.Error:
            return 0, 0, 0

    def _get_month_stats(self, month_date: QDate) -> Tuple[int, int, int]:
        """Return (total, completed, missed) for the month."""
        first = QDate(month_date.year(), month_date.month(), 1)
        last = first.addMonths(1).addDays(-1)
        today = QDate.currentDate()
        try:
            with sqlite3.connect(DB_NAME) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT completed, due_date FROM tasks
                    WHERE due_date BETWEEN ? AND ?
                """, (first.toString("yyyy-MM-dd"), last.toString("yyyy-MM-dd")))
                rows = cursor.fetchall()
            total = len(rows)
            completed = sum(1 for r in rows if r[0] == 1)
            missed = 0
            for comp, due_str in rows:
                if comp == 0:
                    due_date = QDate.fromString(due_str, "yyyy-MM-dd")
                    if due_date < today:
                        missed += 1
            return total, completed, missed
        except sqlite3.Error:
            return 0, 0, 0

    def _create_week_card(self, week_start: QDate, week_end: QDate, stats: Tuple[int, int, int]) -> QFrame:
        """Create a clickable card for a week."""
        total, completed, missed = stats
        card = QFrame()
        card.setFrameShape(QFrame.StyledPanel)
        card.setObjectName("card")
        card.setCursor(Qt.PointingHandCursor)
        card.setMinimumHeight(80)

        layout = QVBoxLayout(card)
        layout.addWidget(QLabel(f"Week of {week_start.toString('MMM d')} – {week_end.toString('MMM d')}"))
        layout.addWidget(QLabel(f"Total: {total}  Completed: {completed}  Missed: {missed}"))

        # Store week start in card for double-click
        card.week_start = week_start
        card.mouseDoubleClickEvent = lambda e: self._jump_to_week(week_start)
        return card

    def _create_month_card(self, month_date: QDate, stats: Tuple[int, int, int]) -> QFrame:
        """Create a clickable card for a month."""
        total, completed, missed = stats
        card = QFrame()
        card.setFrameShape(QFrame.StyledPanel)
        card.setObjectName("card")
        card.setCursor(Qt.PointingHandCursor)
        card.setMinimumHeight(100)

        layout = QVBoxLayout(card)
        layout.addWidget(QLabel(month_date.toString("MMMM yyyy")))
        layout.addWidget(QLabel(f"Total: {total}  Completed: {completed}  Missed: {missed}"))

        card.month_date = month_date
        card.mouseDoubleClickEvent = lambda e: self._jump_to_month(month_date)
        return card

    def _jump_to_week(self, week_start: QDate):
        """Switch to weekly view and show the given week."""
        self.view_mode = "weekly"
        self.weekly_action.setChecked(True)
        self.current_week_start = week_start
        self._update_view()
        self._update_week_display()

    def _jump_to_month(self, month_date: QDate):
        """Switch to monthly view and show the given month."""
        self.view_mode = "monthly"
        self.monthly_action.setChecked(True)
        self.current_month = month_date
        self._update_view()

    # ------------------------------------------------------------------
    # Navigation for monthly/yearly views
    # ------------------------------------------------------------------
    def _navigate_prev(self):
        if self.view_mode == "weekly":
            self._prev_week()
        elif self.view_mode == "monthly":
            self.current_month = self.current_month.addMonths(-1)
            self._update_view()
        elif self.view_mode == "yearly":
            self.current_year = self.current_year.addYears(-1)
            self._update_view()

    def _navigate_next(self):
        if self.view_mode == "weekly":
            self._next_week()
        elif self.view_mode == "monthly":
            self.current_month = self.current_month.addMonths(1)
            self._update_view()
        elif self.view_mode == "yearly":
            self.current_year = self.current_year.addYears(1)
            self._update_view()

    def _navigate_today(self):
        if self.view_mode == "weekly":
            self.current_week_start = self._get_monday_of_week(QDate.currentDate())
            self._update_week_display()
        elif self.view_mode == "monthly":
            self.current_month = QDate.currentDate()
            self._update_view()
        elif self.view_mode == "yearly":
            self.current_year = QDate.currentDate()
            self._update_view()

    # ------------------------------------------------------------------
    # Original weekly view methods (unchanged)
    # ------------------------------------------------------------------
    def _get_monday_of_week(self, qdate: QDate) -> QDate:
        day_of_week = qdate.dayOfWeek()
        return qdate.addDays(-(day_of_week - 1))

    def _update_week_display(self):
        start = self.current_week_start
        end = start.addDays(6)
        self.view_label.setText(f"Week of {start.toString('MMM d')} – {end.toString('MMM d, yyyy')}")

        current = start
        for i in range(7):
            _, date_label, _ = self.day_panels[i]
            date_label.setText(current.toString("dddd, MMM d"))
            current = current.addDays(1)

        self._refresh_view()

    def _refresh_view(self):
        """Reload tasks with optional search filter and update status bar."""
        if self.view_mode != "weekly":
            return
        total_tasks = 0
        completed_tasks = 0
        search_text = self.search_edit.text().strip()

        for i in range(7):
            day_date = self.current_week_start.addDays(i)
            day_str = day_date.toString("yyyy-MM-dd")
            tasks = self._get_tasks_for_date(day_str, search_text)
            self._populate_day_list(i, tasks)
            total_tasks += len(tasks)
            completed_tasks += sum(1 for t in tasks if t[5])  # t[5] is completed

        self.status_label.setText(f"Week total: {total_tasks} tasks  |  Completed: {completed_tasks}")

    def _get_tasks_for_date(self, date_str: str, search: str = "") -> List[Tuple]:
        """Return tasks for date, filtered by search, ordered by order_index."""
        try:
            with sqlite3.connect(DB_NAME) as conn:
                cursor = conn.cursor()
                query = """
                    SELECT id, title, description, due_date, due_time, completed,
                           priority, recurrence, tags
                    FROM tasks
                    WHERE due_date = ?
                """
                params = [date_str]
                if search:
                    query += """ AND (title LIKE ? OR description LIKE ? OR tags LIKE ?) """
                    like = f"%{search}%"
                    params.extend([like, like, like])
                query += " ORDER BY order_index ASC"
                cursor.execute(query, params)
                return cursor.fetchall()
        except sqlite3.Error as e:
            QMessageBox.critical(self, "Database Error", f"Failed to fetch tasks:\n{e}")
            return []

    def _populate_day_list(self, day_index: int, tasks: List[Tuple]):
        """Fill the QListWidget with TaskItemWidgets."""
        _, _, task_list = self.day_panels[day_index]
        task_list.clear()

        for task in tasks:
            task_id, title, _, _, due_time, completed, _, _, tags = task
            item = QListWidgetItem(task_list)

            widget = TaskItemWidget(task_id, title, due_time, bool(completed), tags)
            widget.toggled.connect(self._on_task_toggled)
            widget.double_clicked.connect(self._edit_task_by_id)

            task_list.addItem(item)
            task_list.setItemWidget(item, widget)

            # Adjust size based on compact mode
            base_height = 40 if self.compact_mode else 60
            item.setSizeHint(QSize(200, base_height + (20 if tags else 0)))

    def _on_rows_moved(self, parent, start, end, dest, row):
        """Update order_index in database after a drop."""
        # Find which day list was moved
        for day_index, (_, _, task_list) in enumerate(self.day_panels):
            if task_list.model() == parent.model():
                break
        else:
            return

        # Collect all task IDs in the new order
        task_ids = []
        for i in range(task_list.count()):
            item = task_list.item(i)
            widget = task_list.itemWidget(item)
            if widget:
                task_ids.append(widget.task_id)

        # Update order_index in DB
        try:
            with sqlite3.connect(DB_NAME) as conn:
                cursor = conn.cursor()
                for idx, task_id in enumerate(task_ids):
                    cursor.execute("UPDATE tasks SET order_index = ? WHERE id = ?", (idx, task_id))
                conn.commit()
        except sqlite3.Error as e:
            QMessageBox.critical(self, "Database Error", f"Failed to save order:\n{e}")

    # ------------------------------------------------------------------
    # Task operations (unchanged)
    # ------------------------------------------------------------------
    @Slot(int, bool)
    def _on_task_toggled(self, task_id: int, completed: bool):
        """Update completed status and generate next recurrence if needed."""
        try:
            with sqlite3.connect(DB_NAME) as conn:
                cursor = conn.cursor()
                cursor.execute("UPDATE tasks SET completed = ? WHERE id = ?",
                               (1 if completed else 0, task_id))
                if completed:
                    # Fetch recurrence info
                    cursor.execute("SELECT due_date, recurrence FROM tasks WHERE id = ?", (task_id,))
                    row = cursor.fetchone()
                    if row and row[1] != 'none':
                        old_date = QDate.fromString(row[0], "yyyy-MM-dd")
                        recur = row[1]
                        new_date = None
                        if recur == "daily":
                            new_date = old_date.addDays(1)
                        elif recur == "weekly":
                            new_date = old_date.addDays(7)
                        elif recur == "monthly":
                            new_date = old_date.addMonths(1)
                        elif recur == "yearly":
                            new_date = old_date.addYears(1)
                        if new_date:
                            # Insert a new task with same details but new date and not completed
                            cursor.execute("""
                                INSERT INTO tasks
                                (title, description, due_date, due_time, priority, recurrence, tags)
                                SELECT title, description, ?, due_time, priority, recurrence, tags
                                FROM tasks WHERE id = ?
                            """, (new_date.toString("yyyy-MM-dd"), task_id))
                conn.commit()
        except sqlite3.Error as e:
            QMessageBox.critical(self, "Database Error", f"Failed to update task:\n{e}")

        self._refresh_view()

    def _add_task(self):
        dlg = TaskDialog(self)
        if dlg.exec() == QDialog.Accepted:
            data, add_all = dlg.get_data()
            if data is None:
                return

            try:
                with sqlite3.connect(DB_NAME) as conn:
                    cursor = conn.cursor()
                    if add_all:
                        # Add task to every day of the current week
                        for i in range(7):
                            day_date = self.current_week_start.addDays(i)
                            day_str = day_date.toString("yyyy-MM-dd")
                            # Get next order_index for this day
                            cursor.execute("SELECT COALESCE(MAX(order_index), -1) FROM tasks WHERE due_date = ?", (day_str,))
                            max_order = cursor.fetchone()[0]
                            new_order = max_order + 1
                            cursor.execute("""
                                INSERT INTO tasks
                                (title, description, due_date, due_time, completed, priority, recurrence, tags, order_index)
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """, (data[0], data[1], day_str, data[3], data[4], data[5], data[6], data[7], new_order))
                    else:
                        # Single task
                        day_str = data[2]  # due_date from dialog
                        cursor.execute("SELECT COALESCE(MAX(order_index), -1) FROM tasks WHERE due_date = ?", (day_str,))
                        max_order = cursor.fetchone()[0]
                        new_order = max_order + 1
                        cursor.execute("""
                            INSERT INTO tasks
                            (title, description, due_date, due_time, completed, priority, recurrence, tags, order_index)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, (*data, new_order))
                    conn.commit()
                self._refresh_view()
            except sqlite3.Error as e:
                QMessageBox.critical(self, "Database Error", f"Failed to add task:\n{e}")

    def _edit_task_by_id(self, task_id: int):
        try:
            with sqlite3.connect(DB_NAME) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT id, title, description, due_date, due_time, completed,
                           priority, recurrence, tags
                    FROM tasks WHERE id = ?
                """, (task_id,))
                row = cursor.fetchone()
        except sqlite3.Error as e:
            QMessageBox.critical(self, "Database Error", f"Failed to fetch task:\n{e}")
            return

        if not row:
            return

        dlg = TaskDialog(self, row)
        # Hide the "add to all days" checkbox for edit
        if hasattr(dlg, 'add_all_check'):
            dlg.add_all_check.hide()
        if dlg.exec() == QDialog.Accepted:
            data, _ = dlg.get_data()  # add_all is ignored for edit
            if data is None:
                return
            try:
                with sqlite3.connect(DB_NAME) as conn:
                    cursor = conn.cursor()
                    cursor.execute("""
                        UPDATE tasks
                        SET title=?, description=?, due_date=?, due_time=?,
                            completed=?, priority=?, recurrence=?, tags=?
                        WHERE id = ?
                    """, (*data, task_id))
                    conn.commit()
                self._refresh_view()
            except sqlite3.Error as e:
                QMessageBox.critical(self, "Database Error", f"Failed to update task:\n{e}")

    def _delete_task(self):
        for _, _, task_list in self.day_panels:
            selected = task_list.selectedItems()
            if selected:
                item = selected[0]
                widget = task_list.itemWidget(item)
                if widget and hasattr(widget, 'task_id'):
                    task_id = widget.task_id
                    reply = QMessageBox.question(
                        self, "Confirm Delete",
                        "Are you sure you want to delete this task?",
                        QMessageBox.Yes | QMessageBox.No
                    )
                    if reply == QMessageBox.Yes:
                        try:
                            with sqlite3.connect(DB_NAME) as conn:
                                cursor = conn.cursor()
                                cursor.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
                                conn.commit()
                            self._refresh_view()
                        except sqlite3.Error as e:
                            QMessageBox.critical(self, "Database Error", f"Failed to delete task:\n{e}")
                    return
        QMessageBox.information(self, "No Selection", "Please select a task to delete.")

    def _clear_completed(self):
        dates = [self.current_week_start.addDays(i).toString("yyyy-MM-dd") for i in range(7)]
        placeholders = ','.join(['?'] * len(dates))
        try:
            with sqlite3.connect(DB_NAME) as conn:
                cursor = conn.cursor()
                cursor.execute(f"""
                    DELETE FROM tasks
                    WHERE due_date IN ({placeholders}) AND completed = 1
                """, dates)
                deleted = cursor.rowcount
                conn.commit()
            if deleted > 0:
                QMessageBox.information(self, "Completed", f"Removed {deleted} completed task(s).")
                self._refresh_view()
            else:
                QMessageBox.information(self, "Info", "No completed tasks to clear.")
        except sqlite3.Error as e:
            QMessageBox.critical(self, "Database Error", f"Failed to clear completed tasks:\n{e}")

    def _export_csv(self):
        """Export current week's tasks to CSV."""
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Export to CSV", "weekly_tasks.csv", "CSV Files (*.csv)")
        if not file_path:
            return

        try:
            with sqlite3.connect(DB_NAME) as conn:
                cursor = conn.cursor()
                start = self.current_week_start.toString("yyyy-MM-dd")
                end = self.current_week_start.addDays(6).toString("yyyy-MM-dd")
                cursor.execute("""
                    SELECT due_date, title, description, due_time,
                           CASE priority WHEN 0 THEN 'Low' WHEN 1 THEN 'Normal' ELSE 'High' END,
                           tags, completed
                    FROM tasks
                    WHERE due_date BETWEEN ? AND ?
                    ORDER BY due_date, order_index
                """, (start, end))
                rows = cursor.fetchall()

            with open(file_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(["Date", "Title", "Description", "Time", "Priority", "Tags", "Completed"])
                writer.writerows(rows)

            QMessageBox.information(self, "Export Successful", f"Tasks exported to {file_path}")
        except Exception as e:
            QMessageBox.critical(self, "Export Failed", f"Error: {e}")

    # ------------------------------------------------------------------
    # Week navigation (original)
    # ------------------------------------------------------------------
    def _prev_week(self):
        self.current_week_start = self.current_week_start.addDays(-7)
        self._update_week_display()

    def _next_week(self):
        self.current_week_start = self.current_week_start.addDays(7)
        self._update_week_display()

    # ------------------------------------------------------------------
    # Tray icon & notifications (unchanged)
    # ------------------------------------------------------------------
    def _setup_tray(self):
        self.tray_icon = QSystemTrayIcon(self)
        # Use a simple icon (you can replace with a real .png)
        icon = QIcon.fromTheme("calendar")
        if icon.isNull():
            # Fallback: create a pixmap (not shown here for brevity)
            pass
        self.tray_icon.setIcon(icon)
        self.tray_icon.setVisible(True)

        tray_menu = QMenu()
        show_action = tray_menu.addAction("Show Window")
        show_action.triggered.connect(self.showNormal)
        quit_action = tray_menu.addAction("Quit")
        quit_action.triggered.connect(QApplication.quit)
        self.tray_icon.setContextMenu(tray_menu)

    def _check_reminders(self):
        """Show tray notifications for tasks due in the next hour."""
        now = datetime.now()
        now_str = now.strftime("%Y-%m-%d")
        current_time = now.time()
        # Calculate end of next hour
        later = now + timedelta(hours=1)
        later_str = later.strftime("%Y-%m-%d")
        later_time = later.time()

        try:
            with sqlite3.connect(DB_NAME) as conn:
                cursor = conn.cursor()
                # Tasks due today or tomorrow if time within next hour crossing midnight
                if now_str == later_str:
                    # Same day
                    cursor.execute("""
                        SELECT id, title, due_time FROM tasks
                        WHERE due_date = ? AND due_time IS NOT NULL
                          AND completed = 0
                          AND time(due_time) BETWEEN time(?) AND time(?)
                    """, (now_str, current_time.strftime("%H:%M"), later_time.strftime("%H:%M")))
                else:
                    # Crossing midnight: tasks due today from now to midnight,
                    # and tasks due tomorrow from midnight to later_time
                    cursor.execute("""
                        SELECT id, title, due_time FROM tasks
                        WHERE (due_date = ? AND due_time IS NOT NULL
                               AND time(due_time) >= time(?))
                           OR (due_date = ? AND due_time IS NOT NULL
                               AND time(due_time) <= time(?))
                          AND completed = 0
                    """, (now_str, current_time.strftime("%H:%M"),
                          later_str, later_time.strftime("%H:%M")))

                rows = cursor.fetchall()
                for task_id, title, due_time in rows:
                    if task_id not in self._last_notified:
                        self.tray_icon.showMessage(
                            "Task Reminder",
                            f"'{title}' is due at {due_time}",
                            QSystemTrayIcon.Information,
                            5000
                        )
                        self._last_notified.add(task_id)
        except sqlite3.Error:
            pass

    # ------------------------------------------------------------------
    # Shortcuts
    # ------------------------------------------------------------------
    def _setup_shortcuts(self):
        # New task
        new_shortcut = QAction(self)
        new_shortcut.setShortcut(QKeySequence("Ctrl+N"))
        new_shortcut.triggered.connect(self._add_task)
        self.addAction(new_shortcut)

        # Delete selected
        delete_shortcut = QAction(self)
        delete_shortcut.setShortcut(QKeySequence("Delete"))
        delete_shortcut.triggered.connect(self._delete_task)
        self.addAction(delete_shortcut)

        # Previous (week/month/year)
        prev_shortcut = QAction(self)
        prev_shortcut.setShortcut(QKeySequence("Ctrl+Left"))
        prev_shortcut.triggered.connect(self._navigate_prev)
        self.addAction(prev_shortcut)

        # Next
        next_shortcut = QAction(self)
        next_shortcut.setShortcut(QKeySequence("Ctrl+Right"))
        next_shortcut.triggered.connect(self._navigate_next)
        self.addAction(next_shortcut)

        # Today
        today_shortcut = QAction(self)
        today_shortcut.setShortcut(QKeySequence("Ctrl+T"))
        today_shortcut.triggered.connect(self._navigate_today)
        self.addAction(today_shortcut)

        # Search
        search_shortcut = QAction(self)
        search_shortcut.setShortcut(QKeySequence("Ctrl+F"))
        search_shortcut.triggered.connect(lambda: self.search_edit.setFocus())
        self.addAction(search_shortcut)

    # ------------------------------------------------------------------
    # Toolbar
    # ------------------------------------------------------------------
    def _create_toolbar(self):
        toolbar = QToolBar("Main")
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        # View mode actions (mutually exclusive)
        self.view_action_group = QActionGroup(self)
        self.view_action_group.setExclusive(True)

        self.weekly_action = QAction("📅 Week", self)
        self.weekly_action.setCheckable(True)
        self.weekly_action.setChecked(True)
        self.weekly_action.triggered.connect(self._show_weekly_view)
        self.view_action_group.addAction(self.weekly_action)
        toolbar.addAction(self.weekly_action)

        self.monthly_action = QAction("📆 Month", self)
        self.monthly_action.setCheckable(True)
        self.monthly_action.triggered.connect(self._show_monthly_view)
        self.view_action_group.addAction(self.monthly_action)
        toolbar.addAction(self.monthly_action)

        self.yearly_action = QAction("🗓️ Year", self)
        self.yearly_action.setCheckable(True)
        self.yearly_action.triggered.connect(self._show_yearly_view)
        self.view_action_group.addAction(self.yearly_action)
        toolbar.addAction(self.yearly_action)

        toolbar.addSeparator()

        # Add task
        add_action = QAction("➕ Add Task", self)
        add_action.setShortcut(QKeySequence("Ctrl+N"))
        add_action.triggered.connect(self._add_task)
        toolbar.addAction(add_action)

        # Delete task
        delete_action = QAction("🗑️ Delete Task", self)
        delete_action.setShortcut(QKeySequence("Delete"))
        delete_action.triggered.connect(self._delete_task)
        toolbar.addAction(delete_action)

        # Clear completed
        clear_action = QAction("✅ Clear Completed", self)
        clear_action.triggered.connect(self._clear_completed)
        toolbar.addAction(clear_action)

        # Refresh
        refresh_action = QAction("🔄 Refresh", self)
        refresh_action.triggered.connect(self._refresh_view)
        toolbar.addAction(refresh_action)

        toolbar.addSeparator()

        # Weekly report
        report_action = QAction("📊 Weekly Report", self)
        report_action.triggered.connect(self._show_weekly_report)
        toolbar.addAction(report_action)

        # Compare weeks
        compare_action = QAction("⚖️ Compare Weeks", self)
        compare_action.triggered.connect(self._show_compare_weeks)
        toolbar.addAction(compare_action)

        toolbar.addSeparator()

        # Export CSV
        export_action = QAction("📤 Export CSV", self)
        export_action.triggered.connect(self._export_csv)
        toolbar.addAction(export_action)

        toolbar.addSeparator()

        # Compact view toggle
        self.compact_action = QAction("🗜️ Compact View", self)
        self.compact_action.setCheckable(True)
        self.compact_action.setChecked(self.compact_mode)
        self.compact_action.triggered.connect(self._toggle_compact)
        toolbar.addAction(self.compact_action)

        # Theme toggle
        self.theme_action = QAction("🌙 Dark Mode", self)
        self.theme_action.setCheckable(True)
        self.theme_action.setChecked(self.dark_mode)
        self.theme_action.triggered.connect(self._toggle_theme)
        toolbar.addAction(self.theme_action)

    def _show_weekly_report(self):
        dlg = WeeklyReportDialog(self, self.current_week_start if self.view_mode == "weekly" else None)
        dlg.exec()

    def _show_compare_weeks(self):
        dlg = CompareWeeksDialog(self)
        dlg.exec()

    # ------------------------------------------------------------------
    # Theme & compact mode
    # ------------------------------------------------------------------
    def _toggle_theme(self, checked):
        self.dark_mode = checked
        self.settings.setValue("darkMode", self.dark_mode)
        self._apply_theme(self.dark_mode)
        if self.view_mode == "weekly":
            self._refresh_view()

    def _toggle_compact(self, checked):
        self.compact_mode = checked
        self.settings.setValue("compactMode", self.compact_mode)
        if self.view_mode == "weekly":
            self._refresh_view()  # rebuild with new size hints

    def _apply_theme(self, dark: bool):
        if dark:
            self.setStyleSheet("""
                QMainWindow { background-color: #2b2b2b; }
                QLabel { color: #f0f0f0; }
                QPushButton { background-color: #3c3c3c; color: #ffffff; border: 1px solid #555; padding: 4px 8px; border-radius: 3px; }
                QPushButton:hover { background-color: #4a4a4a; }
                QListWidget { background-color: #3c3c3c; color: #f0f0f0; border: 1px solid #555; border-radius: 4px; }
                QListWidget::item { border-bottom: 1px solid #555; }
                QFrame#dayPanel { background-color: #333333; border: 1px solid #444; border-radius: 6px; }
                QFrame#card { background-color: #333333; border: 1px solid #444; border-radius: 6px; padding: 8px; }
                QFrame#card:hover { background-color: #3a3a3a; }
                QLabel#dayHeader { background-color: #3c3c3c; color: #ffffff; padding: 4px; font-weight: bold; border-top-left-radius: 4px; border-top-right-radius: 4px; }
                QLabel#dayDate { color: #aaa; }
                QToolBar { background-color: #3c3c3c; border: none; spacing: 8px; }
                QDialog { background-color: #2b2b2b; color: #f0f0f0; }
                QLineEdit, QTextEdit, QComboBox, QDateEdit, QTimeEdit, QSearchLine { background-color: #3c3c3c; color: #f0f0f0; border: 1px solid #555; border-radius: 3px; padding: 2px; }
                QCheckBox { color: #f0f0f0; }
                QStatusBar { background-color: #3c3c3c; color: #ccc; }
            """)
        else:
            self.setStyleSheet("""
                QMainWindow { background-color: #f0f0f0; }
                QLabel { color: #000000; }
                QPushButton { background-color: #e0e0e0; color: #000; border: 1px solid #aaa; padding: 4px 8px; border-radius: 3px; }
                QPushButton:hover { background-color: #d0d0d0; }
                QListWidget { background-color: #ffffff; color: #000; border: 1px solid #ccc; border-radius: 4px; }
                QListWidget::item { border-bottom: 1px solid #ddd; }
                QFrame#dayPanel { background-color: #f9f9f9; border: 1px solid #ccc; border-radius: 6px; }
                QFrame#card { background-color: #f9f9f9; border: 1px solid #ccc; border-radius: 6px; padding: 8px; }
                QFrame#card:hover { background-color: #f0f0f0; }
                QLabel#dayHeader { background-color: #e0e0e0; color: #000; padding: 4px; font-weight: bold; border-top-left-radius: 4px; border-top-right-radius: 4px; }
                QLabel#dayDate { color: #555; }
                QToolBar { background-color: #e0e0e0; border: none; spacing: 8px; }
                QDialog { background-color: #f0f0f0; color: #000; }
                QLineEdit, QTextEdit, QComboBox, QDateEdit, QTimeEdit, QSearchLine { background-color: #fff; color: #000; border: 1px solid #aaa; border-radius: 3px; padding: 2px; }
                QCheckBox { color: #000; }
                QStatusBar { background-color: #e0e0e0; color: #333; }
            """)

# ----------------------------------------------------------------------
# Entry point
# ----------------------------------------------------------------------
def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    window = WeeklyTaskMonitor()
    window.show()

    sys.exit(app.exec())

if __name__ == "__main__":
    main()