"""
Main simulation controller for Ver3 Realistic Two-Claw Diamond Sorting System

Features:
- 2D crane movement with optimal scheduling
- Performance metrics tracking (diamonds/minute, throughput)
- Animation with pause/resume
- State management for skip functionality
"""

import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
from matplotlib.patches import Circle, Rectangle
from matplotlib.widgets import Button, TextBox
import matplotlib.patches as mpatches

from . import config
from .scanner import DScanner
from .endBox import Box
from .crane import BlueCrane, RedCrane


class SimulationController:
    """Main controller for the diamond sorting simulation"""

    def __init__(self, enable_side_view=False):
        """Initialize the simulation"""
        # Setup figure with subplots based on side view option
        self.enable_side_view = enable_side_view

        if enable_side_view:
            # Create figure with two subplots side-by-side
            self.fig, (self.ax, self.ax_side) = plt.subplots(
                1, 2,
                figsize=(config.DISPLAY_WIDTH * 1.8, config.DISPLAY_HEIGHT),
                gridspec_kw={'width_ratios': [1, 1]}
            )
            plt.subplots_adjust(bottom=0.15, left=0.05, right=0.98, wspace=0.2)
        else:
            # Single plot (original behavior)
            self.fig, self.ax = plt.subplots(figsize=(config.DISPLAY_WIDTH, config.DISPLAY_HEIGHT))
            plt.subplots_adjust(bottom=0.15)
            self.ax_side = None

        # Position window at top left corner of screen
        manager = plt.get_current_fig_manager()
        try:
            manager.window.update_idletasks()
            # Top left position with small margins
            x = 10  # 10px from left edge
            y = 10  # 10px from top
            manager.window.wm_geometry(f"+{x}+{y}")
        except:
            pass

        self.setup_axes()
        self.draw_static_elements()

        # Create scanners, boxes, and cranes
        self.create_scanners()
        self.create_boxes()
        self.create_cranes()

        # Create side view elements if enabled
        if self.enable_side_view and self.ax_side is not None:
            self.setup_side_view_static()
            self.setup_side_view_dynamic()

        # Simulation state
        self.t_elapsed = 0.0
        self.is_paused = False
        self.diamonds_delivered = 0
        self.diamonds_scanned = 0
        self.simulation_started = False  # Timer starts when blue crane first picks up diamond

        # Metrics
        self.total_ready_wait_time = 0.0

        # Create UI elements
        self.create_metrics_display()
        self.create_controls()

        # Animation
        self.anim = None

    def skip_to_time(self, event):
        """Skip simulation forward or backward to the entered time"""
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

        # CRITICAL: Always do a full reset before skipping
        # This ensures clean state regardless of skip direction
        print(f"\n{'='*70}")
        print(f"SKIP TO t={target_time:.1f}s")
        print(f"{'='*70}")
        print("Resetting simulation...")
        self.full_reset()

        # If target time is 0, we're done (just reset)
        if target_time <= 0.01:  # Use small epsilon for floating point
            print("Skip complete: Reset to t=0")
            self.is_paused = was_paused
            self.fig.canvas.draw_idle()
            if self.enable_side_view:
                self.update_side_view()
            return

        # Fast-forward to target_time with robust error handling
        print(f"Fast-forwarding to t={target_time:.1f}s...")

        # Use SMALLER time steps to prevent collision violations
        # Larger steps cause cranes to "jump" past collision checks
        # CRITICAL: Must use small dt to maintain collision detection
        skip_dt = config.DT  # Use normal simulation timestep (1/60 = 0.0167s)

        # For very large skips, we can afford to skip visual updates
        # but we MUST keep physics/collision timestep small
        print(f"Using dt={skip_dt:.4f}s per step (maintaining collision detection)")

        # Calculate reasonable max steps (with generous buffer)
        max_steps = int(target_time / skip_dt) + 10000
        step_count = 0
        last_valid_state = None
        last_t = 0.0

        # Progress reporting thresholds (report every 5% for better feedback)
        progress_milestones = [int(target_time * p / 100) for p in range(5, 100, 5)]
        next_milestone_idx = 0

        try:
            while self.t_elapsed < target_time and step_count < max_steps:
                # Save state periodically in case we need to recover
                if step_count % 100 == 0:
                    last_valid_state = {
                        't_elapsed': self.t_elapsed,
                        'diamonds_delivered': self.diamonds_delivered,
                        'diamonds_scanned': self.diamonds_scanned
                    }

                # Execute one simulation step
                self.step_simulation(skip_dt, skip_mode=True)

                # Progress reporting (every 5% of target time)
                if (next_milestone_idx < len(progress_milestones) and
                        self.t_elapsed >= progress_milestones[next_milestone_idx]):
                    progress_pct = int((self.t_elapsed / target_time) * 100)
                    print(f"  Progress: {progress_pct}% (t={self.t_elapsed:.1f}s, {self.diamonds_delivered} diamonds)")
                    next_milestone_idx += 1

                # Safety check: ensure time is actually progressing
                # Check every 5000 steps
                if step_count > 0 and step_count % 5000 == 0:
                    time_delta = self.t_elapsed - last_t
                    expected_delta = skip_dt * 5000
                    if time_delta < expected_delta * 0.5:  # Should have made at least 50% of expected progress
                        print(f"Warning: Slow progress at t={self.t_elapsed:.2f}s")
                        print(f"  Expected {expected_delta:.2f}s, got {time_delta:.2f}s over last 5000 steps")
                        # Don't break, just warn
                    last_t = self.t_elapsed

                step_count += 1

                # Every 10000 steps, clean up any stale movement tracking
                if step_count % 10000 == 0:
                    self.cleanup_crane_tracking()

        except Exception as e:
            print(f"Error during skip at t={self.t_elapsed:.2f}s: {e}")
            print("Attempting recovery...")
            # Try to restore last valid state
            if last_valid_state:
                self.t_elapsed = last_valid_state['t_elapsed']
                self.diamonds_delivered = last_valid_state['diamonds_delivered']
                self.diamonds_scanned = last_valid_state['diamonds_scanned']
            else:
                # Fall back to full reset
                self.full_reset()

            import traceback
            traceback.print_exc()

        if step_count >= max_steps:
            print(f"Warning: Skip loop exceeded maximum steps ({max_steps})")
            print(f"Stopped at t={self.t_elapsed:.2f}s")
            print(f"This might indicate a simulation issue or the target time is too large")

        # Post-skip cleanup and validation
        print("Performing post-skip cleanup...")
        self.cleanup_after_skip()

        # Restore pause state
        self.is_paused = was_paused

        # Force full redraw
        self.fig.canvas.draw_idle()
        if self.enable_side_view:
            self.update_side_view()

        print(f"{'='*70}")
        print(f"Skip complete: t={self.t_elapsed:.1f}s, {self.diamonds_delivered} diamonds delivered")
        print(f"{'='*70}\n")

    def full_reset(self):
        """Perform a complete reset of the simulation"""
        # Reset all state variables
        self.t_elapsed = 0.0
        self.diamonds_delivered = 0
        self.diamonds_scanned = 0
        self.total_ready_wait_time = 0.0
        self.simulation_started = False

        # Reset scanners
        for scanner in self.scanner_list:
            scanner.reset()
            if hasattr(scanner, 'scans_done'):
                scanner.scans_done = 0

        # Reset boxes
        for box in self.box_list:
            box.reset()

        # Reset cranes with full cleanup
        self.blue_crane.reset()
        self.red_crane.reset()

        # Extra cleanup
        self.cleanup_crane_tracking()

        # Update display
        self.update_metrics_display()

    def cleanup_crane_tracking(self):
        """Clean up any stale movement tracking variables in cranes"""
        for crane in [self.blue_crane, self.red_crane]:
            # Remove movement tracking variables
            if hasattr(crane, '_move_start_x'):
                del crane._move_start_x
            if hasattr(crane, '_move_start_y'):
                del crane._move_start_y
            if hasattr(crane, '_move_total_time'):
                del crane._move_total_time

            # Ensure visual position matches logical position
            crane.update_position()

            # Update diamond position if carrying
            if crane.has_diamond:
                display_x = config.mm_to_display(crane.x)
                display_y = config.mm_to_display(crane.top_y)
                crane.diamond.xy = (display_x, display_y)

    def cleanup_after_skip(self):
        """Comprehensive cleanup after skip operation"""
        # Clean up crane tracking
        self.cleanup_crane_tracking()

        # Validate crane states
        for crane in [self.blue_crane, self.red_crane]:
            # If crane is in a movement state but has no timer, fix it
            if crane.state in ["MOVE_TO_SCANNER", "MOVE_TO_BOX", "RETURN_HOME",
                               "MOVE_TO_START", "RETURN_TO_START", "MOVE_OUT_OF_WAY_AFTER_RIGHT_PICKUP",
                               "MOVE_OUT_OF_WAY_AFTER_RIGHT_LOAD", "MOVE_TO_BOX_THEN_RIGHT_SCANNER"]:
                if crane.action_timer <= 0:
                    # Timer expired but state not updated - force to WAIT
                    print(f"Warning: {crane.color} crane in movement state with no timer, forcing to WAIT")
                    crane.state = "WAIT"
                    crane.action_timer = 0.0

            # Clear any pick/drop phases that might be stuck
            if crane.action_timer <= 0:
                if crane.pick_phase is not None:
                    crane.pick_phase = None
                if crane.drop_phase is not None:
                    crane.drop_phase = None

        # CRITICAL: Check for collision violations
        distance_between_cranes = abs(self.blue_crane.x - self.red_crane.x)
        safe_distance = config.D_CLAW_SAFE_DISTANCE

        if distance_between_cranes < safe_distance:
            print(f"\n{'!'*70}")
            print(f"ERROR: Collision violation detected after skip!")
            print(f"  Blue crane X: {self.blue_crane.x:.1f}mm")
            print(f"  Red crane X:  {self.red_crane.x:.1f}mm")
            print(f"  Distance:     {distance_between_cranes:.1f}mm")
            print(f"  Safe dist:    {safe_distance:.1f}mm")
            print(f"  Violation:    {safe_distance - distance_between_cranes:.1f}mm")
            print(f"\nAttempting to fix by moving cranes to safe positions...")
            print(f"{'!'*70}\n")

            # Move both cranes to their home positions to separate them
            self.blue_crane.x = config.BLUE_CRANE_HOME_X
            self.blue_crane.y = config.BLUE_CRANE_HOME_Y
            self.blue_crane.state = "WAIT"
            self.blue_crane.action_timer = 0.0
            self.blue_crane.has_diamond = False
            self.blue_crane.diamond.set_visible(False)
            self.blue_crane.update_position()

            self.red_crane.x = config.RED_CRANE_HOME_X
            self.red_crane.y = config.RED_CRANE_HOME_Y
            self.red_crane.state = "WAIT"
            self.red_crane.action_timer = 0.0
            self.red_crane.has_diamond = False
            self.red_crane.diamond.set_visible(False)
            self.red_crane.update_position()

            print("Cranes moved to safe home positions")
            print(f"  Blue crane now at X={self.blue_crane.x:.1f}mm")
            print(f"  Red crane now at X={self.red_crane.x:.1f}mm")
            print(f"  New distance: {abs(self.blue_crane.x - self.red_crane.x):.1f}mm\n")

        # Update metrics
        self.update_metrics_display()

    def setup_axes(self):
        """Setup matplotlib axes with proper scaling"""
        # Main view (top-down) setup
        # Calculate display bounds (with margins)
        margin = 50  # mm
        x_min = config.RAIL_X_MIN - margin
        x_max = config.RAIL_X_MAX + margin
        y_min = config.PICKUP_Y - margin
        y_max = config.RAIL_Y + margin

        # Convert to display units
        self.ax.set_xlim(config.mm_to_display(x_min), config.mm_to_display(x_max))
        self.ax.set_ylim(config.mm_to_display(y_min), config.mm_to_display(y_max))

        self.ax.set_aspect('equal')
        self.ax.grid(True, alpha=0.3, linestyle='--')
        self.ax.set_xlabel('X Position (mm × 0.1)', fontsize=10)
        self.ax.set_ylabel('Y Position (mm × 0.1)', fontsize=10)
        self.ax.set_title('Top-Down View - Diamond Sorting Simulation\nVer3 Realistic Two-Claw System',
                          fontsize=12, fontweight='bold')

        # Side view setup (if enabled)
        if self.enable_side_view and self.ax_side is not None:
            # Side view shows vertical movement
            self.ax_side.set_xlim(config.mm_to_display(x_min), config.mm_to_display(x_max))
            self.ax_side.set_ylim(config.mm_to_display(y_min), config.mm_to_display(y_max))

            self.ax_side.set_aspect('equal')
            self.ax_side.grid(True, alpha=0.3, linestyle='--')
            self.ax_side.set_xlabel('Horizontal Position (mm × 0.1)', fontsize=10)
            self.ax_side.set_ylabel('Vertical Height (mm × 0.1)', fontsize=10)
            self.ax_side.set_title('Side View - Crane Vertical Movement',
                                   fontsize=12, fontweight='bold')

        plt.style.use('ggplot')

    def draw_static_elements(self):
        """Draw rail, scanners, pickup zone, and end boxes"""
        self.draw_rail()
        self.draw_scanners_outline()
        self.draw_pickup_zone()
        self.draw_end_boxes()
        #self.add_legend()

    def draw_rail(self):
        """Draw the rail"""
        x_start = config.mm_to_display(config.RAIL_X_MIN)
        x_end = config.mm_to_display(config.RAIL_X_MAX)
        y = config.mm_to_display(config.RAIL_Y)

        self.ax.plot([x_start, x_end], [y, y],
                     linewidth=6, color=config.COLOR_RAIL,
                     solid_capstyle='round', zorder=1, label='Rail')

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
                alpha=0.5,
                zorder=2
            )
            self.ax.add_patch(scanner)

            # Drop zone circle
            drop_r = config.mm_to_display(config.SCANNER_DROP_RADIUS)
            drop_zone = Circle((x, y), drop_r,
                               facecolor='red', edgecolor='darkred',
                               linewidth=1.5, zorder=3)
            self.ax.add_patch(drop_zone)

            # Label
            label = f"Scanner {i+1}"
            self.ax.text(x, y - h/2 - config.mm_to_display(8),
                         label, ha='center', va='top',
                         fontsize=10, fontweight='bold')

    def draw_pickup_zone(self):
        """Draw pickup zone"""
        x = config.mm_to_display(config.PICKUP_X)
        y = config.mm_to_display(config.PICKUP_Y)
        size = config.mm_to_display(config.PICKUP_RADIUS)

        pickup = Rectangle(
            (x - size/2, y - size/2), size, size,
            facecolor=config.COLOR_PICKUP,
            edgecolor='darkgreen',
            linewidth=2,
            alpha=0.7,
            zorder=2
        )
        self.ax.add_patch(pickup)

        # Crosshair
        cross = size * 0.3
        self.ax.plot([x - cross/2, x + cross/2], [y, y], 'k-', linewidth=2, zorder=3)
        self.ax.plot([x, x], [y - cross/2, y + cross/2], 'k-', linewidth=2, zorder=3)

        self.ax.text(x, y - size/2 - config.mm_to_display(5),
                     'START', ha='center', va='top',
                     fontsize=10, fontweight='bold', color='darkgreen')

    def draw_end_boxes(self):
        """Draw end boxes"""
        positions = config.get_end_box_positions()
        for i, (x_mm, y_mm) in enumerate(positions):
            x = config.mm_to_display(x_mm)
            y = config.mm_to_display(y_mm)
            r = config.mm_to_display(config.BOX_RADIUS)

            box_circle = Circle((x, y), r,
                                facecolor=config.COLOR_END_BOX,
                                edgecolor='darkorange',
                                linewidth=1.5,
                                alpha=0.6,
                                zorder=2)
            self.ax.add_patch(box_circle)

            self.ax.text(x, y, str(i+1),
                         ha='center', va='center',
                         fontsize=8, fontweight='bold')

    def add_legend(self):
        """Add legend"""
        from matplotlib.lines import Line2D
        legend_elements = [
            Line2D([0], [0], marker='s', color='w', markerfacecolor=config.COLOR_BLUE_CLAW,
                   markersize=10, label='Blue Claw'),
            Line2D([0], [0], marker='s', color='w', markerfacecolor=config.COLOR_RED_CLAW,
                   markersize=10, label='Red Claw'),
            Line2D([0], [0], marker='s', color='w', markerfacecolor=config.COLOR_SCANNER,
                   markersize=10, label='Scanner'),
            Line2D([0], [0], marker='o', color='w', markerfacecolor=config.COLOR_END_BOX,
                   markersize=10, label='End Box'),
        ]
        self.ax.legend(handles=legend_elements, loc='upper left', fontsize=9)

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

    def create_cranes(self):
        """Create crane objects"""
        self.blue_crane = BlueCrane(self.ax, self.scanner_list)
        self.red_crane = RedCrane(self.ax, self.scanner_list, self.box_list)

    def setup_side_view_static(self):
        """Setup static elements for side view (rail, scanners, boxes)"""
        if self.ax_side is None:
            return

        print("Setting up side view static elements...")

        # Rail (at the top)
        x_start = config.mm_to_display(config.RAIL_X_MIN)
        x_end = config.mm_to_display(config.RAIL_X_MAX)
        y_rail = config.mm_to_display(config.RAIL_Y)

        self.ax_side.plot([x_start, x_end], [y_rail, y_rail],
                          linewidth=4, color=config.COLOR_RAIL,
                          solid_capstyle='round', zorder=1)

        # Calculate scanner platform height
        scanner_platform_height = config.RAIL_Y - config.D_Z
        y_scanner = config.mm_to_display(scanner_platform_height)

        # Draw scanners
        for i, scanner in enumerate(self.scanner_list):
            scanner_x = scanner.x_pos
            x_display = config.mm_to_display(scanner_x)

            width = config.mm_to_display(config.S_W_SCANNER)
            height = config.mm_to_display(config.S_H_SCANNER)

            # Scanner box
            scanner_rect = Rectangle(
                (x_display - width/2, y_scanner - height/2),
                width, height,
                facecolor=config.COLOR_SCANNER,
                edgecolor='black',
                linewidth=2.5,
                alpha=0.8,
                zorder=2
            )
            self.ax_side.add_patch(scanner_rect)

            # Drop zone line
            drop_y = y_scanner + height/2
            self.ax_side.plot([x_display - width/2, x_display + width/2],
                              [drop_y, drop_y],
                              'r-', linewidth=3, zorder=3, alpha=0.9)

            # Label
            self.ax_side.text(x_display, y_scanner - height/2 - config.mm_to_display(15),
                              f"Scanner {i+1}",
                              ha='center', va='top', fontsize=10, fontweight='bold',
                              bbox=dict(boxstyle='round,pad=0.3', facecolor='white', alpha=0.7))

        # Draw end boxes (first row only)
        box_positions = config.get_end_box_positions()
        first_row_indices = [0, 1, 2, 3]
        y_box = y_scanner

        for idx in first_row_indices:
            if idx < len(box_positions):
                box_x, _ = box_positions[idx]
                x_display = config.mm_to_display(box_x)
                box_radius = config.mm_to_display(config.BOX_RADIUS)

                box_circle = Circle(
                    (x_display, y_box),
                    box_radius,
                    facecolor=config.COLOR_END_BOX,
                    edgecolor='darkorange',
                    linewidth=2,
                    alpha=0.7,
                    zorder=2
                )
                self.ax_side.add_patch(box_circle)

                self.ax_side.text(x_display, y_box,
                                  str(idx + 1),
                                  ha='center', va='center',
                                  fontsize=9, fontweight='bold',
                                  color='black')

        # Draw START box
        pickup_x = config.mm_to_display(config.PICKUP_X)
        pickup_y = config.mm_to_display(config.PICKUP_Y)
        size = config.mm_to_display(config.PICKUP_RADIUS)

        pickup_rect = Rectangle(
            (pickup_x - size/2, pickup_y - size/2), size, size,
            facecolor=config.COLOR_PICKUP,
            edgecolor='darkgreen',
            linewidth=2.5,
            alpha=0.8,
            zorder=2
        )
        self.ax_side.add_patch(pickup_rect)

        # Crosshair
        cross = size * 0.3
        self.ax_side.plot([pickup_x - cross/2, pickup_x + cross/2], [pickup_y, pickup_y],
                          'darkgreen', linewidth=2, zorder=3)
        self.ax_side.plot([pickup_x, pickup_x], [pickup_y - cross/2, pickup_y + cross/2],
                          'darkgreen', linewidth=2, zorder=3)

        # Label
        self.ax_side.text(pickup_x, pickup_y - size/2 - config.mm_to_display(10),
                          'START', ha='center', va='top',
                          fontsize=10, fontweight='bold', color='darkgreen',
                          bbox=dict(boxstyle='round,pad=0.3', facecolor='lightgreen', alpha=0.7))

        print("Side view static elements created")

    def setup_side_view_dynamic(self):
        """Setup dynamic elements for side view (cranes, hoists, diamonds)"""
        if self.ax_side is None:
            return

        print("Setting up side view dynamic elements...")

        w = config.mm_to_display(config.CRANE_WIDTH)
        h = config.mm_to_display(config.CRANE_HEIGHT)

        # Blue crane elements
        blue_x = config.mm_to_display(self.blue_crane.x)
        blue_z = config.mm_to_display(self.blue_crane.z)

        self.side_blue_crane_rect = Rectangle(
            (blue_x - w/2, blue_z - h/2), w, h,
            fc=config.COLOR_BLUE_CLAW, ec='black', lw=1.5, zorder=5
        )
        self.ax_side.add_patch(self.side_blue_crane_rect)

        self.side_blue_hoist, = self.ax_side.plot([], [], color=config.COLOR_BLUE_CLAW,
                                                  lw=2, zorder=4, linestyle='--')

        self.side_blue_hand = Circle((blue_x, blue_z), config.mm_to_display(15),
                                     fc=config.COLOR_BLUE_CLAW, ec='black',
                                     lw=1, zorder=6)
        self.ax_side.add_patch(self.side_blue_hand)

        self.side_blue_diamond = Circle((blue_x, blue_z), config.mm_to_display(10),
                                        fc='#33a3ff', ec='black', lw=1, zorder=7)
        self.side_blue_diamond.set_visible(False)
        self.ax_side.add_patch(self.side_blue_diamond)

        # Red crane elements
        red_x = config.mm_to_display(self.red_crane.x)
        red_z = config.mm_to_display(self.red_crane.z)

        self.side_red_crane_rect = Rectangle(
            (red_x - w/2, red_z - h/2), w, h,
            fc=config.COLOR_RED_CLAW, ec='black', lw=1.5, zorder=5
        )
        self.ax_side.add_patch(self.side_red_crane_rect)

        self.side_red_hoist, = self.ax_side.plot([], [], color=config.COLOR_RED_CLAW,
                                                 lw=2, zorder=4, linestyle='--')

        self.side_red_hand = Circle((red_x, red_z), config.mm_to_display(15),
                                    fc=config.COLOR_RED_CLAW, ec='black',
                                    lw=1, zorder=6)
        self.ax_side.add_patch(self.side_red_hand)

        self.side_red_diamond = Circle((red_x, red_z), config.mm_to_display(10),
                                       fc='#ff6b6b', ec='black', lw=1, zorder=7)
        self.side_red_diamond.set_visible(False)
        self.ax_side.add_patch(self.side_red_diamond)

        print("Side view dynamic elements created")

    def update_side_view(self):
        """Update side view based on current crane positions"""
        if self.ax_side is None:
            return

        w = config.mm_to_display(config.CRANE_WIDTH)
        h = config.mm_to_display(config.CRANE_HEIGHT)

        # Update blue crane
        blue_x = config.mm_to_display(self.blue_crane.x)
        blue_z_crane = config.mm_to_display(self.blue_crane.z)

        self.side_blue_crane_rect.set_xy((blue_x - w/2, blue_z_crane - h/2))

        # Calculate hand position
        blue_hand_z = self.get_crane_hand_z(self.blue_crane)
        blue_hand_z_display = config.mm_to_display(blue_hand_z)

        # Update hoist line
        if blue_hand_z < self.blue_crane.z - 10:
            self.side_blue_hoist.set_data([blue_x, blue_x],
                                          [blue_z_crane, blue_hand_z_display])
            self.side_blue_hoist.set_visible(True)
        else:
            self.side_blue_hoist.set_visible(False)

        # Update hand
        self.side_blue_hand.center = (blue_x, blue_hand_z_display)

        # Update diamond
        if self.blue_crane.has_diamond:
            self.side_blue_diamond.center = (blue_x, blue_hand_z_display)
            self.side_blue_diamond.set_visible(True)
        else:
            self.side_blue_diamond.set_visible(False)

        # Update red crane
        red_x = config.mm_to_display(self.red_crane.x)
        red_z_crane = config.mm_to_display(self.red_crane.z)

        self.side_red_crane_rect.set_xy((red_x - w/2, red_z_crane - h/2))

        # Calculate hand position
        red_hand_z = self.get_crane_hand_z(self.red_crane)
        red_hand_z_display = config.mm_to_display(red_hand_z)

        # Update hoist line
        if red_hand_z < self.red_crane.z - 10:
            self.side_red_hoist.set_data([red_x, red_x],
                                         [red_z_crane, red_hand_z_display])
            self.side_red_hoist.set_visible(True)
        else:
            self.side_red_hoist.set_visible(False)

        # Update hand
        self.side_red_hand.center = (red_x, red_hand_z_display)

        # Update diamond
        if self.red_crane.has_diamond:
            self.side_red_diamond.center = (red_x, red_hand_z_display)
            self.side_red_diamond.set_visible(True)
        else:
            self.side_red_diamond.set_visible(False)

    def get_crane_hand_z(self, crane):
        """Calculate the Z position of the crane's hand based on its state"""
        hand_z = crane.z

        if crane.pick_phase == "LOWER":
            if crane.action_timer > 0:
                progress = 1.0 - (crane.action_timer / crane.lower_time)
                hand_z = crane.rail_y - (crane.rail_y - crane.top_y) * progress
            else:
                hand_z = crane.top_y
        elif crane.pick_phase == "RAISE":
            if crane.action_timer > 0:
                progress = crane.action_timer / crane.raise_time
                hand_z = crane.rail_y - (crane.rail_y - crane.top_y) * progress
            else:
                hand_z = crane.rail_y
        elif crane.drop_phase == "LOWER":
            if crane.action_timer > 0:
                progress = 1.0 - (crane.action_timer / crane.lower_time)
                hand_z = crane.rail_y - (crane.rail_y - crane.top_y) * progress
            else:
                hand_z = crane.top_y
        elif crane.drop_phase == "RAISE":
            if crane.action_timer > 0:
                progress = crane.action_timer / crane.raise_time
                hand_z = crane.rail_y - (crane.rail_y - crane.top_y) * progress
            else:
                hand_z = crane.rail_y

        return hand_z

    def create_metrics_display(self):
        """Create text elements for displaying metrics"""
        # Position at top left of axes
        self.time_text = self.ax.text(
            0.02, 0.98, '', transform=self.ax.transAxes,
            fontsize=11, verticalalignment='top',
            bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.8)
        )

        self.metrics_text = self.ax.text(
            0.02, 0.88, '', transform=self.ax.transAxes,
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

        # Calculate average ready wait time
        if self.diamonds_delivered > 0:
            avg_wait = self.total_ready_wait_time / self.diamonds_delivered
        else:
            avg_wait = 0.0

        # Metrics display
        metrics_str = (
            f'Diamonds Delivered: {self.diamonds_delivered}\n'
            f'Diamonds Scanned: {self.diamonds_scanned}\n'
            f'Throughput: {dpm:.2f} diamonds/min\n'
            f'Avg Ready Wait: {avg_wait:.2f}s'
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
        """Create pause/resume and skip controls, centered below plot"""

        # Common dimensions
        h = 0.05   # height
        w_pause = 0.1
        w_text  = 0.12
        w_go    = 0.08
        spacing = 0.02  # horizontal spacing between widgets

        # Total width of the control row
        total_w = w_pause + spacing + w_text + spacing + w_go

        # Left coordinate so that the row is centered
        left_start = 0.5 - total_w/2
        bottom = 0.02  # vertical position

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

    def step_simulation(self, dt, skip_mode=False):
        """Execute one simulation time step"""
        # CRITICAL: Don't apply speed multiplier during skip mode
        # Speed multiplier is for visual playback speed only
        # During skip, we need consistent physics timestep to prevent collisions
        if not skip_mode:
            dt *= config.SIM_SPEED_MULTIPLIER  # Only for normal animation

        # Check if simulation should start (blue crane starts picking up first diamond)
        if not self.simulation_started:
            if (self.blue_crane.state == "PICK_AT_START" and
                    self.blue_crane.pick_phase == "LOWER"):
                # Blue crane is lowering to pick up first diamond - start timer!
                self.simulation_started = True

        # Update scanners
        for scanner in self.scanner_list:
            scanner.update(dt, self.t_elapsed)
            if not skip_mode:  # Skip label updates during fast-forward
                scanner.update_state_label()

        # Track Total Ready Wait (TRW) time - time diamonds spend waiting in "ready" state
        # Only count if simulation has started
        if self.simulation_started:
            for scanner in self.scanner_list:
                if scanner.state == "ready":
                    # Diamond is ready but not yet being picked up - accumulate wait time
                    self.total_ready_wait_time += dt

        # Update cranes
        self.blue_crane.step(dt, self.blue_crane, self.red_crane)
        self.red_crane.step(dt, self.blue_crane, self.red_crane)

        # Track when red crane delivers diamonds
        # We check if red crane just completed a drop
        if self.red_crane.state == "RETURN_HOME" and self.red_crane.action_timer > 0:
            # Just finished dropping, count was already incremented in crane
            pass

        # Update delivered count from boxes
        current_delivered = sum(box.get_count() for box in self.box_list)
        if current_delivered > self.diamonds_delivered:
            self.diamonds_delivered = current_delivered

        # Update scanned count from scanners
        current_scanned = sum(scanner.scans_done for scanner in self.scanner_list)
        if current_scanned > self.diamonds_scanned:
            self.diamonds_scanned = current_scanned

        # Update time
        # CRITICAL FIX: Always advance time, even before simulation_started
        # This is especially important during skip mode
        if skip_mode:
            # During skip, always advance time to reach target
            self.t_elapsed += dt
        else:
            # During normal animation, only advance time after simulation starts
            if self.simulation_started:
                self.t_elapsed += dt

        # Update metrics display (skip during fast-forward for performance)
        if not skip_mode:
            self.update_metrics_display()

        # Update side view if enabled (skip during fast-forward for performance)
        if self.enable_side_view and not skip_mode:
            try:
                self.update_side_view()
            except Exception as e:
                print(f"Warning: Side view update failed: {e}")

    def reset_simulation(self):
        """Reset simulation to initial state (for skip functionality)"""
        self.full_reset()

    def animation_update(self, frame):
        """Animation update function called by FuncAnimation"""
        if not self.is_paused:
            self.step_simulation(config.DT, skip_mode=False)
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
        plt.show()


def run_simulation(enable_side_view=False):
    """Main entry point to run the simulation"""
    print("=" * 70)
    print("STARTING VER3 DIAMOND SORTING SIMULATION")
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

    controller = SimulationController(enable_side_view=enable_side_view)
    controller.run()


if __name__ == "__main__":
    run_simulation()