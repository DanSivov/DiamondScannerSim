import sys
import tkinter as tk
from RealisticTwoClawSim import config
from RealisticTwoClawSim.simulation import run_simulation

def choose_mode():
    """Popup to choose simulation speed mode"""
    root = tk.Tk()
    root.title("Select Simulation Mode")

    choice = {"mode": None}

    def set_mode(mode):
        choice["mode"] = mode
        root.destroy()

    tk.Label(root, text="Choose Simulation Speed Mode:", font=("Arial", 12)).pack(pady=10)
    tk.Button(root, text="Realistic Speed", width=20, command=lambda: set_mode("normal")).pack(pady=5)
    tk.Button(root, text="Recommended Speed", width=20, command=lambda: set_mode("debug")).pack(pady=5)

    root.mainloop()
    return choice["mode"]

def main():
    print("\n")
    print("╔" + "═" * 68 + "╗")
    print("║" + " " * 10 + "VER3 REALISTIC TWO-CLAW SIMULATION" + " " * 24 + "║")
    print("║" + " " * 14 + "Diamond Sorting System" + " " * 33 + "║")
    print("╚" + "═" * 68 + "╝")
    print("\n")

    config.print_config_summary()
    print("\n")

    if len(sys.argv) > 1 and sys.argv[1] == "--config":
        print("Configuration displayed. Exiting.")
        return

    # Ask user for mode
    mode = choose_mode()
    if mode == "normal":
        config.SIM_SPEED_MULTIPLIER = 2.0
    else:
        config.SIM_SPEED_MULTIPLIER = 1.0  # ~3x slower for debugging

    try:
        run_simulation()
    except KeyboardInterrupt:
        print("\n\nSimulation interrupted by user.")
        sys.exit(0)
    except Exception as e:
        print(f"\n\nError during simulation: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    print("\nSimulation ended.")

if __name__ == "__main__":
    main()
