# Main.py
# Launcher: choose n of scanners (1-2) and configure settings

import tkinter as tk
from tkinter import messagebox
from TwoClawSim import TwoClaw
from TwoClawSim import config
from ConfigDialog import show_config_dialog
import importlib


class LauncherWindow:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Conveyor Simulation Launcher")
        self.selected_scanners = None

        # Main frame
        main_frame = tk.Frame(self.root, padx=20, pady=20)
        main_frame.pack()

        # Title
        title_label = tk.Label(main_frame,
                               text="Conveyor Belt Simulator",
                               font=("Segoe UI", 18, "bold"))
        title_label.pack(pady=(0, 10))

        # Scanner selection
        scanner_label = tk.Label(main_frame,
                                 text="Select number of scanners (1–2):",
                                 font=("Segoe UI", 14))
        scanner_label.pack(padx=16, pady=(16, 8))

        # Scanner buttons - CHANGED to only 1-2
        btn_frame = tk.Frame(main_frame)
        btn_frame.pack(padx=16, pady=(0, 16))

        for n in range(1, 3):  # Changed from range(1, 5) to range(1, 3)
            tk.Button(
                btn_frame,
                text=str(n),
                font=("Segoe UI", 14),
                width=4,
                command=lambda k=n: self.select_scanners(k)
            ).grid(row=0, column=n-1, padx=6, pady=6)

        # Configuration button
        config_btn = tk.Button(
            main_frame,
            text="⚙ Configuration Settings",
            font=("Segoe UI", 12),
            command=self.show_config,
            bg="#e0e0e0"
        )
        config_btn.pack(pady=10)

        # Status label
        self.status_label = tk.Label(main_frame,
                                     text="Please select number of scanners to begin",
                                     font=("Segoe UI", 10),
                                     fg="gray")
        self.status_label.pack(pady=(10, 0))

    def select_scanners(self, n):
        """Handle scanner selection and launch immediately"""
        self.selected_scanners = n

        # Update status
        self.status_label.config(
            text=f"Selected: {n} scanner{'s' if n > 1 else ''}. Launching simulation...",
            fg="green"
        )

        # Reload config and TwoClaw modules to pick up any saved changes
        from TwoClawSim import config
        importlib.reload(config)
        importlib.reload(TwoClaw)

        # Launch directly with current config.py values
        self.root.destroy()
        TwoClaw.runSimulation(self.selected_scanners)

    def show_config(self):
        """Show configuration dialog for editing settings"""
        result = show_config_dialog(self.root)
        if result:
            # Reload the config module to pick up saved changes
            importlib.reload(config)

            messagebox.showinfo(
                "Configuration Saved",
                "Configuration has been saved to file.\nSelect scanners to launch the simulation with new settings.",
                parent=self.root
            )

    def run(self):
        """Start the launcher"""
        self.root.mainloop()


if __name__ == "__main__":
    launcher = LauncherWindow()
    launcher.run()