#!/usr/bin/env python3
"""
Weekly Task Monitor - PySide6
==============================
A premium weekly task manager with dark/light themes, keyboard shortcuts,
and a clean, intuitive interface. All data is stored locally in SQLite.

Features:
- Monday–Sunday grid with per‑day task lists
- Add, edit, delete, and duplicate tasks
- Mark tasks complete with a single click
- Week navigation (previous/next/today)
- Dark/light theme toggle (dark by default, remembers your choice)
- Status bar with task statistics
- Keyboard shortcuts for power users
- Persistent SQLite database
"""

import sys
import sqlite3
from datetime import datetime, timedelta, date
from typing import Optional, List, Tuple

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QGridLayout, QPushButton, QLabel, QListWidget, QListWidgetItem,
    QCheckBox, QDialog, QFormLayout, QLineEdit, QTextEdit,
    QDateEdit, QTimeEdit, QComboBox, QMessageBox, QAbstractItemView,
    QFrame, QToolBar, QSizePolicy, QStatusBar
)
from PySide6.QtCore import Qt, QDate, QTime, Signal, Slot, QSize, QSettings
from PySide6.QtGui import QFont, QAction, QKeySequence, QIcon

# ----------------------------------------------------------------------
# Database setup
# ----------------------------------------------------------------------
DB_NAME = "tasks.db"

def init_db():
    """Create the tasks table if it doesn't exist."""
    try:
        with sqlite3.connect(DB_NAME) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    description TEXT,
                    due_date DATE NOT NULL,
                    due_time TEXT,  -- stored as 'HH:MM'
                    completed BOOLEAN DEFAULT 0,
                    priority INTEGER DEFAULT 0,  -- 0=Low, 1=Normal, 2=High
                    created TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()
    except sqlite3.Error as e:
        QMessageBox.critical(None, "Database Error", f"Cannot initialize database:\n{e}")
        sys.exit(1)

# ----------------------------------------------------------------------
# Task item widget (displayed inside each day's list)
# ----------------------------------------------------------------------
class TaskItemWidget(QWidget):
    """A task row with checkbox, title, and optional time."""

    toggled = Signal(int, bool)      # task_id, completed
    double_clicked = Signal(int)      # task_id

    def __init__(self, task_id: int, title: str, due_time: Optional[str],
                 completed: bool, parent=None):
        super().__init__(parent)
        self.task_id = task_id
        self.completed = completed

        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(8)

        self.checkbox = QCheckBox()
        self.checkbox.setChecked(completed)
        self.checkbox.stateChanged.connect(self._on_toggled)

        self.title_label = QLabel(title)
        self.title_label.setWordWrap(True)
        self.title_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self._update_title_style()

        layout.addWidget(self.checkbox)
        layout.addWidget(self.title_label)

        if due_time:
            self.time_label = QLabel(due_time)
            self.time_label.setStyleSheet("color: #888; font-size: 0.9em;")
            layout.addWidget(self.time_label)

        self.setAttribute(Qt.WA_StyledBackground, True)

    def _update_title_style(self):
        font = self.title_label.font()
        font.setStrikeOut(self.completed)
        self.title_label.setFont(font)
        # Color will be set by global stylesheet; no need to override here

    def _on_toggled(self, state):
        self.completed = (state == Qt.Checked)
        self._update_title_style()
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
        task_data: (id, title, description, due_date, due_time, completed, priority)
        """
        super().__init__(parent)
        self.setWindowTitle("Add Task" if task_data is None else "Edit Task")
        self.setModal(True)
        self.resize(420, 350)
        self.setMinimumSize(380, 300)

        self.task_id = task_data[0] if task_data else None

        # Main layout
        layout = QVBoxLayout(self)

        # Form layout
        form = QFormLayout()
        form.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)

        self.title_edit = QLineEdit()
        if task_data:
            self.title_edit.setText(task_data[1])
        form.addRow("Title:", self.title_edit)

        self.desc_edit = QTextEdit()
        self.desc_edit.setMaximumHeight(80)
        self.desc_edit.setPlaceholderText("Optional description...")
        if task_data:
            self.desc_edit.setPlainText(task_data[2] or "")
        form.addRow("Description:", self.desc_edit)

        self.date_edit = QDateEdit()
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDate(QDate.currentDate())
        if task_data:
            self.date_edit.setDate(QDate.fromString(task_data[3], "yyyy-MM-dd"))
        form.addRow("Date:", self.date_edit)

        self.time_edit = QTimeEdit()
        self.time_edit.setSpecialValueText("--")   # indicates no time
        self.time_edit.setTime(QTime(9, 0))        # default 9:00 AM
        if task_data and task_data[4]:
            qtime = QTime.fromString(task_data[4], "hh:mm")
            if qtime.isValid():
                self.time_edit.setTime(qtime)
        form.addRow("Time (optional):", self.time_edit)

        self.priority_combo = QComboBox()
        self.priority_combo.addItems(["Low", "Normal", "High"])
        if task_data:
            self.priority_combo.setCurrentIndex(task_data[6])
        form.addRow("Priority:", self.priority_combo)

        self.completed_check = QCheckBox("Completed")
        if task_data:
            self.completed_check.setChecked(task_data[5] == 1)
        form.addRow(self.completed_check)

        layout.addLayout(form)

        # Button box
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

        # Set tab order
        self.setTabOrder(self.title_edit, self.desc_edit)
        self.setTabOrder(self.desc_edit, self.date_edit)
        self.setTabOrder(self.date_edit, self.time_edit)
        self.setTabOrder(self.time_edit, self.priority_combo)
        self.setTabOrder(self.priority_combo, self.completed_check)
        self.setTabOrder(self.completed_check, self.save_btn)
        self.setTabOrder(self.save_btn, cancel_btn)

    def get_data(self):
        """
        Return tuple (title, desc, due_date, due_time, completed, priority)
        or None if validation fails.
        """
        title = self.title_edit.text().strip()
        if not title:
            QMessageBox.warning(self, "Validation", "Task title cannot be empty.")
            return None

        desc = self.desc_edit.toPlainText().strip()
        due_date = self.date_edit.date().toString("yyyy-MM-dd")
        qtime = self.time_edit.time()
        # Store time only if it's not the special "--" placeholder
        due_time = qtime.toString("hh:mm") if (qtime.isValid() and
                     self.time_edit.specialValueText() != qtime.toString()) else None
        completed = 1 if self.completed_check.isChecked() else 0
        priority = self.priority_combo.currentIndex()
        return (title, desc, due_date, due_time, completed, priority)

# ----------------------------------------------------------------------
# Main Window
# ----------------------------------------------------------------------
class WeeklyTaskMonitor(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Weekly Task Monitor")
        self.setMinimumSize(1100, 700)

        # Database
        init_db()

        # Settings (persist theme preference)
        self.settings = QSettings("YourCompany", "WeeklyTaskMonitor")

        # Current week start (Monday)
        self.week_start = self._get_monday_of_week(QDate.currentDate())

        # Central widget
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(10, 10, 10, 10)

        # Create toolbar
        self._create_toolbar()

        # Week navigation bar
        nav_layout = QHBoxLayout()
        self.prev_week_btn = QPushButton("◀ Previous Week")
        self.prev_week_btn.clicked.connect(self._prev_week)
        self.next_week_btn = QPushButton("Next Week ▶")
        self.next_week_btn.clicked.connect(self._next_week)
        self.today_btn = QPushButton("📅 Today")
        self.today_btn.clicked.connect(self._go_today)
        self.week_label = QLabel()
        self.week_label.setAlignment(Qt.AlignCenter)
        self.week_label.setStyleSheet("font-weight: bold; font-size: 14px;")

        nav_layout.addWidget(self.prev_week_btn)
        nav_layout.addWidget(self.week_label, 1)
        nav_layout.addWidget(self.next_week_btn)
        nav_layout.addWidget(self.today_btn)
        main_layout.addLayout(nav_layout)

        # Grid for days (Monday to Sunday)
        self.days_grid = QGridLayout()
        self.days_grid.setSpacing(12)
        for col in range(7):
            self.days_grid.setColumnStretch(col, 1)
        main_layout.addLayout(self.days_grid)

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
            # Connect context menu if desired (not implemented here)
            vbox.addWidget(task_list)

            self.days_grid.addWidget(panel, 0, col)
            self.day_panels.append((header, date_label, task_list))

        # Status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_label = QLabel()
        self.status_bar.addWidget(self.status_label)

        # Apply theme from saved preference
        self.dark_mode = self.settings.value("darkMode", True, type=bool)
        self._apply_theme(self.dark_mode)

        # Initial display
        self._update_week_display()

        # Set up keyboard shortcuts
        self._setup_shortcuts()

    def _setup_shortcuts(self):
        """Define global keyboard shortcuts."""
        # New task
        new_shortcut = QAction(self)
        new_shortcut.setShortcut(QKeySequence("Ctrl+N"))
        new_shortcut.triggered.connect(self._add_task)
        self.addAction(new_shortcut)

        # Delete selected task
        delete_shortcut = QAction(self)
        delete_shortcut.setShortcut(QKeySequence("Delete"))
        delete_shortcut.triggered.connect(self._delete_task)
        self.addAction(delete_shortcut)

        # Previous week
        prev_shortcut = QAction(self)
        prev_shortcut.setShortcut(QKeySequence("Ctrl+Left"))
        prev_shortcut.triggered.connect(self._prev_week)
        self.addAction(prev_shortcut)

        # Next week
        next_shortcut = QAction(self)
        next_shortcut.setShortcut(QKeySequence("Ctrl+Right"))
        next_shortcut.triggered.connect(self._next_week)
        self.addAction(next_shortcut)

        # Today
        today_shortcut = QAction(self)
        today_shortcut.setShortcut(QKeySequence("Ctrl+T"))
        today_shortcut.triggered.connect(self._go_today)
        self.addAction(today_shortcut)

    def _create_toolbar(self):
        toolbar = QToolBar("Main")
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

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

        # Clear completed tasks (new feature)
        clear_action = QAction("✅ Clear Completed", self)
        clear_action.triggered.connect(self._clear_completed)
        toolbar.addAction(clear_action)

        # Refresh
        refresh_action = QAction("🔄 Refresh", self)
        refresh_action.triggered.connect(self._refresh_view)
        toolbar.addAction(refresh_action)

        toolbar.addSeparator()

        # Theme toggle
        self.theme_action = QAction("🌙 Dark Mode", self)
        self.theme_action.setCheckable(True)
        self.theme_action.setChecked(self.dark_mode)
        self.theme_action.triggered.connect(self._toggle_theme)
        toolbar.addAction(self.theme_action)

    # ------------------------------------------------------------------
    # Theme handling
    # ------------------------------------------------------------------
    def _toggle_theme(self, checked):
        self.dark_mode = checked
        self.settings.setValue("darkMode", self.dark_mode)
        self._apply_theme(self.dark_mode)

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
                QLabel#dayHeader { background-color: #3c3c3c; color: #ffffff; padding: 4px; font-weight: bold; border-top-left-radius: 4px; border-top-right-radius: 4px; }
                QLabel#dayDate { color: #aaa; }
                QToolBar { background-color: #3c3c3c; border: none; spacing: 8px; }
                QDialog { background-color: #2b2b2b; color: #f0f0f0; }
                QLineEdit, QTextEdit, QComboBox, QDateEdit, QTimeEdit { background-color: #3c3c3c; color: #f0f0f0; border: 1px solid #555; border-radius: 3px; padding: 2px; }
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
                QLabel#dayHeader { background-color: #e0e0e0; color: #000; padding: 4px; font-weight: bold; border-top-left-radius: 4px; border-top-right-radius: 4px; }
                QLabel#dayDate { color: #555; }
                QToolBar { background-color: #e0e0e0; border: none; spacing: 8px; }
                QDialog { background-color: #f0f0f0; color: #000; }
                QLineEdit, QTextEdit, QComboBox, QDateEdit, QTimeEdit { background-color: #fff; color: #000; border: 1px solid #aaa; border-radius: 3px; padding: 2px; }
                QCheckBox { color: #000; }
                QStatusBar { background-color: #e0e0e0; color: #333; }
            """)

    # ------------------------------------------------------------------
    # Week helpers
    # ------------------------------------------------------------------
    def _get_monday_of_week(self, qdate: QDate) -> QDate:
        """Return the Monday of the week containing qdate."""
        day_of_week = qdate.dayOfWeek()  # 1=Monday, 7=Sunday in Qt
        return qdate.addDays(-(day_of_week - 1))

    def _update_week_display(self):
        """Update day headers and reload tasks."""
        start = self.week_start
        end = start.addDays(6)
        self.week_label.setText(f"Week of {start.toString('MMM d')} – {end.toString('MMM d, yyyy')}")

        current = start
        for i in range(7):
            _, date_label, _ = self.day_panels[i]
            date_label.setText(current.toString("dddd, MMM d"))
            current = current.addDays(1)

        self._refresh_view()

    def _refresh_view(self):
        """Reload tasks from database and update status bar."""
        total_tasks = 0
        completed_tasks = 0

        for i in range(7):
            day_date = self.week_start.addDays(i)
            day_str = day_date.toString("yyyy-MM-dd")
            tasks = self._get_tasks_for_date(day_str)
            self._populate_day_list(i, tasks)

            # Count for status bar
            total_tasks += len(tasks)
            completed_tasks += sum(1 for t in tasks if t[5])  # t[5] is completed

        self.status_label.setText(f"Week total: {total_tasks} tasks  |  Completed: {completed_tasks}")

    def _get_tasks_for_date(self, date_str: str) -> List[Tuple]:
        """Return tasks for a given date, ordered by priority then time (null times last)."""
        try:
            with sqlite3.connect(DB_NAME) as conn:
                cursor = conn.cursor()
                # Order: priority DESC, then put NULL times last, then time ASC
                cursor.execute("""
                    SELECT id, title, description, due_date, due_time, completed, priority
                    FROM tasks
                    WHERE due_date = ?
                    ORDER BY priority DESC,
                             CASE WHEN due_time IS NULL THEN 1 ELSE 0 END,
                             due_time ASC
                """, (date_str,))
                return cursor.fetchall()
        except sqlite3.Error as e:
            QMessageBox.critical(self, "Database Error", f"Failed to fetch tasks:\n{e}")
            return []

    def _populate_day_list(self, day_index: int, tasks: List[Tuple]):
        """Fill the QListWidget for day_index with TaskItemWidgets."""
        _, _, task_list = self.day_panels[day_index]
        task_list.clear()

        for task in tasks:
            task_id, title, _, _, due_time, completed, _ = task
            item = QListWidgetItem(task_list)
            item.setSizeHint(QSize(200, 50))  # approximate; actual height adjusts

            widget = TaskItemWidget(task_id, title, due_time, bool(completed))
            widget.toggled.connect(self._on_task_toggled)
            widget.double_clicked.connect(self._edit_task_by_id)

            task_list.addItem(item)
            task_list.setItemWidget(item, widget)

    # ------------------------------------------------------------------
    # Task operations
    # ------------------------------------------------------------------
    @Slot(int, bool)
    def _on_task_toggled(self, task_id: int, completed: bool):
        """Update completed status in database and refresh stats."""
        try:
            with sqlite3.connect(DB_NAME) as conn:
                cursor = conn.cursor()
                cursor.execute("UPDATE tasks SET completed = ? WHERE id = ?",
                               (1 if completed else 0, task_id))
                conn.commit()
        except sqlite3.Error as e:
            QMessageBox.critical(self, "Database Error", f"Failed to update task:\n{e}")
        self._refresh_view()  # to update status bar (though we could just update counts)

    def _add_task(self):
        dlg = TaskDialog(self)
        if dlg.exec() == QDialog.Accepted:
            data = dlg.get_data()
            if data:
                try:
                    with sqlite3.connect(DB_NAME) as conn:
                        cursor = conn.cursor()
                        cursor.execute("""
                            INSERT INTO tasks (title, description, due_date, due_time, completed, priority)
                            VALUES (?, ?, ?, ?, ?, ?)
                        """, data)
                        conn.commit()
                    self._refresh_view()
                except sqlite3.Error as e:
                    QMessageBox.critical(self, "Database Error", f"Failed to add task:\n{e}")

    def _edit_task_by_id(self, task_id: int):
        """Fetch task and open edit dialog."""
        try:
            with sqlite3.connect(DB_NAME) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT id, title, description, due_date, due_time, completed, priority
                    FROM tasks WHERE id = ?
                """, (task_id,))
                row = cursor.fetchone()
        except sqlite3.Error as e:
            QMessageBox.critical(self, "Database Error", f"Failed to fetch task:\n{e}")
            return

        if not row:
            return

        dlg = TaskDialog(self, row)
        if dlg.exec() == QDialog.Accepted:
            data = dlg.get_data()
            if data:
                try:
                    with sqlite3.connect(DB_NAME) as conn:
                        cursor = conn.cursor()
                        cursor.execute("""
                            UPDATE tasks
                            SET title=?, description=?, due_date=?, due_time=?, completed=?, priority=?
                            WHERE id = ?
                        """, (*data, task_id))
                        conn.commit()
                    self._refresh_view()
                except sqlite3.Error as e:
                    QMessageBox.critical(self, "Database Error", f"Failed to update task:\n{e}")

    def _delete_task(self):
        """Delete the currently selected task."""
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
        """Delete all completed tasks in the current week."""
        # Build list of dates in current week
        dates = [self.week_start.addDays(i).toString("yyyy-MM-dd") for i in range(7)]
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

    # ------------------------------------------------------------------
    # Week navigation
    # ------------------------------------------------------------------
    def _prev_week(self):
        self.week_start = self.week_start.addDays(-7)
        self._update_week_display()

    def _next_week(self):
        self.week_start = self.week_start.addDays(7)
        self._update_week_display()

    def _go_today(self):
        self.week_start = self._get_monday_of_week(QDate.currentDate())
        self._update_week_display()

# ----------------------------------------------------------------------
# Entry point
# ----------------------------------------------------------------------
def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")   # consistent cross‑platform look

    window = WeeklyTaskMonitor()
    window.show()

    sys.exit(app.exec())

if __name__ == "__main__":
    main()