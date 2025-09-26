# Main.py
# Launcher: choose n of scanners (1-4)

import tkinter as tk
from TwoClawSim import TwoClaw


def launch(n):
    root.destroy()
    TwoClaw.runSimulation(n) #Launcher

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
