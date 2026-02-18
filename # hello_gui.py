import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import cv2
import numpy as np
import pyautogui
import threading
from PIL import Image, ImageTk
import time
import os

class ScreenRecorder:
    def __init__(self, root):
        self.root = root
        self.root.title("Screen Recorder")
        self.root.geometry("800x600")
        
        # Recording variables
        self.recording = False
        self.video_writer = None
        self.selected_area = None
        self.output_file = None
        self.fps = 20
        self.codec = cv2.VideoWriter_fourcc(*'XVID')
        
        # Create GUI
        self.create_widgets()
        
    def create_widgets(self):
        # Main frame
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Preview area
        self.preview_label = ttk.Label(main_frame, text="Screen Preview", background='lightgray')
        self.preview_label.grid(row=0, column=0, columnspan=3, padx=5, pady=5, sticky=(tk.W, tk.E))
        self.preview_label.bind("<Button-1>", self.start_selection)
        self.preview_label.bind("<B1-Motion>", self.update_selection)
        self.preview_label.bind("<ButtonRelease-1>", self.end_selection)
        
        # Controls frame
        controls_frame = ttk.Frame(main_frame)
        controls_frame.grid(row=1, column=0, columnspan=3, pady=10, sticky=(tk.W, tk.E))
        
        # File selection
        ttk.Label(controls_frame, text="Save to:").grid(row=0, column=0, sticky=tk.W, padx=5)
        self.file_path = tk.StringVar()
        ttk.Entry(controls_frame, textvariable=self.file_path, width=50).grid(row=0, column=1, padx=5)
        ttk.Button(controls_frame, text="Browse", command=self.browse_file).grid(row=0, column=2, padx=5)
        
        # Record button
        self.record_btn = ttk.Button(controls_frame, text="Start Recording", command=self.toggle_recording)
        self.record_btn.grid(row=1, column=0, columnspan=3, pady=10)
        
        # Status label
        self.status_var = tk.StringVar(value="Ready to record")
        ttk.Label(controls_frame, textvariable=self.status_var).grid(row=2, column=0, columnspan=3)
        
        # Configure grid weights
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(0, weight=1)
        controls_frame.columnconfigure(1, weight=1)
        
        # Start preview
        self.update_preview()
        
    def browse_file(self):
        file_path = filedialog.asksaveasfilename(
            defaultextension=".avi",
            filetypes=[("AVI files", "*.avi"), ("MP4 files", "*.mp4"), ("All files", "*.*")]
        )
        if file_path:
            self.file_path.set(file_path)
            
    def start_selection(self, event):
        self.selection_start = (event.x, event.y)
        self.selection_rect = None
        
    def update_selection(self, event):
        if hasattr(self, 'selection_start'):
            x0, y0 = self.selection_start
            x1, y1 = event.x, event.y
            self.selection_rect = (min(x0, x1), min(y0, y1), abs(x1 - x0), abs(y1 - y1))
            self.draw_preview()
            
    def end_selection(self, event):
        if hasattr(self, 'selection_rect') and self.selection_rect:
            # Convert preview coordinates to screen coordinates
            preview_width = self.preview_label.winfo_width()
            preview_height = self.preview_label.winfo_height()
            
            # Get screen size
            screen_width, screen_height = pyautogui.size()
            
            # Calculate scale factors
            scale_x = screen_width / preview_width
            scale_y = screen_height / preview_height
            
            # Convert coordinates
            x, y, w, h = self.selection_rect
            self.selected_area = (
                int(x * scale_x),
                int(y * scale_y),
                int(w * scale_x),
                int(h * scale_y)
            )
            self.status_var.set(f"Selected area: {self.selected_area}")
            
    def draw_preview(self):
        if hasattr(self, 'current_photo'):
            # Create a copy of the current image
            img = self.current_image.copy()
            
            # Draw selection rectangle if exists
            if hasattr(self, 'selection_rect') and self.selection_rect:
                x, y, w, h = self.selection_rect
                cv2.rectangle(img, (x, y), (x + w, y + h), (0, 255, 0), 2)
                
            # Convert to PhotoImage and update label
            photo = ImageTk.PhotoImage(image=Image.fromarray(img))
            self.preview_label.configure(image=photo)
            self.preview_label.image = photo
            
    def update_preview(self):
        if not self.recording:
            # Capture screen
            screenshot = pyautogui.screenshot()
            self.current_image = cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2BGR)
            
            # Resize for preview
            preview_width = 800
            preview_height = 450
            preview_img = cv2.resize(self.current_image, (preview_width, preview_height))
            
            # Convert to PhotoImage
            self.current_photo = ImageTk.PhotoImage(image=Image.fromarray(preview_img))
            self.preview_label.configure(image=self.current_photo)
            self.preview_label.image = self.current_photo
            
            # Draw selection if exists
            self.draw_preview()
            
        # Schedule next update
        self.root.after(100, self.update_preview)
        
    def toggle_recording(self):
        if not self.recording:
            self.start_recording()
        else:
            self.stop_recording()
            
    def start_recording(self):
        if not self.file_path.get():
            messagebox.showerror("Error", "Please select an output file first")
            return
            
        if not self.selected_area:
            messagebox.showerror("Error", "Please select an area to record first")
            return
            
        self.recording = True
        self.record_btn.config(text="Stop Recording")
        self.status_var.set("Recording...")
        
        # Get screen dimensions
        x, y, w, h = self.selected_area
        
        # Initialize video writer
        self.video_writer = cv2.VideoWriter(
            self.file_path.get(), 
            self.codec, 
            self.fps, 
            (w, h)
        )
        
        # Start recording in a separate thread
        self.recording_thread = threading.Thread(target=self.record_screen)
        self.recording_thread.daemon = True
        self.recording_thread.start()
        
    def stop_recording(self):
        self.recording = False
        self.record_btn.config(text="Start Recording")
        self.status_var.set("Recording stopped. File saved.")
        
    def record_screen(self):
        x, y, w, h = self.selected_area
        
        while self.recording:
            # Capture screen
            screenshot = pyautogui.screenshot(region=(x, y, w, h))
            frame = np.array(screenshot)
            frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
            
            # Write to video file
            self.video_writer.write(frame)
            
            # Sleep for a while to maintain FPS
            time.sleep(1/self.fps)
            
        # Release video writer when done
        self.video_writer.release()

if __name__ == "__main__":
    root = tk.Tk()
    app = ScreenRecorder(root)
    root.mainloop()