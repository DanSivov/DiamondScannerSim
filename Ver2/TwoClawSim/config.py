import math
"""
Changed the Config to be more in line with the config values from Ver3/RealisticTwoClawSim/config.py
"""

# Functions
def timeToTravel(D, V_INIT, V_MAX, A):
    # Distance needed to reach vmax
    S_VMAX = (V_MAX**2 - V_INIT**2) / (2 * A)

    if S_VMAX >= D:
        # Never reach vmax – solve s = ut + 0.5*a*t^2
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


# Variables

FPS = 60
DT = 1 / FPS

# Speeds are now in mm/s
# Distances in mm
# Accelerations in mm/s²
# Time in seconds

VMAX_CLAW_X = 333.0   # mm/s (was 33.3 cm/s)
A_CLAW_X   = 1500.0   # mm/s² (was 150.0 cm/s²)

VMAX_CLAW_Z = 50.0    # mm/s (was 5.0 cm/s)
A_CLAW_Z    = 300.0   # mm/s² (was 30.0 cm/s²)

# In Ver1 lowering/raising was 1.8s, translating to lowering Distance being 8.6 cm
D_Z = 86.0            # mm (was 8.6 cm)
T_Z = timeToTravel(D_Z, 0, VMAX_CLAW_Z, A_CLAW_Z)

D_CLAW_SAFE_DISTANCE = 80.0  # mm (was 8.0 cm)

# Scanner dimensions
S_W_SCANNER = 80.0    # mm (was 8.0 cm)
S_H_SCANNER = 150.0   # mm (was 15.0 cm)

T_SCAN = 18.0         # seconds (unchanged)

# Number of boxes (unchanged)
N_BOXES = 10


