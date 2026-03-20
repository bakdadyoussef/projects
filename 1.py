import sys
import subprocess
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QRadioButton, QButtonGroup, QLabel, QFileDialog, QMessageBox
)
from PySide6.QtCore import Qt


class GameLauncher(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Game Resolution Launcher")
        self.setMinimumSize(400, 300)

        # Store the path of the selected .exe file
        self.exe_path = ""

        # Common resolutions (you can add or remove as needed)
        self.resolutions = [
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

        # Central widget and main layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        # --- File selection row ---
        file_layout = QHBoxLayout()
        self.file_label = QLabel("No file selected")
        self.file_label.setWordWrap(True)
        browse_btn = QPushButton("Browse for .exe")
        browse_btn.clicked.connect(self.browse_exe)
        file_layout.addWidget(self.file_label)
        file_layout.addWidget(browse_btn)
        main_layout.addLayout(file_layout)

        # --- Resolution selection area ---
        res_label = QLabel("Select resolution (only one can be chosen):")
        main_layout.addWidget(res_label)

        # Button group to enforce mutual exclusivity
        self.res_group = QButtonGroup(self)
        # Optional: make the group exclusive (already default for QRadioButton)
        self.res_group.setExclusive(True)

        # Create a radio button for each resolution and add to layout
        for res in self.resolutions:
            radio = QRadioButton(res)
            # If you want to use QCheckBox instead, replace QRadioButton with QCheckBox
            # and uncomment the next line to make them exclusive:
            # radio.setCheckable(True)
            self.res_group.addButton(radio)
            main_layout.addWidget(radio)

        # (Optional) select the first resolution by default
        if self.res_group.buttons():
            self.res_group.buttons()[0].setChecked(True)

        # --- Launch button ---
        launch_btn = QPushButton("Launch Game")
        launch_btn.clicked.connect(self.launch_game)
        main_layout.addWidget(launch_btn, alignment=Qt.AlignCenter)

        # Stretch to keep everything at the top
        main_layout.addStretch()

    def browse_exe(self):
        """Open a file dialog to choose an .exe file."""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select Game Executable", "", "Executable Files (*.exe);;All Files (*)"
        )
        if file_path:
            self.exe_path = file_path
            self.file_label.setText(f"Selected: {file_path}")

    def launch_game(self):
        """Launch the selected .exe with the chosen resolution arguments."""
        # Check if an executable has been selected
        if not self.exe_path:
            QMessageBox.warning(self, "No File", "Please select a game executable first.")
            return

        # Find which resolution is selected
        selected_button = self.res_group.checkedButton()
        if selected_button is None:
            QMessageBox.warning(self, "No Resolution", "Please select a resolution.")
            return

        resolution_str = selected_button.text()
        try:
            width, height = resolution_str.split('x')
        except ValueError:
            QMessageBox.critical(self, "Error", f"Invalid resolution format: {resolution_str}")
            return

        # Build the command. Many games accept arguments like -w, -width, -W, etc.
        # Here we use two common patterns: -width / -height and -w / -h.
        # You can modify this list or make it configurable.
        # We'll try both and let the game ignore the ones it doesn't understand.
        cmd = [
            self.exe_path,
            "-width", width,
            "-height", height,
            "-w", width,
            "-h", height
        ]

        try:
            # Launch the process (detached from the GUI so it doesn't block)
            subprocess.Popen(cmd)
            QMessageBox.information(self, "Launched", f"Game launched with resolution {resolution_str}.")
        except Exception as e:
            QMessageBox.critical(self, "Launch Error", f"Failed to launch game:\n{str(e)}")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = GameLauncher()
    window.show()
    sys.exit(app.exec())