# Ver3.5/RealisticDualClawSim/crane.py
"""
Dual-Claw Crane class for Ver3.5 Simulation

Single crane body that moves on X-axis only, with two independent
lowering mechanisms (blue left, red right).

Blue claw: Picks diamonds from START, delivers to scanner deposit zones on plate
Red claw: Picks scanned diamonds from plate, delivers to end boxes
"""

import math
from matplotlib.patches import Rectangle, RegularPolygon
from . import config


def make_diamond(x, y, color, size=0.18, z=6):
    """Create a diamond visual element for matplotlib"""
    return RegularPolygon(
        (x, y), numVertices=4, radius=size, orientation=math.pi/4,
        facecolor=color, edgecolor='black', lw=1.0, zorder=z
    )


class DualClawCrane:
    """
    Dual-Claw Crane with independent blue (left) and red (right) mechanisms

    Architecture:
    - Single crane body moves on X-axis only at scanner level (Y=SCANNER_Y)
    - Two independent claws can lower/raise separately
    - Blue claw (left): START → Plate (scanner deposits)
    - Red claw (right): Plate (scanner pickups) → Boxes
    - Moving plate handles Y-axis positioning
    """

    def __init__(self, ax, scanner_list, box_list, moving_plate):
        """
        Initialize dual-claw crane

        Args:
            ax: Matplotlib axes
            scanner_list: List of DScanner objects
            box_list: List of Box objects
            moving_plate: MovingPlate object
        """
        self.ax = ax
        self.scanner_list = scanner_list
        self.box_list = box_list
        self.moving_plate = moving_plate

        # Crane position (single body, moves on X-axis only)
        self.x = config.CRANE_HOME_X
        self.y = config.CRANE_Y  # Fixed Y at scanner level
        self.z = self.y  # Z starts at crane level

        # Movement parameters
        self.vmax_x = config.VMAX_CRANE_X
        self.a_x = config.A_CRANE_X
        self.vmax_z = config.VMAX_CLAW_Z
        self.a_z = config.A_CLAW_Z
        self.lower_time = config.T_Z
        self.raise_time = config.T_Z

        # Crane state
        self.crane_state = "IDLE"  # IDLE, MOVING_TO_X
        self.target_x = None
        self.action_timer = 0.0

        # Movement tracking for X-axis
        self._move_start_x = None
        self._move_total_time = None

        # Blue claw (left) state
        self.blue_state = "IDLE"
        self.blue_z = self.y  # Z position of blue claw
        self.blue_has_diamond = False
        self.blue_has_buffered_diamond = False  # Holding a preloaded diamond
        self.blue_target_scanner = None  # Which scanner to deliver to
        self.blue_timer = 0.0
        self.blue_phase = None  # LOWER, RAISE, SETTLE

        # Cycle tracking for optimized logic
        self.cycle_step = 0  # Track position in optimization cycle
        self.left_scanner_filled = False
        self.right_scanner_filled = False

        # Red claw (right) state
        self.red_state = "IDLE"
        self.red_z = self.y  # Z position of red claw
        self.red_has_diamond = False
        self.red_source_scanner = None  # Which scanner to pick from
        self.red_target_box = None  # Which box to deliver to
        self.red_timer = 0.0
        self.red_phase = None  # LOWER, RAISE, SETTLE
        self.red_waiting_for_blue_refill = False  # True when red picked and waiting for blue to refill scanner
        self.red_early_arrival = False  # True when using early arrival optimization

        # Visual elements
        self.create_visuals()

    def create_visuals(self):
        """Create visual elements for crane and claws"""
        display_x = config.mm_to_display(self.x)
        display_y = config.mm_to_display(self.y)
        display_width = config.mm_to_display(config.CRANE_WIDTH)
        display_height = config.mm_to_display(config.CRANE_HEIGHT)

        # Main crane body (gray rectangle)
        self.crane_rect = Rectangle(
            (display_x - display_width/2, display_y - display_height/2),
            display_width, display_height,
            fc='#888888', ec='black', lw=2, zorder=5
        )
        self.ax.add_patch(self.crane_rect)

        # Blue claw (left side)
        blue_x = display_x + config.mm_to_display(config.BLUE_CLAW_OFFSET)
        claw_w = config.mm_to_display(config.CLAW_WIDTH)
        claw_h = config.mm_to_display(config.CLAW_HEIGHT)

        self.blue_claw_rect = Rectangle(
            (blue_x - claw_w/2, display_y - claw_h/2),
            claw_w, claw_h,
            fc=config.COLOR_BLUE_CLAW, ec='black', lw=1.5, zorder=6
        )
        self.ax.add_patch(self.blue_claw_rect)

        # Blue progress bar (initially invisible)
        prog_bar_h = 0.3
        self.blue_progress_bg = Rectangle(
            (blue_x - claw_w/2, display_y - claw_h/2 - prog_bar_h - 0.2),
            claw_w, prog_bar_h,
            fc='white', ec='black', lw=1, zorder=7
        )
        self.ax.add_patch(self.blue_progress_bg)
        self.blue_progress_bg.set_visible(False)

        self.blue_progress_bar = Rectangle(
            (blue_x - claw_w/2, display_y - claw_h/2 - prog_bar_h - 0.2),
            0, prog_bar_h,
            fc=config.COLOR_BLUE_CLAW, ec='none', zorder=8
        )
        self.ax.add_patch(self.blue_progress_bar)
        self.blue_progress_bar.set_visible(False)

        # Blue status text
        self.blue_status_text = self.ax.text(
            blue_x, display_y + claw_h/2 + 0.5,
            '', ha='center', va='bottom',
            fontsize=8, fontweight='bold', color=config.COLOR_BLUE_CLAW,
            zorder=9
        )

        # Blue diamond
        self.blue_diamond = make_diamond(blue_x, display_y, '#33a3ff', size=0.18, z=7)
        self.blue_diamond.set_visible(False)
        self.ax.add_patch(self.blue_diamond)

        # Red claw (right side)
        red_x = display_x + config.mm_to_display(config.RED_CLAW_OFFSET)

        self.red_claw_rect = Rectangle(
            (red_x - claw_w/2, display_y - claw_h/2),
            claw_w, claw_h,
            fc=config.COLOR_RED_CLAW, ec='black', lw=1.5, zorder=6
        )
        self.ax.add_patch(self.red_claw_rect)

        # Red progress bar (initially invisible)
        self.red_progress_bg = Rectangle(
            (red_x - claw_w/2, display_y - claw_h/2 - prog_bar_h - 0.2),
            claw_w, prog_bar_h,
            fc='white', ec='black', lw=1, zorder=7
        )
        self.ax.add_patch(self.red_progress_bg)
        self.red_progress_bg.set_visible(False)

        self.red_progress_bar = Rectangle(
            (red_x - claw_w/2, display_y - claw_h/2 - prog_bar_h - 0.2),
            0, prog_bar_h,
            fc=config.COLOR_RED_CLAW, ec='none', zorder=8
        )
        self.ax.add_patch(self.red_progress_bar)
        self.red_progress_bar.set_visible(False)

        # Red status text
        self.red_status_text = self.ax.text(
            red_x, display_y + claw_h/2 + 0.5,
            '', ha='center', va='bottom',
            fontsize=8, fontweight='bold', color=config.COLOR_RED_CLAW,
            zorder=9
        )

        # Red diamond
        self.red_diamond = make_diamond(red_x, display_y, '#ff6b6b', size=0.18, z=7)
        self.red_diamond.set_visible(False)
        self.ax.add_patch(self.red_diamond)

    def update_visuals(self):
        """Update visual positions of crane and claws"""
        display_x = config.mm_to_display(self.x)
        display_y = config.mm_to_display(self.y)
        display_width = config.mm_to_display(config.CRANE_WIDTH)
        display_height = config.mm_to_display(config.CRANE_HEIGHT)

        # Update crane body
        self.crane_rect.set_xy((display_x - display_width/2, display_y - display_height/2))

        # Update blue claw
        blue_x = display_x + config.mm_to_display(config.BLUE_CLAW_OFFSET)
        claw_w = config.mm_to_display(config.CLAW_WIDTH)
        claw_h = config.mm_to_display(config.CLAW_HEIGHT)

        # Blue claw stays at crane level, but shows progress
        self.blue_claw_rect.set_xy((blue_x - claw_w/2, display_y - claw_h/2))

        # Update blue progress bar and text
        prog_bar_h = 0.3
        if self.blue_phase in ["LOWER", "RAISE", "SETTLE"]:
            # Show progress bar
            self.blue_progress_bg.set_visible(True)
            self.blue_progress_bar.set_visible(True)

            # Calculate progress
            if self.blue_phase == "LOWER":
                progress = 1.0 - (self.blue_timer / self.lower_time)
                self.blue_status_text.set_text("LOWERING")
            elif self.blue_phase == "RAISE":
                progress = 1.0 - (self.blue_timer / self.raise_time)
                self.blue_status_text.set_text("RAISING")
            else:  # SETTLE
                progress = 1.0  # Full progress bar during settle
                self.blue_status_text.set_text("SETTLING")

            # Update progress bar width
            self.blue_progress_bar.set_width(claw_w * progress)

            # Update positions
            self.blue_progress_bg.set_xy((blue_x - claw_w/2, display_y - claw_h/2 - prog_bar_h - 0.2))
            self.blue_progress_bar.set_xy((blue_x - claw_w/2, display_y - claw_h/2 - prog_bar_h - 0.2))
            self.blue_status_text.set_position((blue_x, display_y + claw_h/2 + 0.5))
        else:
            # Hide progress bar
            self.blue_progress_bg.set_visible(False)
            self.blue_progress_bar.set_visible(False)
            self.blue_status_text.set_text("")

        # Update blue diamond (show both active and buffered)
        if self.blue_has_diamond or self.blue_has_buffered_diamond:
            self.blue_diamond.xy = (blue_x, display_y)
            self.blue_diamond.set_visible(True)
            # Change color if buffered
            if self.blue_has_buffered_diamond:
                self.blue_diamond.set_facecolor('#88ccff')  # Lighter blue for buffered
            else:
                self.blue_diamond.set_facecolor('#33a3ff')  # Normal blue for active
        else:
            self.blue_diamond.set_visible(False)

        # Update red claw
        red_x = display_x + config.mm_to_display(config.RED_CLAW_OFFSET)

        # Red claw stays at crane level, but shows progress
        self.red_claw_rect.set_xy((red_x - claw_w/2, display_y - claw_h/2))

        # Update red progress bar and text
        if self.red_phase in ["LOWER", "RAISE", "SETTLE", "WAIT_AT_BOTTOM"] or self.red_state == "WAIT_FOR_BLUE_REFILL":
            # Show progress bar
            self.red_progress_bg.set_visible(True)
            self.red_progress_bar.set_visible(True)

            # Calculate progress
            if self.red_phase == "LOWER":
                progress = 1.0 - (self.red_timer / self.lower_time)
                self.red_status_text.set_text("LOWERING")
            elif self.red_phase == "RAISE":
                progress = 1.0 - (self.red_timer / self.raise_time)
                self.red_status_text.set_text("RAISING")
            elif self.red_phase == "SETTLE":
                progress = 1.0  # Full progress bar during settle
                self.red_status_text.set_text("SETTLING")
            elif self.red_phase == "WAIT_AT_BOTTOM":
                progress = 1.0  # Full progress bar while waiting
                self.red_status_text.set_text("WAITING")
            elif self.red_state == "WAIT_FOR_BLUE_REFILL":
                progress = 1.0  # Full progress bar while waiting for blue
                self.red_status_text.set_text("WAIT REFILL")
            else:
                progress = 0.0
                self.red_status_text.set_text("")

            # Update progress bar width
            self.red_progress_bar.set_width(claw_w * progress)

            # Update positions
            self.red_progress_bg.set_xy((red_x - claw_w/2, display_y - claw_h/2 - prog_bar_h - 0.2))
            self.red_progress_bar.set_xy((red_x - claw_w/2, display_y - claw_h/2 - prog_bar_h - 0.2))
            self.red_status_text.set_position((red_x, display_y + claw_h/2 + 0.5))
        else:
            # Hide progress bar
            self.red_progress_bg.set_visible(False)
            self.red_progress_bar.set_visible(False)
            self.red_status_text.set_text("")

        # Update red diamond
        if self.red_has_diamond:
            self.red_diamond.xy = (red_x, display_y)
            self.red_diamond.set_visible(True)
        else:
            self.red_diamond.set_visible(False)

    def move_to_x(self, target_x):
        """
        Start moving crane to target X position

        Args:
            target_x: Target X position in mm
        """
        if abs(self.x - target_x) < 1.0:  # Already at target
            self.crane_state = "IDLE"
            return

        self.crane_state = "MOVING_TO_X"
        self.target_x = target_x
        self.action_timer = config.calculate_x_travel_time(self.x, target_x)

        # Reset movement tracking
        self._move_start_x = None
        self._move_total_time = None

    def step(self, dt):
        """
        Update crane state for one time step

        Args:
            dt: Time step in seconds
        """
        # Update crane X movement
        if self.crane_state == "MOVING_TO_X":
            self.action_timer = max(0.0, self.action_timer - dt)

            if self.action_timer > 0:
                # Still moving
                if self._move_start_x is None:
                    self._move_start_x = self.x
                    self._move_total_time = self.action_timer + dt

                # Calculate progress
                progress = 1.0 - (self.action_timer / self._move_total_time)
                self.x = self._move_start_x + (self.target_x - self._move_start_x) * progress
            else:
                # Arrived at target
                self.x = self.target_x
                self._move_start_x = None
                self._move_total_time = None
                self.crane_state = "IDLE"
                self.target_x = None

        # Update blue claw
        self.step_blue_claw(dt)

        # Update red claw
        self.step_red_claw(dt)

        # Update visuals
        self.update_visuals()

    def step_blue_claw(self, dt):
        """Update blue claw state with optimized cycle logic"""
        if self.blue_state == "IDLE":
            # Decide next action based on cycle step
            # Steps 1-4: Initial filling of both scanners
            # Steps 5+: Maintain steady state with buffering

            if not self.blue_has_diamond and not self.blue_has_buffered_diamond:
                # Need to get a diamond from START
                # Check if we should preload (buffer) or fill a scanner

                if self.cycle_step < 2:
                    # Steps 1-2: Fill left scanner, then right scanner (initial fill)
                    if not self.left_scanner_filled:
                        self.blue_target_scanner = 0  # Left scanner
                        self.blue_state = "GO_TO_START"
                        self.blue_timer = 0.0
                    elif not self.right_scanner_filled:
                        self.blue_target_scanner = 1  # Right scanner
                        self.blue_state = "GO_TO_START"
                        self.blue_timer = 0.0
                else:
                    # Steady state: Always preload when idle and no buffer
                    if not self.blue_has_buffered_diamond:
                        self.blue_target_scanner = None  # Will be determined when red picks
                        self.blue_state = "GO_TO_START"
                        self.blue_timer = 0.0

        elif self.blue_state == "GO_TO_START":
            # Wait for:
            # 1. Plate brings START to rail Y level (CRANE_Y)
            # 2. Crane is stationary
            # 3. Blue claw is EXACTLY above pickup X position
            pickup_x = config.PICKUP_X
            blue_claw_x = self.x + config.BLUE_CLAW_OFFSET

            if (self.moving_plate.is_at_position(config.CRANE_Y) and  # Plate at rail level
                    self.moving_plate.is_idle() and  # Plate stopped moving
                    self.crane_state == "IDLE" and   # Crane stopped moving
                    abs(blue_claw_x - pickup_x) < 2.0):  # Blue claw above pickup (tighter tolerance)
                # Start picking
                self.blue_state = "PICK_AT_START"
                self.blue_timer = self.lower_time
                self.blue_phase = "LOWER"

        elif self.blue_state == "PICK_AT_START":
            self.blue_timer = max(0.0, self.blue_timer - dt)

            if self.blue_phase == "LOWER":
                # Animate lowering
                if self.blue_timer > 0:
                    progress = 1.0 - (self.blue_timer / self.lower_time)
                    self.blue_z = self.y - config.D_Z * progress
                else:
                    # Finished lowering, now raise with diamond
                    self.blue_z = self.y - config.D_Z
                    self.blue_has_diamond = True
                    self.blue_phase = "RAISE"
                    self.blue_timer = self.raise_time

            elif self.blue_phase == "RAISE":
                # Animate raising
                if self.blue_timer > 0:
                    progress = self.blue_timer / self.raise_time
                    self.blue_z = self.y - config.D_Z * progress
                else:
                    # Finished raising - wait a moment before state change
                    self.blue_z = self.y
                    self.blue_phase = "SETTLE"
                    self.blue_timer = 0.3  # 300ms settle time to ensure visual completion

            elif self.blue_phase == "SETTLE":
                # Wait for settle time before transitioning
                self.blue_timer = max(0.0, self.blue_timer - dt)
                if self.blue_timer <= 0:
                    self.blue_phase = None

                    # Decide next action based on cycle
                    if self.cycle_step < 2:
                        # Initial fill: deliver immediately to scanner
                        print(f"[BLUE] Initial fill - delivering to scanner {self.blue_target_scanner}")
                        self.blue_state = "MOVE_TO_SCANNER"
                    else:
                        # Steady state: buffer the diamond
                        print(f"[BLUE] Buffering diamond, cycle_step={self.cycle_step}")
                        self.blue_has_buffered_diamond = True
                        self.blue_has_diamond = False  # Move from active to buffer
                        self.blue_state = "WAITING_FOR_RED"  # Wait for red to pick before refilling

        elif self.blue_state == "MOVE_TO_SCANNER":
            # Scanners are STATIONARY at rail level (CRANE_Y)
            # Wait for:
            # 1. Crane is stationary
            # 2. Blue claw is EXACTLY above scanner X position
            scanner_x, _ = self.scanner_list[self.blue_target_scanner].get_position()
            blue_claw_x = self.x + config.BLUE_CLAW_OFFSET

            if (self.crane_state == "IDLE" and   # Crane stopped moving
                    abs(blue_claw_x - scanner_x) < 2.0):  # Blue claw above scanner
                # Start dropping
                self.blue_state = "DROP_AT_SCANNER"
                self.blue_timer = self.lower_time
                self.blue_phase = "LOWER"

        elif self.blue_state == "DROP_AT_SCANNER":
            self.blue_timer = max(0.0, self.blue_timer - dt)

            if self.blue_phase == "LOWER":
                # Animate lowering
                if self.blue_timer > 0:
                    progress = 1.0 - (self.blue_timer / self.lower_time)
                    self.blue_z = self.y - config.D_Z * progress
                else:
                    # Finished lowering, drop diamond
                    self.blue_z = self.y - config.D_Z
                    self.blue_has_diamond = False
                    # Trigger scanner scan
                    self.scanner_list[self.blue_target_scanner].scan()

                    # If this was a refill for red, clear the waiting flag
                    if self.red_waiting_for_blue_refill and self.red_source_scanner == self.blue_target_scanner:
                        print(f"[BLUE] Refilled scanner {self.blue_target_scanner}, clearing red's waiting flag")
                        self.red_waiting_for_blue_refill = False

                    self.blue_phase = "RAISE"
                    self.blue_timer = self.raise_time

            elif self.blue_phase == "RAISE":
                # Animate raising
                if self.blue_timer > 0:
                    progress = self.blue_timer / self.raise_time
                    self.blue_z = self.y - config.D_Z * progress
                else:
                    # Finished raising - wait a moment before state change
                    self.blue_z = self.y
                    self.blue_phase = "SETTLE"
                    self.blue_timer = 0.3  # 300ms settle time to ensure visual completion

            elif self.blue_phase == "SETTLE":
                # Wait for settle time before transitioning
                self.blue_timer = max(0.0, self.blue_timer - dt)
                if self.blue_timer <= 0:
                    self.blue_phase = None

                    # Update cycle tracking
                    if self.blue_target_scanner == 0:
                        self.left_scanner_filled = True
                        if self.cycle_step == 0:
                            self.cycle_step = 1
                    elif self.blue_target_scanner == 1:
                        self.right_scanner_filled = True
                        if self.cycle_step == 1:
                            self.cycle_step = 2  # Enter steady state

                    self.blue_target_scanner = None
                    self.blue_state = "IDLE"

        elif self.blue_state == "WAITING_FOR_RED":
            # Holding buffered diamond, waiting for red to pick from scanner
            # Red will signal when it's safe to refill
            if self.red_waiting_for_blue_refill and self.red_source_scanner is not None:
                # Red has picked and is waiting for us to refill
                print(f"[BLUE] Red picked from scanner {self.red_source_scanner}, refilling now!")
                self.blue_target_scanner = self.red_source_scanner
                self.blue_has_diamond = True  # Move from buffer to active
                self.blue_has_buffered_diamond = False
                self.blue_state = "MOVE_TO_SCANNER"  # Go refill the scanner red just emptied

    def step_red_claw(self, dt):
        """Update red claw state with early arrival and synchronized refill"""
        if self.red_state == "IDLE":
            # Check if any scanner has a diamond ready or will be ready soon
            if not self.red_has_diamond:
                # CRITICAL: In steady state, only pick if blue has pre-loaded a diamond
                # This ensures blue is ready to refill immediately after red picks
                if self.cycle_step >= 2 and not self.blue_has_buffered_diamond:
                    # Blue hasn't pre-loaded yet, wait for it
                    return

                target_scanner = None
                earliest_ready_time = float('inf')
                use_early_arrival = False

                for i, scanner in enumerate(self.scanner_list):
                    if scanner.state == "ready":
                        # Scanner already ready - check if we can pick it
                        if self.cycle_step < 2:
                            # Initial fill phase: pick immediately
                            target_scanner = i
                            earliest_ready_time = 0
                            use_early_arrival = False
                            break
                        else:
                            # Steady state: pick immediately (blue already has buffer)
                            target_scanner = i
                            earliest_ready_time = 0
                            use_early_arrival = False
                            break
                    elif scanner.state == "scanning" and self.cycle_step >= 2:
                        # Steady state: Check if we can use early arrival
                        time_until_ready = scanner.timer
                        if time_until_ready < earliest_ready_time:
                            # Calculate if we can arrive and lower before it's ready
                            scanner_x, _ = scanner.get_position()
                            travel_time = config.calculate_x_travel_time(self.x, scanner_x)

                            if travel_time + self.lower_time < time_until_ready:
                                # We can arrive early!
                                earliest_ready_time = time_until_ready
                                target_scanner = i
                                use_early_arrival = True

                if target_scanner is not None:
                    self.red_source_scanner = target_scanner
                    self.red_target_box = self.scanner_list[target_scanner].get_target_box()
                    self.red_early_arrival = use_early_arrival
                    print(f"[RED] Going to scanner {target_scanner}, early_arrival={use_early_arrival}, blue_buffered={self.blue_has_buffered_diamond}")
                    self.red_state = "GO_TO_SCANNER"
                    self.red_timer = 0.0

        elif self.red_state == "GO_TO_SCANNER":
            # Scanners are STATIONARY at rail level (CRANE_Y)
            # Wait for crane to be stationary and positioned
            scanner_x, _ = self.scanner_list[self.red_source_scanner].get_position()
            red_claw_x = self.x + config.RED_CLAW_OFFSET

            if (self.crane_state == "IDLE" and abs(red_claw_x - scanner_x) < 2.0):
                # Arrived at scanner
                if self.red_early_arrival:
                    # Early arrival: Can start lowering even if not ready yet
                    self.red_state = "PICK_AT_SCANNER"
                    self.red_timer = self.lower_time
                    self.red_phase = "LOWER"
                else:
                    # Normal arrival: Scanner should be ready
                    if self.scanner_list[self.red_source_scanner].state == "ready":
                        self.red_state = "PICK_AT_SCANNER"
                        self.red_timer = self.lower_time
                        self.red_phase = "LOWER"

        elif self.red_state == "PICK_AT_SCANNER":
            self.red_timer = max(0.0, self.red_timer - dt)

            if self.red_phase == "LOWER":
                # Animate lowering
                if self.red_timer > 0:
                    progress = 1.0 - (self.red_timer / self.lower_time)
                    self.red_z = self.y - config.D_Z * progress
                else:
                    # Finished lowering - now at bottom
                    self.red_z = self.y - config.D_Z

                    # Check if scanner is ready (might be waiting for scan to complete)
                    if self.scanner_list[self.red_source_scanner].state == "ready":
                        # Scanner is ready! Pick it up
                        self.red_has_diamond = True
                        box_id = self.scanner_list[self.red_source_scanner].pickup()
                        if box_id is not None:
                            self.red_target_box = box_id

                        # Signal blue to refill this scanner
                        print(f"[RED] Picked from scanner {self.red_source_scanner}, signaling blue to refill")
                        self.red_waiting_for_blue_refill = True

                        self.red_phase = "RAISE"
                        self.red_timer = self.raise_time
                    else:
                        # Still scanning - wait at bottom (early arrival case)
                        self.red_phase = "WAIT_AT_BOTTOM"
                        self.red_timer = 0.0

            elif self.red_phase == "WAIT_AT_BOTTOM":
                # Waiting at bottom for scanner to finish
                if self.scanner_list[self.red_source_scanner].state == "ready":
                    # Scanner ready! Pick it up
                    self.red_has_diamond = True
                    box_id = self.scanner_list[self.red_source_scanner].pickup()
                    if box_id is not None:
                        self.red_target_box = box_id

                    # Signal blue to refill this scanner
                    print(f"[RED] Scanner ready! Picked from scanner {self.red_source_scanner}, signaling blue to refill")
                    self.red_waiting_for_blue_refill = True

                    self.red_phase = "RAISE"
                    self.red_timer = self.raise_time

            elif self.red_phase == "RAISE":
                # Animate raising
                if self.red_timer > 0:
                    progress = self.red_timer / self.raise_time
                    self.red_z = self.y - config.D_Z * progress
                else:
                    # Finished raising - wait a moment before state change
                    self.red_z = self.y
                    self.red_phase = "SETTLE"
                    self.red_timer = 0.3  # 300ms settle time to ensure visual completion

            elif self.red_phase == "SETTLE":
                # Wait for settle time before transitioning
                self.red_timer = max(0.0, self.red_timer - dt)
                if self.red_timer <= 0:
                    self.red_phase = None
                    # Check if blue has refilled the scanner
                    if not self.red_waiting_for_blue_refill:
                        # Blue already refilled, can move to box
                        self.red_state = "MOVE_TO_BOX"
                    else:
                        # Wait for blue to refill
                        self.red_state = "WAIT_FOR_BLUE_REFILL"

        elif self.red_state == "WAIT_FOR_BLUE_REFILL":
            # Picked diamond and raised, waiting for blue to refill scanner before leaving
            # Blue will detect this state and refill, then clear the flag
            if not self.red_waiting_for_blue_refill:
                # Blue has refilled! Now we can go to box
                print(f"[RED] Blue refilled! Going to box {self.red_target_box}")
                self.red_state = "MOVE_TO_BOX"

        elif self.red_state == "MOVE_TO_BOX":
            # Wait for:
            # 1. Plate brings box to rail Y level (CRANE_Y)
            # 2. Crane is stationary
            # 3. Red claw is EXACTLY above box X position
            box_x, box_y = self.box_list[self.red_target_box].get_position()
            red_claw_x = self.x + config.RED_CLAW_OFFSET

            # Calculate what Y position the plate needs to be at to bring this box to rail level
            # Box is at offset box_y from plate, so: plate_y + box_y = CRANE_Y
            # Therefore: plate_y = CRANE_Y - box_y
            target_plate_y = config.CRANE_Y - box_y

            if (self.moving_plate.is_at_position(target_plate_y) and  # Plate brings box to rail level
                    self.moving_plate.is_idle() and  # Plate stopped moving
                    self.crane_state == "IDLE" and   # Crane stopped moving
                    abs(red_claw_x - box_x) < 2.0):  # Red claw above box
                # Start dropping
                self.red_state = "DROP_AT_BOX"
                self.red_timer = self.lower_time
                self.red_phase = "LOWER"

        elif self.red_state == "DROP_AT_BOX":
            self.red_timer = max(0.0, self.red_timer - dt)

            if self.red_phase == "LOWER":
                # Animate lowering
                if self.red_timer > 0:
                    progress = 1.0 - (self.red_timer / self.lower_time)
                    self.red_z = self.y - config.D_Z * progress
                else:
                    # Finished lowering, drop diamond
                    self.red_z = self.y - config.D_Z
                    self.red_has_diamond = False
                    # Add diamond to box (just increment count, don't show visual)
                    self.box_list[self.red_target_box].add_diamond()
                    self.red_phase = "RAISE"
                    self.red_timer = self.raise_time

            elif self.red_phase == "RAISE":
                # Animate raising
                if self.red_timer > 0:
                    progress = self.red_timer / self.raise_time
                    self.red_z = self.y - config.D_Z * progress
                else:
                    # Finished raising - wait a moment before state change
                    self.red_z = self.y
                    self.red_phase = "SETTLE"
                    self.red_timer = 0.3  # 300ms settle time to ensure visual completion

            elif self.red_phase == "SETTLE":
                # Wait for settle time before transitioning
                self.red_timer = max(0.0, self.red_timer - dt)
                if self.red_timer <= 0:
                    self.red_phase = None
                    self.red_source_scanner = None
                    self.red_target_box = None
                    self.red_state = "IDLE"

    def reset(self):
        """Reset crane to initial state"""
        self.x = config.CRANE_HOME_X
        self.y = config.CRANE_Y
        self.z = self.y
        self.crane_state = "IDLE"
        self.target_x = None
        self.action_timer = 0.0
        self._move_start_x = None
        self._move_total_time = None

        # Reset blue claw
        self.blue_state = "IDLE"
        self.blue_z = self.y
        self.blue_has_diamond = False
        self.blue_has_buffered_diamond = False
        self.blue_target_scanner = None
        self.blue_timer = 0.0
        self.blue_phase = None

        # Reset cycle tracking
        self.cycle_step = 0
        self.left_scanner_filled = False
        self.right_scanner_filled = False

        # Reset red claw
        self.red_state = "IDLE"
        self.red_z = self.y
        self.red_has_diamond = False
        self.red_source_scanner = None
        self.red_target_box = None
        self.red_timer = 0.0
        self.red_phase = None
        self.red_waiting_for_blue_refill = False
        self.red_early_arrival = False

        self.update_visuals()
