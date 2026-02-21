#!/usr/bin/env python3
"""
Weekly Task Monitor - PySide6
--------------------------------
A feature-rich weekly task manager with:
- Monday–Sunday grid
- SQLite persistence
- Full CRUD (Add/Edit/Delete)
- Checkbox completion
- Week navigation & Today button
- Dark/Light theme toggle (dark by default)
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
    QFrame, QToolBar, QSizePolicy
)
from PySide6.QtCore import Qt, QDate, QTime, Signal, Slot, QSize
from PySide6.QtGui import QFont, QAction, QPalette, QColor

# ----------------------------------------------------------------------
# Database
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
                    priority INTEGER DEFAULT 0,
                    created TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()
    except sqlite3.Error as e:
        QMessageBox.critical(None, "Database Error", f"Failed to initialize database:\n{e}")
        sys.exit(1)

# ----------------------------------------------------------------------
# Task Item Widget (displayed inside each day's list)
# ----------------------------------------------------------------------
class TaskItemWidget(QWidget):
    """Custom widget for a task row: checkbox, title, optional time."""

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
        color = "#888" if self.completed else "#FFF"  # adapt for dark theme
        self.title_label.setStyleSheet(f"color: {color};")

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
    def __init__(self, parent=None, task_data: Optional[Tuple] = None):
        """
        task_data: (id, title, description, due_date, due_time, completed, priority)
        """
        super().__init__(parent)
        self.setWindowTitle("Add Task" if task_data is None else "Edit Task")
        self.setModal(True)
        self.resize(420, 350)

        self.task_id = task_data[0] if task_data else None

        # Main layout
        layout = QVBoxLayout(self)

        # Form
        form = QFormLayout()
        self.title_edit = QLineEdit()
        if task_data:
            self.title_edit.setText(task_data[1])
        form.addRow("Title:", self.title_edit)

        self.desc_edit = QTextEdit()
        self.desc_edit.setMaximumHeight(80)
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
        self.time_edit.setSpecialValueText("--")   # indicates no time set
        self.time_edit.setTime(QTime(9, 0))        # default 9:00 AM
        if task_data and task_data[4]:
            # FIX: use QTime.fromString, not QDate.fromString
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

        # Buttons
        btn_layout = QHBoxLayout()
        save_btn = QPushButton("Save")
        save_btn.clicked.connect(self.accept)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addStretch()
        btn_layout.addWidget(save_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)

    def get_data(self):
        """Return tuple (title, desc, due_date, due_time, completed, priority) or None."""
        title = self.title_edit.text().strip()
        if not title:
            QMessageBox.warning(self, "Validation", "Title cannot be empty.")
            return None

        desc = self.desc_edit.toPlainText().strip()
        due_date = self.date_edit.date().toString("yyyy-MM-dd")
        qtime = self.time_edit.time()
        # Store only if a valid time (not the special "--" value) was set
        due_time = qtime.toString("hh:mm") if qtime.isValid() and self.time_edit.specialValueText() != qtime.toString() else None
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
        self.setMinimumSize(1000, 650)

        # Database
        init_db()

        # Current week start (Monday)
        self.week_start = self._get_monday_of_week(QDate.currentDate())

        # Central widget and main layout
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(10, 10, 10, 10)

        # Toolbar
        self._create_toolbar()

        # Week navigation
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
        self.days_grid.setColumnStretch(0, 1)
        self.days_grid.setColumnStretch(1, 1)
        self.days_grid.setColumnStretch(2, 1)
        self.days_grid.setColumnStretch(3, 1)
        self.days_grid.setColumnStretch(4, 1)
        self.days_grid.setColumnStretch(5, 1)
        self.days_grid.setColumnStretch(6, 1)
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
            vbox.addWidget(task_list)

            self.days_grid.addWidget(panel, 0, col)
            self.day_panels.append((header, date_label, task_list))

        # Initial display
        self._update_week_display()

    def _create_toolbar(self):
        toolbar = QToolBar("Main")
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        add_action = QAction("➕ Add Task", self)
        add_action.triggered.connect(self._add_task)
        toolbar.addAction(add_action)

        delete_action = QAction("🗑️ Delete Task", self)
        delete_action.triggered.connect(self._delete_task)
        toolbar.addAction(delete_action)

        refresh_action = QAction("🔄 Refresh", self)
        refresh_action.triggered.connect(self._refresh_view)
        toolbar.addAction(refresh_action)

        toolbar.addSeparator()

        # Theme toggle (optional but nice)
        self.theme_action = QAction("🌙 Dark Mode", self)
        self.theme_action.setCheckable(True)
        self.theme_action.setChecked(True)   # dark by default
        self.theme_action.triggered.connect(self._toggle_theme)
        toolbar.addAction(self.theme_action)

    def _toggle_theme(self, checked):
        if checked:
            self._apply_dark_theme()
        else:
            self._apply_light_theme()

    def _apply_dark_theme(self):
        dark_stylesheet = """
            QMainWindow { background-color: #2b2b2b; }
            QLabel { color: #f0f0f0; }
            QPushButton { background-color: #3c3c3c; color: #ffffff; border: 1px solid #555; padding: 4px 8px; }
            QPushButton:hover { background-color: #4a4a4a; }
            QListWidget { background-color: #3c3c3c; color: #f0f0f0; border: 1px solid #555; }
            QListWidget::item { border-bottom: 1px solid #555; }
            QFrame#dayPanel { background-color: #333333; border: 1px solid #444; border-radius: 6px; }
            QLabel#dayHeader { background-color: #3c3c3c; color: #ffffff; padding: 4px; font-weight: bold; border-top-left-radius: 4px; border-top-right-radius: 4px; }
            QLabel#dayDate { color: #aaa; }
            QToolBar { background-color: #3c3c3c; border: none; }
            QDialog { background-color: #2b2b2b; color: #f0f0f0; }
            QLineEdit, QTextEdit, QComboBox, QDateEdit, QTimeEdit { background-color: #3c3c3c; color: #f0f0f0; border: 1px solid #555; }
            QCheckBox { color: #f0f0f0; }
        """
        self.setStyleSheet(dark_stylesheet)

    def _apply_light_theme(self):
        light_stylesheet = """
            QMainWindow { background-color: #f0f0f0; }
            QLabel { color: #000000; }
            QPushButton { background-color: #e0e0e0; color: #000; border: 1px solid #aaa; padding: 4px 8px; }
            QPushButton:hover { background-color: #d0d0d0; }
            QListWidget { background-color: #ffffff; color: #000; border: 1px solid #ccc; }
            QListWidget::item { border-bottom: 1px solid #ddd; }
            QFrame#dayPanel { background-color: #f9f9f9; border: 1px solid #ccc; border-radius: 6px; }
            QLabel#dayHeader { background-color: #e0e0e0; color: #000; padding: 4px; font-weight: bold; border-top-left-radius: 4px; border-top-right-radius: 4px; }
            QLabel#dayDate { color: #555; }
            QToolBar { background-color: #e0e0e0; border: none; }
            QDialog { background-color: #f0f0f0; color: #000; }
            QLineEdit, QTextEdit, QComboBox, QDateEdit, QTimeEdit { background-color: #fff; color: #000; border: 1px solid #aaa; }
            QCheckBox { color: #000; }
        """
        self.setStyleSheet(light_stylesheet)

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

        # Set each day's date label
        current = start
        for i in range(7):
            _, date_label, _ = self.day_panels[i]
            date_label.setText(current.toString("dddd, MMM d"))
            current = current.addDays(1)

        self._refresh_view()

    def _refresh_view(self):
        """Reload tasks from database for the current week."""
        for i in range(7):
            day_date = self.week_start.addDays(i)
            day_str = day_date.toString("yyyy-MM-dd")
            tasks = self._get_tasks_for_date(day_str)
            self._populate_day_list(i, tasks)

    def _get_tasks_for_date(self, date_str: str) -> List[Tuple]:
        """Return tasks for a given date, ordered by priority (high first) then time."""
        try:
            with sqlite3.connect(DB_NAME) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT id, title, description, due_date, due_time, completed, priority
                    FROM tasks
                    WHERE due_date = ?
                    ORDER BY priority DESC, due_time ASC
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
            # Set size hint based on content height (approx)
            item.setSizeHint(QSize(200, 50))

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
        """Update completed status in database."""
        try:
            with sqlite3.connect(DB_NAME) as conn:
                cursor = conn.cursor()
                cursor.execute("UPDATE tasks SET completed = ? WHERE id = ?",
                               (1 if completed else 0, task_id))
                conn.commit()
        except sqlite3.Error as e:
            QMessageBox.critical(self, "Database Error", f"Failed to update task:\n{e}")

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
    app.setStyle("Fusion")   # Modern base style

    window = WeeklyTaskMonitor()
    window._apply_dark_theme()   # Start with dark theme
    window.show()

    sys.exit(app.exec())

if __name__ == "__main__":
    main()