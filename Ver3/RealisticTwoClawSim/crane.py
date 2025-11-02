"""
Crane classes for Ver3 Realistic Two-Claw Simulation

Supports 2D movement (x, y axes can move simultaneously)
Z-axis (vertical) movement is separate and cannot occur during x/y movement
"""

import math
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, RegularPolygon

from . import config


def make_diamond(x, y, color, size=0.18, z=6):
    """Create a diamond visual element for matplotlib"""
    return RegularPolygon(
        (x, y), numVertices=4, radius=size, orientation=math.pi/4,
        facecolor=color, edgecolor='black', lw=1.0, zorder=z
    )


class Crane:
    """
    Base Crane class with 2D movement support

    Movement capabilities:
    - X and Y axes: Can move simultaneously with independent dynamics
    - Z axis: Vertical lowering/raising, must be done while X/Y are stationary

    The crane moves along a rail at fixed Y=RAIL_Y, but can position itself
    at any (x, y) coordinate within the workspace.
    """

    def __init__(self, ax, color, initial_x, initial_y, crane_width=None, crane_height=None,
                 rail_y=None, top_y=None, safe_distance=None):
        """
        Initialize crane

        Args:
            ax: Matplotlib axes
            color: Color for crane visualization
            initial_x: Starting X position in mm
            initial_y: Starting Y position in mm (typically RAIL_Y)
            crane_width: Width in mm (default from config)
            crane_height: Height in mm (default from config)
            rail_y: Y position of rail in mm (default from config)
            top_y: Y position when at scanner/box height in mm
            safe_distance: Minimum distance between cranes in mm (default from config)
        """
        self.ax = ax
        self.color = color

        # Set defaults from config if not provided
        if crane_width is None:
            crane_width = config.CRANE_WIDTH
        if crane_height is None:
            crane_height = config.CRANE_HEIGHT
        if rail_y is None:
            rail_y = config.RAIL_Y
        if safe_distance is None:
            safe_distance = config.D_CLAW_SAFE_DISTANCE
        if top_y is None:
            # Calculate top_y based on scanner/pickup positions
            top_y = rail_y - config.D_Z  # Drop zone is D_Z below rail

        # Position and dimensions (in mm)
        self.x = initial_x
        self.y = initial_y
        self.z = rail_y  # Z starts at rail height
        self.initial_x = initial_x
        self.initial_y = initial_y
        self.crane_width = crane_width
        self.crane_height = crane_height
        self.rail_y = rail_y
        self.top_y = top_y  # Height when picking/dropping
        self.safe_distance = safe_distance

        # Movement parameters from config
        self.vmax_x = config.VMAX_CLAW_X
        self.a_x = config.A_CLAW_X
        self.vmax_y = config.VMAX_CLAW_Y
        self.a_y = config.A_CLAW_Y
        self.vmax_z = config.VMAX_CLAW_Z
        self.a_z = config.A_CLAW_Z
        self.lower_time = config.T_Z  # Time to lower/raise
        self.raise_time = config.T_Z

        # State variables
        self.state = "WAIT"
        self.action_timer = 0.0
        self.has_diamond = False
        self.target_i = None
        self.departure_time = float('inf')
        self.time_under_scanner = 0.0
        self.t_elapsed = 0.0  # Current simulation time

        # Phase tracking for animations
        self.pick_phase = None  # "LOWER" or "RAISE"
        self.drop_phase = None  # "LOWER" or "RAISE"

        # Visual elements (convert mm to display units)
        display_x = config.mm_to_display(self.x)
        display_y = config.mm_to_display(self.y)
        display_width = config.mm_to_display(crane_width)
        display_height = config.mm_to_display(crane_height)

        self.crane_rect = Rectangle(
            (display_x - display_width/2, display_y - display_height/2),
            display_width, display_height,
            fc=color, ec='black', lw=1.5, zorder=5
        )
        ax.add_patch(self.crane_rect)

        self.hoist, = ax.plot([], [], color=color, lw=2, zorder=4)
        self.hoist.set_visible(False)

        # Diamond carried by this crane
        display_carry_y = config.mm_to_display(self.top_y)
        self.diamond = make_diamond(display_x, display_carry_y, self.get_diamond_color())
        self.diamond.set_visible(False)
        ax.add_patch(self.diamond)

    def get_diamond_color(self):
        """Override in subclasses for different diamond colors"""
        return '#66bb6a'

    def update_position(self):
        """Update visual position of crane"""
        display_x = config.mm_to_display(self.x)
        display_y = config.mm_to_display(self.y)
        display_width = config.mm_to_display(self.crane_width)
        display_height = config.mm_to_display(self.crane_height)

        self.crane_rect.set_xy((display_x - display_width/2, display_y - display_height/2))

    def set_hoist(self, x, y, z_top, show):
        """
        Control hoist visibility and position

        Args:
            x: X position in mm
            y: Y position in mm
            z_top: Z position of crane hand in mm
            show: Boolean to show/hide hoist
        """
        if show:
            display_x = config.mm_to_display(x)
            display_rail_y = config.mm_to_display(self.rail_y)
            display_z_top = config.mm_to_display(z_top)
            self.hoist.set_data([display_x, display_x], [display_rail_y, display_z_top])
            self.hoist.set_visible(True)
        else:
            self.hoist.set_visible(False)

    def travel_time_2d(self, x0, y0, x1, y1):
        """
        Calculate time to travel from (x0, y0) to (x1, y1)
        Both axes can move simultaneously

        Returns: time in seconds
        """
        return config.calculate_2d_travel_time(x0, y0, x1, y1)

    def would_collide_with(self, other_crane, safe_distance=None):
        """
        Check if this crane would collide with another crane
        Uses X-axis distance only since both cranes are on the same rail

        Args:
            other_crane: Another Crane object
            safe_distance: Minimum safe distance in mm (default: self.safe_distance)

        Returns: Boolean
        """
        if safe_distance is None:
            safe_distance = self.safe_distance

        # Only check X-axis distance since they're both on the same rail
        distance_x = abs(self.x - other_crane.x)

        return distance_x < safe_distance

    def is_left_of(self, other_crane):
        """Check if this crane is to the left of another crane"""
        return self.x < other_crane.x

    def can_move_to_x(self, target_x, other_crane, safe_distance=None):
        """
        Check if crane can move to target_x without colliding with other crane

        Args:
            target_x: Target X position in mm
            other_crane: Another Crane object
            safe_distance: Minimum safe distance in mm

        Returns: Boolean
        """
        if safe_distance is None:
            safe_distance = self.safe_distance

        # Check if moving to target_x would cause collision
        distance_to_other = abs(target_x - other_crane.x)
        return distance_to_other >= safe_distance

    def distance_to(self, x, y):
        """
        Calculate 2D distance from current position to (x, y)

        Returns: distance in mm
        """
        dx = self.x - x
        dy = self.y - y
        return math.sqrt(dx**2 + dy**2)

    def reset(self):
        """Reset crane to initial state"""
        self.x = self.initial_x
        self.y = self.initial_y
        self.z = self.rail_y
        self.state = "WAIT"
        self.action_timer = 0.0
        self.has_diamond = False
        self.target_i = None
        self.departure_time = float('inf')
        self.time_under_scanner = 0.0
        self.pick_phase = None
        self.drop_phase = None
        self.t_elapsed = 0.0

        # CRITICAL: Clear all movement tracking variables
        if hasattr(self, '_move_start_x'):
            del self._move_start_x
        if hasattr(self, '_move_start_y'):
            del self._move_start_y
        if hasattr(self, '_move_total_time'):
            del self._move_total_time

        self.update_position()
        self.set_hoist(self.x, self.y, self.top_y, False)
        self.diamond.set_visible(False)


class BlueCrane(Crane):
    """
    Blue Crane: Handles pickup from START and delivery to scanners

    Workflow:
    1. Pick diamond from pickup zone (0, 0)
    2. Travel to target scanner position
    3. Drop diamond at scanner
    4. Return to pickup zone
    """

    def __init__(self, ax, scanner_list, **kwargs):
        """
        Initialize Blue Crane

        Args:
            ax: Matplotlib axes
            scanner_list: List of DScanner objects
            **kwargs: Additional parameters passed to Crane.__init__
        """
        # Use config defaults if not provided
        if 'initial_x' not in kwargs:
            kwargs['initial_x'] = config.BLUE_CRANE_HOME_X
        if 'initial_y' not in kwargs:
            kwargs['initial_y'] = config.BLUE_CRANE_HOME_Y

        super().__init__(ax, '#1f77b4', **kwargs)

        self.scanner_list = scanner_list

        # Track which scanners have been loaded
        self.scanners_loaded = set()  # Track by index
        self.waiting_at_home = False
        self.waiting_for_red_to_clear = False  # New flag for coordination

        # Blue crane starts at HOME without a diamond - must go to START first
        self.state = "MOVE_TO_START"
        pickup_x, pickup_y = config.get_pickup_position()
        self.action_timer = self.travel_time_2d(self.x, self.y, pickup_x, pickup_y)

        # Diamond at start position (always visible - infinite supply)
        pickup_x, pickup_y = config.get_pickup_position()
        display_x = config.mm_to_display(pickup_x)
        display_y = config.mm_to_display(pickup_y)
        self.start_diamond = make_diamond(display_x, display_y, '#33a3ff', size=0.18)
        ax.add_patch(self.start_diamond)
        self.start_diamond.set_visible(True)  # Always visible - represents infinite supply

    def get_diamond_color(self):
        """Blue diamonds for blue crane"""
        return '#33a3ff'

    def reset(self):
        """Reset blue crane to initial state"""
        super().reset()
        # Blue crane starts by going to START to pick up first diamond
        self.state = "MOVE_TO_START"
        pickup_x, pickup_y = config.get_pickup_position()
        self.action_timer = self.travel_time_2d(self.x, self.y, pickup_x, pickup_y)
        # Start diamond is always visible
        self.start_diamond.set_visible(True)
        # Clear tracking
        self.scanners_loaded = set()
        self.waiting_at_home = False
        self.waiting_for_red_to_clear = False
        # Clear any movement tracking from parent reset
        if hasattr(self, '_move_start_x'):
            del self._move_start_x
        if hasattr(self, '_move_start_y'):
            del self._move_start_y
        if hasattr(self, '_move_total_time'):
            del self._move_total_time

    def nearest_empty_scanner(self):
        """Find nearest empty scanner to HOME position (for optimal loading)"""
        empties = [i for i, scanner in enumerate(self.scanner_list) if scanner.state == "empty"]
        if not empties:
            return None

        # Find closest to HOME position (not current position)
        # This ensures we load the scanner closest to where blue crane starts
        return min(empties, key=lambda i: self.distance_to_position(
            *self.scanner_list[i].get_position(),
            from_x=self.initial_x,
            from_y=self.initial_y
        ))

    def distance_to_position(self, x, y, from_x=None, from_y=None):
        """
        Calculate 2D distance from a position to (x, y)
        If from_x/from_y not specified, uses current position

        Returns: distance in mm
        """
        if from_x is None:
            from_x = self.x
        if from_y is None:
            from_y = self.y

        dx = from_x - x
        dy = from_y - y
        return math.sqrt(dx**2 + dy**2)

    def step(self, dt, blue_crane, red_crane):
        """
        Update blue crane state for one time step

        Args:
            dt: Time step in seconds
            blue_crane: Reference to self (for compatibility)
            red_crane: Reference to red crane for collision avoidance
        """
        self.action_timer = max(0.0, self.action_timer - dt)

        if self.state == "WAIT":
            # Check if red crane is waiting for us to load the right scanner
            if (red_crane.state == "MOVE_OUT_OF_WAY_AFTER_RIGHT_PICKUP" or
                    red_crane.state == "WAIT_FOR_BLUE_TO_LOAD_RIGHT"):
                # Red crane picked from right scanner and is out of the way
                # Check if right scanner (scanner 1) is empty
                if len(self.scanner_list) > 1 and self.scanner_list[1].state == "empty":
                    # We need to load the right scanner
                    # First check if we have a diamond
                    if self.has_diamond:
                        # Go directly to right scanner
                        self.target_i = 1
                        target_x, target_y = self.scanner_list[1].get_drop_zone_position()
                        self.state = "MOVE_TO_SCANNER"
                        self.action_timer = self.travel_time_2d(self.x, self.y, target_x, target_y)
                        return
                    else:
                        # Go get a diamond first
                        pickup_x, pickup_y = config.get_pickup_position()
                        self.state = "MOVE_TO_START"
                        self.action_timer = self.travel_time_2d(self.x, self.y, pickup_x, pickup_y)
                        # Remember we need to go to right scanner after picking up
                        self.target_i = 1
                        return

            # Normal wait logic
            target_i = self.nearest_empty_scanner()
            if target_i is not None:
                self.target_i = target_i
                # Go to START to pick up diamond
                pickup_x, pickup_y = config.get_pickup_position()
                self.state = "MOVE_TO_START"
                self.action_timer = self.travel_time_2d(self.x, self.y, pickup_x, pickup_y)
            else:
                # No empty scanner - go to home position if not already there
                if abs(self.x - self.initial_x) > 1.0 or abs(self.y - self.initial_y) > 1.0:
                    self.state = "MOVE_TO_HOME_EMPTY"
                    self.action_timer = self.travel_time_2d(self.x, self.y, self.initial_x, self.initial_y)

        elif self.state == "MOVE_TO_START":
            # Move crane to START position to pick up diamond
            # Check for collision with red crane
            if self.would_collide_with(red_crane):
                # Too close to red crane - stop and wait
                return

            if self.action_timer > 0:
                pickup_x, pickup_y = config.get_pickup_position()

                # Store initial position at start of movement
                if not hasattr(self, '_move_start_x'):
                    self._move_start_x = self.x
                    self._move_start_y = self.y
                    self._move_total_time = self.action_timer + dt

                # Calculate progress (0 to 1)
                progress = 1.0 - (self.action_timer / self._move_total_time)

                # Interpolate position
                self.x = self._move_start_x + (pickup_x - self._move_start_x) * progress
                self.y = self._move_start_y + (pickup_y - self._move_start_y) * progress
                self.update_position()
            else:
                # Arrived at START
                pickup_x, pickup_y = config.get_pickup_position()
                self.x, self.y = pickup_x, pickup_y
                self.update_position()

                # Clean up movement tracking
                if hasattr(self, '_move_start_x'):
                    del self._move_start_x
                    del self._move_start_y
                    del self._move_total_time

                # Now pick up diamond
                self.state = "PICK_AT_START"
                self.action_timer = self.lower_time
                self.pick_phase = "LOWER"

        elif self.state == "PICK_AT_START":
            # Two-phase pick: LOWER then RAISE
            if self.pick_phase == "LOWER":
                # Animate lowering
                prog = 1.0 - (self.action_timer / self.lower_time)
                z = self.rail_y - (self.rail_y - self.top_y) * prog
                self.set_hoist(self.x, self.y, z, True)

                if self.action_timer <= 0:
                    # Finished lowering, now raise with diamond
                    self.pick_phase = "RAISE"
                    self.action_timer = self.raise_time
                    self.has_diamond = True
                    # Start diamond stays visible - infinite supply
                    self.diamond.set_visible(True)

            elif self.pick_phase == "RAISE":
                # Animate raising
                prog = self.action_timer / self.raise_time
                z = self.rail_y - (self.rail_y - self.top_y) * prog
                self.set_hoist(self.x, self.y, z, True)

                if self.action_timer <= 0:
                    # Finished raising, now check what to do next
                    self.pick_phase = None
                    self.set_hoist(self.x, self.y, self.top_y, False)

                    # Check if we need to move out of way after loading right scanner
                    if self.waiting_for_red_to_clear and self.has_diamond:
                        self.waiting_for_red_to_clear = False
                        self.state = "MOVE_OUT_OF_WAY_AFTER_RIGHT_LOAD"
                        # Move far to the left (home position)
                        self.action_timer = self.travel_time_2d(self.x, self.y, self.initial_x, self.initial_y)
                        return

                    # PRIORITY: If red crane is waiting for us to load right scanner, do that first
                    if (red_crane.state == "MOVE_OUT_OF_WAY_AFTER_RIGHT_PICKUP" or
                            red_crane.state == "WAIT_FOR_BLUE_TO_LOAD_RIGHT"):
                        # Check if right scanner (scanner 1) is empty
                        if len(self.scanner_list) > 1 and self.scanner_list[1].state == "empty":
                            # Go directly to right scanner
                            self.target_i = 1
                            target_x, target_y = self.scanner_list[1].get_drop_zone_position()
                            if self.can_move_to_x(target_x, red_crane):
                                self.state = "MOVE_TO_SCANNER"
                                self.action_timer = self.travel_time_2d(self.x, self.y, target_x, target_y)
                                return

                    # Otherwise find next empty scanner
                    self.target_i = self.nearest_empty_scanner()

                    if self.target_i is not None:
                        target_x, target_y = self.scanner_list[self.target_i].get_drop_zone_position()

                        # Check if we can reach this scanner without collision
                        if self.can_move_to_x(target_x, red_crane):
                            self.state = "MOVE_TO_SCANNER"
                            self.action_timer = self.travel_time_2d(self.x, self.y, target_x, target_y)
                        else:
                            # Can't reach scanner due to red crane blocking
                            self.state = "WAIT"
                    else:
                        # No empty scanner - go to home with diamond
                        self.state = "RETURN_TO_HOME_WITH_DIAMOND"
                        self.action_timer = self.travel_time_2d(self.x, self.y, self.initial_x, self.initial_y)

        elif self.state == "MOVE_TO_SCANNER":
            # Move crane in 2D from current position to target scanner
            # Safety check: ensure target_i is valid
            if self.target_i is None or self.target_i >= len(self.scanner_list):
                # Lost target, return to start
                self.state = "RETURN_TO_START"
                pickup_x, pickup_y = config.get_pickup_position()
                self.action_timer = self.travel_time_2d(self.x, self.y, pickup_x, pickup_y)
                return

            # Check for collision with red crane during movement
            if self.would_collide_with(red_crane):
                # Too close to red crane - stop and wait
                # Don't move this frame
                return

            if self.action_timer > 0:
                target_x, target_y = self.scanner_list[self.target_i].get_drop_zone_position()

                # Store initial position at start of movement
                if not hasattr(self, '_move_start_x'):
                    self._move_start_x = self.x
                    self._move_start_y = self.y
                    self._move_total_time = self.action_timer + dt

                # Calculate progress (0 to 1)
                progress = 1.0 - (self.action_timer / self._move_total_time)

                # Interpolate position
                self.x = self._move_start_x + (target_x - self._move_start_x) * progress
                self.y = self._move_start_y + (target_y - self._move_start_y) * progress
                self.update_position()
            else:
                # Arrived at scanner
                target_x, target_y = self.scanner_list[self.target_i].get_drop_zone_position()
                self.x, self.y = target_x, target_y
                self.update_position()

                # Clean up movement tracking
                if hasattr(self, '_move_start_x'):
                    del self._move_start_x
                    del self._move_start_y
                    del self._move_total_time

                self.state = "DROP_AT_SCANNER"
                self.action_timer = self.lower_time
                self.drop_phase = "LOWER"

        elif self.state == "DROP_AT_SCANNER":
            # Safety check: ensure target_i is valid
            if self.target_i is None or self.target_i >= len(self.scanner_list):
                # Lost target, return to start with diamond
                self.state = "RETURN_TO_START"
                pickup_x, pickup_y = config.get_pickup_position()
                self.action_timer = self.travel_time_2d(self.x, self.y, pickup_x, pickup_y)
                return

            # Two-phase drop: LOWER then RAISE
            if self.drop_phase == "LOWER":
                # Animate lowering
                prog = 1.0 - (self.action_timer / self.lower_time)
                z = self.rail_y - (self.rail_y - self.top_y) * prog
                self.set_hoist(self.x, self.y, z, True)

                if self.action_timer <= 0:
                    # Finished lowering, drop diamond
                    self.drop_phase = "RAISE"
                    self.action_timer = self.raise_time
                    self.has_diamond = False
                    self.diamond.set_visible(False)

                    # Trigger scanner to start scanning
                    self.scanner_list[self.target_i].scan()

            elif self.drop_phase == "RAISE":
                # Animate raising
                prog = self.action_timer / self.raise_time
                z = self.rail_y - (self.rail_y - self.top_y) * prog
                self.set_hoist(self.x, self.y, z, True)

                if self.action_timer <= 0:
                    # Finished raising
                    self.drop_phase = None
                    self.set_hoist(self.x, self.y, self.top_y, False)

                    # Mark this scanner as loaded
                    if self.target_i is not None:
                        self.scanners_loaded.add(self.target_i)

                    # Check if we just loaded the right scanner while red crane is waiting
                    if (self.target_i == 1 and
                            red_crane.state == "WAIT_FOR_BLUE_TO_LOAD_RIGHT"):
                        # We loaded right scanner, now go pick up another diamond and move out of way
                        self.state = "RETURN_TO_START"
                        pickup_x, pickup_y = config.get_pickup_position()
                        self.action_timer = self.travel_time_2d(self.x, self.y, pickup_x, pickup_y)
                        # Set flag so we know to move out of way after picking up diamond
                        self.waiting_for_red_to_clear = True
                        return

                    # Always return to start for next diamond
                    self.state = "RETURN_TO_START"
                    pickup_x, pickup_y = config.get_pickup_position()
                    self.action_timer = self.travel_time_2d(self.x, self.y, pickup_x, pickup_y)

        elif self.state == "RETURN_TO_START":
            # Move crane back to pickup zone
            # Check for collision with red crane
            if self.would_collide_with(red_crane):
                # Too close to red crane - stop and wait
                return

            if self.action_timer > 0:
                pickup_x, pickup_y = config.get_pickup_position()

                # Store initial position at start of movement
                if not hasattr(self, '_move_start_x'):
                    self._move_start_x = self.x
                    self._move_start_y = self.y
                    self._move_total_time = self.action_timer + dt

                # Calculate progress (0 to 1)
                progress = 1.0 - (self.action_timer / self._move_total_time)

                # Interpolate position
                self.x = self._move_start_x + (pickup_x - self._move_start_x) * progress
                self.y = self._move_start_y + (pickup_y - self._move_start_y) * progress
                self.update_position()
            else:
                # Arrived at start
                pickup_x, pickup_y = config.get_pickup_position()
                self.x, self.y = pickup_x, pickup_y
                self.update_position()

                # Clean up movement tracking
                if hasattr(self, '_move_start_x'):
                    del self._move_start_x
                    del self._move_start_y
                    del self._move_total_time

                # Always pick up the next diamond
                self.state = "PICK_AT_START"
                self.action_timer = self.lower_time
                self.pick_phase = "LOWER"

        elif self.state == "MOVE_OUT_OF_WAY_AFTER_RIGHT_LOAD":
            # Blue crane moves to home after picking up diamond and loading right scanner
            # This clears the way for red crane to drop its diamond at the end box
            if self.action_timer > 0:
                # Store initial position at start of movement
                if not hasattr(self, '_move_start_x'):
                    self._move_start_x = self.x
                    self._move_start_y = self.y
                    self._move_total_time = self.action_timer + dt

                # Calculate progress (0 to 1)
                progress = 1.0 - (self.action_timer / self._move_total_time)

                # Interpolate position
                self.x = self._move_start_x + (self.initial_x - self._move_start_x) * progress
                self.y = self._move_start_y + (self.initial_y - self._move_start_y) * progress
                self.update_position()
            else:
                # Arrived home
                self.x, self.y = self.initial_x, self.initial_y
                self.update_position()

                # Clean up movement tracking
                if hasattr(self, '_move_start_x'):
                    del self._move_start_x
                    del self._move_start_y
                    del self._move_total_time

                # Now wait at home
                self.state = "WAIT_AT_HOME"
                self.waiting_at_home = True

        elif self.state == "RETURN_TO_HOME_WITH_DIAMOND":
            # Move crane back to home position (left side) while carrying diamond
            # Check for collision with red crane during movement
            if self.would_collide_with(red_crane):
                # Too close to red crane - stop and wait
                return

            if self.action_timer > 0:
                # Store initial position at start of movement
                if not hasattr(self, '_move_start_x'):
                    self._move_start_x = self.x
                    self._move_start_y = self.y
                    self._move_total_time = self.action_timer + dt

                # Calculate progress (0 to 1)
                progress = 1.0 - (self.action_timer / self._move_total_time)

                # Interpolate position
                self.x = self._move_start_x + (self.initial_x - self._move_start_x) * progress
                self.y = self._move_start_y + (self.initial_y - self._move_start_y) * progress
                self.update_position()
            else:
                # Arrived home
                self.x, self.y = self.initial_x, self.initial_y
                self.update_position()

                # Clean up movement tracking
                if hasattr(self, '_move_start_x'):
                    del self._move_start_x
                    del self._move_start_y
                    del self._move_total_time

                # Wait at home with diamond
                self.state = "WAIT_AT_HOME"
                self.waiting_at_home = True

        elif self.state == "WAIT_AT_HOME":
            # Waiting at home position (left side) with a diamond
            # Check if any scanner became empty
            empty_scanners = [i for i, scanner in enumerate(self.scanner_list) if scanner.state == "empty"]

            if empty_scanners:
                # A scanner became empty, remove it from loaded set and deliver diamond
                for i in empty_scanners:
                    if i in self.scanners_loaded:
                        self.scanners_loaded.remove(i)

                # Go directly to the empty scanner with our diamond
                self.target_i = self.nearest_empty_scanner()
                if self.target_i is not None:
                    target_x, target_y = self.scanner_list[self.target_i].get_drop_zone_position()

                    # Check if we can reach this scanner without collision
                    if self.can_move_to_x(target_x, red_crane):
                        self.state = "MOVE_TO_SCANNER"
                        self.action_timer = self.travel_time_2d(self.x, self.y, target_x, target_y)
                        self.waiting_at_home = False
                    # else: stay waiting at home until path is clear

        elif self.state == "MOVE_TO_HOME_EMPTY":
            # Move to home position without diamond (when no scanners need loading)
            if self.action_timer > 0:
                # Store initial position at start of movement
                if not hasattr(self, '_move_start_x'):
                    self._move_start_x = self.x
                    self._move_start_y = self.y
                    self._move_total_time = self.action_timer + dt

                # Calculate progress (0 to 1)
                progress = 1.0 - (self.action_timer / self._move_total_time)

                # Interpolate position
                self.x = self._move_start_x + (self.initial_x - self._move_start_x) * progress
                self.y = self._move_start_y + (self.initial_y - self._move_start_y) * progress
                self.update_position()
            else:
                # Arrived home
                self.x, self.y = self.initial_x, self.initial_y
                self.update_position()

                # Clean up movement tracking
                if hasattr(self, '_move_start_x'):
                    del self._move_start_x
                    del self._move_start_y
                    del self._move_total_time

                # Wait at home for scanners to become available
                self.state = "WAIT"

        # Update diamond position if carrying
        if self.has_diamond:
            display_x = config.mm_to_display(self.x)
            display_y = config.mm_to_display(self.top_y)
            self.diamond.xy = (display_x, display_y)


class RedCrane(Crane):
    """
    Red Crane: Handles pickup from scanners and delivery to end boxes

    Workflow:
    1. Wait for scanner to have ready diamond
    2. Travel to scanner position
    3. Pick diamond from scanner
    4. Travel to target end box position
    5. Drop diamond at box
    6. Return to home position
    """

    def __init__(self, ax, scanner_list, box_list, **kwargs):
        """
        Initialize Red Crane

        Args:
            ax: Matplotlib axes
            scanner_list: List of DScanner objects
            box_list: List of Box objects
            **kwargs: Additional parameters passed to Crane.__init__
        """
        # Use config defaults if not provided
        if 'initial_x' not in kwargs:
            kwargs['initial_x'] = config.RED_CRANE_HOME_X
        if 'initial_y' not in kwargs:
            kwargs['initial_y'] = config.RED_CRANE_HOME_Y

        super().__init__(ax, '#d62728', **kwargs)

        self.scanner_list = scanner_list
        self.box_list = box_list
        self.target_box = None
        self.state = "WAIT"
        self.from_rightmost = False

        # Predictive scheduling - track when to depart for each scanner
        self.departure_times = {}  # {scanner_index: departure_time}

    def get_diamond_color(self):
        """Red diamonds for red crane"""
        return '#ff6b6b'

    def reset(self):
        """Reset red crane to initial state"""
        super().reset()
        self.target_box = None
        self.departure_times = {}
        self.from_rightmost = False
        # Clear any movement tracking
        if hasattr(self, '_move_start_x'):
            del self._move_start_x
        if hasattr(self, '_move_start_y'):
            del self._move_start_y
        if hasattr(self, '_move_total_time'):
            del self._move_total_time

    def nearest_ready_scanner(self):
        """Find nearest ready scanner using 2D distance"""
        ready = [i for i, scanner in enumerate(self.scanner_list) if scanner.state == "ready"]
        if not ready:
            return None

        # Find closest using 2D distance
        return min(ready, key=lambda i: self.distance_to(*self.scanner_list[i].get_drop_zone_position()))

    def step(self, dt, blue_crane, red_crane):
        """
        Update red crane state for one time step

        Args:
            dt: Time step in seconds
            blue_crane: Reference to blue crane for collision avoidance
            red_crane: Reference to self (for compatibility)
        """
        # advance timers
        self.action_timer = max(0.0, self.action_timer - dt)
        self.t_elapsed = getattr(self, 't_elapsed', 0.0) + dt
        current_time = self.t_elapsed

        if self.state == "WAIT":
            # Predictive scheduling: compute/update departure times
            earliest_to_depart = None
            earliest_time = float('inf')
            for i, scanner in enumerate(self.scanner_list):
                if scanner.state == "scanning":
                    time_until_ready = scanner.timer
                    scanner_x, scanner_y = scanner.get_drop_zone_position()
                    travel_time = self.travel_time_2d(self.x, self.y, scanner_x, scanner_y)

                    departure_time = current_time + time_until_ready - travel_time - self.lower_time

                    prev = self.departure_times.get(i)
                    if prev is None or departure_time < prev:
                        self.departure_times[i] = departure_time

                    # If it's time to depart for this scanner
                    if current_time >= self.departure_times[i]:
                        # Check path/collision using the exact drop-zone x that we'll approach
                        if self.can_move_to_x(scanner_x, blue_crane):
                            # Commit the run
                            self.target_i = i
                            self.target_box = scanner.get_target_box()
                            self.state = "MOVE_TO_SCANNER"
                            self.action_timer = travel_time
                            # Clear stored prediction
                            self.departure_times.pop(i, None)
                            # Track if this is the right scanner
                            self.from_rightmost = (i == 1)
                            break
                        # else: leave departure_times[i] and wait for path to clear

            # Fallback: if no scheduled run and a scanner is already ready
            if self.target_i is None:
                ready_scanners = [i for i, s in enumerate(self.scanner_list) if s.state == "ready"]
                if ready_scanners:
                    target_i = self.nearest_ready_scanner()
                    if target_i is not None:
                        target_x, target_y = self.scanner_list[target_i].get_drop_zone_position()
                        if self.can_move_to_x(target_x, blue_crane):
                            self.target_i = target_i
                            self.target_box = self.scanner_list[target_i].get_target_box()
                            self.state = "MOVE_TO_SCANNER"
                            self.action_timer = self.travel_time_2d(self.x, self.y, target_x, target_y)
                            # Track if this is the right scanner
                            self.from_rightmost = (target_i == 1)

        elif self.state == "MOVE_TO_SCANNER":
            # Safety check: ensure target_i is valid
            if self.target_i is None or self.target_i >= len(self.scanner_list):
                self.state = "RETURN_HOME"
                self.action_timer = self.travel_time_2d(self.x, self.y, self.initial_x, self.initial_y)
                return

            # Collision with blue crane blocks movement this frame
            if self.would_collide_with(blue_crane):
                return

            if self.action_timer > 0:
                target_x, target_y = self.scanner_list[self.target_i].get_drop_zone_position()

                # Store interpolation start
                if not hasattr(self, '_move_start_x'):
                    self._move_start_x = self.x
                    self._move_start_y = self.y
                    self._move_total_time = self.action_timer + dt

                progress = 1.0 - (self.action_timer / self._move_total_time)

                self.x = self._move_start_x + (target_x - self._move_start_x) * progress
                self.y = self._move_start_y + (target_y - self._move_start_y) * progress
                self.update_position()
            else:
                # Arrived at scanner
                target_x, target_y = self.scanner_list[self.target_i].get_drop_zone_position()
                self.x, self.y = target_x, target_y
                self.update_position()

                if hasattr(self, '_move_start_x'):
                    del self._move_start_x
                    del self._move_start_y
                    del self._move_total_time

                # Decide next state based on scanner status
                s_state = self.scanner_list[self.target_i].state
                if s_state == "scanning":
                    self.state = "LOWER_FOR_PICKUP"
                    self.action_timer = self.lower_time
                    self.pick_phase = "LOWER"
                elif s_state in ("ready", "occupied"):
                    self.state = "PICK_AT_SCANNER"
                    self.action_timer = self.lower_time
                    self.pick_phase = "LOWER"
                else:
                    # Scanner empty or unexpected — return home
                    self.state = "RETURN_HOME"
                    self.action_timer = self.travel_time_2d(self.x, self.y, self.initial_x, self.initial_y)

        elif self.state == "LOWER_FOR_PICKUP":
            if self.target_i is None or self.target_i >= len(self.scanner_list):
                self.state = "RETURN_HOME"
                self.action_timer = self.travel_time_2d(self.x, self.y, self.initial_x, self.initial_y)
                return

            # If scanner became ready while lowering
            if self.scanner_list[self.target_i].state == "ready" and self.action_timer <= 0:
                self.pick_phase = "RAISE"
                self.action_timer = self.raise_time
                self.has_diamond = True

                box_id = self.scanner_list[self.target_i].pickup()
                if box_id is not None:
                    self.target_box = box_id
                else:
                    # defensive fallback
                    self.target_box = self.scanner_list[self.target_i].get_target_box()
                self.diamond.set_visible(True)

                self.state = "PICK_AT_SCANNER"
                return

            # Animate lowering
            prog = 1.0 - (self.action_timer / self.lower_time)
            z = self.rail_y - (self.rail_y - self.top_y) * prog
            self.set_hoist(self.x, self.y, z, True)

            if self.action_timer <= 0:
                # At bottom, wait until scanner ready
                self.set_hoist(self.x, self.y, self.top_y, True)
                if self.scanner_list[self.target_i].state == "ready":
                    self.pick_phase = "RAISE"
                    self.action_timer = self.raise_time
                    self.has_diamond = True

                    box_id = self.scanner_list[self.target_i].pickup()
                    if box_id is not None:
                        self.target_box = box_id
                    else:
                        # defensive fallback
                        self.target_box = self.scanner_list[self.target_i].get_target_box()
                    self.diamond.set_visible(True)

                    self.state = "PICK_AT_SCANNER"

        elif self.state == "PICK_AT_SCANNER":
            if self.target_i is None or self.target_i >= len(self.scanner_list):
                self.state = "RETURN_HOME"
                self.action_timer = self.travel_time_2d(self.x, self.y, self.initial_x, self.initial_y)
                return

            if self.pick_phase == "LOWER":
                prog = 1.0 - (self.action_timer / self.lower_time)
                z = self.rail_y - (self.rail_y - self.top_y) * prog
                self.set_hoist(self.x, self.y, z, True)

                if self.action_timer <= 0:
                    self.pick_phase = "RAISE"
                    self.action_timer = self.raise_time
                    self.has_diamond = True

                    box_id = self.scanner_list[self.target_i].pickup()
                    if box_id is not None:
                        self.target_box = box_id
                    else:
                        # defensive fallback
                        self.target_box = self.scanner_list[self.target_i].get_target_box()
                    self.diamond.set_visible(True)

            elif self.pick_phase == "RAISE":
                prog = self.action_timer / self.raise_time
                z = self.rail_y - (self.rail_y - self.top_y) * prog
                self.set_hoist(self.x, self.y, z, True)

                if self.action_timer <= 0:
                    self.pick_phase = None
                    self.set_hoist(self.x, self.y, self.top_y, False)

                    if self.target_box is None:
                        # fallback: pick box 0 if none set
                        self.target_box = 0

                    # NEW COORDINATION LOGIC: If we just picked from right scanner
                    if self.from_rightmost:
                        # Remove right scanner from blue crane's loaded set so it knows to reload it
                        if hasattr(blue_crane, 'scanners_loaded') and 1 in blue_crane.scanners_loaded:
                            blue_crane.scanners_loaded.remove(1)

                        # Move out of the way to a FIXED X position
                        # This ensures consistent behavior and no blocking issues
                        self.state = "MOVE_OUT_OF_WAY_AFTER_RIGHT_PICKUP"

                        # HARD-CODED X POSITION: Calculate once based on scanner position
                        rightmost_scanner_x, _ = self.scanner_list[1].get_drop_zone_position()
                        # Fixed waiting X: 250mm to the right of the right scanner
                        fixed_waiting_x = rightmost_scanner_x + 250

                        if self.target_box is not None and self.target_box < len(self.box_list):
                            # Y position adapts to target box row
                            _, target_box_y = self.box_list[self.target_box].get_position()
                            self.action_timer = self.travel_time_2d(self.x, self.y, fixed_waiting_x, target_box_y)
                        else:
                            # Fallback: stay at scanner Y level
                            _, rightmost_scanner_y = self.scanner_list[1].get_drop_zone_position()
                            self.action_timer = self.travel_time_2d(self.x, self.y, fixed_waiting_x, rightmost_scanner_y)
                    else:
                        # From left scanner - go directly to right scanner (not home)
                        # Check if right scanner has a diamond ready
                        if len(self.scanner_list) > 1:
                            right_scanner = self.scanner_list[1]
                            if right_scanner.state in ("ready", "scanning"):
                                # Go to right scanner next
                                target_x, target_y = right_scanner.get_drop_zone_position()
                                self.target_i = 1
                                self.target_box = right_scanner.get_target_box()
                                self.state = "MOVE_TO_BOX_THEN_RIGHT_SCANNER"
                                # First go to box to drop current diamond
                                box_x, box_y = self.box_list[self.target_box].get_position()
                                self.action_timer = self.travel_time_2d(self.x, self.y, box_x, box_y)
                                return

                        # Default behavior: go to box
                        target_x, target_y = self.box_list[self.target_box].get_position()
                        self.state = "MOVE_TO_BOX"
                        self.action_timer = self.travel_time_2d(self.x, self.y, target_x, target_y)

        elif self.state == "MOVE_OUT_OF_WAY_AFTER_RIGHT_PICKUP":
            # Red crane moves to FIXED waiting position - X is hard-coded, Y adapts to target box
            if self.action_timer > 0:
                # HARD-CODED X POSITION
                rightmost_scanner_x, _ = self.scanner_list[1].get_drop_zone_position()
                fixed_waiting_x = rightmost_scanner_x + 250  # Fixed: 250mm right of scanner

                # Y position adapts to target box
                if self.target_box is not None and self.target_box < len(self.box_list):
                    _, target_box_y = self.box_list[self.target_box].get_position()
                    waiting_y = target_box_y
                else:
                    # Fallback
                    _, rightmost_scanner_y = self.scanner_list[1].get_drop_zone_position()
                    waiting_y = rightmost_scanner_y

                if not hasattr(self, '_move_start_x'):
                    self._move_start_x = self.x
                    self._move_start_y = self.y
                    self._move_total_time = self.action_timer + dt

                progress = 1.0 - (self.action_timer / self._move_total_time)
                self.x = self._move_start_x + (fixed_waiting_x - self._move_start_x) * progress
                self.y = self._move_start_y + (waiting_y - self._move_start_y) * progress
                self.update_position()
            else:
                # Arrived at waiting position
                rightmost_scanner_x, _ = self.scanner_list[1].get_drop_zone_position()
                fixed_waiting_x = rightmost_scanner_x + 250

                if self.target_box is not None and self.target_box < len(self.box_list):
                    _, target_box_y = self.box_list[self.target_box].get_position()
                    waiting_y = target_box_y
                else:
                    _, rightmost_scanner_y = self.scanner_list[1].get_drop_zone_position()
                    waiting_y = rightmost_scanner_y

                self.x, self.y = fixed_waiting_x, waiting_y
                self.update_position()

                if hasattr(self, '_move_start_x'):
                    del self._move_start_x
                    del self._move_start_y
                    del self._move_total_time

                # Now wait for blue crane to load the right scanner and move out of the way
                self.state = "WAIT_FOR_BLUE_TO_LOAD_RIGHT"

        elif self.state == "WAIT_FOR_BLUE_TO_LOAD_RIGHT":
            # Wait at fixed position until blue crane is out of the way
            # Red crane stays at: (rightmost_scanner_x + 250, target_box_y)

            # Check if blue crane is out of the way
            pickup_x, _ = config.get_pickup_position()
            blue_is_out_of_way = (
                # State-based check
                    blue_crane.state in ("WAIT_AT_HOME", "MOVE_OUT_OF_WAY_AFTER_RIGHT_LOAD", "WAIT", "MOVE_TO_HOME_EMPTY") or
                    # Position-based check: blue crane is far to the left (near home/start)
                    blue_crane.x < pickup_x + self.safe_distance * 2
            )

            if blue_is_out_of_way:
                # Blue crane is out of the way, we can now go to the box
                if self.target_box is not None and self.target_box < len(self.box_list):
                    target_x, target_y = self.box_list[self.target_box].get_position()

                    # Clean up any old movement tracking before starting new movement
                    if hasattr(self, '_move_start_x'):
                        del self._move_start_x
                    if hasattr(self, '_move_start_y'):
                        del self._move_start_y
                    if hasattr(self, '_move_total_time'):
                        del self._move_total_time

                    self.state = "MOVE_TO_BOX"
                    self.action_timer = self.travel_time_2d(self.x, self.y, target_x, target_y)
                    # Signal to blue crane that we're moving
                    if hasattr(blue_crane, 'waiting_for_red_to_clear'):
                        blue_crane.waiting_for_red_to_clear = True
                return

            # Otherwise just wait at current position - no staging movement needed

        elif self.state == "MOVE_TO_BOX_THEN_RIGHT_SCANNER":
            # Special state: after dropping at box from left scanner, go to right scanner
            if self.target_box is None or self.target_box >= len(self.box_list):
                self.state = "RETURN_HOME"
                self.action_timer = self.travel_time_2d(self.x, self.y, self.initial_x, self.initial_y)
                return

            if self.would_collide_with(blue_crane):
                return

            if self.action_timer > 0:
                target_x, target_y = self.box_list[self.target_box].get_position()

                if not hasattr(self, '_move_start_x'):
                    self._move_start_x = self.x
                    self._move_start_y = self.y
                    self._move_total_time = self.action_timer + dt

                progress = 1.0 - (self.action_timer / self._move_total_time)
                self.x = self._move_start_x + (target_x - self._move_start_x) * progress
                self.y = self._move_start_y + (target_y - self._move_start_y) * progress
                self.update_position()
            else:
                target_x, target_y = self.box_list[self.target_box].get_position()
                self.x, self.y = target_x, target_y
                self.update_position()

                if hasattr(self, '_move_start_x'):
                    del self._move_start_x
                    del self._move_start_y
                    del self._move_total_time

                # Drop at box, then go to right scanner
                self.state = "DROP_AT_BOX_THEN_RIGHT_SCANNER"
                self.action_timer = self.lower_time
                self.drop_phase = "LOWER"

        elif self.state == "DROP_AT_BOX_THEN_RIGHT_SCANNER":
            # Drop diamond at box, then go to right scanner
            if self.target_box is None or self.target_box >= len(self.box_list):
                self.state = "RETURN_HOME"
                self.action_timer = self.travel_time_2d(self.x, self.y, self.initial_x, self.initial_y)
                return

            if self.drop_phase == "LOWER":
                prog = 1.0 - (self.action_timer / self.lower_time)
                z = self.rail_y - (self.rail_y - self.top_y) * prog
                self.set_hoist(self.x, self.y, z, True)

                if self.action_timer <= 0:
                    self.drop_phase = "RAISE"
                    self.action_timer = self.raise_time
                    self.has_diamond = False
                    self.diamond.set_visible(False)

                    diamond_patch = self.box_list[self.target_box].add_diamond()
                    self.ax.add_patch(diamond_patch)

            elif self.drop_phase == "RAISE":
                prog = self.action_timer / self.raise_time
                z = self.rail_y - (self.rail_y - self.top_y) * prog
                self.set_hoist(self.x, self.y, z, True)

                if self.action_timer <= 0:
                    self.drop_phase = None
                    self.set_hoist(self.x, self.y, self.top_y, False)

                    # Now go to right scanner (scanner 1)
                    if len(self.scanner_list) > 1:
                        target_x, target_y = self.scanner_list[1].get_drop_zone_position()
                        self.target_i = 1
                        self.from_rightmost = True
                        self.state = "MOVE_TO_SCANNER"
                        self.action_timer = self.travel_time_2d(self.x, self.y, target_x, target_y)
                    else:
                        # No right scanner, return home
                        self.state = "RETURN_HOME"
                        self.action_timer = self.travel_time_2d(self.x, self.y, self.initial_x, self.initial_y)

        elif self.state == "MOVE_TO_BOX":
            if self.target_box is None or self.target_box >= len(self.box_list):
                self.state = "RETURN_HOME"
                self.action_timer = self.travel_time_2d(self.x, self.y, self.initial_x, self.initial_y)
                return

            # Check for collision with blue crane
            if self.would_collide_with(blue_crane):
                # Blocked by blue crane - reset movement tracking and recalculate time
                if hasattr(self, '_move_start_x'):
                    del self._move_start_x
                    del self._move_start_y
                    del self._move_total_time

                # Recalculate travel time from current position
                target_x, target_y = self.box_list[self.target_box].get_position()
                self.action_timer = self.travel_time_2d(self.x, self.y, target_x, target_y)
                return

            if self.action_timer > 0:
                target_x, target_y = self.box_list[self.target_box].get_position()

                # Initialize movement tracking on first frame
                if not hasattr(self, '_move_start_x'):
                    self._move_start_x = self.x
                    self._move_start_y = self.y
                    self._move_total_time = self.action_timer + dt

                # Prevent division by zero
                if self._move_total_time > 0:
                    progress = 1.0 - (self.action_timer / self._move_total_time)
                    self.x = self._move_start_x + (target_x - self._move_start_x) * progress
                    self.y = self._move_start_y + (target_y - self._move_start_y) * progress
                    self.update_position()
            else:
                # Movement complete - set final position
                target_x, target_y = self.box_list[self.target_box].get_position()
                self.x, self.y = target_x, target_y
                self.update_position()

                if hasattr(self, '_move_start_x'):
                    del self._move_start_x
                    del self._move_start_y
                    del self._move_total_time

                self.state = "DROP_AT_BOX"
                self.action_timer = self.lower_time
                self.drop_phase = "LOWER"

        elif self.state == "DROP_AT_BOX":
            if self.target_box is None or self.target_box >= len(self.box_list):
                self.state = "RETURN_HOME"
                self.action_timer = self.travel_time_2d(self.x, self.y, self.initial_x, self.initial_y)
                return

            if self.drop_phase == "LOWER":
                prog = 1.0 - (self.action_timer / self.lower_time)
                z = self.rail_y - (self.rail_y - self.top_y) * prog
                self.set_hoist(self.x, self.y, z, True)

                if self.action_timer <= 0:
                    self.drop_phase = "RAISE"
                    self.action_timer = self.raise_time
                    self.has_diamond = False
                    self.diamond.set_visible(False)

                    diamond_patch = self.box_list[self.target_box].add_diamond()
                    self.ax.add_patch(diamond_patch)

            elif self.drop_phase == "RAISE":
                prog = self.action_timer / self.raise_time
                z = self.rail_y - (self.rail_y - self.top_y) * prog
                self.set_hoist(self.x, self.y, z, True)

                if self.action_timer <= 0:
                    self.drop_phase = None
                    self.set_hoist(self.x, self.y, self.top_y, False)

                    # After dropping, check what to do next
                    if self.from_rightmost:
                        # Just finished dropping from right scanner
                        # Check if left scanner has a diamond ready or will be ready soon
                        if len(self.scanner_list) > 0:
                            left_scanner = self.scanner_list[0]

                            # Go to left scanner if it's ready or scanning
                            if left_scanner.state in ("ready", "scanning"):
                                # Go to left scanner
                                target_x, target_y = left_scanner.get_drop_zone_position()
                                self.target_i = 0
                                self.target_box = left_scanner.get_target_box()
                                self.from_rightmost = False  # Reset flag
                                self.state = "MOVE_TO_SCANNER"
                                self.action_timer = self.travel_time_2d(self.x, self.y, target_x, target_y)
                                return

                        # If left scanner not ready, reset flag and go home
                        self.from_rightmost = False
                        self.state = "RETURN_HOME"
                        self.action_timer = self.travel_time_2d(self.x, self.y, self.initial_x, self.initial_y)
                    else:
                        # Default: return home
                        self.state = "RETURN_HOME"
                        self.action_timer = self.travel_time_2d(self.x, self.y, self.initial_x, self.initial_y)

        elif self.state == "RETURN_HOME":
            if self.would_collide_with(blue_crane):
                return

            if self.action_timer > 0:
                if not hasattr(self, '_move_start_x'):
                    self._move_start_x = self.x
                    self._move_start_y = self.y
                    self._move_total_time = self.action_timer + dt

                progress = 1.0 - (self.action_timer / self._move_total_time)
                self.x = self._move_start_x + (self.initial_x - self._move_start_x) * progress
                self.y = self._move_start_y + (self.initial_y - self._move_start_y) * progress
                self.update_position()
            else:
                self.x, self.y = self.initial_x, self.initial_y
                self.update_position()
                if hasattr(self, '_move_start_x'):
                    del self._move_start_x
                    del self._move_start_y
                    del self._move_total_time
                self.state = "WAIT"

        # Update diamond visual if carrying
        if self.has_diamond:
            display_x = config.mm_to_display(self.x)
            display_y = config.mm_to_display(self.top_y)
            self.diamond.xy = (display_x, display_y)