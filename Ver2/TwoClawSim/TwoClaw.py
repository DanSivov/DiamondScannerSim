#TwoClaw.py
#Improvements from Ver1:
#   Add failure of system and failure response. I.E. a dropped diamond
#   Add scanner sorting, scanner will give specific box to take diamond
# Otherwise same system: two claws, n scanners (n = {1,2,3,4}).

import math
import matplotlib.pyplot as plt
from .Scanner import DScanner

# Import ALL necessary config values
from . import config
from .config import (S_W_SCANNER, S_H_SCANNER, N_BOXES, FPS, DT,
                     VMAX_CLAW_X, T_Z, D_CLAW_SAFE_DISTANCE)
from .endBox import Box
from .Crane import BlueCrane, RedCrane, make_diamond
from matplotlib.animation import FuncAnimation
from matplotlib.patches import Circle, Rectangle, RegularPolygon
from matplotlib.widgets import Button, TextBox

#Functions
def timeToTravel(x0,x1,V_INIT,V_MAX,A):
    D = abs(x0 - x1) * 10
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

def runSimulation(N_SCANNERS: int = 1, loading_strategy: str = "closest"):
    assert 1 <= N_SCANNERS <= 4, "N_SCANNERS must be 1..4"
    assert loading_strategy in ["closest", "furthest"], "loading_strategy must be 'closest' or 'furthest'"

    # -----------------------------
    # Style & figure
    # -----------------------------
    plt.style.use('ggplot')
    fig, ax = plt.subplots(figsize=(15, 5.5))
    plt.subplots_adjust(bottom=0.22)

    # Position window at top right of screen
    try:
        fig_manager = plt.get_current_fig_manager()
        # For TkAgg backend (Windows default)
        if hasattr(fig_manager, 'window'):
            fig_manager.window.update_idletasks()
            screen_width = fig_manager.window.winfo_screenwidth()
            window_width = fig_manager.window.winfo_reqwidth()

            # Position at top right (with small margin from edge)
            x = screen_width - window_width - 10  # 10px margin from right edge
            y = 10  # 10px margin from top

            # Move window to top right
            fig_manager.window.wm_geometry(f"+{x}+{y}")
    except Exception as e:
        print(f"Could not position window: {e}")

    ax.set_xlim(0, 15)
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
    END_X = 10

    # Evenly place scanners around center while keeping margins
    center = 5.5
    spacing = 1.2 # distance between scanners
    scanner_List = []

    SCANNER_WIDTH = S_W_SCANNER / 10
    SCANNER_HEIGHT = S_H_SCANNER / 10

    if N_SCANNERS == 1:
        scanner_List.append(DScanner(center))
        # Draw the scanner box
        ax.add_patch(Rectangle(
            (center - SCANNER_WIDTH/2, TOP_Y - SCANNER_HEIGHT/2),
            SCANNER_WIDTH,
            SCANNER_HEIGHT,
            facecolor='lightblue',
            edgecolor='black',
            lw=2,
            zorder=3
        ))
    else:
        total_span = spacing * (N_SCANNERS - 1)
        left = center - total_span / 2
        for i in range(N_SCANNERS):
            x_pos = left + i * spacing
            scanner_List.append(DScanner(x_pos))
            # Draw the scanner box
            ax.add_patch(Rectangle(
                (x_pos - SCANNER_WIDTH/2, TOP_Y - SCANNER_HEIGHT/2),
                SCANNER_WIDTH,
                SCANNER_HEIGHT,
                facecolor='lightblue',
                edgecolor='black',
                lw=2,
                zorder=3
            ))

    # Add scanner diamonds to plot
    for scanner in scanner_List:
        scanner.add_diamond_to_plot(ax)

    # Process line
    ax.plot([START_X + 0.35, END_X - 0.35], [TOP_Y, TOP_Y], color='gray', linewidth=2, alpha=0.6)

    # Start circle
    start_circle = Circle((START_X, TOP_Y), 0.35, fc='white', ec='black', lw=2, zorder=2)
    ax.add_patch(start_circle)
    ax.text(START_X, TOP_Y + 0.8, "start", ha='center')

    #create end boxes - all stacked at the same location
    box_list = []
    END_BOX_X = END_X  # All boxes at the same x position

    for i in range(N_BOXES):
        box_list.append(Box(i, END_BOX_X, TOP_Y))
        # Draw all boxes at the same position, stacked visually
        endtempCircle = Circle((END_BOX_X, TOP_Y), 0.4, fc='white', ec='black', lw=2, zorder=2)
        ax.add_patch(endtempCircle)

    # Single label for the stacked boxes
    ax.text(END_BOX_X, TOP_Y + 0.8, f"Boxes 1-{N_BOXES}", ha='center')

    #counters
    delivered_total = 0
    end_count_text = ax.text(END_X + 1, TOP_Y + 1.6, "Total num of diamonds: "+f"{delivered_total}", ha='center', va='center', fontsize=10)

    #rail
    ax.plot([0.6, END_BOX_X + 0.4], [RAIL_Y, RAIL_Y], color='black', lw=4, alpha=0.85, solid_capstyle='round')

    # -----------------------------
    # Create Cranes with config values
    # -----------------------------
    blue_crane = BlueCrane(ax, START_X, scanner_List,
                           rail_y=RAIL_Y, carry_y=CARRY_Y, top_y=TOP_Y,
                           v_traverse=VMAX_CLAW_X / 10,  # Convert cm/s to units/s
                           lower_time=T_Z, raise_time=T_Z,
                           safe_distance=D_CLAW_SAFE_DISTANCE / 10)  # Convert cm to units
    red_crane = RedCrane(ax, END_X, scanner_List, box_list,
                         rail_y=RAIL_Y, carry_y=CARRY_Y, top_y=TOP_Y,
                         v_traverse=VMAX_CLAW_X / 10,  # Convert cm/s to units/s
                         lower_time=T_Z, raise_time=T_Z,
                         safe_distance=D_CLAW_SAFE_DISTANCE / 10)  # Convert cm to units

    # Timer and metrics
    timer_text = ax.text(5.5, 9.2, "Time: 0.0 s", ha='center', fontsize=12, fontweight='bold')
    throughput_text = ax.text(10.6, 8.5, "Diamonds/min: --", ha='left', fontsize=11, fontweight='bold')
    total_ready_wait = 0.0
    total_wait_text = ax.text(10.6, 8.1, "Total ready-wait: 0.0 s", ha='left', fontsize=11, fontweight='bold', color='black')

    # Per-scanner ready-wait tracking and labels
    ready_wait_start = [None for _ in range(N_SCANNERS)]
    ready_wait_labels = []
    for i, scanner in enumerate(scanner_List):
        lbl = ax.text(scanner.POS_X, TOP_Y + 0.9, "", ha='center', va='bottom',
                      color='red', fontsize=10, fontweight='bold', zorder=10)
        ready_wait_labels.append(lbl)

    # Box count displays - stacked vertically since boxes are at same location
    box_count_texts = []
    for i, box in enumerate(box_list):
        count_text = ax.text(END_BOX_X + 1.2, TOP_Y + 0.3 - (i * 0.3), f"Box {i+1}: 0", ha='left', fontsize=9)
        box_count_texts.append(count_text)

    # -----------------------------
    # Simulation parameters from config
    # -----------------------------
    ARRIVE_EPS = 1e-6

    t_elapsed = 0.0
    is_paused = False

    # -----------------------------
    # Helpers
    # -----------------------------
    def add_delivered_marker():
        nonlocal delivered_total
        delivered_total += 1
        end_count_text.set_text(f"Total num of diamonds: {delivered_total}")

    def update_throughput():
        current_minute = t_elapsed / 60.0
        if current_minute >= 1.0:
            throughput_text.set_text(f"Diamonds/min: {delivered_total / current_minute:.2f}")
        else:
            throughput_text.set_text("Diamonds/min: --")

    def update_box_counts():
        for i, (box, text) in enumerate(zip(box_list, box_count_texts)):
            text.set_text(f"Box {i+1}: {box.get_count()}")

    def close_ready_wait(i):
        nonlocal total_ready_wait
        if ready_wait_start[i] is not None:
            total_ready_wait += (t_elapsed - ready_wait_start[i])
            total_wait_text.set_text(f"Total ready-wait: {total_ready_wait:.1f} s")
            ready_wait_start[i] = None

    def schedule_red_departure():
        red_crane.schedule_departure(t_elapsed)

    # -----------------------------
    # Reset (for skip backward)
    # -----------------------------
    def reset_simulation():
        nonlocal t_elapsed, delivered_total, total_ready_wait

        # CRITICAL: Set time and counters to ZERO first
        t_elapsed = 0.0
        delivered_total = 0
        total_ready_wait = 0.0

        # Update all text displays immediately
        timer_text.set_text("Time: 0.0 s")
        throughput_text.set_text("Diamonds/min: --")
        end_count_text.set_text(f"Total num of diamonds: 0")
        total_wait_text.set_text("Total ready-wait: 0.0 s")

        # Reset cranes to initial state
        blue_crane.reset()
        red_crane.reset()

        # Reset ALL scanners completely
        for scanner in scanner_List:
            scanner.state = "empty"
            scanner.timer = 0.0
            scanner.ready_time = None
            scanner.target_box_id = None
            scanner.diamond.set_visible(False)
            scanner.scans_done = 0

        # Reset ready wait tracking
        for i in range(N_SCANNERS):
            ready_wait_start[i] = None
            ready_wait_labels[i].set_text("")

        # Reset boxes and clear ALL visual diamonds
        for box in box_list:
            # Remove all delivered diamond patches from the plot
            for diamond in box.delivered_diamonds:
                try:
                    # Try to set invisible instead of removing
                    diamond.set_visible(False)
                    # If it has a remove method that works, use it
                    if hasattr(diamond, 'remove'):
                        diamond.remove()
                except Exception as e:
                    # If removal fails, just continue
                    pass
            # Clear the list
            box.delivered_diamonds.clear()
            # Reset box counter to 0
            box.diamond_count = 0

        # Update box count displays to show 0
        update_box_counts()

        # Force canvas redraw
        fig.canvas.draw_idle()

    # init visuals
    reset_simulation()

    # -----------------------------
    # Simulation step
    # -----------------------------
    def step_sim(dt):
        nonlocal t_elapsed, total_ready_wait

        try:
            # time
            t_elapsed += dt
            timer_text.set_text(f"Time: {t_elapsed:0.1f} s")

            # throughput update each minute rollover
            current_minute = int(t_elapsed / 60.0)
            last_checked_minute = int((t_elapsed - dt) / 60.0)
            if current_minute > last_checked_minute and current_minute > 0:
                update_throughput()

            # --- Update scanners ---
            for i, scanner in enumerate(scanner_List):
                scanner.update(dt, t_elapsed)

                # Track ready wait times
                if scanner.state == "ready" and ready_wait_start[i] is None:
                    ready_wait_start[i] = t_elapsed
                elif scanner.state != "ready" and ready_wait_start[i] is not None:
                    ready_wait_start[i] = None

            PENALTY_THRESHOLD = 0.0  # seconds before showing timer

            # Update per-scanner ready-wait labels
            for i, scanner in enumerate(scanner_List):
                if scanner.state == "ready" and ready_wait_start[i] is not None:
                    wait_time = t_elapsed - ready_wait_start[i]
                    if wait_time > PENALTY_THRESHOLD:
                        ready_wait_labels[i].set_text(f"{wait_time:.1f}")
                    else:
                        ready_wait_labels[i].set_text("")
                else:
                    ready_wait_labels[i].set_text("")

            # >>> EARLY-DEPARTURE POLL FOR RED CRANE <<<
            if (all(scanner.state == "scanning" for scanner in scanner_List) and
                    red_crane.earliest_ready_scanner() is None and
                    red_crane.state == "WAIT" and
                    red_crane.departure_time == float('inf')):
                i_scan = red_crane.earliest_finishing_scan()
                if i_scan is not None:
                    rem = scanner_List[i_scan].timer
                    tt = red_crane.travel_time(red_crane.x, scanner_List[i_scan].POS_X)
                    red_crane.target_i = i_scan
                    t_ready = t_elapsed + rem
                    red_crane.lower_start_time = t_ready - red_crane.lower_time
                    red_crane.lower_planned_for_i = i_scan
                    red_crane.departure_time = max(red_crane.lower_start_time - tt, t_elapsed)

            # --- Step both cranes ---
            blue_crane.step(dt, red_crane, schedule_red_departure)
            red_crane.step(dt, t_elapsed, blue_crane, close_ready_wait, add_delivered_marker)

            # Keep scanner diamonds fixed to TOP_Y when not being picked
            for i, scanner in enumerate(scanner_List):
                if (scanner.diamond.get_visible() and
                        scanner.state in ("scanning", "ready") and
                        red_crane.state != "PICK_AT_SCANNER"):
                    scanner.diamond.xy = (scanner.POS_X, TOP_Y)

            # Update box counts
            update_box_counts()

            # Add delivered diamonds to boxes visually
            for box in box_list:
                while len(box.delivered_diamonds) < box.diamond_count:
                    diamond = box.add_diamond()
                    ax.add_patch(diamond)

        except Exception as e:
            print(f"Error in simulation step: {e}")
            print(f"Time: {t_elapsed}")
            raise

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
        is_paused = True

        # ALWAYS reset to 0 if target is earlier than now, OR if target is 0
        # This ensures clean state when skipping backwards
        if target_time_s < t_elapsed - 1e-9 or target_time_s == 0:
            print(f"Resetting simulation (current: {t_elapsed:.1f}s, target: {target_time_s:.1f}s)")
            reset_simulation()

            # If target is 0, we're done - just stay at reset state
            if target_time_s <= 1e-9:
                is_paused = True
                pause_button.label.set_text('Resume')
                fig.canvas.draw_idle()
                return

        # Now simulate forward from current time (0 after reset) to target
        ff_dt = 0.1  # Timestep for faster skipping
        max_iterations = int((target_time_s - t_elapsed) / ff_dt) + 1000  # Safety limit
        iterations = 0

        print(f"Fast forwarding from {t_elapsed:.1f}s to {target_time_s:.1f}s")

        while iterations < max_iterations:
            remaining = target_time_s - t_elapsed
            if remaining <= 1e-9:
                break
            step_dt = min(ff_dt, remaining)
            try:
                step_sim(step_dt)
            except Exception as e:
                print(f"Error during fast forward at time {t_elapsed}: {e}")
                break
            iterations += 1

        if iterations >= max_iterations:
            print(f"Fast forward stopped at max iterations. Time: {t_elapsed:.1f}s")

        # Update throughput and pause state
        update_throughput()
        is_paused = True
        pause_button.label.set_text('Resume')
        print(f"Fast forward complete. Final time: {t_elapsed:.1f}s, Diamonds: {delivered_total}")
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
    # Animation - Use config FPS
    # -----------------------------
    def update(_):
        if not is_paused:
            step_sim(DT)
        return ()

    anim = FuncAnimation(fig, update, interval=int(1000 / FPS), blit=False, cache_frame_data=False)
    plt.show()