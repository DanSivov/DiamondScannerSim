# Ver3.5/main.py
"""
Main entry point for Ver3.5 Dual-Claw Simulation

Features:
- Single crane with two independent lowering mechanisms (blue left, red right)
- Crane moves only on X-axis at scanner level
- Moving plate handles Y-axis positioning
- Simplified logic - no collision detection needed
"""

import sys
from RealisticDualClawSim import config
from RealisticDualClawSim.simulation import run_simulation


def main():
    # Set UTF-8 encoding for Windows console
    if sys.platform == 'win32':
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

    print("\n")
    print("╔" + "═" * 68 + "╗")
    print("║" + " " * 10 + "VER3.5 REALISTIC DUAL-CLAW SIMULATION" + " " * 21 + "║")
    print("║" + " " * 14 + "Diamond Sorting System" + " " * 33 + "║")
    print("╚" + "═" * 68 + "╝")
    print("\n")

    config.print_config_summary()
    print("\n")

    if len(sys.argv) > 1 and sys.argv[1] == "--config":
        print("Configuration displayed. Exiting.")
        return

    print("\n" + "=" * 70)
    print("ARCHITECTURE OVERVIEW")
    print("=" * 70)
    print("\nKEY FEATURES:")
    print("  • Single crane body with two independent lowering mechanisms")
    print("  • Blue claw (left): Picks from START → Delivers to scanners")
    print("  • Red claw (right): Picks from scanners → Delivers to boxes")
    print("  • Crane moves only on X-axis (horizontal)")
    print("  • Moving plate handles Y-axis positioning")
    print("  • No collision detection needed (single crane)")
    print("\nCONTROLS:")
    print("  • Pause/Resume button to control simulation")
    print("  • Close window to exit")
    print("=" * 70 + "\n")

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
