from PySide6.QtWidgets import QSystemTrayIcon, QMenu
from PySide6.QtGui import QIcon, QAction
from PySide6.QtCore import Signal

class TrayIcon(QSystemTrayIcon):
    show_window_signal = Signal()
    quit_signal = Signal()

    def __init__(self, icon: QIcon, parent=None):
        super().__init__(icon, parent)
        self.setToolTip("AirClicker - PPT Remote")
        self.setup_menu()
        self.activated.connect(self.on_activated)

    def setup_menu(self):
        menu = QMenu()
        menu.setStyleSheet("""
            QMenu {
                background-color: #2b2b2b;
                color: #ffffff;
                border: 1px solid #555;
            }
            QMenu::item::selected {
                background-color: #4CAF50;
            }
        """)
        
        show_action = QAction("Show Dashboard", menu)
        show_action.triggered.connect(self.show_window_signal.emit)
        menu.addAction(show_action)
        
        menu.addSeparator()
        
        quit_action = QAction("Quit AirClicker", menu)
        quit_action.triggered.connect(self.quit_signal.emit)
        menu.addAction(quit_action)
        
        self.setContextMenu(menu)

    def on_activated(self, reason):
        if reason == QSystemTrayIcon.Trigger:
            self.show_window_signal.emit()
