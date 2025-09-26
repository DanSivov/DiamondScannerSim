# TwoClaw.py
# Conveyor Flow Simulation (ggplot) with 1–4 scanners.
# - Blue crane: Start → nearest EMPTY scanner (pre-staging near target) → return & preload next
# - Red crane: READY scanner → End → return (FCFS by ready time; schedules to meet earliest finishing scan)
# - Controls: Pause/Resume, Jump-to-time, Diamonds/minute

import math
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
from matplotlib.patches import Circle, Rectangle, RegularPolygon
from matplotlib.widgets import Button, TextBox

# -----------------------------
# Utility
# -----------------------------
def make_diamond(x, y, color, size=0.18, z=6):
    return RegularPolygon(
        (x, y), numVertices=4, radius=size, orientation=math.pi/4,
        facecolor=color, edgecolor='black', lw=1.0, zorder=z
    )

# -----------------------------
# Public entry point
# -----------------------------
def run_simulation(N_SCANNERS: int = 1):
    assert 1 <= N_SCANNERS <= 4, "N_SCANNERS must be 1..4"

    # -----------------------------
    # Style & figure
    # -----------------------------
    plt.style.use('ggplot')
    fig, ax = plt.subplots(figsize=(11, 5.5))
    plt.subplots_adjust(bottom=0.22)
    ax.set_xlim(0, 11)
    ax.set_ylim(0, 9.6)
    ax.set_aspect('equal')
    ax.axis('off')

    # -----------------------------
    # Layout
    # -----------------------------
    TOP_Y = 7.5
    RAIL_Y = 1.0
    CARRY_Y = 4.0
    START_X = 1.2
    END_X = 9.8

    # Evenly place scanners around center while keeping margins
    center = 5.5
    spacing = 1.6  # distance between scanners
    if N_SCANNERS == 1:
        scanner_xs = [center]
    else:
        total_span = spacing * (N_SCANNERS - 1)
        left = center - total_span / 2
        scanner_xs = [left + i * spacing for i in range(N_SCANNERS)]

    # Process line
    ax.plot([START_X + 0.35, END_X - 0.35], [TOP_Y, TOP_Y], color='gray', linewidth=2, alpha=0.6)

    # Start/End circles
    start_circle = Circle((START_X, TOP_Y), 0.35, fc='white', ec='black', lw=2, zorder=2)
    end_circle = Circle((END_X, TOP_Y), 0.35, fc='white', ec='black', lw=2, zorder=2)
    ax.add_patch(start_circle)
    ax.add_patch(end_circle)
    ax.text(START_X, TOP_Y - 0.8, "start", ha='center')
    ax.text(END_X, TOP_Y - 0.8, "end", ha='center')

    # Counters
    delivered = 0
    start_count_text = ax.text(START_X, TOP_Y + 0.8, "∞", ha='center', va='center', fontsize=10)
    end_count_text = ax.text(END_X, TOP_Y + 0.8, f"{delivered}", ha='center', va='center', fontsize=10)

    # Scanners
    SCANNER_W, SCANNER_H = 1.5, 0.8

    scanner_rects = []
    scanner_labels = []
    scanner_state = []      # "EMPTY" | "SCANNING" | "READY"
    scanner_timer = []      # remaining time if SCANNING
    scanner_ready_since = []  # timestamp when became READY (for FCFS red)
    diamond_scanners = []

    for i, sx in enumerate(scanner_xs):
        r = Rectangle((sx - SCANNER_W/2, TOP_Y - SCANNER_H/2),
                      SCANNER_W, SCANNER_H, fc='white', ec='black', lw=2, zorder=2)
        ax.add_patch(r)
        scanner_rects.append(r)
        lab = ax.text(sx, TOP_Y, f"scanner {i+1}", ha='center', va='center', fontsize=9)
        scanner_labels.append(lab)
        scanner_state.append("EMPTY")
        scanner_timer.append(0.0)
        scanner_ready_since.append(None)
        d = make_diamond(sx, TOP_Y, '#ffd54f'); d.set_visible(False); ax.add_patch(d)
        diamond_scanners.append(d)

    # Per-scanner ready-wait tracking and labels
    ready_wait_start = [None for _ in range(N_SCANNERS)]
    ready_wait_labels = []
    for i, sx in enumerate(scanner_xs):
        lbl = ax.text(sx, TOP_Y + 0.9, "", ha='center', va='bottom',
                      color='red', fontsize=10, fontweight='bold', zorder=10)
        ready_wait_labels.append(lbl)

    # Rail
    ax.plot([0.6, 10.4], [RAIL_Y, RAIL_Y], color='black', lw=4, alpha=0.85, solid_capstyle='round')

    # -----------------------------
    # Dynamic elements
    # -----------------------------
    BLUE_COLOR = '#1f77b4'
    RED_COLOR = '#d62728'
    CRANE_W, CRANE_H = 0.6, 0.28

    blue_x = START_X
    red_x = END_X

    blue_crane = Rectangle((blue_x - CRANE_W/2, RAIL_Y - CRANE_H/2), CRANE_W, CRANE_H,
                           fc=BLUE_COLOR, ec='black', lw=1.5, zorder=5)
    red_crane = Rectangle((red_x - CRANE_W/2, RAIL_Y - CRANE_H/2), CRANE_W, CRANE_H,
                          fc=RED_COLOR, ec='black', lw=1.5, zorder=5)
    ax.add_patch(blue_crane)
    ax.add_patch(red_crane)

    blue_hoist, = ax.plot([], [], color=BLUE_COLOR, lw=2, zorder=4)
    red_hoist,  = ax.plot([], [], color=RED_COLOR, lw=2, zorder=4)
    blue_hoist.set_visible(False)
    red_hoist.set_visible(False)

    # Diamonds
    diamond_blue = make_diamond(START_X, TOP_Y, '#33a3ff'); ax.add_patch(diamond_blue)
    diamond_red = make_diamond(scanner_xs[0], CARRY_Y, '#66bb6a'); diamond_red.set_visible(False); ax.add_patch(diamond_red)

    # Delivered pile
    delivered_pile = []

    # Timer and metrics
    timer_text = ax.text(5.5, 9.2, "Time: 0.0 s", ha='center', fontsize=12, fontweight='bold')
    throughput_text = ax.text(10.6, 7.0, "Diamonds/min: --", ha='left', fontsize=11, fontweight='bold')
    total_ready_wait = 0.0
    total_wait_text = ax.text(10.6, 6.6, "Total ready-wait: 0.0 s",ha='left', fontsize=11, fontweight='bold', color='black')

    # -----------------------------
    # Simulation parameters
    # -----------------------------
    FPS = 60
    DT = 1.0 / FPS
    V_TRAVERSE = 3.0

    # Two-phase vertical motions
    LOWER_TIME = 1.8   # extend
    RAISE_TIME = 1.8    # retract

    # Keep your original names if you reference them elsewhere (metrics/display)
    PICK_TIME = LOWER_TIME + RAISE_TIME
    DROP_TIME = LOWER_TIME + RAISE_TIME
    SCAN_TIME = 15.0
    SAFE_DISTANCE = 0.8
    ARRIVE_EPS = 1e-6

    t_elapsed = 0.0
    last_minute_update = 0.0
    delivered_at_last_update = 0

    # Travel helpers
    def travel_time(x0, x1):
        return abs(x1 - x0) / V_TRAVERSE

    # Blue FSM
    # PICK_AT_START -> MOVE_TO_SCANNER -> WAIT_AT_STAGING -> DROP_AT_SCANNER -> RETURN_TO_START
    blue_state = "PICK_AT_START"
    blue_action_timer = PICK_TIME
    blue_has_diamond = False
    blue_target_i = None  # index of target scanner

    # Red FSM
    # WAIT -> MOVE_TO_SCANNER -> PICK_AT_SCANNER -> MOVE_TO_END -> DROP_AT_END -> RETURN_TO_SCANNER
    red_state = "WAIT"
    red_action_timer = 0.0
    red_has_diamond = False
    red_target_i = None
    red_departure_time = float('inf')
    red_time_under_scanner = 0.0

    # --- Red FSM new phases ---
    # vertical split for pick and drop
    # (LOWER_* means lowering hoist; *_RAISE means raising/retracting hoist)
    # These are *phases* within the broader red_state values.
    # You’ll drive them in your FSM logic.
    red_lower_start_time = float('inf')   # planned time to start lowering for a pick
    red_lower_planned_for_i = None        # which scanner that plan was for

    # --- Blue FSM new phases ---
    # for two-phase pick from start and two-phase drop to scanner
    blue_pick_phase = None        # "LOWER" or "RAISE"
    blue_drop_phase = None        # "LOWER" or "RAISE"

    # --- Red FSM new phases ---
    red_pick_phase = None         # "LOWER" or "RAISE"
    red_drop_phase = None         # "LOWER" or "RAISE"

    is_paused = False

    # -----------------------------
    # Helpers
    # -----------------------------
    def update_crane_positions():
        blue_crane.set_xy((blue_x - CRANE_W/2, RAIL_Y - CRANE_H/2))
        red_crane.set_xy((red_x - CRANE_W/2, RAIL_Y - CRANE_H/2))

    def set_hoist(line, x, y_top, show):
        if show:
            line.set_data([x, x], [RAIL_Y, y_top])
            line.set_visible(True)
        else:
            line.set_visible(False)

    def add_delivered_marker():
        nonlocal delivered
        delivered += 1
        end_count_text.set_text(f"{delivered}")
        idx = len(delivered_pile)
        cols = 5
        dx = (idx % cols) * 0.12 - 0.24
        dy = (idx // cols) * 0.12
        d = make_diamond(END_X + dx, TOP_Y + dy, '#66bb6a', size=0.16, z=3)
        delivered_pile.append(d)
        ax.add_patch(d)

    def clear_delivered_markers():
        while delivered_pile:
            d = delivered_pile.pop(); d.remove()

    def update_throughput():
        current_minute = t_elapsed / 60.0
        if current_minute >= 1.0:
            throughput_text.set_text(f"Diamonds/min: {delivered / current_minute:.1f}")
        else:
            throughput_text.set_text("Diamonds/min: --")

    def set_scanner_visuals():
        for i in range(N_SCANNERS):
            st = scanner_state[i]
            if st == "SCANNING":
                scanner_rects[i].set_edgecolor('#f39c12'); scanner_rects[i].set_linewidth(2.4)
            elif st == "READY":
                scanner_rects[i].set_edgecolor('#27ae60'); scanner_rects[i].set_linewidth(2.4)
            else:
                scanner_rects[i].set_edgecolor('black'); scanner_rects[i].set_linewidth(2.0)

    def cranes_would_collide(blue_pos, red_pos):
        return abs(blue_pos - red_pos) < SAFE_DISTANCE

    def staging_x_for(i):
        return scanner_xs[i] - SAFE_DISTANCE - 1e-3

    def nearest_empty_scanner(from_x):
        empties = [i for i in range(N_SCANNERS) if scanner_state[i] == "EMPTY"]
        if not empties:
            return None
        return min(empties, key=lambda i: abs(scanner_xs[i] - from_x))

    def earliest_ready_scanner():
        ready = [(i, scanner_ready_since[i]) for i in range(N_SCANNERS) if scanner_state[i] == "READY"]
        if not ready:
            return None
        ready.sort(key=lambda t: t[1])
        return ready[0][0]

    def earliest_finishing_scan():
        scanning = [(i, scanner_timer[i]) for i in range(N_SCANNERS) if scanner_state[i] == "SCANNING"]
        if not scanning:
            return None
        # choose the one finishing soonest (smallest remaining timer)
        scanning.sort(key=lambda t: t[1])
        return scanning[0][0]

    def schedule_red_departure():
        nonlocal red_departure_time, red_target_i
        nonlocal red_lower_start_time, red_lower_planned_for_i

        # If there is READY, go now (and lower immediately)
        i_ready = earliest_ready_scanner()
        if i_ready is not None:
            red_target_i = i_ready
            red_lower_start_time = t_elapsed                 # can start lowering now
            red_lower_planned_for_i = i_ready
            red_departure_time = t_elapsed
            return

        # Otherwise target earliest finishing SCANNING
        i_scan = earliest_finishing_scan()
        if i_scan is None:
            return  # leave any existing plan as-is

        target_x = scanner_xs[i_scan]
        t_travel = travel_time(red_x, target_x)

        # Plan to finish LOWER exactly at READY:
        #   lower_start = (now + remaining_scan) - LOWER_TIME
        t_ready = t_elapsed + scanner_timer[i_scan]
        plan_lower_start = t_ready - LOWER_TIME
        depart = plan_lower_start - t_travel

        # Only set if we don't already have a plan, or this is sooner
        if red_departure_time == float('inf') or depart < red_departure_time:
            red_target_i = i_scan
            red_lower_start_time = plan_lower_start
            red_lower_planned_for_i = i_scan
            red_departure_time = max(depart, t_elapsed)

    # -----------------------------
    # Reset (for skip backward)
    # -----------------------------
    def reset_simulation():
        nonlocal blue_pick_phase, blue_drop_phase
        nonlocal red_pick_phase, red_drop_phase
        nonlocal red_lower_start_time, red_lower_planned_for_i
        nonlocal t_elapsed, delivered
        nonlocal blue_x, red_x
        nonlocal blue_state, blue_action_timer, blue_has_diamond, blue_target_i
        nonlocal red_state, red_action_timer, red_has_diamond, red_target_i, red_departure_time
        nonlocal last_minute_update, delivered_at_last_update
        nonlocal total_ready_wait
        nonlocal red_time_under_scanner

        t_elapsed = 0.0
        timer_text.set_text("Time: 0.0 s")
        last_minute_update = 0.0
        delivered_at_last_update = 0
        throughput_text.set_text("Diamonds/min: --")

        blue_x = START_X; red_x = END_X
        update_crane_positions()
        set_hoist(blue_hoist, blue_x, TOP_Y, False)
        set_hoist(red_hoist, red_x, TOP_Y, False)

        diamond_blue.set_visible(True); diamond_blue.xy = (START_X, TOP_Y)
        diamond_red.set_visible(False)

        # scanners reset
        for i in range(N_SCANNERS):
            scanner_state[i] = "EMPTY"
            scanner_timer[i] = 0.0
            scanner_ready_since[i] = None
            diamond_scanners[i].set_visible(False)
            diamond_scanners[i].set_facecolor('#ffd54f')
        set_scanner_visuals()
        for i in range(N_SCANNERS):
            ready_wait_start[i] = None
            ready_wait_labels[i].set_text("")
        total_ready_wait = 0.0
        total_wait_text.set_text("Total ready-wait: 0.0 s")


        delivered = 0
        end_count_text.set_text(f"{delivered}")
        clear_delivered_markers()

        blue_state = "PICK_AT_START"
        blue_action_timer = PICK_TIME
        blue_has_diamond = False
        blue_target_i = None

        red_state = "WAIT"
        red_action_timer = 0.0
        red_has_diamond = False
        red_target_i = None
        red_departure_time = float('inf')
        red_time_under_scanner = 0.0

        blue_pick_phase = None
        blue_drop_phase = None
        red_pick_phase = None
        red_drop_phase = None
        red_lower_start_time = float('inf')
        red_lower_planned_for_i = None

        fig.canvas.draw_idle()

    # init visuals
    reset_simulation()

    # -----------------------------
    # Simulation step
    # -----------------------------
    def step_sim(dt):
        nonlocal t_elapsed
        nonlocal blue_x, blue_state, blue_action_timer, blue_has_diamond, blue_target_i
        nonlocal red_x, red_state, red_action_timer, red_has_diamond, red_target_i, red_departure_time
        nonlocal total_ready_wait
        nonlocal red_lower_start_time, red_lower_planned_for_i
        nonlocal red_time_under_scanner

        # time
        t_elapsed += dt
        timer_text.set_text(f"Time: {t_elapsed:0.1f} s")
        # throughput update each minute rollover
        current_minute = int(t_elapsed / 60.0)
        last_checked_minute = int((t_elapsed - dt) / 60.0)
        if current_minute > last_checked_minute and current_minute > 0:
            update_throughput()

        # --- scanners progression ---
        for i in range(N_SCANNERS):
            if scanner_state[i] == "SCANNING":
                diamond_scanners[i].set_facecolor('#ffd54f')
                scanner_timer[i] -= dt
                if scanner_timer[i] <= 0:
                    scanner_state[i] = "READY"
                    scanner_ready_since[i] = t_elapsed
                    diamond_scanners[i].set_facecolor('#66bb6a')
                    # start ready-wait timer
                    ready_wait_start[i] = t_elapsed
                    ready_wait_labels[i].set_text("")
        set_scanner_visuals()

        PENALTY_THRESHOLD = 0.0  # seconds before showing timer

        # Update per-scanner ready-wait labels (only show if penalty)
        for i in range(N_SCANNERS):
            if scanner_state[i] == "READY" and ready_wait_start[i] is not None:
                wait_time = t_elapsed - ready_wait_start[i]
                if wait_time > PENALTY_THRESHOLD:
                    ready_wait_labels[i].set_text(f"{wait_time:.1f}")
                else:
                    ready_wait_labels[i].set_text("")
            else:
                ready_wait_labels[i].set_text("")

        # >>> EARLY-DEPARTURE POLL GOES HERE <<<
        if all(st == "SCANNING" for st in scanner_state) and earliest_ready_scanner() is None \
                and red_state == "WAIT" and red_departure_time == float('inf'):
            i_scan = earliest_finishing_scan()
            if i_scan is not None:
                rem = scanner_timer[i_scan]
                tt  = travel_time(red_x, scanner_xs[i_scan])
                red_target_i = i_scan
                t_ready = t_elapsed + rem
                red_lower_start_time = t_ready - LOWER_TIME
                red_lower_planned_for_i = i_scan
                red_departure_time = max(red_lower_start_time - tt, t_elapsed)

        # --- Blue logic ---
        if blue_state == "PICK_AT_START":
            if blue_action_timer == PICK_TIME:
                diamond_blue.set_visible(True)
                diamond_blue.xy = (START_X, TOP_Y)
                set_hoist(blue_hoist, blue_x, TOP_Y, True)
            blue_action_timer -= dt
            prog = max(0.0, min(1.0, 1.0 - blue_action_timer / PICK_TIME))
            y = TOP_Y + (CARRY_Y - TOP_Y) * prog
            diamond_blue.xy = (START_X, y)
            set_hoist(blue_hoist, blue_x, y, True)
            if blue_action_timer <= 0:
                blue_has_diamond = True
                diamond_blue.xy = (blue_x, CARRY_Y)
                set_hoist(blue_hoist, blue_x, CARRY_Y, False)
                blue_target_i = nearest_empty_scanner(blue_x)
                if blue_target_i is None:
                    # stage near the earliest READY if exists; otherwise near earliest finishing scan
                    j = earliest_ready_scanner()
                    if j is None:
                        j = earliest_finishing_scan()
                    blue_target_i = j if j is not None else 0
                blue_state = "MOVE_TO_SCANNER"

        elif blue_state == "MOVE_TO_SCANNER":
            target_i = blue_target_i
            sx = scanner_xs[target_i]
            want_scanner = (scanner_state[target_i] == "EMPTY") and (not cranes_would_collide(sx, red_x))
            target_x = sx if want_scanner else max(START_X, staging_x_for(target_i))
            step = V_TRAVERSE * dt
            new_pos = blue_x + step if blue_x < target_x else max(blue_x - step, target_x)
            if not cranes_would_collide(new_pos, red_x):
                blue_x = new_pos
            if blue_has_diamond:
                diamond_blue.xy = (blue_x, CARRY_Y)
            # retarget if a closer EMPTY appears
            if scanner_state[target_i] != "EMPTY":
                alt = nearest_empty_scanner(blue_x)
                if alt is not None and alt != target_i:
                    blue_target_i = alt
            # arrival checks
            if abs(blue_x - sx) <= ARRIVE_EPS and scanner_state[target_i] == "EMPTY":
                blue_state = "DROP_AT_SCANNER"
                blue_action_timer = DROP_TIME
                set_hoist(blue_hoist, blue_x, CARRY_Y, True)
            elif abs(blue_x - target_x) <= ARRIVE_EPS and not want_scanner:
                blue_state = "WAIT_AT_STAGING"

        elif blue_state == "WAIT_AT_STAGING":
            target_i = blue_target_i
            sx = scanner_xs[target_i]
            can_advance = (scanner_state[target_i] == "EMPTY") and (not cranes_would_collide(sx, red_x))
            if can_advance:
                blue_state = "MOVE_TO_SCANNER"

        elif blue_state == "DROP_AT_SCANNER":
            blue_action_timer -= dt
            prog = max(0.0, min(1.0, 1.0 - blue_action_timer / DROP_TIME))
            y = CARRY_Y + (TOP_Y - CARRY_Y) * prog
            diamond_blue.xy = (scanner_xs[blue_target_i], y)
            set_hoist(blue_hoist, blue_x, y, True)
            if blue_action_timer <= 0:
                # deposit and start scanning
                diamond_blue.set_visible(False)
                di = blue_target_i
                ds = diamond_scanners[di]
                ds.set_visible(True); ds.xy = (scanner_xs[di], TOP_Y)
                scanner_state[di] = "SCANNING"
                scanner_timer[di] = SCAN_TIME
                scanner_ready_since[di] = None
                blue_has_diamond = False
                set_hoist(blue_hoist, blue_x, TOP_Y, False)
                blue_state = "RETURN_TO_START"
                schedule_red_departure()

        elif blue_state == "RETURN_TO_START":
            step = V_TRAVERSE * dt
            new_pos = max(blue_x - step, START_X)
            if not cranes_would_collide(new_pos, red_x):
                blue_x = new_pos
            if blue_x <= START_X + 1e-6:
                blue_state = "PICK_AT_START"
                blue_action_timer = PICK_TIME

        # --- Red logic ---
        if red_state == "WAIT":
            ready_exists = earliest_ready_scanner() is not None
            should_depart = (red_departure_time <= t_elapsed and red_departure_time < float('inf'))

            # first-cycle optimisation — nothing READY yet, all SCANNING
            if not ready_exists and all(st == "SCANNING" for st in scanner_state) and red_departure_time == float('inf'):
                i_scan = earliest_finishing_scan()
                if i_scan is not None:
                    t_travel = travel_time(red_x, scanner_xs[i_scan])
                    t_ready  = t_elapsed + scanner_timer[i_scan]
                    red_target_i = i_scan
                    red_lower_start_time = t_ready - LOWER_TIME
                    red_lower_planned_for_i = i_scan
                    red_departure_time = max(red_lower_start_time - t_travel, t_elapsed)

            if ready_exists:
                red_target_i = earliest_ready_scanner()
                red_state = "MOVE_TO_SCANNER"
                red_departure_time = float('inf')
            elif should_depart:
                red_state = "MOVE_TO_SCANNER"
                red_departure_time = float('inf')
            else:
                # don't overwrite an existing plan
                if red_departure_time == float('inf'):
                    schedule_red_departure()

        elif red_state == "MOVE_TO_SCANNER":
            if red_target_i is None:
                red_state = "WAIT"
            else:
                sx = scanner_xs[red_target_i]
                step = V_TRAVERSE * dt
                new_pos = red_x - step if red_x > sx else min(red_x + step, sx)
                if not cranes_would_collide(blue_x, new_pos):
                    red_x = new_pos

                # arrival check
                # arrival check (allow equality tolerance)
                if abs(red_x - sx) <= ARRIVE_EPS:
                    if scanner_state[red_target_i] == "READY":
                        # Arrived and it's READY now: pick immediately (raise phase)
                        close_ready_wait(red_target_i)
                        red_state = "PICK_AT_SCANNER"
                        red_action_timer = RAISE_TIME
                        set_hoist(red_hoist, red_x, TOP_Y, True)
                        red_time_under_scanner = 0.0
                    else:
                        # Not READY yet: enter controlled pre-lowering so we can finish exactly at READY.
                        remaining_lower = max(0.0, LOWER_TIME - red_time_under_scanner)
                        red_state = "LOWER_FOR_PICK"
                        red_action_timer = remaining_lower
                        # Draw the current hoist position to match accrued lowering
                        frac = 1.0 - (red_action_timer / LOWER_TIME) if LOWER_TIME > 0 else 1.0
                        y = RAIL_Y + (TOP_Y - RAIL_Y) * frac
                        set_hoist(red_hoist, red_x, y, True)

        elif red_state == "PICK_AT_SCANNER":
            red_action_timer -= dt
            prog = max(0.0, min(1.0, 1.0 - red_action_timer / RAISE_TIME))
            y = TOP_Y + (CARRY_Y - TOP_Y) * prog
            diamond_scanners[red_target_i].xy = (scanner_xs[red_target_i], y)
            if red_action_timer <= 0:
                # lift complete → scanner becomes EMPTY
                ds = diamond_scanners[red_target_i]
                ds.set_visible(False)
                diamond_red.set_visible(True)
                diamond_red.xy = (red_x, CARRY_Y)
                set_hoist(red_hoist, red_x, CARRY_Y, False)
                red_has_diamond = True
                scanner_state[red_target_i] = "EMPTY"
                scanner_ready_since[red_target_i] = None
                red_state = "MOVE_TO_END"
                red_time_under_scanner = 0.0

        elif red_state == "MOVE_TO_END":
            step = V_TRAVERSE * dt
            new_pos = min(red_x + step, END_X)
            if not cranes_would_collide(blue_x, new_pos):
                red_x = new_pos
            if red_has_diamond:
                diamond_red.xy = (red_x, CARRY_Y)
            if red_x >= END_X - 1e-6:
                red_state = "DROP_AT_END"
                red_action_timer = DROP_TIME
                set_hoist(red_hoist, red_x, CARRY_Y, True)

        elif red_state == "DROP_AT_END":
            red_action_timer -= dt
            prog = max(0.0, min(1.0, 1.0 - red_action_timer / DROP_TIME))
            y = CARRY_Y + (TOP_Y - CARRY_Y) * prog
            diamond_red.xy = (END_X, y)
            set_hoist(red_hoist, red_x, y, True)
            if red_action_timer <= 0:
                set_hoist(red_hoist, red_x, TOP_Y, False)
                diamond_red.set_visible(False)
                red_has_diamond = False
                add_delivered_marker()
                red_state = "RETURN_TO_SCANNER"

        elif red_state == "RETURN_TO_SCANNER":
            # return to last target scanner x (or center if none)
            back_x = scanner_xs[red_target_i] if red_target_i is not None else center
            step = V_TRAVERSE * dt
            new_pos = red_x - step if red_x > back_x else min(red_x + step, back_x)
            if not cranes_would_collide(blue_x, new_pos):
                red_x = new_pos
            if abs(red_x - back_x) <= ARRIVE_EPS:
                red_state = "WAIT"
                red_time_under_scanner = 0.0
                schedule_red_departure()

        elif red_state == "LOWER_FOR_PICK":
            red_action_timer = max(0.0, red_action_timer - dt)
            red_time_under_scanner = min(LOWER_TIME, red_time_under_scanner + dt)
            prog = red_time_under_scanner / LOWER_TIME if LOWER_TIME > 0 else 1.0
            y = RAIL_Y + (TOP_Y - RAIL_Y) * prog
            set_hoist(red_hoist, red_x, y, True)

            if scanner_state[red_target_i] == "READY":
                close_ready_wait(red_target_i)
                red_state = "PICK_AT_SCANNER"
                red_action_timer = RAISE_TIME
                set_hoist(red_hoist, red_x, TOP_Y, True)

        # Apply positions
        update_crane_positions()

        # Keep scanner diamonds fixed to TOP_Y when not being picked
        for i in range(N_SCANNERS):
            if diamond_scanners[i].get_visible() and scanner_state[i] in ("SCANNING", "READY") and red_state != "PICK_AT_SCANNER":
                diamond_scanners[i].xy = (scanner_xs[i], TOP_Y)

        # Keep carried diamonds with cranes
        if blue_has_diamond and diamond_blue.get_visible() and blue_state not in ("DROP_AT_SCANNER", "PICK_AT_START"):
            diamond_blue.xy = (blue_x, CARRY_Y)
        if red_has_diamond and diamond_red.get_visible() and red_state not in ("DROP_AT_END", "PICK_AT_SCANNER"):
            diamond_red.xy = (red_x, CARRY_Y)

    # -----------------------------
    # Controls
    # -----------------------------
    pause_ax = plt.axes([0.20, 0.06, 0.12, 0.08])
    skip_text_ax = plt.axes([0.40, 0.06, 0.20, 0.08])
    skip_btn_ax = plt.axes([0.62, 0.06, 0.12, 0.08])

    pause_button = Button(pause_ax, 'Pause')
    skip_text = TextBox(skip_text_ax, 'Jump to t (s): ', initial='60')
    skip_button = Button(skip_btn_ax, 'Skip')
    def remaining_scan(i):
        """Return how many seconds remain until scanner i finishes."""
        if scanner_state[i] != "SCANNING":
            return float('inf')
        # Adjust depending on whether your timer counts down or up:
        # Your code shows `scanner_timer[i] -= dt` while scanning,
        # so it counts DOWN to 0 — meaning scanner_timer[i] is already 'remaining time'.
        return scanner_timer[i]

    def close_ready_wait(i):
        nonlocal total_ready_wait
        if ready_wait_start[i] is not None:
            total_ready_wait += (t_elapsed - ready_wait_start[i])
            total_wait_text.set_text(f"Total ready-wait: {total_ready_wait:.1f} s")
            ready_wait_start[i] = None

    def on_pause(_event):
        nonlocal is_paused
        is_paused = not is_paused
        pause_button.label.set_text('Resume' if is_paused else 'Pause')

    def fast_forward_to(target_time_s):
        nonlocal is_paused
        prev_paused = is_paused
        is_paused = True

        # If target earlier than now, reset first
        if target_time_s < t_elapsed - 1e-9:
            reset_simulation()

        ff_dt = 0.02
        while True:
            remaining = target_time_s - (t_elapsed)
            if remaining <= 1e-9:
                break
            step_dt = ff_dt if remaining > ff_dt else remaining
            step_sim(step_dt)

        update_throughput()
        is_paused = True
        pause_button.label.set_text('Resume')
        fig.canvas.draw_idle()

    def on_skip(_event):
        text = skip_text.text.strip()
        try:
            target = float(text)
            if target >= 0:
                fast_forward_to(target)
        except ValueError:
            pass

    pause_button.on_clicked(on_pause)
    skip_button.on_clicked(on_skip)

    # -----------------------------
    # Animation
    # -----------------------------
    def update(_):
        if not is_paused:
            step_sim(DT)
        return ()

    anim = FuncAnimation(fig, update, interval=int(1000 / FPS), blit=False)
    plt.show()