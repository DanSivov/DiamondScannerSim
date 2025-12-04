# Ver3.5/RealisticDualClawSim/moving_plate.py
"""
Moving Plate class for Ver3.5 Dual-Claw Simulation

The moving plate holds pickup/deposit points for both scanners and moves
on the Y-axis to position them where needed:
- At pickup zone (Y=0) to load new diamonds
- At scanner level (Y=SCANNER_Y) for crane access
- At box level for depositing scanned diamonds
"""

from matplotlib.patches import Rectangle
from . import config


class MovingPlate:
    """
    Moving plate that travels on Y-axis

    The plate holds the pickup/deposit zones for both scanners and moves
    to align them with:
    1. Pickup zone (for loading new diamonds)
    2. Crane level (for crane to access)
    3. Box levels (for depositing)
    """

    def __init__(self, ax):
        """
        Initialize moving plate

        Args:
            ax: Matplotlib axes for visualization
        """
        self.ax = ax

        # Position (in mm)
        self.x = config.PLATE_X_CENTER
        self.y = config.PLATE_Y_HOME  # Start at home (pickup zone)

        # Movement parameters
        self.vmax_y = config.VMAX_PLATE_Y
        self.a_y = config.A_PLATE_Y

        # State
        self.state = "IDLE"  # IDLE, MOVING_TO_TARGET
        self.target_y = None
        self.action_timer = 0.0

        # Tracking for interpolated movement
        self._move_start_y = None
        self._move_total_time = None

        # Visual elements - semi-transparent rectangle behind boxes
        display_x = config.mm_to_display(self.x)
        display_y = config.mm_to_display(self.y)

        # Make plate wider and taller to encompass all boxes and pickup zone
        # Calculate bounds from box positions and pickup zone
        box_positions = config.get_end_box_positions()
        all_x = [config.PICKUP_X] + [x for x, y in box_positions]
        all_y = [config.PICKUP_Y] + [y for x, y in box_positions]

        min_x = min(all_x) - 30  # Add padding
        max_x = max(all_x) + 30
        min_y_offset = min(all_y) - 30  # Relative to plate Y
        max_y_offset = max(all_y) + 30

        plate_width = max_x - min_x
        plate_height = max_y_offset - min_y_offset

        self.plate_rect = Rectangle(
            (config.mm_to_display(min_x), display_y + config.mm_to_display(min_y_offset)),
            config.mm_to_display(plate_width),
            config.mm_to_display(plate_height),
            fc=config.COLOR_PLATE, ec='black', lw=2, zorder=2, alpha=0.4
        )
        ax.add_patch(self.plate_rect)

        # Store bounds for updates
        self._plate_min_x = min_x
        self._plate_min_y_offset = min_y_offset
        self._plate_width = plate_width
        self._plate_height = plate_height

        # Pickup zone ON the plate (moves with plate)
        pickup_size = config.mm_to_display(config.PICKUP_RADIUS)
        pickup_display_x = config.mm_to_display(config.PICKUP_X)

        self.pickup_rect = Rectangle(
            (pickup_display_x - pickup_size/2, display_y - pickup_size/2),
            pickup_size, pickup_size,
            facecolor=config.COLOR_PICKUP,
            edgecolor='darkgreen',
            linewidth=2,
            alpha=0.9,
            zorder=4
        )
        ax.add_patch(self.pickup_rect)

        # Crosshair on pickup zone
        cross = pickup_size * 0.3
        self.pickup_crosshair_h, = ax.plot(
            [pickup_display_x - cross/2, pickup_display_x + cross/2],
            [display_y, display_y],
            'k-', linewidth=2, zorder=5
        )
        self.pickup_crosshair_v, = ax.plot(
            [pickup_display_x, pickup_display_x],
            [display_y - cross/2, display_y + cross/2],
            'k-', linewidth=2, zorder=5
        )

        # Pickup label
        self.pickup_label = ax.text(
            pickup_display_x, display_y - pickup_size/2 - 0.5,
            'START', ha='center', va='top',
            fontsize=10, fontweight='bold', color='darkgreen',
            zorder=5
        )

        # Note: Scanners are STATIONARY at rail level, not on the moving plate
        # The plate moves under the scanners

        # End boxes ON the plate (move with plate)
        from matplotlib.patches import Circle
        self.end_box_circles = []
        self.end_box_labels = []
        box_positions = config.get_end_box_positions()
        for i, (box_x, box_y) in enumerate(box_positions):
            # Box Y is relative to plate, so we need to offset
            box_display_x = config.mm_to_display(box_x)
            box_display_y = display_y + config.mm_to_display(box_y)
            r = config.mm_to_display(config.BOX_RADIUS)

            box_circle = Circle(
                (box_display_x, box_display_y),
                r,
                facecolor=config.COLOR_END_BOX,
                edgecolor='darkorange',
                linewidth=1.5,
                alpha=0.6,
                zorder=4
            )
            ax.add_patch(box_circle)
            self.end_box_circles.append(box_circle)

            # Box label
            box_label = ax.text(
                box_display_x, box_display_y, str(i+1),
                ha='center', va='center',
                fontsize=8, fontweight='bold',
                zorder=5
            )
            self.end_box_labels.append(box_label)

    def update_position(self):
        """Update visual position of plate and all elements on it"""
        display_x = config.mm_to_display(self.x)
        display_y = config.mm_to_display(self.y)

        # Update plate rectangle
        self.plate_rect.set_xy((
            config.mm_to_display(self._plate_min_x),
            display_y + config.mm_to_display(self._plate_min_y_offset)
        ))

        # Update pickup zone position
        pickup_size = config.mm_to_display(config.PICKUP_RADIUS)
        pickup_display_x = config.mm_to_display(config.PICKUP_X)
        pickup_display_y = display_y + config.mm_to_display(config.PICKUP_Y)

        self.pickup_rect.set_xy((pickup_display_x - pickup_size/2, pickup_display_y - pickup_size/2))

        # Update crosshair
        cross = pickup_size * 0.3
        self.pickup_crosshair_h.set_data(
            [pickup_display_x - cross/2, pickup_display_x + cross/2],
            [pickup_display_y, pickup_display_y]
        )
        self.pickup_crosshair_v.set_data(
            [pickup_display_x, pickup_display_x],
            [pickup_display_y - cross/2, pickup_display_y + cross/2]
        )

        # Update pickup label position
        self.pickup_label.set_position((pickup_display_x, pickup_display_y - pickup_size/2 - 0.5))

        # Update end box positions
        box_positions = config.get_end_box_positions()
        for i, (box_x, box_y) in enumerate(box_positions):
            if i < len(self.end_box_circles):
                box_display_x = config.mm_to_display(box_x)
                box_display_y = display_y + config.mm_to_display(box_y)
                self.end_box_circles[i].center = (box_display_x, box_display_y)
                self.end_box_labels[i].set_position((box_display_x, box_display_y))

    def move_to(self, target_y):
        """
        Start moving to target Y position

        Args:
            target_y: Target Y position in mm
        """
        if abs(self.y - target_y) < 1.0:  # Already at target
            self.state = "IDLE"
            self.target_y = None
            self.action_timer = 0.0
            return

        self.state = "MOVING_TO_TARGET"
        self.target_y = target_y
        self.action_timer = config.calculate_y_travel_time(self.y, target_y)

        # Reset movement tracking
        self._move_start_y = None
        self._move_total_time = None

    def step(self, dt):
        """
        Update plate state for one time step

        Args:
            dt: Time step in seconds
        """
        if self.state == "IDLE":
            return

        if self.state == "MOVING_TO_TARGET":
            self.action_timer = max(0.0, self.action_timer - dt)

            if self.action_timer > 0:
                # Still moving
                if self._move_start_y is None:
                    # Initialize movement tracking
                    self._move_start_y = self.y
                    self._move_total_time = self.action_timer + dt

                # Calculate progress (0 to 1)
                progress = 1.0 - (self.action_timer / self._move_total_time)

                # Interpolate position
                self.y = self._move_start_y + (self.target_y - self._move_start_y) * progress
                self.update_position()
            else:
                # Arrived at target
                self.y = self.target_y
                self.update_position()

                # Clean up movement tracking
                self._move_start_y = None
                self._move_total_time = None

                # Return to idle
                self.state = "IDLE"
                self.target_y = None

    def get_position(self):
        """Get current position of plate"""
        return (self.x, self.y)

    def get_deposit_position(self, scanner_index):
        """
        Get the position where crane can access a scanner's deposit zone on the plate

        Args:
            scanner_index: 0 for left scanner, 1 for right scanner

        Returns: (x, y) tuple in mm
        """
        scanner_positions = config.get_scanner_positions()
        if 0 <= scanner_index < len(scanner_positions):
            scanner_x, _ = scanner_positions[scanner_index]
            return (scanner_x, self.y)  # Plate's current Y position
        return (self.x, self.y)

    def is_at_position(self, target_y, tolerance=5.0):
        """
        Check if plate is at target Y position

        Args:
            target_y: Target Y position in mm
            tolerance: Acceptable distance in mm (default 5mm)

        Returns: Boolean
        """
        return abs(self.y - target_y) < tolerance

    def is_idle(self):
        """Check if plate is idle (not moving)"""
        return self.state == "IDLE"

    def reset(self):
        """Reset plate to initial position"""
        self.y = config.PLATE_Y_HOME
        self.state = "IDLE"
        self.target_y = None
        self.action_timer = 0.0
        self._move_start_y = None
        self._move_total_time = None
        self.update_position()
