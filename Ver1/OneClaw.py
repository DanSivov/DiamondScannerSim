# OneClaw.py
# Conveyor Flow Simulation (ggplot) — single crane, single scanner
# UI, controls, colors, and layout match the two-crane version.

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
def run_single_crane_sim(
        # ---- Tunable parameters ----
        FPS: float = 60,
        V_TRAVERSE: float = 3.0,
        PICK_TIME: float = 3.6,
        DROP_TIME: float = 3.6,
        SCAN_TIME: float = 15.0,
):
    N_SCANNERS = 1  # fixed to one scanner for this variant

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

    # Single scanner centered
    center = 5.5
    scanner_xs = [center]

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
    scanner_state = []          # "EMPTY" | "SCANNING" | "READY"
    scanner_timer = []          # remaining time if SCANNING
    scanner_ready_since = []    # timestamp when became READY
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

    # Per-scanner ready-wait tracking and labels (aligned with your UI)
    ready_wait_start = [None for _ in range(N_SCANNERS)]
    ready_wait_labels = []
    for i, sx in enumerate(scanner_xs):
        lbl = ax.text(sx, TOP_Y + 0.9, "", ha='center', va='bottom',
                      color='red', fontsize=10, fontweight='bold', zorder=10)
        ready_wait_labels.append(lbl)

    # Rail
    ax.plot([0.6, 10.4], [RAIL_Y, RAIL_Y], color='black', lw=4, alpha=0.85, solid_capstyle='round')

    # -----------------------------
    # Dynamic elements (single crane, blue)
    # -----------------------------
    BLUE_COLOR = '#1f77b4'
    CRANE_W, CRANE_H = 0.6, 0.28

    crane_x = START_X
    blue_crane = Rectangle((crane_x - CRANE_W/2, RAIL_Y - CRANE_H/2), CRANE_W, CRANE_H,
                           fc=BLUE_COLOR, ec='black', lw=1.5, zorder=5)
    ax.add_patch(blue_crane)

    blue_hoist, = ax.plot([], [], color=BLUE_COLOR, lw=2, zorder=4)
    blue_hoist.set_visible(False)

    # Diamonds: keep your colors (blue inbound, green outbound)
    diamond_blue = make_diamond(START_X, TOP_Y, '#33a3ff'); ax.add_patch(diamond_blue)
    diamond_red = make_diamond(scanner_xs[0], CARRY_Y, '#66bb6a'); diamond_red.set_visible(False); ax.add_patch(diamond_red)

    # Delivered pile
    delivered_pile = []

    # Timer and metrics (same placement/styles)
    timer_text = ax.text(5.5, 9.2, "Time: 0.0 s", ha='center', fontsize=12, fontweight='bold')
    throughput_text = ax.text(10.6, 7.0, "Diamonds/min: --", ha='left', fontsize=11, fontweight='bold')
    total_ready_wait = 0.0
    total_wait_text = ax.text(10.6, 6.6, "Total ready-wait: 0.0 s", ha='left', fontsize=11, fontweight='bold', color='black')

    # -----------------------------
    # Simulation parameters
    # -----------------------------
    DT = 1.0 / FPS

    t_elapsed = 0.0

    # -----------------------------
    # Helpers
    # -----------------------------
    def update_crane_position():
        blue_crane.set_xy((crane_x - CRANE_W/2, RAIL_Y - CRANE_H/2))

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
        st = scanner_state[0]
        if st == "SCANNING":
            scanner_rects[0].set_edgecolor('#f39c12'); scanner_rects[0].set_linewidth(2.4)
        elif st == "READY":
            scanner_rects[0].set_edgecolor('#27ae60'); scanner_rects[0].set_linewidth(2.4)
        else:
            scanner_rects[0].set_edgecolor('black'); scanner_rects[0].set_linewidth(2.0)

    # -----------------------------
    # Reset (for skip backward)
    # -----------------------------
    def reset_simulation():
        nonlocal t_elapsed, delivered
        nonlocal crane_x
        nonlocal crane_state, crane_action_timer, crane_has_diamond, carrying_phase
        nonlocal total_ready_wait

        t_elapsed = 0.0
        timer_text.set_text("Time: 0.0 s")
        throughput_text.set_text("Diamonds/min: --")

        crane_x = START_X
        update_crane_position()
        set_hoist(blue_hoist, crane_x, TOP_Y, False)

        diamond_blue.set_visible(True); diamond_blue.xy = (START_X, TOP_Y)
        diamond_red.set_visible(False)

        # scanner reset
        scanner_state[0] = "EMPTY"
        scanner_timer[0] = 0.0
        scanner_ready_since[0] = None
        diamond_scanners[0].set_visible(False)
        diamond_scanners[0].set_facecolor('#ffd54f')
        set_scanner_visuals()

        ready_wait_start[0] = None
        ready_wait_labels[0].set_text("")
        total_ready_wait = 0.0
        total_wait_text.set_text("Total ready-wait: 0.0 s")

        delivered = 0
        end_count_text.set_text(f"{delivered}")
        clear_delivered_markers()

        crane_state = "PICK_AT_START"
        crane_action_timer = PICK_TIME
        crane_has_diamond = False
        carrying_phase = None  # "INBOUND" or "OUTBOUND"

        fig.canvas.draw_idle()

    # init visuals
    reset_simulation()

    # -----------------------------
    # Single-crane FSM
    # -----------------------------
    # States:
    # PICK_AT_START -> MOVE_TO_SCANNER -> DROP_AT_SCANNER -> WAIT_FOR_SCAN
    # -> PICK_AT_SCANNER -> MOVE_TO_END -> DROP_AT_END -> RETURN_TO_START

    crane_state = "PICK_AT_START"
    crane_action_timer = PICK_TIME
    crane_has_diamond = False
    carrying_phase = None

    # -----------------------------
    # Simulation step
    # -----------------------------
    is_paused = False

    def step_sim(dt):
        nonlocal t_elapsed
        nonlocal crane_x, crane_state, crane_action_timer, crane_has_diamond, carrying_phase
        nonlocal total_ready_wait

        # time
        t_elapsed += dt
        timer_text.set_text(f"Time: {t_elapsed:0.1f} s")
        # throughput update each minute rollover
        current_minute = int(t_elapsed / 60.0)
        last_checked_minute = int((t_elapsed - dt) / 60.0)
        if current_minute > last_checked_minute and current_minute > 0:
            update_throughput()

        # --- scanner progression ---
        if scanner_state[0] == "SCANNING":
            diamond_scanners[0].set_facecolor('#ffd54f')
            scanner_timer[0] -= dt
            if scanner_timer[0] <= 0:
                scanner_state[0] = "READY"
                scanner_ready_since[0] = t_elapsed
                diamond_scanners[0].set_facecolor('#66bb6a')
                # start ready-wait timer
                ready_wait_start[0] = t_elapsed
                ready_wait_labels[0].set_text("")

        set_scanner_visuals()

        PENALTY_THRESHOLD = 0.0  # seconds before showing label
        if scanner_state[0] == "READY" and ready_wait_start[0] is not None:
            wait_time = t_elapsed - ready_wait_start[0]
            if wait_time > PENALTY_THRESHOLD:
                ready_wait_labels[0].set_text(f"{wait_time:.1f}")
            else:
                ready_wait_labels[0].set_text("")
        else:
            ready_wait_labels[0].set_text("")

        # --- crane FSM ---
        if crane_state == "PICK_AT_START":
            if crane_action_timer == PICK_TIME:
                diamond_blue.set_visible(True)
                diamond_blue.xy = (START_X, TOP_Y)
                set_hoist(blue_hoist, crane_x, TOP_Y, True)
            crane_action_timer -= dt
            prog = max(0.0, min(1.0, 1.0 - crane_action_timer / PICK_TIME))
            y = TOP_Y + (CARRY_Y - TOP_Y) * prog
            diamond_blue.xy = (START_X, y)
            set_hoist(blue_hoist, crane_x, y, True)
            if crane_action_timer <= 0:
                crane_has_diamond = True
                carrying_phase = "INBOUND"
                diamond_blue.xy = (crane_x, CARRY_Y)
                set_hoist(blue_hoist, crane_x, CARRY_Y, False)
                crane_state = "MOVE_TO_SCANNER"

        elif crane_state == "MOVE_TO_SCANNER":
            sx = scanner_xs[0]
            step = V_TRAVERSE * dt
            crane_x = min(crane_x + step, sx)
            if crane_has_diamond and carrying_phase == "INBOUND":
                diamond_blue.xy = (crane_x, CARRY_Y)
            if abs(crane_x - sx) < 1e-6:
                if scanner_state[0] == "EMPTY":
                    crane_state = "DROP_AT_SCANNER"
                    crane_action_timer = DROP_TIME
                    set_hoist(blue_hoist, crane_x, CARRY_Y, True)
                else:
                    # Rare: if scanner isn't empty yet, wait here
                    crane_state = "WAIT_FOR_SCAN"

        elif crane_state == "DROP_AT_SCANNER":
            crane_action_timer -= dt
            prog = max(0.0, min(1.0, 1.0 - crane_action_timer / DROP_TIME))
            y = CARRY_Y + (TOP_Y - CARRY_Y) * prog
            diamond_blue.xy = (scanner_xs[0], y)
            set_hoist(blue_hoist, crane_x, y, True)
            if crane_action_timer <= 0:
                # deposit and start scanning
                diamond_blue.set_visible(False)
                ds = diamond_scanners[0]
                ds.set_visible(True); ds.xy = (scanner_xs[0], TOP_Y)
                scanner_state[0] = "SCANNING"
                scanner_timer[0] = SCAN_TIME
                scanner_ready_since[0] = None
                crane_has_diamond = False
                carrying_phase = None
                set_hoist(blue_hoist, crane_x, TOP_Y, False)
                crane_state = "WAIT_FOR_SCAN"

        elif crane_state == "WAIT_FOR_SCAN":
            # Hold at scanner until it becomes READY, then pick
            if scanner_state[0] == "READY":
                # stop per-scanner ready-wait timer when we start picking
                if ready_wait_start[0] is not None:
                    total_ready_wait += (t_elapsed - ready_wait_start[0])
                    total_wait_text.set_text(f"Total ready-wait: {total_ready_wait:.1f} s")
                    ready_wait_start[0] = None
                crane_state = "PICK_AT_SCANNER"
                crane_action_timer = PICK_TIME
                set_hoist(blue_hoist, crane_x, TOP_Y, True)

        elif crane_state == "PICK_AT_SCANNER":
            crane_action_timer -= dt
            prog = max(0.0, min(1.0, 1.0 - crane_action_timer / PICK_TIME))
            y = TOP_Y + (CARRY_Y - TOP_Y) * prog
            diamond_scanners[0].xy = (scanner_xs[0], y)
            if crane_action_timer <= 0:
                # lift complete → scanner becomes EMPTY
                ds = diamond_scanners[0]
                ds.set_visible(False)
                diamond_red.set_visible(True)
                diamond_red.xy = (crane_x, CARRY_Y)
                set_hoist(blue_hoist, crane_x, CARRY_Y, False)
                crane_has_diamond = True
                carrying_phase = "OUTBOUND"
                scanner_state[0] = "EMPTY"
                scanner_ready_since[0] = None
                crane_state = "MOVE_TO_END"

        elif crane_state == "MOVE_TO_END":
            step = V_TRAVERSE * dt
            crane_x = min(crane_x + step, END_X)
            if crane_has_diamond and carrying_phase == "OUTBOUND":
                diamond_red.xy = (crane_x, CARRY_Y)
            if crane_x >= END_X - 1e-6:
                crane_state = "DROP_AT_END"
                crane_action_timer = DROP_TIME
                set_hoist(blue_hoist, crane_x, CARRY_Y, True)

        elif crane_state == "DROP_AT_END":
            crane_action_timer -= dt
            prog = max(0.0, min(1.0, 1.0 - crane_action_timer / DROP_TIME))
            y = CARRY_Y + (TOP_Y - CARRY_Y) * prog
            diamond_red.xy = (END_X, y)
            set_hoist(blue_hoist, crane_x, y, True)
            if crane_action_timer <= 0:
                set_hoist(blue_hoist, crane_x, TOP_Y, False)
                diamond_red.set_visible(False)
                crane_has_diamond = False
                carrying_phase = None
                add_delivered_marker()
                crane_state = "RETURN_TO_START"

        elif crane_state == "RETURN_TO_START":
            step = V_TRAVERSE * dt
            crane_x = max(crane_x - step, START_X)
            if crane_x <= START_X + 1e-6:
                crane_state = "PICK_AT_START"
                crane_action_timer = PICK_TIME

        # Apply positions
        update_crane_position()

        # Keep scanner diamond fixed at TOP_Y when not being picked
        if diamond_scanners[0].get_visible() and scanner_state[0] in ("SCANNING", "READY") and crane_state != "PICK_AT_SCANNER":
            diamond_scanners[0].xy = (scanner_xs[0], TOP_Y)

        # Keep carried diamonds with crane when appropriate
        if crane_has_diamond and carrying_phase == "INBOUND" and diamond_blue.get_visible() and crane_state not in ("DROP_AT_SCANNER", "PICK_AT_START"):
            diamond_blue.xy = (crane_x, CARRY_Y)
        if crane_has_diamond and carrying_phase == "OUTBOUND" and diamond_red.get_visible() and crane_state not in ("DROP_AT_END", "PICK_AT_SCANNER"):
            diamond_red.xy = (crane_x, CARRY_Y)

    # -----------------------------
    # Controls
    # -----------------------------
    pause_ax = plt.axes([0.20, 0.06, 0.12, 0.08])
    skip_text_ax = plt.axes([0.40, 0.06, 0.20, 0.08])
    skip_btn_ax = plt.axes([0.62, 0.06, 0.12, 0.08])

    pause_button = Button(pause_ax, 'Pause')
    skip_text = TextBox(skip_text_ax, 'Jump to t (s): ', initial='60')
    skip_button = Button(skip_btn_ax, 'Skip')

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


if __name__ == "__main__":
    run_single_crane_sim()
