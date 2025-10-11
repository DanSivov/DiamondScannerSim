import tkinter as tk
from tkinter import ttk, messagebox
from TwoClawSim import config
import os
import importlib

class ConfigDialog:
    def __init__(self, parent):
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Simulation Configuration")
        self.dialog.geometry("500x700")
        self.dialog.resizable(False, False)

        # Make dialog modal
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.config_values = {}
        self.result = None

        # Store config file path
        self.config_path = os.path.join(os.path.dirname(config.__file__), 'config.py')

        self.create_widgets()

        # Center the dialog
        self.dialog.update_idletasks()
        x = (self.dialog.winfo_screenwidth() // 2) - (self.dialog.winfo_width() // 2)
        y = (self.dialog.winfo_screenheight() // 2) - (self.dialog.winfo_height() // 2)
        self.dialog.geometry(f'+{x}+{y}')

    def create_widgets(self):
        # Main frame with padding
        main_frame = ttk.Frame(self.dialog, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Title
        title_label = ttk.Label(main_frame, text="Simulation Configuration",
                                font=('Arial', 14, 'bold'))
        title_label.pack(pady=(0, 20))

        # Create scrollable frame for config entries
        self.canvas = tk.Canvas(main_frame, height=450)
        scrollbar = ttk.Scrollbar(main_frame, orient="vertical", command=self.canvas.yview)
        scrollable_frame = ttk.Frame(self.canvas)

        scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )

        self.canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=scrollbar.set)

        # Bind mouse wheel scrolling
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)  # Windows and MacOS
        self.canvas.bind_all("<Button-4>", self._on_mousewheel)    # Linux scroll up
        self.canvas.bind_all("<Button-5>", self._on_mousewheel)    # Linux scroll down

        # Configuration sections based on actual config.py
        self.create_section(scrollable_frame, "Simulation Settings", [
            ("FPS (Frames Per Second)", "FPS", config.FPS),
        ])

        self.create_section(scrollable_frame, "Claw Movement - X Axis (cm/s)", [
            ("Max Speed X", "VMAX_CLAW_X", config.VMAX_CLAW_X),
            ("Acceleration X", "A_CLAW_X", config.A_CLAW_X),
        ])

        self.create_section(scrollable_frame, "Claw Movement - Z Axis (cm/s)", [
            ("Max Speed Z", "VMAX_CLAW_Z", config.VMAX_CLAW_Z),
            ("Acceleration Z", "A_CLAW_Z", config.A_CLAW_Z),
            ("Lowering Distance (cm)", "D_Z", config.D_Z),
        ])

        self.create_section(scrollable_frame, "Safety & Spacing", [
            ("Safe Distance Between Claws (cm)", "D_CLAW_SAFE_DISTANCE", config.D_CLAW_SAFE_DISTANCE),
        ])

        self.create_section(scrollable_frame, "Scanner Settings (cm)", [
            ("Scanner Width", "S_W_SCANNER", config.S_W_SCANNER),
            ("Scanner Height", "S_H_SCANNER", config.S_H_SCANNER),
            ("Scan Time (seconds)", "T_SCAN", config.T_SCAN),
        ])

        self.create_section(scrollable_frame, "System Settings", [
            ("Number of End Boxes", "N_BOXES", config.N_BOXES),
        ])

        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Buttons frame with better layout
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(pady=(20, 0), fill=tk.X)

        # Top row: Reset and Update buttons (left side, same size)
        top_row = ttk.Frame(button_frame)
        top_row.pack(fill=tk.X, pady=(0, 10))

        reset_btn = ttk.Button(top_row, text="Reset",
                               command=self.reset_to_defaults,
                               width=15)
        reset_btn.pack(side=tk.LEFT, padx=(0, 5))

        update_btn = ttk.Button(top_row, text="Update",
                                command=self.update_config,
                                width=15)
        update_btn.pack(side=tk.LEFT)

        # Bottom row: Cancel and Apply buttons (right side)
        bottom_row = ttk.Frame(button_frame)
        bottom_row.pack(fill=tk.X)

        # Apply & Start button
        apply_btn = ttk.Button(bottom_row, text="Apply",
                               command=self.apply,
                               width=15)
        apply_btn.pack(side=tk.RIGHT)

        # Cancel button
        cancel_btn = ttk.Button(bottom_row, text="Cancel",
                                command=self.cancel,
                                width=15)
        cancel_btn.pack(side=tk.RIGHT, padx=(0, 5))

    def _on_mousewheel(self, event):
        """Handle mouse wheel scrolling"""
        if event.num == 4 or event.delta > 0:  # Scroll up (Linux or Windows/Mac)
            self.canvas.yview_scroll(-1, "units")
        elif event.num == 5 or event.delta < 0:  # Scroll down (Linux or Windows/Mac)
            self.canvas.yview_scroll(1, "units")

    def create_section(self, parent, title, fields):
        # Section frame
        section_frame = ttk.LabelFrame(parent, text=title, padding="10")
        section_frame.pack(fill=tk.X, padx=5, pady=5)

        for label_text, config_key, _ in fields:
            row_frame = ttk.Frame(section_frame)
            row_frame.pack(fill=tk.X, pady=3)

            # Label
            label = ttk.Label(row_frame, text=label_text + ":", width=30, anchor='w')
            label.pack(side=tk.LEFT)

            # Get current value from config (not the default passed in)
            current_value = getattr(config, config_key)

            # Entry
            entry_var = tk.StringVar(value=str(current_value))
            entry = ttk.Entry(row_frame, textvariable=entry_var, width=15)
            entry.pack(side=tk.LEFT, padx=10)

            # Store reference (no need to store default anymore)
            self.config_values[config_key] = {
                'var': entry_var,
                'label': label_text
            }

    def validate_inputs(self):
        """Validate all input fields"""
        errors = []

        for key, data in self.config_values.items():
            value = data['var'].get().strip()

            # Check if empty
            if not value:
                errors.append(f"'{data['label']}' cannot be empty")
                continue

            # Check if valid number
            try:
                num_value = float(value)

                # Additional validation
                if key in ["N_BOXES", "FPS"]:
                    if num_value < 1 or num_value != int(num_value):
                        errors.append(f"'{data['label']}' must be a positive integer")
                elif num_value <= 0:
                    errors.append(f"'{data['label']}' must be greater than 0")

            except ValueError:
                errors.append(f"'{data['label']}' must be a valid number")

        return errors

    def update_config_values(self):
        """Update config values from the dialog entries"""
        for key, data in self.config_values.items():
            value = data['var'].get().strip()

            # Convert to appropriate type
            if key in ["N_BOXES", "FPS"]:
                setattr(config, key, int(float(value)))
            else:
                setattr(config, key, float(value))

        # Recalculate derived values
        config.DT = 1 / config.FPS
        config.T_Z = config.timeToTravel(config.D_Z, 0, config.VMAX_CLAW_Z, config.A_CLAW_Z)

    def save_config_to_file(self):
        """Write current config values to the config.py file"""
        try:
            config_content = f'''import math

#Functions
def timeToTravel(D,V_INIT,V_MAX,A):
    # Distance needed to reach vmax
    S_VMAX = (V_MAX**2 - V_INIT**2) / (2 * A)

    if S_VMAX >= D:
        # Never reach vmax — solve s = ut + 0.5*a*t^2
        # 0.5*a*t^2 + u*t - distance = 0
        A = 0.5 * A
        B = V_INIT
        C = -D
        t = (-B + math.sqrt(B**2 - 4*A*C)) / (2*A)
        return t
    else:
        # Accelerate to vmax
        t_accel = (V_MAX - V_INIT) / A
        s_const = D - S_VMAX
        t_const = s_const / V_MAX
        return t_accel + t_const



#Variables

FPS = {config.FPS}
DT = 1/FPS

#speeds are in centimeter/sec, V in front
#distance is in centimeters, D in front (S for size)
#acceleration is in centimeters/second^2, A in front
#time is in seconds, T in front

VMAX_CLAW_X = {config.VMAX_CLAW_X} #claw max speed in X axis
A_CLAW_X = {config.A_CLAW_X} #claw acceleration

VMAX_CLAW_Z = {config.VMAX_CLAW_Z} #claw max lowering/raising speed
A_CLAW_Z = {config.A_CLAW_Z} #claw lowering/raising acceleration
#in Ver1 lowering/raising was 1.8s, translating to lowering Distance being 8.6cm
D_Z = {config.D_Z} #distance from claw to scanner, (claw positioned above the scanner)
T_Z = timeToTravel(D_Z,0,VMAX_CLAW_Z, A_CLAW_Z) #time to lower claw

D_CLAW_SAFE_DISTANCE = {config.D_CLAW_SAFE_DISTANCE} # safe distance to avoid claw collisions

S_W_SCANNER = {config.S_W_SCANNER}
S_H_SCANNER = {config.S_H_SCANNER}
T_SCAN = {config.T_SCAN}

N_BOXES = {config.N_BOXES}
'''

            with open(self.config_path, 'w') as f:
                f.write(config_content)

            return True
        except Exception as e:
            messagebox.showerror("Error Saving Config",
                                 f"Failed to save configuration file:\n{str(e)}",
                                 parent=self.dialog)
            return False

    def reload_config_from_file(self):
        """Reload config values from the config.py file"""
        try:
            # Reload the config module
            importlib.reload(config)

            # Update all entry fields with reloaded values
            for key, data in self.config_values.items():
                current_value = getattr(config, key)
                data['var'].set(str(current_value))

            return True
        except Exception as e:
            messagebox.showerror("Error Loading Config",
                                 f"Failed to reload configuration file:\n{str(e)}",
                                 parent=self.dialog)
            return False

    def update_config(self):
        """Update configuration in memory only (does NOT save to file)"""
        # Validate inputs
        errors = self.validate_inputs()

        if errors:
            error_message = "Please fix the following errors:\n\n" + "\n".join(f"• {err}" for err in errors)
            messagebox.showerror("Configuration Error", error_message, parent=self.dialog)
            return

        # Update config values in memory only
        self.update_config_values()

        # Show success message
        messagebox.showinfo("Configuration Updated",
                            "Configuration has been updated in memory!\n\nNote: Changes are not saved to file yet.\nClick 'Apply & Start' to save and launch.",
                            parent=self.dialog)

    def apply(self):
        """Apply configuration, save to file, and close dialog"""
        # Validate inputs
        errors = self.validate_inputs()

        if errors:
            error_message = "Please fix the following errors:\n\n" + "\n".join(f"• {err}" for err in errors)
            messagebox.showerror("Configuration Error", error_message, parent=self.dialog)
            return

        # Update config values in memory
        self.update_config_values()

        # Save to config.py file
        if not self.save_config_to_file():
            return  # Don't close if save failed

        self.result = True
        self.dialog.destroy()

    def cancel(self):
        """Cancel and close dialog"""
        self.result = False
        self.dialog.destroy()

    def reset_to_defaults(self):
        """Reset all fields to values from the config file"""
        if messagebox.askyesno("Reset Configuration",
                               "Reset all values to the last saved configuration?",
                               parent=self.dialog):
            self.reload_config_from_file()

    def show(self):
        """Show dialog and wait for result"""
        self.dialog.wait_window()
        return self.result


def show_config_dialog(parent=None):
    """
    Show configuration dialog and return True if applied, False if cancelled

    Args:
        parent: Parent window (optional)

    Returns:
        bool: True if configuration was applied, False if cancelled
    """
    if parent is None:
        root = tk.Tk()
        root.withdraw()
        parent = root

    dialog = ConfigDialog(parent)
    return dialog.show()