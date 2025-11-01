#Crane.py
import math
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, RegularPolygon

def make_diamond(x, y, color, size=0.18, z=6):
    return RegularPolygon(
        (x, y), numVertices=4, radius=size, orientation=math.pi/4,
        facecolor=color, edgecolor='black', lw=1.0, zorder=z
    )

class Crane:
    def __init__(self, ax, color, initial_x, crane_width=6, crane_height=2.8,
                 rail_y=1.0, carry_y=4.0, top_y=7.5, v_traverse=3.0,
                 lower_time=1.8, raise_time=1.8, safe_distance=10):
        self.ax = ax
        self.color = color
        self.x = initial_x
        self.initial_x = initial_x
        self.crane_width = crane_width
        self.crane_height = crane_height
        self.rail_y = rail_y
        self.carry_y = carry_y
        self.top_y = top_y
        self.v_traverse = v_traverse
        self.lower_time = lower_time
        self.raise_time = raise_time
        self.safe_distance = safe_distance  # Store safe distance

        # State variables
        self.state = "WAIT"
        self.action_timer = 0.0
        self.has_diamond = False
        self.target_i = None
        self.departure_time = float('inf')
        self.time_under_scanner = 0.0

        # Phase tracking
        self.pick_phase = None
        self.drop_phase = None

        # Visual elements
        self.crane_rect = Rectangle(
            (self.x - crane_width/2, rail_y - crane_height/2),
            crane_width, crane_height,
            fc=color, ec='black', lw=1.5, zorder=5
        )
        ax.add_patch(self.crane_rect)

        self.hoist, = ax.plot([], [], color=color, lw=2, zorder=4)
        self.hoist.set_visible(False)

        # Diamond carried by this crane
        self.diamond = make_diamond(initial_x, carry_y, self.get_diamond_color())
        self.diamond.set_visible(False)
        ax.add_patch(self.diamond)

    def get_diamond_color(self):
        """Override in subclasses for different diamond colors"""
        return '#66bb6a'

    def update_position(self):
        """Update visual position of crane"""
        self.crane_rect.set_xy((self.x - self.crane_width/2, self.rail_y - self.crane_height/2))

    def set_hoist(self, x, y_top, show):
        """Control hoist visibility and position"""
        if show:
            self.hoist.set_data([x, x], [self.rail_y, y_top])
            self.hoist.set_visible(True)
        else:
            self.hoist.set_visible(False)

    def travel_time(self, x0, x1):
        """Calculate travel time between positions"""
        return abs(x1 - x0) / self.v_traverse

    def would_collide_with(self, other_crane):
        """Check if this crane would collide with another"""
        return abs(self.x - other_crane.x) < self.safe_distance

    def reset(self):
        """Reset crane to initial state"""
        self.x = self.initial_x
        self.state = "WAIT"
        self.action_timer = 0.0
        self.has_diamond = False
        self.target_i = None
        self.departure_time = float('inf')
        self.time_under_scanner = 0.0
        self.pick_phase = None
        self.drop_phase = None

        self.update_position()
        self.set_hoist(self.x, self.top_y, False)
        self.diamond.set_visible(False)

class BlueCrane(Crane):
    def __init__(self, ax, start_x, scanner_list, loading_strategy="closest", **kwargs):
        # Remove loading_strategy from kwargs before passing to parent
        crane_kwargs = {k: v for k, v in kwargs.items() if k != 'loading_strategy'}
        super().__init__(ax, '#1f77b4', start_x, **crane_kwargs)

        self.start_x = start_x
        self.scanner_list = scanner_list
        self.loading_strategy = loading_strategy  # "closest" or "furthest"
        self.state = "PICK_AT_START"
        self.pick_phase = "LOWER"
        self.action_timer = self.lower_time

        # Blue crane specific diamond (starts at start position)
        self.start_diamond = make_diamond(start_x, kwargs.get('top_y', 7.5), '#33a3ff')
        ax.add_patch(self.start_diamond)

    def get_diamond_color(self):
        return '#33a3ff'

    def nearest_empty_scanner(self):
        """Find nearest empty scanner"""
        empties = [i for i, scanner in enumerate(self.scanner_list) if scanner.state == "empty"]
        if not empties:
            return None
        return min(empties, key=lambda i: abs(self.scanner_list[i].POS_X - self.x))

    def furthest_empty_scanner(self):
        """Find furthest empty scanner"""
        empties = [i for i, scanner in enumerate(self.scanner_list) if scanner.state == "empty"]
        if not empties:
            return None
        return max(empties, key=lambda i: abs(self.scanner_list[i].POS_X - self.x))

    def get_target_scanner(self):
        """Get target scanner based on loading strategy"""
        if self.loading_strategy == "furthest":
            return self.furthest_empty_scanner()
        else:  # default to closest
            return self.nearest_empty_scanner()

    def earliest_ready_scanner(self):
        """Find earliest ready scanner (for staging)"""
        ready = [i for i, scanner in enumerate(self.scanner_list) if scanner.state == "ready"]
        if not ready:
            return None
        return ready[0]  # Could be enhanced with actual timing

    def earliest_finishing_scan(self):
        """Find scanner that will finish soonest"""
        scanning = [(i, scanner.timer) for i, scanner in enumerate(self.scanner_list) if scanner.state == "scanning"]
        if not scanning:
            return None
        scanning.sort(key=lambda t: t[1])
        return scanning[0][0]

    def staging_x_for(self, i):
        """Get staging position for scanner i - park further left to avoid blocking red crane"""
        return self.scanner_list[i].POS_X - (self.safe_distance * 1.2) - 1e-3

    def step(self, dt, red_crane, schedule_red_callback=None):
        """Step the blue crane simulation"""
        ARRIVE_EPS = 1e-6

        if self.state == "PICK_AT_START":
            # Two-phase pick: LOWER then RAISE
            if self.pick_phase == "LOWER":
                if self.action_timer == self.lower_time:  # First frame
                    self.start_diamond.set_visible(False)  # Hide during lowering
                    self.set_hoist(self.x, self.carry_y, True)

                self.action_timer -= dt
                prog = max(0.0, min(1.0, 1.0 - self.action_timer / self.lower_time))
                y = self.carry_y + (self.top_y - self.carry_y) * prog
                self.set_hoist(self.x, y, True)

                if self.action_timer <= 0:
                    # Switch to RAISE phase
                    self.pick_phase = "RAISE"
                    self.action_timer = self.raise_time
                    # NOW show the diamond at the pick position
                    self.start_diamond.set_visible(True)
                    self.start_diamond.xy = (self.start_x, self.top_y)

            elif self.pick_phase == "RAISE":
                self.action_timer -= dt
                prog = max(0.0, min(1.0, 1.0 - self.action_timer / self.raise_time))
                y = self.top_y + (self.carry_y - self.top_y) * prog
                self.start_diamond.xy = (self.start_x, y)
                self.set_hoist(self.x, y, True)

                if self.action_timer <= 0:
                    # Pick complete
                    self.has_diamond = True
                    self.start_diamond.xy = (self.x, self.carry_y)
                    self.set_hoist(self.x, self.carry_y, False)
                    self.pick_phase = None
                    self.target_i = self.get_target_scanner()
                    if self.target_i is None:
                        # stage near the earliest READY if exists; otherwise near earliest finishing scan
                        j = self.earliest_ready_scanner()
                        if j is None:
                            j = self.earliest_finishing_scan()
                        self.target_i = j if j is not None else 0
                    self.state = "MOVE_TO_SCANNER"

        elif self.state == "MOVE_TO_SCANNER":
            target_i = self.target_i
            sx = self.scanner_list[target_i].POS_X
            want_scanner = (self.scanner_list[target_i].state == "empty") and (not self.would_collide_with(red_crane))
            target_x = sx if want_scanner else max(self.start_x, self.staging_x_for(target_i))

            step = self.v_traverse * dt
            new_pos = self.x + step if self.x < target_x else max(self.x - step, target_x)
            if not abs(new_pos - red_crane.x) < self.safe_distance:
                self.x = new_pos

            if self.has_diamond:
                self.start_diamond.xy = (self.x, self.carry_y)

            # retarget if a closer EMPTY appears (or furthest for furthest strategy)
            if self.scanner_list[target_i].state != "empty":
                alt = self.get_target_scanner()
                if alt is not None and alt != target_i:
                    self.target_i = alt

            # arrival checks
            if abs(self.x - sx) <= ARRIVE_EPS and self.scanner_list[target_i].state == "empty":
                self.state = "DROP_AT_SCANNER"
                self.drop_phase = "LOWER"
                self.action_timer = self.lower_time
                self.set_hoist(self.x, self.carry_y, True)
            elif abs(self.x - target_x) <= ARRIVE_EPS and not want_scanner:
                self.state = "WAIT_AT_STAGING"

        elif self.state == "WAIT_AT_STAGING":
            target_i = self.target_i
            sx = self.scanner_list[target_i].POS_X
            can_advance = (self.scanner_list[target_i].state == "empty") and (not self.would_collide_with(red_crane))
            if can_advance:
                self.state = "MOVE_TO_SCANNER"

        elif self.state == "DROP_AT_SCANNER":
            # Two-phase drop: LOWER then RAISE
            if self.drop_phase == "LOWER":
                self.action_timer -= dt
                prog = max(0.0, min(1.0, 1.0 - self.action_timer / self.lower_time))
                y = self.carry_y + (self.top_y - self.carry_y) * prog
                self.start_diamond.xy = (self.scanner_list[self.target_i].POS_X, y)
                self.set_hoist(self.x, y, True)

                if self.action_timer <= 0:
                    # Switch to RAISE phase
                    self.drop_phase = "RAISE"
                    self.action_timer = self.raise_time
                    # Deposit diamond
                    self.start_diamond.set_visible(False)
                    self.scanner_list[self.target_i].scan(None)  # Start scanning
                    self.has_diamond = False

            elif self.drop_phase == "RAISE":
                self.action_timer -= dt
                prog = max(0.0, min(1.0, 1.0 - self.action_timer / self.raise_time))
                y = self.top_y + (self.carry_y - self.top_y) * prog
                self.set_hoist(self.x, y, True)

                if self.action_timer <= 0:
                    # Drop complete
                    self.set_hoist(self.x, self.carry_y, False)
                    self.drop_phase = None
                    self.state = "RETURN_TO_START"
                    if schedule_red_callback:
                        schedule_red_callback()

        elif self.state == "RETURN_TO_START":
            step = self.v_traverse * dt
            new_pos = max(self.x - step, self.start_x)
            if not abs(new_pos - red_crane.x) < self.safe_distance:
                self.x = new_pos

            if self.x <= self.start_x + 1e-6:
                self.state = "PICK_AT_START"
                self.pick_phase = "LOWER"
                self.action_timer = self.lower_time

        self.update_position()

    def reset(self):
        super().reset()
        self.state = "PICK_AT_START"
        self.pick_phase = "LOWER"
        self.action_timer = self.lower_time
        self.start_diamond.set_visible(False)  # Start hidden, will show when picked


class RedCrane(Crane):
    def __init__(self, ax, end_x, scanner_list, box_list, **kwargs):
        super().__init__(ax, '#d62728', end_x, **kwargs)
        self.end_x = end_x
        self.scanner_list = scanner_list
        self.box_list = box_list
        self.lower_start_time = float('inf')
        self.lower_planned_for_i = None
        self.target_box = None  # Which box to deliver to
        self.drop_x = None  # Store drop position
        self.drop_y = None

    def get_diamond_color(self):
        return '#66bb6a'

    def earliest_ready_scanner(self):
        """Find earliest ready scanner by ready time (FCFS)"""
        ready = [(i, scanner.ready_time) for i, scanner in enumerate(self.scanner_list)
                 if scanner.state == "ready" and scanner.ready_time is not None]
        if not ready:
            return None
        ready.sort(key=lambda t: t[1])
        return ready[0][0]

    def earliest_finishing_scan(self):
        """Find scanner finishing soonest"""
        scanning = [(i, scanner.timer) for i, scanner in enumerate(self.scanner_list)
                    if scanner.state == "scanning"]
        if not scanning:
            return None
        scanning.sort(key=lambda t: t[1])
        return scanning[0][0]

    def schedule_departure(self, t_elapsed):
        """Schedule when red crane should depart"""
        # If there is READY, go now
        i_ready = self.earliest_ready_scanner()
        if i_ready is not None:
            self.target_i = i_ready
            self.lower_start_time = t_elapsed
            self.lower_planned_for_i = i_ready
            self.departure_time = t_elapsed
            # Assign target box when we have a ready scanner
            self.target_box = self.scanner_list[i_ready].get_target_box()
            return

        # Otherwise target earliest finishing SCANNING
        i_scan = self.earliest_finishing_scan()
        if i_scan is None:
            return

        target_x = self.scanner_list[i_scan].POS_X
        t_travel = self.travel_time(self.x, target_x)

        # Plan to finish LOWER exactly at READY
        t_ready = t_elapsed + self.scanner_list[i_scan].timer
        plan_lower_start = t_ready - self.lower_time
        depart = plan_lower_start - t_travel

        # Only set if we don't already have a plan, or this is sooner
        if self.departure_time == float('inf') or depart < self.departure_time:
            self.target_i = i_scan
            self.lower_start_time = plan_lower_start
            self.lower_planned_for_i = i_scan
            self.departure_time = max(depart, t_elapsed)

    def step(self, dt, t_elapsed, blue_crane, close_ready_wait_callback, add_delivered_callback):
        """Step the red crane simulation"""
        ARRIVE_EPS = 1e-6

        if self.state == "WAIT":
            ready_exists = self.earliest_ready_scanner() is not None
            should_depart = (self.departure_time <= t_elapsed and self.departure_time < float('inf'))

            if ready_exists or should_depart:
                print(f"[RED CRANE] WAIT -> MOVE_TO_SCANNER at time {t_elapsed:.1f}, ready_exists={ready_exists}, should_depart={should_depart}")

            # first-cycle optimisation
            if not ready_exists and all(scanner.state == "scanning" for scanner in self.scanner_list) and self.departure_time == float('inf'):
                i_scan = self.earliest_finishing_scan()
                if i_scan is not None:
                    t_travel = self.travel_time(self.x, self.scanner_list[i_scan].POS_X)
                    t_ready = t_elapsed + self.scanner_list[i_scan].timer
                    self.target_i = i_scan
                    self.lower_start_time = t_ready - self.lower_time
                    self.lower_planned_for_i = i_scan
                    self.departure_time = max(self.lower_start_time - t_travel, t_elapsed)
                    print(f"[RED CRANE] Scheduled departure for scanner {i_scan} at time {self.departure_time:.1f}")

            if ready_exists:
                self.target_i = self.earliest_ready_scanner()
                self.target_box = self.scanner_list[self.target_i].get_target_box()
                self.state = "MOVE_TO_SCANNER"
                self.departure_time = float('inf')
            elif should_depart:
                self.state = "MOVE_TO_SCANNER"
                self.departure_time = float('inf')
            else:
                if self.departure_time == float('inf'):
                    self.schedule_departure(t_elapsed)

        elif self.state == "MOVE_TO_SCANNER":
            if self.target_i is None:
                print(f"[RED CRANE] MOVE_TO_SCANNER with target_i=None, returning to WAIT")
                self.state = "WAIT"
            else:
                sx = self.scanner_list[self.target_i].POS_X
                step = self.v_traverse * dt
                new_pos = self.x - step if self.x > sx else min(self.x + step, sx)
                if not self.would_collide_with(blue_crane):
                    self.x = new_pos

                # Debug: print when close to arrival
                if abs(self.x - sx) <= 0.1 and abs(self.x - sx) > ARRIVE_EPS:
                    print(f"[RED CRANE] Getting close to scanner {self.target_i}: distance={abs(self.x - sx):.4f}, scanner_state={self.scanner_list[self.target_i].state}")

                if abs(self.x - sx) <= ARRIVE_EPS:
                    if self.scanner_list[self.target_i].state == "ready":
                        # Arrived and it's READY now: start two-phase pick
                        print(f"[RED CRANE] Arrived at ready scanner {self.target_i}, entering PICK_AT_SCANNER")
                        close_ready_wait_callback(self.target_i)
                        self.target_box = self.box_list[self.scanner_list[self.target_i].get_target_box()]
                        # ENSURE scanner diamond is visible and positioned correctly
                        self.scanner_list[self.target_i].diamond.set_visible(True)
                        self.scanner_list[self.target_i].diamond.xy = (self.scanner_list[self.target_i].POS_X, self.carry_y)
                        self.state = "PICK_AT_SCANNER"
                        self.pick_phase = "LOWER"
                        self.action_timer = self.lower_time
                        print(f"[RED CRANE] Set state=PICK_AT_SCANNER, pick_phase=LOWER, action_timer={self.action_timer}")
                        self.set_hoist(self.x, self.carry_y, True)
                        self.time_under_scanner = 0.0
                    else:
                        print(f"[RED CRANE] Arrived at scanner {self.target_i} but state is {self.scanner_list[self.target_i].state}, entering LOWER_FOR_PICK")
                        # Not READY yet: enter controlled pre-lowering
                        remaining_lower = max(0.0, self.lower_time - self.time_under_scanner)
                        self.state = "LOWER_FOR_PICK"
                        self.action_timer = remaining_lower
                        frac = 1.0 - (self.action_timer / self.lower_time) if self.lower_time > 0 else 1.0
                        y = self.rail_y + (self.top_y - self.rail_y) * frac
                        self.set_hoist(self.x, y, True)

        elif self.state == "PICK_AT_SCANNER":
            # Two-phase pick: LOWER then RAISE
            if self.pick_phase == "LOWER":
                if self.action_timer == self.lower_time:
                    print(f"[RED CRANE] Starting LOWER phase, timer={self.action_timer}")

                self.action_timer -= dt
                prog = max(0.0, min(1.0, 1.0 - self.action_timer / self.lower_time))
                y = self.carry_y + (self.top_y - self.carry_y) * prog
                self.scanner_list[self.target_i].diamond.xy = (self.scanner_list[self.target_i].POS_X, y)
                self.set_hoist(self.x, y, True)

                if self.action_timer <= 0:
                    # Switch to RAISE phase
                    print(f"[RED CRANE] LOWER complete, switching to RAISE phase")
                    self.pick_phase = "RAISE"
                    self.action_timer = self.raise_time

            elif self.pick_phase == "RAISE":
                self.action_timer -= dt
                prog = max(0.0, min(1.0, 1.0 - self.action_timer / self.raise_time))
                y = self.top_y + (self.carry_y - self.top_y) * prog
                self.scanner_list[self.target_i].diamond.xy = (self.scanner_list[self.target_i].POS_X, y)
                self.set_hoist(self.x, y, True)

                if self.action_timer <= 0:
                    # Pick complete
                    print(f"[RED CRANE] RAISE complete, pick finished")
                    self.scanner_list[self.target_i].diamond.set_visible(False)
                    self.diamond.set_visible(True)
                    self.diamond.xy = (self.x, self.carry_y)
                    self.set_hoist(self.x, self.carry_y, False)
                    self.has_diamond = True
                    self.pick_phase = None
                    wait_time = self.scanner_list[self.target_i].pickup()  # This resets scanner to empty
                    self.state = "MOVE_TO_END"
                    self.time_under_scanner = 0.0

        elif self.state == "MOVE_TO_END":
            # Move to the target box position using get_coordinates()
            if self.target_box and hasattr(self.target_box, 'get_coordinates'):
                target_x, target_y = self.target_box.get_coordinates()
            else:
                # Fallback or fix target_box if it's not properly set
                if isinstance(self.target_box, int) and self.target_box < len(self.box_list):
                    self.target_box = self.box_list[self.target_box]
                    target_x, target_y = self.target_box.get_coordinates()
                else:
                    target_x = self.end_x  # ultimate fallback

            step = self.v_traverse * dt
            new_pos = min(self.x + step, target_x)
            if not self.would_collide_with(blue_crane):
                self.x = new_pos
            if self.has_diamond:
                self.diamond.xy = (self.x, self.carry_y)
            if self.x >= target_x - 1e-6:
                self.state = "DROP_AT_END"
                self.drop_phase = "LOWER"
                self.action_timer = self.lower_time
                self.drop_x = None  # Reset drop position for fresh calculation
                self.drop_y = None
                self.set_hoist(self.x, self.carry_y, True)

        elif self.state == "DROP_AT_END":
            # Two-phase drop: LOWER then RAISE
            if self.drop_phase == "LOWER":
                # Calculate drop position once at start of LOWER phase
                if self.drop_x is None:
                    if self.target_box and hasattr(self.target_box, 'get_coordinates'):
                        self.drop_x, self.drop_y = self.target_box.get_coordinates()
                    else:
                        # Fallback or fix target_box if it's not properly set
                        if isinstance(self.target_box, int) and self.target_box < len(self.box_list):
                            self.target_box = self.box_list[self.target_box]
                            self.drop_x, self.drop_y = self.target_box.get_coordinates()
                        else:
                            self.drop_x, self.drop_y = self.end_x, self.top_y

                if self.action_timer == self.lower_time:  # First frame
                    # Ensure diamond is visible and positioned at carry height
                    self.diamond.set_visible(True)
                    self.diamond.xy = (self.drop_x, self.carry_y)

                self.action_timer -= dt
                prog = max(0.0, min(1.0, 1.0 - self.action_timer / self.lower_time))
                y = self.carry_y + (self.drop_y - self.carry_y) * prog
                self.diamond.xy = (self.drop_x, y)
                self.set_hoist(self.x, y, True)

                if self.action_timer <= 0:
                    # Switch to RAISE phase
                    self.drop_phase = "RAISE"
                    self.action_timer = self.raise_time
                    # Deposit diamond
                    self.diamond.set_visible(False)
                    self.has_diamond = False
                    if self.target_box and hasattr(self.target_box, 'add_diamond'):
                        self.target_box.add_diamond()
                    add_delivered_callback()

            elif self.drop_phase == "RAISE":
                self.action_timer -= dt
                prog = max(0.0, min(1.0, 1.0 - self.action_timer / self.raise_time))
                y = self.drop_y + (self.carry_y - self.drop_y) * prog
                self.set_hoist(self.x, y, True)

                if self.action_timer <= 0:
                    # Drop complete
                    self.set_hoist(self.x, self.carry_y, False)
                    self.drop_phase = None
                    self.drop_x = None  # Reset for next drop
                    self.drop_y = None
                    self.state = "RETURN_TO_SCANNER"

        elif self.state == "RETURN_TO_SCANNER":
            # return to last target scanner x (or center if none)
            scanner_xs = [scanner.POS_X for scanner in self.scanner_list]
            center = sum(scanner_xs) / len(scanner_xs)
            back_x = self.scanner_list[self.target_i].POS_X if self.target_i is not None else center
            step = self.v_traverse * dt
            new_pos = self.x - step if self.x > back_x else min(self.x + step, back_x)
            if not self.would_collide_with(blue_crane):
                self.x = new_pos
            if abs(self.x - back_x) <= ARRIVE_EPS:
                self.state = "WAIT"
                self.time_under_scanner = 0.0
                self.schedule_departure(t_elapsed)

        elif self.state == "LOWER_FOR_PICK":
            self.action_timer = max(0.0, self.action_timer - dt)
            self.time_under_scanner = min(self.lower_time, self.time_under_scanner + dt)
            prog = self.time_under_scanner / self.lower_time if self.lower_time > 0 else 1.0
            y = self.rail_y + (self.top_y - self.rail_y) * prog
            self.set_hoist(self.x, y, True)

            if self.scanner_list[self.target_i].state == "ready":
                print(f"[RED CRANE] Scanner ready during LOWER_FOR_PICK, transitioning to PICK_AT_SCANNER RAISE phase")
                close_ready_wait_callback(self.target_i)
                self.target_box = self.box_list[self.scanner_list[self.target_i].get_target_box()]
                # Make sure scanner diamond is visible before transitioning
                self.scanner_list[self.target_i].diamond.set_visible(True)
                self.scanner_list[self.target_i].diamond.xy = (self.scanner_list[self.target_i].POS_X, self.top_y)
                self.state = "PICK_AT_SCANNER"
                self.pick_phase = "RAISE"  # Already lowered, just need to raise
                self.action_timer = self.raise_time
                print(f"[RED CRANE] Set state=PICK_AT_SCANNER, pick_phase=RAISE, action_timer={self.action_timer}")
                self.set_hoist(self.x, self.top_y, True)

        self.update_position()

    def reset(self):
        super().reset()
        self.lower_start_time = float('inf')
        self.lower_planned_for_i = None
        self.target_box = None
        self.drop_x = None
        self.drop_y = None