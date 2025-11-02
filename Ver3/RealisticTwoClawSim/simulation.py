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

    def __init__(self):
        """Initialize the simulation"""
        # Setup figure and axes
        self.fig, self.ax = plt.subplots(figsize=(config.DISPLAY_WIDTH, config.DISPLAY_HEIGHT))
        plt.subplots_adjust(bottom=0.15)  # Make room for controls

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

        # Always reset to ensure clean state
        self.reset_simulation()

        # If target time is 0, we're done (just reset)
        if target_time == 0:
            self.is_paused = was_paused
            self.fig.canvas.draw_idle()
            return

        # Fast-forward until target_time
        # Use a safety counter to prevent infinite loops
        max_steps = int(target_time / config.DT) + 1000  # Extra buffer
        step_count = 0

        while self.t_elapsed < target_time and step_count < max_steps:
            try:
                self.step_simulation(config.DT)
            except Exception as e:
                print(f"Error during skip at t={self.t_elapsed:.2f}s: {e}")
                print("Resetting simulation to safe state")
                self.reset_simulation()
                self.is_paused = was_paused
                self.fig.canvas.draw_idle()
                return
            step_count += 1

        if step_count >= max_steps:
            print(f"Warning: Skip loop exceeded maximum steps. Stopped at t={self.t_elapsed:.2f}s")

        # Post-skip validation: ensure cranes are in valid states
        # Clear any stale movement tracking that might have accumulated
        for crane in [self.blue_crane, self.red_crane]:
            if hasattr(crane, '_move_start_x'):
                del crane._move_start_x
            if hasattr(crane, '_move_start_y'):
                del crane._move_start_y
            if hasattr(crane, '_move_total_time'):
                del crane._move_total_time
            # Update visual position to match logical position
            crane.update_position()

        # Force metrics update
        self.update_metrics_display()

        # Restore pause state
        self.is_paused = was_paused

        # Redraw
        self.fig.canvas.draw_idle()

        print(f"Skipped to t={self.t_elapsed:.1f}s (Diamonds delivered: {self.diamonds_delivered})")

    def setup_axes(self):
        """Setup matplotlib axes with proper scaling"""
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
        self.ax.set_title('Diamond Sorting Simulation - Ver3\nRealistic Two-Claw System',
                          fontsize=14, fontweight='bold')

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

    def step_simulation(self, dt):
        """Execute one simulation time step"""
        dt *= config.SIM_SPEED_MULTIPLIER # speed

        # Check if simulation should start (blue crane starts picking up first diamond)
        if not self.simulation_started:
            if (self.blue_crane.state == "PICK_AT_START" and
                    self.blue_crane.pick_phase == "LOWER"):
                # Blue crane is lowering to pick up first diamond - start timer!
                self.simulation_started = True

        # Update scanners
        for scanner in self.scanner_list:
            scanner.update(dt, self.t_elapsed)
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

        # Update time - only if simulation has started
        if self.simulation_started:
            self.t_elapsed += dt

        # Update metrics display
        self.update_metrics_display()

    def reset_simulation(self):
        """Reset simulation to initial state (for skip functionality)"""
        self.t_elapsed = 0.0
        self.diamonds_delivered = 0
        self.diamonds_scanned = 0
        self.total_ready_wait_time = 0.0
        self.simulation_started = False  # Reset timer start flag

        # Reset scanners
        for scanner in self.scanner_list:
            scanner.reset()
            # Ensure scans_done counter is reset (in case scanner.reset() doesn't do this)
            if hasattr(scanner, 'scans_done'):
                scanner.scans_done = 0

        # Reset boxes
        for box in self.box_list:
            box.reset()

        # Reset cranes
        self.blue_crane.reset()
        self.red_crane.reset()

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
        plt.show()


def run_simulation():
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

    controller = SimulationController()
    controller.run()


if __name__ == "__main__":
    run_simulation()