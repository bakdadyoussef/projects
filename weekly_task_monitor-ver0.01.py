#!/usr/bin/env python3
"""
Weekly Task Monitor - A PySide6 application for organizing weekly tasks.
Features a Monday-Sunday grid, task persistence via SQLite, and full CRUD operations.
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
    QHeaderView, QSplitter, QFrame
)
from PySide6.QtCore import Qt, QDate, QSize, Signal, Slot
from PySide6.QtGui import QFont, QIcon, QAction

# ----------------------------------------------------------------------
# Database setup
# ----------------------------------------------------------------------
DB_NAME = "tasks.db"

def init_db():
    """Create the tasks table if it doesn't exist."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT,
            due_date DATE NOT NULL,
            due_time TIME,
            completed BOOLEAN DEFAULT 0,
            priority INTEGER DEFAULT 0,
            created TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

# ----------------------------------------------------------------------
# Task Item Widget (displayed inside each day's list)
# ----------------------------------------------------------------------
class TaskItemWidget(QWidget):
    """Custom widget showing a checkbox (completed), title, and time."""

    toggled = Signal(int, bool)  # task_id, completed
    double_clicked = Signal(int)  # task_id

    def __init__(self, task_id: int, title: str, due_time: Optional[str],
                 completed: bool, parent=None):
        super().__init__(parent)
        self.task_id = task_id
        self.completed = completed

        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(6)

        self.checkbox = QCheckBox()
        self.checkbox.setChecked(completed)
        self.checkbox.stateChanged.connect(self._on_toggled)

        self.title_label = QLabel(title)
        self.title_label.setWordWrap(True)
        font = self.title_label.font()
        if completed:
            font.setStrikeOut(True)
            self.title_label.setStyleSheet("color: gray;")
        else:
            font.setStrikeOut(False)
            self.title_label.setStyleSheet("color: black;")
        self.title_label.setFont(font)

        layout.addWidget(self.checkbox)
        layout.addWidget(self.title_label, 1)

        if due_time:
            self.time_label = QLabel(due_time)
            self.time_label.setStyleSheet("color: #666; font-size: 0.9em;")
            layout.addWidget(self.time_label)

        self.setAttribute(Qt.WA_StyledBackground, True)

    def _on_toggled(self, state):
        self.completed = (state == Qt.Checked)
        font = self.title_label.font()
        font.setStrikeOut(self.completed)
        self.title_label.setFont(font)
        self.title_label.setStyleSheet("color: gray;" if self.completed else "color: black;")
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
        self.resize(400, 300)

        self.task_id = None
        if task_data:
            self.task_id = task_data[0]

        layout = QVBoxLayout(self)

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
            dt = QDate.fromString(task_data[3], "yyyy-MM-dd")
            self.date_edit.setDate(dt)
        form.addRow("Date:", self.date_edit)

        self.time_edit = QTimeEdit()
        self.time_edit.setSpecialValueText("--")
        if task_data and task_data[4]:
            tm = QDate.fromString(task_data[4], "hh:mm")
            self.time_edit.setTime(tm)
        else:
            self.time_edit.setTime(QTime(9, 0))  # default 9am
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
        """Return tuple for database: (title, desc, date, time, completed, priority)"""
        title = self.title_edit.text().strip()
        if not title:
            QMessageBox.warning(self, "Validation", "Title cannot be empty.")
            return None

        desc = self.desc_edit.toPlainText().strip()
        qdate = self.date_edit.date()
        due_date = qdate.toString("yyyy-MM-dd")
        qtime = self.time_edit.time()
        due_time = qtime.toString("hh:mm") if qtime.isValid() and qtime.toString() != "" else None
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
        self.setMinimumSize(900, 600)

        # Database
        init_db()

        # Current week start (Monday)
        self.week_start = self._get_monday_of_week(QDate.currentDate())

        # Central widget and main layout
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)

        # Toolbar
        toolbar = self._create_toolbar()
        main_layout.addWidget(toolbar)

        # Week navigation and display
        nav_layout = QHBoxLayout()
        self.prev_week_btn = QPushButton("< Previous Week")
        self.prev_week_btn.clicked.connect(self._prev_week)
        self.next_week_btn = QPushButton("Next Week >")
        self.next_week_btn.clicked.connect(self._next_week)
        self.week_label = QLabel()
        self.week_label.setAlignment(Qt.AlignCenter)
        self.week_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        nav_layout.addWidget(self.prev_week_btn)
        nav_layout.addWidget(self.week_label, 1)
        nav_layout.addWidget(self.next_week_btn)
        main_layout.addLayout(nav_layout)

        # Grid for days
        self.days_grid = QGridLayout()
        self.days_grid.setSpacing(10)
        main_layout.addLayout(self.days_grid)

        # Create day panels (Monday to Sunday)
        self.day_panels = []  # list of (day_label, list_widget)
        day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        for col, day_name in enumerate(day_names):
            # Container for one day
            panel = QFrame()
            panel.setFrameShape(QFrame.StyledPanel)
            panel.setStyleSheet("QFrame { background-color: #f9f9f9; border-radius: 5px; }")
            vbox = QVBoxLayout(panel)

            # Header with day name and date
            header = QLabel(day_name)
            header.setAlignment(Qt.AlignCenter)
            header.setStyleSheet("font-weight: bold; background-color: #e0e0e0; padding: 4px;")
            vbox.addWidget(header)

            # Date label (will be updated)
            date_label = QLabel()
            date_label.setAlignment(Qt.AlignCenter)
            date_label.setStyleSheet("color: #555; font-size: 0.9em;")
            vbox.addWidget(date_label)

            # Task list
            task_list = QListWidget()
            task_list.setSelectionMode(QAbstractItemView.SingleSelection)
            task_list.setDragDropMode(QAbstractItemView.NoDragDrop)
            task_list.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
            task_list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            task_list.setSizePolicy(task_list.sizePolicy().horizontalPolicy(),
                                    task_list.sizePolicy().verticalPolicy())
            task_list.setMinimumHeight(200)
            vbox.addWidget(task_list)

            self.days_grid.addWidget(panel, 0, col)
            self.day_panels.append((header, date_label, task_list))

        # Refresh view with current week
        self._update_week_display()

    def _create_toolbar(self):
        toolbar = self.addToolBar("Main")
        toolbar.setMovable(False)

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
        return toolbar

    def _get_monday_of_week(self, qdate: QDate) -> QDate:
        """Return the Monday of the week containing qdate."""
        day_of_week = qdate.dayOfWeek()  # 1=Monday, 7=Sunday in Qt
        return qdate.addDays(-(day_of_week - 1))

    def _update_week_display(self):
        """Update day labels and reload tasks for the current week."""
        # Set week label (e.g., "Week of Mar 10 - Mar 16, 2025")
        start = self.week_start
        end = start.addDays(6)
        self.week_label.setText(f"Week of {start.toString('MMM d')} - {end.toString('MMM d, yyyy')}")

        # Update each day's header date
        current = start
        for i in range(7):
            header, date_label, task_list = self.day_panels[i]
            date_label.setText(current.toString("dddd, MMM d"))
            current = current.addDays(1)

        self._refresh_view()

    def _refresh_view(self):
        """Clear and repopulate all day lists with tasks from database."""
        # Get tasks for each day of the week
        start_date = self.week_start.toString("yyyy-MM-dd")
        # We'll query for each day individually
        for i in range(7):
            day_date = self.week_start.addDays(i)
            day_str = day_date.toString("yyyy-MM-dd")
            tasks = self._get_tasks_for_date(day_str)
            self._populate_day_list(i, tasks)

    def _get_tasks_for_date(self, date_str: str) -> List[Tuple]:
        """Return list of tasks for given date, ordered by priority and time."""
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, title, description, due_date, due_time, completed, priority
            FROM tasks
            WHERE due_date = ?
            ORDER BY priority DESC, due_time ASC
        """, (date_str,))
        rows = cursor.fetchall()
        conn.close()
        return rows

    def _populate_day_list(self, day_index: int, tasks: List[Tuple]):
        """Fill the QListWidget for day_index with TaskItemWidgets."""
        _, _, task_list = self.day_panels[day_index]
        task_list.clear()

        for task in tasks:
            task_id, title, desc, due_date, due_time, completed, priority = task
            # Create item and custom widget
            item = QListWidgetItem(task_list)
            item.setSizeHint(QSize(200, 50))  # rough height, will adjust

            widget = TaskItemWidget(task_id, title, due_time, bool(completed))
            widget.toggled.connect(self._on_task_toggled)
            widget.double_clicked.connect(self._edit_task_by_id)

            task_list.addItem(item)
            task_list.setItemWidget(item, widget)

    def _on_task_toggled(self, task_id: int, completed: bool):
        """Update completed status in database."""
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("UPDATE tasks SET completed = ? WHERE id = ?",
                       (1 if completed else 0, task_id))
        conn.commit()
        conn.close()
        # No need to refresh the whole view, but if we want to reflect strikethrough,
        # the widget already did. However, other views of the same task (if moved across days)
        # would need refresh, but tasks are only in one day. So fine.

    def _add_task(self):
        """Open dialog to create new task, then refresh."""
        dlg = TaskDialog(self)
        if dlg.exec() == QDialog.Accepted:
            data = dlg.get_data()
            if data:
                conn = sqlite3.connect(DB_NAME)
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO tasks (title, description, due_date, due_time, completed, priority)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, data)
                conn.commit()
                conn.close()
                self._refresh_view()

    def _edit_task_by_id(self, task_id: int):
        """Open edit dialog for task with given id."""
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, title, description, due_date, due_time, completed, priority
            FROM tasks WHERE id = ?
        """, (task_id,))
        row = cursor.fetchone()
        conn.close()
        if not row:
            return

        dlg = TaskDialog(self, row)
        if dlg.exec() == QDialog.Accepted:
            data = dlg.get_data()
            if data:
                conn = sqlite3.connect(DB_NAME)
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE tasks
                    SET title=?, description=?, due_date=?, due_time=?, completed=?, priority=?
                    WHERE id = ?
                """, (*data, task_id))
                conn.commit()
                conn.close()
                self._refresh_view()

    def _delete_task(self):
        """Delete the currently selected task (from any day)."""
        # Find which day list has focus or selection
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
                        conn = sqlite3.connect(DB_NAME)
                        cursor = conn.cursor()
                        cursor.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
                        conn.commit()
                        conn.close()
                        self._refresh_view()
                    return
        QMessageBox.information(self, "No Selection", "Please select a task to delete.")

    def _prev_week(self):
        self.week_start = self.week_start.addDays(-7)
        self._update_week_display()

    def _next_week(self):
        self.week_start = self.week_start.addDays(7)
        self._update_week_display()

# ----------------------------------------------------------------------
# Entry point
# ----------------------------------------------------------------------
def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")  # modern look

    # Optional dark stylesheet (you can customize)
    app.setStyleSheet("""
        QMainWindow {
            background-color: #f0f0f0;
        }
        QPushButton {
            padding: 4px 8px;
        }
        QListWidget {
            border: none;
            background-color: white;
        }
        QListWidget::item {
            border-bottom: 1px solid #ddd;
        }
    """)

    window = WeeklyTaskMonitor()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()