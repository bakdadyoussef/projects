import sys
import os
from pathlib import Path

from PySide6.QtCore import QThread, Signal, QUrl
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLineEdit, QPushButton, QComboBox, QProgressBar, QTextEdit,
    QFileDialog, QLabel, QMessageBox
)
from PySide6.QtGui import QFont

import yt_dlp


class DownloadWorker(QThread):
    """Worker thread that runs the yt-dlp download."""
    progress = Signal(dict)      # progress info (downloaded bytes, total, speed, etc.)
    log = Signal(str)            # status messages
    finished = Signal(bool, str) # success flag and message

    def __init__(self, url, download_path, format_choice):
        super().__init__()
        self.url = url
        self.download_path = download_path
        self.format_choice = format_choice  # 'video' or 'audio'

    def run(self):
        # Determine yt-dlp format based on user choice
        if self.format_choice == "audio":
            ydl_format = 'bestaudio/best'
            postprocessors = [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }]
        else:  # video
            ydl_format = 'bestvideo+bestaudio/best'
            postprocessors = [{
                'key': 'FFmpegVideoConvertor',
                'preferedformat': 'mp4',
            }]

        ydl_opts = {
            'format': ydl_format,
            'outtmpl': str(Path(self.download_path) / '%(title)s.%(ext)s'),
            'postprocessors': postprocessors,
            'progress_hooks': [self._progress_hook],
            'logger': self,  # yt-dlp will call our debug/warning/error methods
            'quiet': True,
            'no_warnings': False,
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                self.log.emit(f"Starting download: {self.url}")
                ydl.download([self.url])
            self.finished.emit(True, "Download completed successfully.")
        except Exception as e:
            self.finished.emit(False, f"Download failed: {str(e)}")

    def _progress_hook(self, d):
        """yt-dlp calls this with progress information."""
        if d['status'] == 'downloading':
            # Extract info for a nice progress display
            if 'total_bytes' in d:
                total = d['total_bytes']
            elif 'total_bytes_estimate' in d:
                total = d['total_bytes_estimate']
            else:
                total = 0

            downloaded = d.get('downloaded_bytes', 0)
            if total > 0:
                percent = downloaded / total * 100
                speed = d.get('speed', 0)
                speed_str = f"{speed / 1024:.1f} KB/s" if speed else "N/A"
                eta = d.get('eta', 0)
                eta_str = f"{eta}s" if eta else "N/A"

                self.progress.emit({
                    'percent': percent,
                    'downloaded': downloaded,
                    'total': total,
                    'speed': speed_str,
                    'eta': eta_str
                })
        elif d['status'] == 'finished':
            self.log.emit("Download finished, now processing...")

    # yt-dlp logger interface
    def debug(self, msg):
        self.log.emit(f"[DEBUG] {msg}")

    def warning(self, msg):
        self.log.emit(f"[WARNING] {msg}")

    def error(self, msg):
        self.log.emit(f"[ERROR] {msg}")


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Video Downloader")
        self.setMinimumSize(700, 500)

        # Central widget and layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)

        # URL input
        url_layout = QHBoxLayout()
        url_label = QLabel("URL:")
        self.url_edit = QLineEdit()
        self.url_edit.setPlaceholderText("Paste video URL here...")
        url_layout.addWidget(url_label)
        url_layout.addWidget(self.url_edit)
        layout.addLayout(url_layout)

        # Format selection
        format_layout = QHBoxLayout()
        format_label = QLabel("Format:")
        self.format_combo = QComboBox()
        self.format_combo.addItems(["Video (MP4)", "Audio only (MP3)"])
        format_layout.addWidget(format_label)
        format_layout.addWidget(self.format_combo)
        format_layout.addStretch()
        layout.addLayout(format_layout)

        # Download folder selection
        folder_layout = QHBoxLayout()
        self.folder_edit = QLineEdit()
        self.folder_edit.setReadOnly(True)
        self.folder_edit.setText(str(Path.home() / "Downloads"))  # default
        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self.browse_folder)
        folder_layout.addWidget(QLabel("Save to:"))
        folder_layout.addWidget(self.folder_edit)
        folder_layout.addWidget(browse_btn)
        layout.addLayout(folder_layout)

        # Download button and progress bar
        self.download_btn = QPushButton("Download")
        self.download_btn.clicked.connect(self.start_download)
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        layout.addWidget(self.progress_bar)
        layout.addWidget(self.download_btn)

        # Log area
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setFont(QFont("Courier", 9))
        layout.addWidget(self.log_text)

        # Worker thread reference
        self.worker = None

    def browse_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Download Folder")
        if folder:
            self.folder_edit.setText(folder)

    def start_download(self):
        url = self.url_edit.text().strip()
        if not url:
            QMessageBox.warning(self, "No URL", "Please enter a video URL.")
            return

        folder = self.folder_edit.text().strip()
        if not folder or not os.path.isdir(folder):
            QMessageBox.warning(self, "Invalid Folder", "Please select a valid download folder.")
            return

        # Determine format string for worker
        format_choice = "video" if self.format_combo.currentIndex() == 0 else "audio"

        # Disable button during download
        self.download_btn.setEnabled(False)
        self.log_text.clear()
        self.progress_bar.setValue(0)

        # Create and start worker thread
        self.worker = DownloadWorker(url, folder, format_choice)
        self.worker.progress.connect(self.update_progress)
        self.worker.log.connect(self.append_log)
        self.worker.finished.connect(self.download_finished)
        self.worker.start()

    def update_progress(self, info):
        percent = info['percent']
        self.progress_bar.setValue(int(percent))
        # Also show speed and eta in the log (optional)
        self.append_log(f"Progress: {percent:.1f}%  Speed: {info['speed']}  ETA: {info['eta']}")

    def append_log(self, message):
        self.log_text.append(message)
        # Auto-scroll to bottom
        cursor = self.log_text.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        self.log_text.setTextCursor(cursor)

    def download_finished(self, success, message):
        self.download_btn.setEnabled(True)
        if success:
            self.progress_bar.setValue(100)
            QMessageBox.information(self, "Success", message)
        else:
            QMessageBox.critical(self, "Error", message)
        self.worker = None


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())