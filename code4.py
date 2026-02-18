import tkinter as tk

window = tk.Tk()
window.title("My App")
window.geometry("400x300")

label = tk.Label(window, text="Hello World ■", font=("Arial", 16))
label.pack()

window.mainloop()
