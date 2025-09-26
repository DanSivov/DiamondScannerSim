# main.py
# Launcher: choose number of scanners (1–4) and start the simulation.

import tkinter as tk
from TwoClaw import run_simulation

def launch(n):
    root.destroy()
    run_simulation(n)

root = tk.Tk()
root.title("Conveyor simulation launcher")

label = tk.Label(root, text="Select number of scanners (1–4):", font=("Segoe UI", 14))
label.pack(padx=16, pady=(16, 8))

btn_frame = tk.Frame(root)
btn_frame.pack(padx=16, pady=(0, 16))

for n in range(1, 5):
    tk.Button(
        btn_frame,
        text=str(n),
        font=("Segoe UI", 14),
        width=4,
        command=lambda k=n: launch(k)
    ).grid(row=0, column=n-1, padx=6, pady=6)

root.mainloop()
