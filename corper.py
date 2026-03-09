import sys
import os
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QSlider, QFileDialog, QMessageBox
)
from PySide6.QtCore import Qt, QThread, Signal, Slot
from moviepy.editor import VideoFileClip


class SaveThread(QThread):
    """Thread for saving the video clip without freezing the GUI."""
    finished = Signal(str)  # emits output path when done
    error = Signal(str)     # emits error message if something fails

    def __init__(self, video_path, start_time, end_time, output_path):
        super().__init__()
        self.video_path = video_path
        self.start_time = start_time
        self.end_time = end_time
        self.output_path = output_path

    def run(self):
        try:
            # Load the video, extract subclip, and write it
            with VideoFileClip(self.video_path) as clip:
                subclip = clip.subclip(self.start_time, self.end_time)
                subclip.write_videofile(
                    self.output_path,
                    codec='libx264',
                    audio_codec='aac',
                    temp_audiofile='temp-audio.m4a',
                    remove_temp=True,
                    logger=None  # disable verbose output
                )
            self.finished.emit(self.output_path)
        except Exception as e:
            self.error.emit(str(e))


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("1‑Minute Video Trimmer")
        self.setMinimumSize(400, 200)

        # Central widget and main layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)

        # Load button and file info
        self.load_btn = QPushButton("Load Video")
        self.load_btn.clicked.connect(self.load_video)
        layout.addWidget(self.load_btn)

        self.file_label = QLabel("No video loaded")
        self.file_label.setWordWrap(True)
        layout.addWidget(self.file_label)

        # Slider and time info
        slider_layout = QHBoxLayout()
        self.start_label = QLabel("Start: 0.0 s")
        self.slider = QSlider(Qt.Horizontal)
        self.slider.setEnabled(False)
        self.slider.valueChanged.connect(self.slider_changed)
        self.end_label = QLabel("End: 60.0 s")
        slider_layout.addWidget(self.start_label)
        slider_layout.addWidget(self.slider)
        slider_layout.addWidget(self.end_label)
        layout.addLayout(slider_layout)

        # Save button and status
        self.save_btn = QPushButton("Save Cropped Video")
        self.save_btn.setEnabled(False)
        self.save_btn.clicked.connect(self.save_video)
        layout.addWidget(self.save_btn)

        self.status_label = QLabel("")
        layout.addWidget(self.status_label)

        # Data members
        self.video_path = None
        self.duration = 0.0
        self.start_time = 0.0
        self.save_thread = None

    def load_video(self):
        """Open a file dialog, load the video, and initialise the slider."""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select a video file", "",
            "Video files (*.mp4 *.avi *.mov *.mkv *.flv *.wmv);;All files (*.*)"
        )
        if not file_path:
            return

        try:
            # Get video duration without loading the whole clip
            with VideoFileClip(file_path) as clip:
                self.duration = clip.duration
            self.video_path = file_path
            self.file_label.setText(f"Loaded: {os.path.basename(file_path)}\nDuration: {self.duration:.2f} s")

            # Configure slider: if video shorter than 60s, use whole video
            if self.duration <= 60:
                self.slider.setEnabled(False)
                self.start_time = 0.0
                self.start_label.setText(f"Start: 0.0 s")
                self.end_label.setText(f"End: {self.duration:.2f} s")
                QMessageBox.information(self, "Info", "Video is shorter than 1 minute.\nThe whole video will be saved.")
            else:
                self.slider.setEnabled(True)
                self.slider.setRange(0, int((self.duration - 60) * 10))  # tenths of a second
                self.slider.setValue(0)
                self.start_time = 0.0
                self.start_label.setText("Start: 0.0 s")
                self.end_label.setText(f"End: 60.0 s")

            self.save_btn.setEnabled(True)
            self.status_label.setText("")

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not load video:\n{str(e)}")

    def slider_changed(self, value):
        """Update the displayed start and end times when the slider moves."""
        # Slider stores tenths of seconds for finer control
        self.start_time = value / 10.0
        self.start_label.setText(f"Start: {self.start_time:.1f} s")
        end_time = self.start_time + 60.0
        self.end_label.setText(f"End: {end_time:.1f} s")

    def save_video(self):
        """Start the saving thread."""
        if not self.video_path:
            return

        # Ask for output file name
        output_path, _ = QFileDialog.getSaveFileName(
            self, "Save cropped video as",
            os.path.splitext(os.path.basename(self.video_path))[0] + "_cropped.mp4",
            "MP4 files (*.mp4);;All files (*.*)"
        )
        if not output_path:
            return

        # Ensure .mp4 extension
        if not output_path.lower().endswith('.mp4'):
            output_path += '.mp4'

        # Compute end time
        if self.duration <= 60:
            start = 0.0
            end = self.duration
        else:
            start = self.start_time
            end = self.start_time + 60.0

        # Disable buttons during save
        self.load_btn.setEnabled(False)
        self.save_btn.setEnabled(False)
        self.status_label.setText("Saving... please wait")

        # Create and start the save thread
        self.save_thread = SaveThread(self.video_path, start, end, output_path)
        self.save_thread.finished.connect(self.on_save_finished)
        self.save_thread.error.connect(self.on_save_error)
        self.save_thread.start()

    @Slot(str)
    def on_save_finished(self, output_path):
        """Called when saving completes successfully."""
        self.load_btn.setEnabled(True)
        self.save_btn.setEnabled(True)
        self.status_label.setText(f"Saved successfully to:\n{output_path}")
        QMessageBox.information(self, "Success", f"Video saved to:\n{output_path}")
        self.save_thread = None

    @Slot(str)
    def on_save_error(self, error_msg):
        """Called if an error occurs during saving."""
        self.load_btn.setEnabled(True)
        self.save_btn.setEnabled(True)
        self.status_label.setText("Save failed")
        QMessageBox.critical(self, "Error", f"Could not save video:\n{error_msg}")
        self.save_thread = None


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())