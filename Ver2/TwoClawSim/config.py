import math

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

FPS = 60
DT = 1/FPS

#speeds are in centimeter/sec, V in front
#distance is in centimeters, D in front (S for size)
#acceleration is in centimeters/second^2, A in front
#time is in seconds, T in front

VMAX_CLAW_X = 33.3 #claw max speed in X axis
A_CLAW_X = 150.0 #claw acceleration

VMAX_CLAW_Z = 5.0 #claw max lowering/raising speed
A_CLAW_Z = 30.0 #claw lowering/raising acceleration
#in Ver1 lowering/raising was 1.8s, translating to lowering Distance being 8.6cm
D_Z = 8.6 #distance from claw to scanner, (claw positioned above the scanner)
T_Z = timeToTravel(D_Z,0,VMAX_CLAW_Z, A_CLAW_Z) #time to lower claw

D_CLAW_SAFE_DISTANCE = 8.0 # safe distance to avoid claw collisions

S_W_SCANNER = 8.0
S_H_SCANNER = 15.0
T_SCAN = 18.0

N_BOXES = 10
