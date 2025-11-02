# Ver3/RealisticTwoClawSim/config.py
"""
Configuration for Ver3 Realistic Two-Claw Diamond Sorting Simulation

This config contains:
1. Real-world measurements and positions (in mm)
2. Movement dynamics (speeds, accelerations, timing)
3. Scanner and box configurations
"""

import math

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================
def distance_with_time_mm(v0: float, vmax: float, a: float, t: float) -> float:
    """
    Calculate distance traveled given initial velocity, max velocity,
    acceleration, and elapsed time. All units in mm and seconds.

    Parameters:
        v0 (float): initial velocity (mm/s)
        vmax (float): maximum velocity (mm/s)
        a (float): constant acceleration (mm/s^2)
        t (float): elapsed time (s)

    Returns:
        float: distance traveled (mm)
    """
    if a < 0:
        raise ValueError("Acceleration must be non-negative.")
    if vmax < v0:
        raise ValueError("Max velocity must be >= initial velocity.")
    if t < 0:
        raise ValueError("Time must be non-negative.")

    v_t = v0 + a * t

    if v_t <= vmax:
        # Still accelerating
        return v0 * t + 0.5 * a * t**2
    else:
        # Accelerate until vmax, then continue at vmax
        t_acc = (vmax - v0) / a
        s_acc = v0 * t_acc + 0.5 * a * t_acc**2
        t_const = t - t_acc
        s_const = vmax * t_const
        return s_acc + s_const

def timeToTravel(D, V_INIT, V_MAX, A):
    """
    Calculate time to travel distance D with initial velocity V_INIT,
    max velocity V_MAX, and acceleration A

    Returns: time in seconds
    """
    # Distance needed to reach vmax
    S_VMAX = (V_MAX**2 - V_INIT**2) / (2 * A)
    if S_VMAX >= D:
        # Never reach vmax – solve s = ut + 0.5*a*t^2
        # 0.5*a*t^2 + u*t - distance = 0
        a = 0.5 * A
        b = V_INIT
        c = -D
        t = (-b + math.sqrt(b**2 - 4*a*c)) / (2*a)
        return t
    else:
        # Accelerate to vmax
        t_accel = (V_MAX - V_INIT) / A
        s_const = D - S_VMAX
        t_const = s_const / V_MAX
        return t_accel + t_const

def mm_to_display(mm):
    """Convert millimeters to display units (for visualization)"""
    return mm / 10.0

def display_to_mm(display_units):
    """Convert display units back to millimeters"""
    return display_units * 10.0

# ============================================================================
# SIMULATION PARAMETERS
# ============================================================================

FPS = 60
DT = 1.0 / FPS
SIM_SPEED_MULTIPLIER = 1.0

# ============================================================================
# MOVEMENT DYNAMICS (in mm/s and mm/s²)
# ============================================================================

# X-axis movement (horizontal along rail)
VMAX_CLAW_X = 333.0  # mm/s (33.3 cm/s from Ver2)
A_CLAW_X = 1500.0    # mm/s² (150 cm/s² from Ver2)

# Y-axis movement (horizontal perpendicular to rail)
VMAX_CLAW_Y = 333.0  # mm/s (same as X)
A_CLAW_Y = 1500.0    # mm/s² (same as X)

# Z-axis movement (vertical lowering/raising)
VMAX_CLAW_Z = 100.0   # mm/s (5.0 cm/s from Ver2)
A_CLAW_Z = 300.0     # mm/s² (30 cm/s² from Ver2)
D_Z = distance_with_time_mm(0, VMAX_CLAW_Z, A_CLAW_Z, 1.8)           # mm (8.6 cm from Ver2) - distance from rail to pickup/drop point

# Calculate vertical movement time
T_Z = timeToTravel(D_Z, 0, VMAX_CLAW_Z, A_CLAW_Z)

# Safety distances
D_CLAW_SAFE_DISTANCE = 80.0  # mm minimum distance between cranes on shared rail

# ============================================================================
# SCANNER CONFIGURATION
# ============================================================================

T_SCAN = 18.0  # seconds - time to scan a diamond
S_W_SCANNER = 80.0  # mm - scanner width
S_H_SCANNER = 150.0  # mm - scanner height

# Scanner positions (symmetric around center)
SCANNER_Y = 60.0  # mm - Y position of scanners
SCANNER_SPACING = 356.0  # mm - distance between scanner centers
SCANNER_1_X = -178.0  # mm - left scanner X position
SCANNER_2_X = 178.0   # mm - right scanner X position

SCANNER_DROP_RADIUS = 1.5  # 1-2mm radius circle

# Scanner state label offset (distance below scanner in mm)
SCANNER_STATE_LABEL_OFFSET = 20.0

# ============================================================================
# END BOX CONFIGURATION
# ============================================================================

N_BOXES = 8  # Total number of end boxes (2 rows × 4 columns)

# End box grid layout
BOX_ROWS = 2
BOX_COLS = 4
BOX_START_X = -60.0   # mm - left edge of box grid
BOX_END_X = 60.0      # mm - right edge of box grid
BOX_START_Y = 80.0    # mm - bottom edge of box grid
BOX_END_Y = 120.0     # mm - top edge of box grid
BOX_SPACING_X = (BOX_END_X - BOX_START_X) / (BOX_COLS - 1)
BOX_SPACING_Y = (BOX_END_Y - BOX_START_Y) / (BOX_ROWS - 1)
BOX_RADIUS = 15.0  # mm - visual radius for display

# ============================================================================
# RAIL AND CRANE POSITIONS
# ============================================================================

RAIL_Y = 200.0  # mm - Y position of the rail
RAIL_X_MIN = -400.0  # mm - left extent of rail (EXTENDED)
RAIL_X_MAX = 400.0   # mm - right extent of rail (EXTENDED)

# Crane home positions (far apart to avoid blocking scanners)
BLUE_CRANE_HOME_X = -320.0  # mm - blue crane waits far left
BLUE_CRANE_HOME_Y = SCANNER_Y  # mm - at scanner level
RED_CRANE_HOME_X = 320.0   # mm - red crane waits far right
RED_CRANE_HOME_Y = SCANNER_Y  # mm - at scanner level

# Crane dimensions
CRANE_WIDTH = 30.0   # mm
CRANE_HEIGHT = 28.0  # mm

# ============================================================================
# PICKUP ZONE CONFIGURATION
# ============================================================================

PICKUP_X = 0.0      # mm - pickup zone at center X
PICKUP_Y = 0.0      # mm - pickup zone at center Y (origin)
PICKUP_RADIUS = 20.0  # mm - visual radius for display

# ============================================================================
# DISPLAY SETTINGS
# ============================================================================

DISPLAY_SCALE = 0.005  # Scale factor for converting mm to display units
DISPLAY_WIDTH = 14  # Display width in units
DISPLAY_HEIGHT = 10  # Display height in units

# Colors
COLOR_BLUE_CLAW = '#1f77b4'
COLOR_RED_CLAW = '#d62728'
COLOR_SCANNER = '#00CED1'  # Cyan like in the image
COLOR_PICKUP = '#90EE90'   # Light green
COLOR_END_BOX = '#FFD700'  # Gold
COLOR_RAIL = '#2F4F4F'     # Dark gray
COLOR_DIAMOND = '#FFD54F'  # Yellow diamond

# ============================================================================
# HELPER FUNCTIONS FOR POSITIONS
# ============================================================================

def get_scanner_positions():
    """Returns list of (x, y) tuples for all scanner positions"""
    return [
        (SCANNER_1_X, SCANNER_Y),
        (SCANNER_2_X, SCANNER_Y)
    ]

def get_end_box_positions():
    """Returns list of (x, y) tuples for all end box positions in grid layout"""
    positions = []
    for row in range(BOX_ROWS):
        for col in range(BOX_COLS):
            x = BOX_START_X + col * BOX_SPACING_X
            y = BOX_START_Y + row * BOX_SPACING_Y
            positions.append((x, y))
    return positions

def get_end_box_by_index(index):
    """Get the (x, y) position of a specific end box by index (0 to N_BOXES-1)"""
    if not (0 <= index < N_BOXES):
        raise ValueError(f"Box index {index} out of range [0, {N_BOXES-1}]")

    positions = get_end_box_positions()
    return positions[index]

def get_pickup_position():
    """Returns (x, y) tuple for pickup zone"""
    return (PICKUP_X, PICKUP_Y)

def calculate_2d_travel_time(x0, y0, x1, y1):
    """
    Calculate time to travel from (x0, y0) to (x1, y1)
    Both X and Y can move simultaneously with their respective dynamics

    Returns: time in seconds
    """
    dx = abs(x1 - x0)
    dy = abs(y1 - y0)

    # Calculate time for each axis independently
    time_x = timeToTravel(dx, 0, VMAX_CLAW_X, A_CLAW_X) if dx > 0 else 0
    time_y = timeToTravel(dy, 0, VMAX_CLAW_Y, A_CLAW_Y) if dy > 0 else 0

    # Since both axes can move simultaneously, total time is the maximum
    return max(time_x, time_y)

# ============================================================================
# CONFIGURATION SUMMARY
# ============================================================================

def print_config_summary():
    """Print a summary of the configuration"""
    print("=" * 70)
    print("VER3 REALISTIC TWO-CLAW SIMULATION CONFIGURATION")
    print("=" * 70)
    print("\nMOVEMENT DYNAMICS:")
    print(f"  X-axis: Vmax={VMAX_CLAW_X} mm/s, A={A_CLAW_X} mm/s²")
    print(f"  Y-axis: Vmax={VMAX_CLAW_Y} mm/s, A={A_CLAW_Y} mm/s²")
    print(f"  Z-axis: Vmax={VMAX_CLAW_Z} mm/s, A={A_CLAW_Z} mm/s², Distance={D_Z} mm")
    print(f"  Vertical movement time: {T_Z:.3f}s")

    print("\nSCANNERS:")
    print(f"  Number: 2")
    print(f"  Scan time: {T_SCAN}s")
    print(f"  Positions: {get_scanner_positions()}")

    print("\nEND BOXES:")
    print(f"  Number: {N_BOXES} ({BOX_ROWS}×{BOX_COLS} grid)")
    print(f"  Positions: {get_end_box_positions()}")

    print("\nRAIL:")
    print(f"  Y position: {RAIL_Y} mm")
    print(f"  X extent: [{RAIL_X_MIN}, {RAIL_X_MAX}] mm")

    print("\nCRANE HOMES:")
    print(f"  Blue: ({BLUE_CRANE_HOME_X}, {BLUE_CRANE_HOME_Y}) mm")
    print(f"  Red: ({RED_CRANE_HOME_X}, {RED_CRANE_HOME_Y}) mm")

    print("\nPICKUP ZONE:")
    print(f"  Position: ({PICKUP_X}, {PICKUP_Y}) mm (origin)")

    print("=" * 70)