import sys
import subprocess
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QRadioButton, QButtonGroup, QLabel, QFileDialog,
    QMessageBox, QGroupBox, QSpinBox, QFormLayout, QListWidget,
    QListWidgetItem, QLineEdit, QDialog, QDialogButtonBox, QComboBox,
    QStatusBar, QCheckBox, QMenuBar, QMenu
)
from PySide6.QtCore import Qt, QSettings, QSize, QByteArray, QBuffer
from PySide6.QtGui import QIcon, QFont, QAction, QPixmap, QPainter, QColor, QPen, QBrush

# -------------------------------
# Custom dialog for saving/loading profiles
# -------------------------------
class ProfileDialog(QDialog):
    def __init__(self, parent=None, profile_names=None):
        super().__init__(parent)
        self.setWindowTitle("Manage Profiles")
        self.setModal(True)
        self.setMinimumWidth(300)

        layout = QVBoxLayout(self)

        # Profile name input
        form_layout = QFormLayout()
        self.profile_name_edit = QLineEdit()
        form_layout.addRow("Profile name:", self.profile_name_edit)
        layout.addLayout(form_layout)

        # List of existing profiles (if any)
        if profile_names:
            self.profile_list = QListWidget()
            self.profile_list.addItems(profile_names)
            self.profile_list.itemClicked.connect(self.on_profile_selected)
            layout.addWidget(QLabel("Existing profiles (click to load):"))
            layout.addWidget(self.profile_list)
        else:
            self.profile_list = None

        # Buttons
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

        self.selected_profile = None

    def on_profile_selected(self, item):
        self.profile_name_edit.setText(item.text())
        self.selected_profile = item.text()

    def get_profile_name(self):
        return self.profile_name_edit.text().strip()


# -------------------------------
# Main application window
# -------------------------------
class GameLauncher(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Crimson Game Launcher")
        self.setMinimumSize(750, 600)

        # Set custom window icon
        self.setWindowIcon(self.create_crimson_icon())

        # Load settings
        self.settings = QSettings("CrimsonLauncher", "GameLauncher")

        # Data structures
        self.profiles = {}  # name -> dict with keys: exe, resolution, hz, force_hz, default, windowed
        self.recent_files = []  # list of exe paths

        # Current selection
        self.current_exe = self.settings.value("last_exe", "")
        self.current_resolution = self.settings.value("last_resolution", "1920x1080")
        self.custom_width = int(self.settings.value("custom_width", 1920))
        self.custom_height = int(self.settings.value("custom_height", 1080))
        self.force_hz = self.settings.value("force_hz", False, type=bool)
        self.hz_value = int(self.settings.value("hz_value", 60))
        self.windowed_mode = self.settings.value("windowed_mode", False, type=bool)
        self.default_settings = self.settings.value("default_settings", False, type=bool)

        # Predefined resolutions (you can edit this list)
        self.preset_resolutions = [
            "640x480",
            "800x600",
            "1024x768",
            "1280x720",
            "1366x768",
            "1600x900",
            "1920x1080",
            "2560x1440",
            "3840x2160"
        ]

        # Load recent files from settings
        recent_list = self.settings.value("recent_files", [])
        if isinstance(recent_list, list):
            self.recent_files = recent_list[:5]  # keep max 5

        # Load profiles from settings (handle old tuple format and missing keys)
        profiles_dict = self.settings.value("profiles", {})
        if isinstance(profiles_dict, dict):
            self.profiles = {}
            for name, value in profiles_dict.items():
                # Convert old tuple format (exe, resolution) to new dict format
                if isinstance(value, tuple) and len(value) == 2:
                    self.profiles[name] = {
                        'exe': value[0],
                        'resolution': value[1],
                        'hz': 60,
                        'force_hz': False,
                        'windowed': False,
                        'default': False
                    }
                elif isinstance(value, dict):
                    # Ensure all keys exist, supply defaults if missing
                    profile = value
                    profile.setdefault('hz', 60)
                    profile.setdefault('force_hz', False)
                    profile.setdefault('windowed', False)
                    profile.setdefault('default', False)
                    self.profiles[name] = profile
                # else skip invalid entries
        else:
            self.profiles = {}

        # Setup UI
        self.setup_ui()
        self.apply_theme()
        self.create_menu_bar()

        # Restore last selection
        self.restore_last_selection()

        # Update status
        self.update_status()

    def create_crimson_icon(self):
        """Generate a cool crimson icon with a white 'C'."""
        pixmap = QPixmap(64, 64)
        pixmap.fill(Qt.transparent)

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)

        # Draw crimson circle
        painter.setBrush(QBrush(QColor("#8b0000")))
        painter.setPen(QPen(QColor("#ff4d4d"), 2))
        painter.drawEllipse(2, 2, 60, 60)

        # Draw white 'C'
        painter.setFont(QFont("Arial", 36, QFont.Bold))
        painter.setPen(QColor("white"))
        painter.drawText(pixmap.rect(), Qt.AlignCenter, "C")

        painter.end()
        return QIcon(pixmap)

    def setup_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        # Top area: file selection + recent games
        top_layout = QHBoxLayout()

        # File selection group
        file_group = QGroupBox("Game Executable")
        file_layout = QVBoxLayout(file_group)

        # Selected file label
        self.file_label = QLabel(self.current_exe if self.current_exe else "No file selected")
        self.file_label.setWordWrap(True)
        self.file_label.setStyleSheet("font-weight: bold;")
        file_layout.addWidget(self.file_label)

        # Buttons row
        btn_layout = QHBoxLayout()
        self.browse_btn = QPushButton("Browse...")
        self.browse_btn.clicked.connect(self.browse_exe)
        btn_layout.addWidget(self.browse_btn)

        self.recent_combo = QComboBox()
        self.recent_combo.setEditable(False)
        self.recent_combo.addItem("Recent games")
        self.recent_combo.addItems(self.recent_files)
        self.recent_combo.activated.connect(self.on_recent_selected)
        btn_layout.addWidget(self.recent_combo)

        file_layout.addLayout(btn_layout)
        top_layout.addWidget(file_group)

        # Profile management group
        profile_group = QGroupBox("Profiles")
        profile_layout = QVBoxLayout(profile_group)

        self.profile_combo = QComboBox()
        self.profile_combo.setEditable(False)
        self.profile_combo.addItem("Select profile")
        self.profile_combo.addItems(self.profiles.keys())
        self.profile_combo.activated.connect(self.on_profile_selected)
        profile_layout.addWidget(self.profile_combo)

        profile_btn_layout = QHBoxLayout()
        self.save_profile_btn = QPushButton("Save Profile")
        self.save_profile_btn.clicked.connect(self.save_profile)
        profile_btn_layout.addWidget(self.save_profile_btn)

        self.delete_profile_btn = QPushButton("Delete Profile")
        self.delete_profile_btn.clicked.connect(self.delete_profile)
        profile_btn_layout.addWidget(self.delete_profile_btn)

        profile_layout.addLayout(profile_btn_layout)
        top_layout.addWidget(profile_group)

        main_layout.addLayout(top_layout)

        # Resolution selection area
        res_group = QGroupBox("Resolution (select one)")
        res_layout = QVBoxLayout(res_group)

        # Radio button group for mutual exclusivity
        self.res_radio_group = QButtonGroup(self)
        self.res_radio_group.setExclusive(True)
        self.res_radio_group.buttonToggled.connect(self.on_resolution_toggled)

        # Add preset resolutions
        self.preset_radios = []
        for res in self.preset_resolutions:
            radio = QRadioButton(res)
            self.res_radio_group.addButton(radio)
            res_layout.addWidget(radio)
            self.preset_radios.append(radio)

        # Custom resolution row (as a radio with spin boxes)
        custom_layout = QHBoxLayout()
        self.custom_radio = QRadioButton("Custom:")
        self.res_radio_group.addButton(self.custom_radio)
        custom_layout.addWidget(self.custom_radio)

        self.width_spin = QSpinBox()
        self.width_spin.setRange(1, 7680)
        self.width_spin.setValue(self.custom_width)
        self.width_spin.setSuffix(" px")
        self.width_spin.setEnabled(False)  # initially disabled
        custom_layout.addWidget(self.width_spin)

        self.height_spin = QSpinBox()
        self.height_spin.setRange(1, 4320)
        self.height_spin.setValue(self.custom_height)
        self.height_spin.setSuffix(" px")
        self.height_spin.setEnabled(False)
        custom_layout.addWidget(self.height_spin)

        res_layout.addLayout(custom_layout)

        # Connect custom radio to enable/disable spin boxes
        self.custom_radio.toggled.connect(self.on_custom_toggled)

        main_layout.addWidget(res_group)

        # Advanced options (Hz, Windowed, Default)
        adv_group = QGroupBox("Advanced Options")
        adv_layout = QVBoxLayout(adv_group)

        # Force Hz row
        hz_layout = QHBoxLayout()
        self.force_hz_check = QCheckBox("Force refresh rate (Hz)")
        self.force_hz_check.setChecked(self.force_hz)
        self.force_hz_check.toggled.connect(self.on_force_hz_toggled)
        hz_layout.addWidget(self.force_hz_check)

        self.hz_spin = QSpinBox()
        self.hz_spin.setRange(1, 1000)
        self.hz_spin.setValue(self.hz_value)
        self.hz_spin.setSuffix(" Hz")
        self.hz_spin.setEnabled(self.force_hz)
        self.hz_spin.valueChanged.connect(self.on_hz_changed)
        hz_layout.addWidget(self.hz_spin)

        adv_layout.addLayout(hz_layout)

        # Force window mode checkbox
        self.windowed_check = QCheckBox("Force windowed mode")
        self.windowed_check.setChecked(self.windowed_mode)
        self.windowed_check.toggled.connect(self.on_windowed_toggled)
        adv_layout.addWidget(self.windowed_check)

        # Launch with default settings checkbox
        self.default_check = QCheckBox("Launch with default settings (ignore all custom settings)")
        self.default_check.setChecked(self.default_settings)
        self.default_check.toggled.connect(self.on_default_toggled)
        adv_layout.addWidget(self.default_check)

        main_layout.addWidget(adv_group)

        # Launch button
        self.launch_btn = QPushButton("Launch Game")
        self.launch_btn.setMinimumHeight(50)
        self.launch_btn.setFont(QFont("Arial", 14))
        self.launch_btn.clicked.connect(self.launch_game)
        main_layout.addWidget(self.launch_btn)

        # Status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)

    def create_menu_bar(self):
        """Create a custom menu bar with File and Help menus."""
        menubar = self.menuBar()

        # File menu
        file_menu = menubar.addMenu("File")

        # Minimize action
        minimize_action = QAction("Minimize", self)
        minimize_action.triggered.connect(self.showMinimized)
        file_menu.addAction(minimize_action)

        # Close action
        close_action = QAction("Close", self)
        close_action.triggered.connect(self.close)
        file_menu.addAction(close_action)

        # Help menu
        help_menu = menubar.addMenu("Help")

        about_action = QAction("About", self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)

    def show_about(self):
        """Show about dialog."""
        QMessageBox.about(
            self,
            "About Crimson Game Launcher",
            "<h2>Crimson Game Launcher</h2>"
            "<p>Version 3.0</p>"
            "<p>A feature-rich game launcher with resolution, Hz forcing, windowed mode, and profiles.</p>"
            "<p>Created with PySide6.</p>"
        )

    def apply_theme(self):
        """Apply red/crimson dark theme using QSS."""
        self.setStyleSheet("""
            QMainWindow {
                background-color: #1a0b0b;
            }
            QGroupBox {
                font: bold 12px;
                border: 2px solid #8b0000;
                border-radius: 8px;
                margin-top: 1ex;
                padding-top: 10px;
                color: #f0e6e6;
                background-color: #2d1a1a;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
                color: #ff4d4d;
            }
            QLabel {
                color: #f0e6e6;
            }
            QPushButton {
                background-color: #8b0000;
                color: white;
                border: 1px solid #b30000;
                padding: 6px;
                border-radius: 5px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #a52a2a;
            }
            QPushButton:pressed {
                background-color: #5a0000;
            }
            QComboBox, QSpinBox, QLineEdit, QListWidget {
                background-color: #3d2a2a;
                color: #f0e6e6;
                border: 1px solid #8b0000;
                border-radius: 4px;
                padding: 3px;
            }
            QComboBox::drop-down {
                background-color: #8b0000;
            }
            QRadioButton, QCheckBox {
                color: #f0e6e6;
                spacing: 5px;
            }
            QRadioButton::indicator, QCheckBox::indicator {
                width: 13px;
                height: 13px;
                background-color: #3d2a2a;
                border: 1px solid #8b0000;
                border-radius: 3px;
            }
            QRadioButton::indicator:checked, QCheckBox::indicator:checked {
                background-color: #b30000;
                border: 2px solid #ff4d4d;
            }
            QStatusBar {
                color: #f0e6e6;
                background-color: #2d1a1a;
            }
            QMenuBar {
                background-color: #2d1a1a;
                color: #f0e6e6;
                border-bottom: 1px solid #8b0000;
            }
            QMenuBar::item:selected {
                background-color: #8b0000;
            }
            QMenu {
                background-color: #2d1a1a;
                color: #f0e6e6;
                border: 1px solid #8b0000;
            }
            QMenu::item:selected {
                background-color: #8b0000;
            }
        """)

    def restore_last_selection(self):
        """Restore the last used executable, resolution, Hz, windowed, and default flag from settings."""
        if self.current_exe:
            self.file_label.setText(self.current_exe)

        # Find which preset matches current_resolution
        matched = False
        for radio in self.preset_radios:
            if radio.text() == self.current_resolution:
                radio.setChecked(True)
                matched = True
                break
        if not matched:
            # Assume custom resolution
            self.custom_radio.setChecked(True)
            self.width_spin.setValue(self.custom_width)
            self.height_spin.setValue(self.custom_height)

        # Restore Hz, windowed, and default
        self.force_hz_check.setChecked(self.force_hz)
        self.hz_spin.setValue(self.hz_value)
        self.windowed_check.setChecked(self.windowed_mode)
        self.default_check.setChecked(self.default_settings)

        # Enable/disable controls based on default flag
        self.on_default_toggled(self.default_settings)

    def browse_exe(self):
        """Open file dialog to select an .exe."""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select Game Executable", "", "Executable Files (*.exe);;All Files (*)"
        )
        if file_path:
            self.set_current_exe(file_path)

    def set_current_exe(self, path):
        """Set the current executable and update recent list."""
        self.current_exe = path
        self.file_label.setText(path)

        # Add to recent files (avoid duplicates)
        if path in self.recent_files:
            self.recent_files.remove(path)
        self.recent_files.insert(0, path)
        self.recent_files = self.recent_files[:5]

        # Update combo box
        self.recent_combo.clear()
        self.recent_combo.addItem("Recent games")
        self.recent_combo.addItems(self.recent_files)

        # Save to settings
        self.settings.setValue("last_exe", path)
        self.settings.setValue("recent_files", self.recent_files)

        self.update_status()

    def on_recent_selected(self, index):
        """Handle selection from recent games combo box."""
        if index == 0:  # placeholder
            return
        path = self.recent_combo.itemText(index)
        self.set_current_exe(path)

    def on_resolution_toggled(self, button, checked):
        """When a resolution radio button is toggled, update current_resolution."""
        if checked and button != self.custom_radio:
            self.current_resolution = button.text()
            self.settings.setValue("last_resolution", self.current_resolution)
            self.update_status()

    def on_custom_toggled(self, checked):
        """Enable/disable spin boxes based on custom radio state."""
        self.width_spin.setEnabled(checked)
        self.height_spin.setEnabled(checked)
        if checked:
            # Update current_resolution from spin boxes
            self.update_custom_resolution()
            self.settings.setValue("last_resolution", "custom")

    def update_custom_resolution(self):
        """Read spin boxes and store custom values."""
        self.custom_width = self.width_spin.value()
        self.custom_height = self.height_spin.value()
        self.settings.setValue("custom_width", self.custom_width)
        self.settings.setValue("custom_height", self.custom_height)

    def on_force_hz_toggled(self, checked):
        """Enable/disable Hz spin box based on checkbox."""
        self.hz_spin.setEnabled(checked)
        self.force_hz = checked
        self.settings.setValue("force_hz", checked)
        if checked:
            self.hz_value = self.hz_spin.value()
            self.settings.setValue("hz_value", self.hz_value)
        self.update_status()

    def on_hz_changed(self, value):
        """Called when Hz spin box value changes."""
        self.hz_value = value
        self.settings.setValue("hz_value", value)

    def on_windowed_toggled(self, checked):
        """Handle windowed mode checkbox."""
        self.windowed_mode = checked
        self.settings.setValue("windowed_mode", checked)
        self.update_status()

    def on_default_toggled(self, checked):
        """Handle default settings checkbox."""
        self.default_settings = checked
        self.settings.setValue("default_settings", checked)
        # Enable/disable the relevant widgets
        for radio in self.preset_radios:
            radio.setEnabled(not checked)
        self.custom_radio.setEnabled(not checked)
        self.width_spin.setEnabled(not checked and self.custom_radio.isChecked())
        self.height_spin.setEnabled(not checked and self.custom_radio.isChecked())
        self.force_hz_check.setEnabled(not checked)
        self.hz_spin.setEnabled(not checked and self.force_hz_check.isChecked())
        self.windowed_check.setEnabled(not checked)
        self.update_status()

    def get_selected_resolution(self):
        """Return the currently selected resolution as a string (widthxheight)."""
        if self.custom_radio.isChecked():
            self.update_custom_resolution()
            return f"{self.custom_width}x{self.custom_height}"
        else:
            selected = self.res_radio_group.checkedButton()
            if selected:
                return selected.text()
        return None

    def launch_game(self):
        """Launch the selected executable with the chosen resolution, Hz, and windowed arguments."""
        if not self.current_exe:
            QMessageBox.warning(self, "No File", "Please select a game executable first.")
            return

        # If default settings is checked, launch without any arguments
        if self.default_check.isChecked():
            cmd = [self.current_exe]
            try:
                subprocess.Popen(cmd)
                self.status_bar.showMessage("Launched with default settings", 3000)
                QMessageBox.information(self, "Launched", "Game launched with default settings.")
            except Exception as e:
                QMessageBox.critical(self, "Launch Error", f"Failed to launch game:\n{str(e)}")
            return

        # Otherwise, build command with resolution, Hz, and windowed arguments
        resolution_str = self.get_selected_resolution()
        if not resolution_str:
            QMessageBox.warning(self, "No Resolution", "Please select a resolution.")
            return

        try:
            width, height = resolution_str.split('x')
        except ValueError:
            QMessageBox.critical(self, "Error", f"Invalid resolution format: {resolution_str}")
            return

        # Start building command
        cmd = [self.current_exe]

        # Resolution arguments (common patterns)
        cmd.extend(["-width", width, "-height", height, "-w", width, "-h", height])

        # Hz arguments if enabled
        if self.force_hz_check.isChecked():
            hz = str(self.hz_spin.value())
            cmd.extend(["-refresh", hz, "-hz", hz, "-freq", hz])

        # Windowed mode arguments if enabled
        if self.windowed_check.isChecked():
            cmd.extend(["-windowed", "-w", "-window"])

        try:
            subprocess.Popen(cmd)
            msg = f"Launched with {resolution_str}"
            if self.force_hz_check.isChecked():
                msg += f" @ {hz} Hz"
            if self.windowed_check.isChecked():
                msg += " (windowed)"
            self.status_bar.showMessage(msg, 3000)
            info_msg = f"Game launched with {resolution_str}"
            if self.force_hz_check.isChecked():
                info_msg += f" at {hz} Hz"
            if self.windowed_check.isChecked():
                info_msg += " in windowed mode"
            QMessageBox.information(self, "Launched", info_msg + ".")
        except Exception as e:
            QMessageBox.critical(self, "Launch Error", f"Failed to launch game:\n{str(e)}")

    # -------------------- Profile Management --------------------
    def save_profile(self):
        """Save current settings as a named profile."""
        if not self.current_exe:
            QMessageBox.warning(self, "No File", "Cannot save profile without a game executable.")
            return

        resolution = self.get_selected_resolution()
        if not resolution:
            QMessageBox.warning(self, "No Resolution", "Cannot save profile without a resolution.")
            return

        dialog = ProfileDialog(self, list(self.profiles.keys()))
        if dialog.exec() == QDialog.Accepted:
            name = dialog.get_profile_name()
            if not name:
                QMessageBox.warning(self, "Invalid Name", "Profile name cannot be empty.")
                return

            # Gather current settings
            self.profiles[name] = {
                'exe': self.current_exe,
                'resolution': resolution,
                'hz': self.hz_spin.value(),
                'force_hz': self.force_hz_check.isChecked(),
                'windowed': self.windowed_check.isChecked(),
                'default': self.default_check.isChecked()
            }
            self.settings.setValue("profiles", self.profiles)

            # Update profile combo
            self.profile_combo.clear()
            self.profile_combo.addItem("Select profile")
            self.profile_combo.addItems(self.profiles.keys())
            self.status_bar.showMessage(f"Profile '{name}' saved.", 3000)

    def on_profile_selected(self, index):
        """Load the selected profile."""
        if index == 0:  # placeholder
            return
        name = self.profile_combo.itemText(index)
        if name in self.profiles:
            profile = self.profiles[name]
            # Load executable
            self.set_current_exe(profile['exe'])

            # Load resolution
            resolution = profile.get('resolution', '1920x1080')
            if resolution in self.preset_resolutions:
                for radio in self.preset_radios:
                    if radio.text() == resolution:
                        radio.setChecked(True)
                        break
            else:
                # Assume custom
                try:
                    w, h = resolution.split('x')
                    self.custom_radio.setChecked(True)
                    self.width_spin.setValue(int(w))
                    self.height_spin.setValue(int(h))
                except:
                    pass

            # Load Hz, windowed, and default settings
            self.force_hz_check.setChecked(profile.get('force_hz', False))
            self.hz_spin.setValue(profile.get('hz', 60))
            self.windowed_check.setChecked(profile.get('windowed', False))
            self.default_check.setChecked(profile.get('default', False))

            # Enable/disable controls based on default flag
            self.on_default_toggled(self.default_check.isChecked())

            self.status_bar.showMessage(f"Profile '{name}' loaded.", 3000)

    def delete_profile(self):
        """Delete the currently selected profile."""
        current = self.profile_combo.currentText()
        if current == "Select profile" or current not in self.profiles:
            QMessageBox.information(self, "No Selection", "Select a profile to delete.")
            return

        reply = QMessageBox.question(
            self, "Confirm Delete",
            f"Delete profile '{current}'?",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            del self.profiles[current]
            self.settings.setValue("profiles", self.profiles)
            self.profile_combo.removeItem(self.profile_combo.currentIndex())
            self.status_bar.showMessage(f"Profile '{current}' deleted.", 3000)

    def update_status(self):
        """Update status bar with current selection."""
        if self.current_exe:
            if self.default_check.isChecked():
                self.status_bar.showMessage(f"Ready: {self.current_exe} (default settings)")
                return
            res = self.get_selected_resolution()
            if res:
                msg = f"Ready: {self.current_exe} @ {res}"
                if self.force_hz_check.isChecked():
                    msg += f" @ {self.hz_spin.value()} Hz"
                if self.windowed_check.isChecked():
                    msg += " (windowed)"
                self.status_bar.showMessage(msg)
            else:
                self.status_bar.showMessage(f"Ready: {self.current_exe} (no resolution)")
        else:
            self.status_bar.showMessage("No game selected.")


# -------------------------------
# Entry point
# -------------------------------
if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = GameLauncher()
    window.show()
    sys.exit(app.exec())