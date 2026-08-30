from PySide6.QtWidgets import QMainWindow, QTabWidget, QWidget, QVBoxLayout
from PySide6.QtGui import QIcon, QCloseEvent
from .tabs.home_tab import HomeTab
from .tabs.mappings_tab import MappingsTab
from .tabs.settings_tab import SettingsTab
from .tabs.help_tab import HelpTab
from core.listener import MediaKeyListener
from core.config import config

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("AirClicker")
        self.setMinimumSize(700, 500)
        
        self.listener_thread = MediaKeyListener(self)
        
        self.setup_ui()

    def setup_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        layout = QVBoxLayout(central_widget)
        layout.setContentsMargins(15, 15, 15, 15)
        
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet("""
            QTabBar::tab {
                padding: 10px 20px;
                font-size: 14px;
                font-weight: bold;
                background: #333;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
                margin-right: 2px;
            }
            QTabBar::tab:selected {
                background: #4CAF50;
                color: white;
            }
            QTabWidget::pane {
                border: 1px solid #444;
                top: -1px;
                background: #2a2a2a;
                border-bottom-left-radius: 5px;
                border-bottom-right-radius: 5px;
                border-top-right-radius: 5px;
            }
        """)
        
        self.home_tab = HomeTab()
        self.mappings_tab = MappingsTab()
        self.settings_tab = SettingsTab()
        self.help_tab = HelpTab()
        
        # Tab content wrapper
        for tab in [self.home_tab, self.mappings_tab, self.settings_tab, self.help_tab]:
            tab.setStyleSheet("QWidget { background: #2a2a2a; }")

        self.tabs.addTab(self.home_tab, "Dashboard")
        self.tabs.addTab(self.mappings_tab, "Mappings")
        self.tabs.addTab(self.settings_tab, "Settings")
        self.tabs.addTab(self.help_tab, "Help")
        
        layout.addWidget(self.tabs)
        
        # Connect signals
        self.home_tab.toggle_listener_signal.connect(self.toggle_listener)

    def toggle_listener(self, is_active):
        if is_active:
            self.listener_thread.start()
        else:
            self.listener_thread.stop()

    def closeEvent(self, event: QCloseEvent):
        # Determine if we should minimize to tray
        if config.get_setting("minimize_to_tray"):
            event.ignore()
            self.hide()
        else:
            self.cleanup()
            event.accept()

    def cleanup(self):
        self.listener_thread.stop()
