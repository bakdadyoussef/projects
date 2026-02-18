import tkinter as tk

window = tk.Tk()
window.title("Button App")
window.geometry("400x300")

button = tk.Button(window, text="Click Me")
button.pack()

window.mainloop()
