import sys
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QSlider, QLabel, QFileDialog
)
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
from PySide6.QtCore import Qt, QUrl


class AudioPlayer(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Simple Audio Player")
        self.setMinimumSize(400, 150)

        # Central widget and main layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        # Label to show current file
        self.file_label = QLabel("No file loaded")
        self.file_label.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(self.file_label)

        # Control buttons layout
        controls_layout = QHBoxLayout()

        # Open file button
        self.open_btn = QPushButton("Open File")
        self.open_btn.clicked.connect(self.open_file)
        controls_layout.addWidget(self.open_btn)

        # Play / Pause button
        self.play_btn = QPushButton("Play")
        self.play_btn.setEnabled(False)
        self.play_btn.setCheckable(True)
        self.play_btn.clicked.connect(self.play_pause)
        controls_layout.addWidget(self.play_btn)

        # Mute button
        self.mute_btn = QPushButton("Mute")
        self.mute_btn.setCheckable(True)
        self.mute_btn.clicked.connect(self.toggle_mute)
        controls_layout.addWidget(self.mute_btn)

        main_layout.addLayout(controls_layout)

        # Volume slider
        volume_layout = QHBoxLayout()
        volume_layout.addWidget(QLabel("Volume"))
        self.volume_slider = QSlider(Qt.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(70)  # default volume
        self.volume_slider.valueChanged.connect(self.change_volume)
        volume_layout.addWidget(self.volume_slider)
        main_layout.addLayout(volume_layout)

        # Create media player and audio output
        self.player = QMediaPlayer()
        self.audio_output = QAudioOutput()
        self.player.setAudioOutput(self.audio_output)

        # Set initial volume
        self.audio_output.setVolume(0.7)  # 70%

        # Connect player state to update play button
        self.player.playbackStateChanged.connect(self.update_play_button)

        # When media changes, update file label and enable play button
        self.player.sourceChanged.connect(self.update_file_label)

    def open_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Open Audio File", "", "Audio Files (*.mp3 *.wav *.ogg *.flac *.m4a)"
        )
        if file_path:
            self.player.setSource(QUrl.fromLocalFile(file_path))
            self.play_btn.setEnabled(True)

    def play_pause(self):
        if self.player.playbackState() == QMediaPlayer.PlayingState:
            self.player.pause()
        else:
            self.player.play()

    def toggle_mute(self, checked):
        self.audio_output.setMuted(checked)
        self.mute_btn.setText("Unmute" if checked else "Mute")

    def change_volume(self, value):
        # volume expects a qreal between 0.0 and 1.0
        self.audio_output.setVolume(value / 100.0)

    def update_play_button(self, state):
        if state == QMediaPlayer.PlayingState:
            self.play_btn.setText("Pause")
            self.play_btn.setChecked(True)
        else:
            self.play_btn.setText("Play")
            self.play_btn.setChecked(False)

    def update_file_label(self, source):
        if source.isEmpty():
            self.file_label.setText("No file loaded")
        else:
            # Extract file name from URL
            file_name = source.fileName()
            self.file_label.setText(f"Now playing: {file_name}")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = AudioPlayer()
    window.show()
    sys.exit(app.exec())