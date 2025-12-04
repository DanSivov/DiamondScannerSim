# Ver3.5/RealisticDualClawSim/simulation.py
"""
Main simulation controller for Ver3.5 Realistic Dual-Claw Diamond Sorting System

Features:
- Dual-claw crane with independent lowering mechanisms
- Moving plate for Y-axis positioning
- Simplified logic (no collision detection needed)
- Performance metrics tracking
"""

import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
from matplotlib.patches import Circle, Rectangle
from matplotlib.widgets import Button, TextBox

from . import config
from .scanner import DScanner
from .endBox import Box
from .moving_plate import MovingPlate
from .crane import DualClawCrane


class SimulationController:
    """Main controller for the diamond sorting simulation"""

    def __init__(self):
        """Initialize the simulation"""
        # Setup figure with larger size for better visibility
        self.fig, self.ax = plt.subplots(figsize=(16, 12))
        plt.subplots_adjust(bottom=0.12, top=0.95, left=0.08, right=0.95)

        self.setup_axes()
        self.draw_static_elements()

        # Create components
        self.create_scanners()
        self.create_boxes()
        self.moving_plate = MovingPlate(self.ax)
        self.crane = DualClawCrane(self.ax, self.scanner_list, self.box_list, self.moving_plate)

        # Add START diamond visual (always visible - infinite supply)
        pickup_x, pickup_y = config.get_pickup_position()
        display_x = config.mm_to_display(pickup_x)
        display_y = config.mm_to_display(pickup_y)
        from .scanner import make_diamond
        self.start_diamond = make_diamond(display_x, display_y, '#33a3ff', size=0.18)
        self.ax.add_patch(self.start_diamond)
        self.start_diamond.set_visible(True)

        # Simulation state
        self.t_elapsed = 0.0
        self.is_paused = False
        self.diamonds_delivered = 0
        self.diamonds_scanned = 0
        self.timer_started = False  # Start timer only when first diamond is picked by blue

        # Simple coordinator state
        self.coordinator_state = "INIT"
        self.coordinator_timer = 0.0

        # Create UI elements
        self.create_metrics_display()
        self.create_controls()

        # Animation
        self.anim = None

    def setup_axes(self):
        """Setup matplotlib axes with proper scaling"""
        # Calculate display bounds (with larger margins for less cramped view)
        margin = 100  # mm - increased for better view
        x_min = -500 - margin
        x_max = 500 + margin
        y_min = -100  # More space below
        y_max = 300  # More space above

        # Convert to display units
        self.ax.set_xlim(config.mm_to_display(x_min), config.mm_to_display(x_max))
        self.ax.set_ylim(config.mm_to_display(y_min), config.mm_to_display(y_max))

        self.ax.set_aspect('equal')
        self.ax.grid(True, alpha=0.3, linestyle='--')
        self.ax.set_xlabel('X Position (mm × 0.1)', fontsize=10)
        self.ax.set_ylabel('Y Position (mm × 0.1)', fontsize=10)
        self.ax.set_title('Ver3.5 Dual-Claw Simulation\nDiamond Sorting System',
                          fontsize=12, fontweight='bold')

        plt.style.use('ggplot')

    def draw_static_elements(self):
        """Draw crane track and scanners"""
        self.draw_crane_track()
        self.draw_scanners_outline()
        # Note: Pickup zone and end boxes are now on the moving plate

    def draw_crane_track(self):
        """Draw the crane track (horizontal line at scanner level)"""
        x_start = config.mm_to_display(-400)
        x_end = config.mm_to_display(400)
        y = config.mm_to_display(config.CRANE_Y)

        self.ax.plot([x_start, x_end], [y, y],
                     linewidth=6, color=config.COLOR_RAIL,
                     solid_capstyle='round', zorder=1, label='Crane Track')

    def draw_scanners_outline(self):
        """Draw scanner outlines"""
        for i, (x_mm, y_mm) in enumerate(config.get_scanner_positions()):
            x = config.mm_to_display(x_mm)
            y = config.mm_to_display(y_mm)
            w = config.mm_to_display(config.S_W_SCANNER)
            h = config.mm_to_display(config.S_H_SCANNER)

            # Scanner body
            scanner = Rectangle(
                (x - w/2, y - h/2), w, h,
                facecolor=config.COLOR_SCANNER,
                edgecolor='black',
                linewidth=2,
                alpha=0.8,
                zorder=2
            )
            self.ax.add_patch(scanner)

            # Drop zone circle
            drop_r = config.mm_to_display(config.SCANNER_DROP_RADIUS)
            drop_zone = Circle((x, y), drop_r,
                               facecolor='red', edgecolor='darkred',
                               linewidth=1.5, zorder=3)
            self.ax.add_patch(drop_zone)

    def create_scanners(self):
        """Create scanner objects"""
        self.scanner_list = []
        for x, y in config.get_scanner_positions():
            scanner = DScanner(x, y)
            scanner.add_diamond_to_plot(self.ax)
            scanner.add_state_label(self.ax)
            self.scanner_list.append(scanner)

    def create_boxes(self):
        """Create end box objects"""
        self.box_list = []
        positions = config.get_end_box_positions()
        for i, (x, y) in enumerate(positions):
            box = Box(i, x, y)
            self.box_list.append(box)

    def create_metrics_display(self):
        """Create text elements for displaying metrics"""
        # Time display - top left
        self.time_text = self.fig.text(
            0.02, 0.98, '',
            fontsize=11, verticalalignment='top',
            bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.8)
        )

        # Metrics display - top center
        self.metrics_text = self.fig.text(
            0.3, 0.98, '',
            fontsize=10, verticalalignment='top',
            bbox=dict(boxstyle='round', facecolor='lightblue', alpha=0.8)
        )

    def update_metrics_display(self):
        """Update the metrics text display"""
        # Time display
        self.time_text.set_text(f'Time: {self.t_elapsed:.1f}s')

        # Calculate diamonds per minute
        if self.t_elapsed > 0:
            dpm = (self.diamonds_delivered / self.t_elapsed) * 60
        else:
            dpm = 0.0

        # Metrics display
        metrics_str = (
            f'Diamonds Delivered: {self.diamonds_delivered}\n'
            f'Diamonds Scanned: {self.diamonds_scanned}\n'
            f'Throughput: {dpm:.2f} diamonds/min'
        )

        # Add box distribution
        box_counts = [box.get_count() for box in self.box_list]
        metrics_str += f'\n\nBox Distribution:'
        for i, count in enumerate(box_counts):
            if i % 4 == 0:
                metrics_str += '\n'
            metrics_str += f' {i+1}:{count}'

        self.metrics_text.set_text(metrics_str)

    def create_controls(self):
        """Create pause/resume and skip controls"""
        # Control dimensions
        h = 0.05
        w_pause = 0.1
        w_text = 0.12
        w_go = 0.06
        spacing = 0.015

        # Calculate centered starting position
        total_width = w_pause + spacing + w_text + spacing + w_go
        left_start = 0.5 - total_width / 2
        bottom = 0.02

        # Pause button
        pause_ax = plt.axes([left_start, bottom, w_pause, h])
        self.pause_button = Button(pause_ax, 'Pause')
        self.pause_button.on_clicked(self.toggle_pause)

        # Skip text box
        skip_text_ax = plt.axes([left_start + w_pause + spacing, bottom, w_text, h])
        self.skip_textbox = TextBox(skip_text_ax, 'Skip t=', initial="0.0")

        # Skip button
        skip_button_ax = plt.axes([left_start + w_pause + spacing + w_text + spacing, bottom, w_go, h])
        self.skip_button = Button(skip_button_ax, 'Go')
        self.skip_button.on_clicked(self.skip_to_time)

    def toggle_pause(self, event):
        """Toggle pause state"""
        self.is_paused = not self.is_paused
        self.pause_button.label.set_text('Resume' if self.is_paused else 'Pause')

    def skip_to_time(self, event):
        """Skip simulation forward to the entered time"""
        try:
            target_time = float(self.skip_textbox.text)
        except ValueError:
            print("Invalid time entered")
            return

        # Validate target time
        if target_time < 0:
            print("Cannot skip to negative time")
            return

        # Store current pause state
        was_paused = self.is_paused
        self.is_paused = True  # Pause during skip

        print(f"\n{'='*70}")
        print(f"SKIP TO t={target_time:.1f}s")
        print(f"{'='*70}")
        print("Resetting simulation...")
        self.full_reset()

        # Update metrics display to show reset values
        self.update_metrics_display()

        # If target time is 0, we're done (just reset)
        if target_time <= 0.01:
            print("Skip complete: Reset to t=0")
            self.is_paused = was_paused
            self.fig.canvas.draw_idle()
            return

        print(f"Fast-forwarding to t={target_time:.1f}s...")

        # Use normal simulation timestep for accuracy
        skip_dt = config.DT
        max_steps = int(target_time / skip_dt) + 1000
        step_count = 0

        # Fast-forward
        while self.t_elapsed < target_time and step_count < max_steps:
            self.step_simulation(skip_dt, skip_mode=True)
            step_count += 1

            # Progress reporting (every 10% of target time)
            if step_count % 1000 == 0:
                progress = (self.t_elapsed / target_time) * 100
                print(f"  Progress: {progress:.1f}% (t={self.t_elapsed:.1f}s)")

        # Update metrics display with final values
        self.update_metrics_display()

        # Update visuals
        self.fig.canvas.draw_idle()

        print(f"{'='*70}")
        print(f"Skip complete: t={self.t_elapsed:.1f}s, {self.diamonds_delivered} diamonds delivered")
        print(f"{'='*70}\n")

        # Restore pause state
        self.is_paused = was_paused

    def full_reset(self):
        """Full reset of simulation to initial state"""
        # Reset time and metrics
        self.t_elapsed = 0.0
        self.diamonds_delivered = 0
        self.diamonds_scanned = 0
        self.timer_started = False

        # Reset coordinator
        self.coordinator_state = "INIT"
        self.coordinator_timer = 0.0

        # Reset scanners
        for scanner in self.scanner_list:
            scanner.reset()

        # Reset boxes
        for box in self.box_list:
            box.reset()

        # Reset moving plate
        self.moving_plate.reset()

        # Reset crane
        self.crane.reset()

        # Update displays
        self.update_metrics_display()

    def coordinate_movements(self, dt):
        """
        Coordinator to manage plate and crane movements

        Key rules:
        1. Position crane so ACTIVE claw is directly above target
        2. Blue and red CAN'T operate simultaneously if at different Y levels
        3. NEVER move crane if ANY claw is in a PICK or DROP state (including phases)
        """
        # Update coordinator timer
        self.coordinator_timer = max(0.0, self.coordinator_timer - dt)

        if self.coordinator_state == "INIT":
            # Start: plate at home (brings START to rail level), crane at center
            if self.coordinator_timer <= 0:
                # Plate should already be at PLATE_Y_HOME from initialization
                # Just ensure crane is centered
                self.crane.move_to_x(config.CRANE_HOME_X)
                self.coordinator_state = "RUNNING"
                self.coordinator_timer = 0.5  # Short wait

        elif self.coordinator_state == "RUNNING":
            # CRITICAL: Check if ANY claw is currently in a pick/drop operation
            # WAITING states are passive and should NOT block movement (the other claw needs to move!)
            blue_is_picking_or_dropping = self.crane.blue_state in ["PICK_AT_START", "DROP_AT_SCANNER"]
            red_is_picking_or_dropping = self.crane.red_state in ["PICK_AT_SCANNER", "DROP_AT_BOX"]
            any_claw_has_phase = self.crane.blue_phase is not None or self.crane.red_phase is not None

            # If any claw is actively picking/dropping or has an active phase, block ALL movement commands
            if blue_is_picking_or_dropping or red_is_picking_or_dropping or any_claw_has_phase:
                return  # Exit early, don't issue any movement commands

            # Coordinate crane and plate movements
            # Key rules:
            # 1. Blue picks from START: plate brings START to CRANE_Y
            # 2. Blue deposits at scanner: scanner already at CRANE_Y (stationary)
            # 3. Red picks from scanner: scanner already at CRANE_Y (stationary)
            # 4. Red deposits at box: plate brings box to CRANE_Y
            # 5. Crane positions so active claw is directly above target X

            # Now that we've verified no claw is picking/dropping, handle movement states
            # PRIORITY ORDER: Red with diamond > Red picking > Blue operations
            # Red carrying a diamond to box should have highest priority

            if self.crane.red_state == "MOVE_TO_BOX":
                # HIGHEST PRIORITY: Red delivering diamond to box
                if self.crane.red_target_box is not None:
                    box_x, box_y = self.box_list[self.crane.red_target_box].get_position()
                    target_plate_y = config.CRANE_Y - box_y
                    if not self.moving_plate.is_at_position(target_plate_y):
                        self.moving_plate.move_to(target_plate_y)

                    target_crane_x = box_x - config.RED_CLAW_OFFSET
                    if abs(self.crane.x - target_crane_x) > 2.0:
                        self.crane.move_to_x(target_crane_x)

            elif self.crane.red_state == "GO_TO_SCANNER":
                # PRIORITY 2: Red going to pick from scanner
                if self.crane.red_source_scanner is not None:
                    scanner_x, _ = self.scanner_list[self.crane.red_source_scanner].get_position()
                    target_crane_x = scanner_x - config.RED_CLAW_OFFSET
                    if abs(self.crane.x - target_crane_x) > 2.0:
                        self.crane.move_to_x(target_crane_x)

            elif self.crane.blue_state == "MOVE_TO_SCANNER":
                # PRIORITY 3: Blue delivering to scanner (refill operation)
                if self.crane.blue_target_scanner is not None:
                    scanner_x, _ = self.scanner_list[self.crane.blue_target_scanner].get_position()
                    target_crane_x = scanner_x - config.BLUE_CLAW_OFFSET
                    if abs(self.crane.x - target_crane_x) > 2.0:
                        self.crane.move_to_x(target_crane_x)

            elif self.crane.blue_state == "GO_TO_START":
                # PRIORITY 4: Blue picking from START (lowest priority)
                target_plate_y = config.CRANE_Y - config.PICKUP_Y
                if not self.moving_plate.is_at_position(target_plate_y):
                    self.moving_plate.move_to(target_plate_y)

                target_crane_x = config.PICKUP_X - config.BLUE_CLAW_OFFSET
                if abs(self.crane.x - target_crane_x) > 2.0:
                    self.crane.move_to_x(target_crane_x)

    def step_simulation(self, dt, skip_mode=False):
        """Execute one simulation time step"""
        # Don't apply speed multiplier during skip mode
        if not skip_mode:
            dt *= config.SIM_SPEED_MULTIPLIER

        # Update scanners
        for scanner in self.scanner_list:
            scanner.update(dt, self.t_elapsed)
            if not skip_mode:  # Skip label updates during fast-forward
                scanner.update_state_label()

        # Update moving plate
        self.moving_plate.step(dt)

        # Coordinate movements
        self.coordinate_movements(dt)

        # Update crane
        self.crane.step(dt)

        # Start timer when blue picks first diamond
        if not self.timer_started and self.crane.blue_has_diamond:
            self.timer_started = True
            print("[TIMER] Started! First diamond picked by blue claw")

        # Update delivered count
        current_delivered = sum(box.get_count() for box in self.box_list)
        if current_delivered > self.diamonds_delivered:
            self.diamonds_delivered = current_delivered

        # Update scanned count
        current_scanned = sum(scanner.scans_done for scanner in self.scanner_list)
        if current_scanned > self.diamonds_scanned:
            self.diamonds_scanned = current_scanned

        # Update time (only if timer has started)
        if self.timer_started:
            self.t_elapsed += dt

        # Update START diamond position (moves with plate)
        if not skip_mode:  # Skip visual updates during fast-forward
            pickup_x, pickup_y = config.get_pickup_position()
            display_x = config.mm_to_display(pickup_x)
            # Pickup Y is relative to plate
            plate_y = self.moving_plate.y
            display_y = config.mm_to_display(plate_y + pickup_y)
            self.start_diamond.xy = (display_x, display_y)

        # Update metrics display
        if not skip_mode:  # Skip metric updates during fast-forward
            self.update_metrics_display()

    def animation_update(self, frame):
        """Animation update function called by FuncAnimation"""
        if not self.is_paused:
            self.step_simulation(config.DT)
        return []

    def run(self):
        """Start the simulation animation"""
        self.anim = FuncAnimation(
            self.fig,
            self.animation_update,
            interval=int(1000 / config.FPS),
            blit=False,
            cache_frame_data=False
        )

        # Position window at top-left corner of screen
        try:
            mng = plt.get_current_fig_manager()
            # Try TkAgg backend
            try:
                mng.window.wm_geometry("+0+0")
            except AttributeError:
                # Try Qt backend
                try:
                    mng.window.setGeometry(0, 0, 1600, 1200)
                except:
                    pass  # Other backends - use default position
        except:
            pass  # If positioning fails, just use default

        plt.show()


def run_simulation():
    """Main entry point to run the simulation"""
    print("=" * 70)
    print("STARTING VER3.5 DUAL-CLAW SIMULATION")
    print("=" * 70)
    print("\nConfiguration:")
    print(f"  Scanners: 2")
    print(f"  End Boxes: {config.N_BOXES}")
    print(f"  Scan Time: {config.T_SCAN}s")
    print(f"  FPS: {config.FPS}")
    print("\nControls:")
    print("  - Pause/Resume button to control simulation")
    print("  - Close window to exit")
    print("\nStarting simulation...")
    print("=" * 70)

    controller = SimulationController()
    controller.run()


if __name__ == "__main__":
    run_simulation()
