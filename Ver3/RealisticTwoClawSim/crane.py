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

        # No hoist visualization in top-down view
        # Side view will handle vertical movement visualization

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

    def update_rendering(self, other_crane):
        """
        Update visual rendering to prevent cranes from appearing to overlap

        Strategy:
        1. Adjust zorder so moving crane renders in front
        2. Add slight Y-offset when cranes are close for visual separation

        Args:
            other_crane: The other crane to check position against
        """
        # Calculate distance
        distance = abs(self.x - other_crane.x)

        # Base zorder for cranes
        base_zorder = 5

        # Determine which crane should render in front based on state priority
        movement_states = [
            "MOVE_TO_SCANNER", "MOVE_TO_BOX", "RETURN_HOME",
            "MOVE_TO_START", "RETURN_TO_START", "RETURN_TO_HOME_WITH_DIAMOND",
            "MOVE_OUT_OF_WAY_AFTER_RIGHT_PICKUP", "MOVE_OUT_OF_WAY_AFTER_RIGHT_LOAD",
            "MOVE_TO_BOX_THEN_RIGHT_SCANNER", "MOVE_TO_HOME_EMPTY"
        ]

        # Check if cranes are close enough to need visual adjustment
        if distance < self.safe_distance * 1.5:  # Within 1.5x safe distance
            # Determine rendering priority
            self_moving = self.state in movement_states
            other_moving = other_crane.state in movement_states

            # Rendering priority rules:
            # 1. Moving crane in front of stationary crane
            # 2. If both moving or both stationary: use crane priority
            # 3. Crane with priority renders in front

            if self_moving and not other_moving:
                # This crane is moving, render in front
                my_zorder = base_zorder + 2
                other_zorder = base_zorder
            elif other_moving and not self_moving:
                # Other crane is moving, render in back
                my_zorder = base_zorder
                other_zorder = base_zorder + 2
            else:
                # Both moving or both stationary - use priority system
                if self.has_priority_over(other_crane):
                    my_zorder = base_zorder + 2
                    other_zorder = base_zorder
                else:
                    my_zorder = base_zorder
                    other_zorder = base_zorder + 2

            # Update zorder
            self.crane_rect.set_zorder(my_zorder)
            other_crane.crane_rect.set_zorder(other_zorder)

            # Add visual Y-offset for additional separation when very close
            if distance < self.safe_distance:
                # Apply small Y offset based on X position
                # Crane on left gets slight downward offset, crane on right gets upward offset
                if self.x < other_crane.x:
                    # This crane is on left - shift down slightly
                    y_offset = -3  # Small offset in mm
                    other_y_offset = 3
                else:
                    # This crane is on right - shift up slightly
                    y_offset = 3
                    other_y_offset = -3

                # Apply offset to visual position
                display_x = config.mm_to_display(self.x)
                display_y = config.mm_to_display(self.y + y_offset)
                display_width = config.mm_to_display(self.crane_width)
                display_height = config.mm_to_display(self.crane_height)
                self.crane_rect.set_xy((display_x - display_width/2, display_y - display_height/2))

                # Apply offset to other crane
                other_display_x = config.mm_to_display(other_crane.x)
                other_display_y = config.mm_to_display(other_crane.y + other_y_offset)
                other_display_width = config.mm_to_display(other_crane.crane_width)
                other_display_height = config.mm_to_display(other_crane.crane_height)
                other_crane.crane_rect.set_xy((other_display_x - other_display_width/2,
                                               other_display_y - other_display_height/2))
        else:
            # Cranes far apart - reset to normal rendering
            self.crane_rect.set_zorder(base_zorder)
            other_crane.crane_rect.set_zorder(base_zorder)

            # Reset positions (remove any Y-offset)
            display_x = config.mm_to_display(self.x)
            display_y = config.mm_to_display(self.y)
            display_width = config.mm_to_display(self.crane_width)
            display_height = config.mm_to_display(self.crane_height)
            self.crane_rect.set_xy((display_x - display_width/2, display_y - display_height/2))

    def set_hoist(self, x, y, z_top, show):
        """Dummy method - hoist visualization removed from top-down view"""
        pass

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

        collision = distance_x < safe_distance

        # DIAGNOSTIC: Log collision checks
        if collision:
            print(f"⚠️  COLLISION DETECTED:")
            print(f"   {self.color} crane at X={self.x:.1f}mm, state={self.state}, has_diamond={self.has_diamond}")
            print(f"   {other_crane.color} crane at X={other_crane.x:.1f}mm, state={other_crane.state}, has_diamond={other_crane.has_diamond}")
            print(f"   Distance: {distance_x:.1f}mm < {safe_distance:.1f}mm (COLLISION)")
            print(f"   Time: {getattr(self, 't_elapsed', 0):.2f}s")

        return collision

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

    def is_in_deadlock_with(self, other_crane):
        """
        Check if both cranes are in a deadlock situation
        Deadlock occurs when both cranes are:
        1. Too close to each other (collision)
        2. Both trying to move (in movement states)
        3. NOT when one crane is actively working (picking/dropping/loading)

        Returns: Boolean
        """
        # Check if we're too close
        if not self.would_collide_with(other_crane):
            return False

        # Check if both cranes are in movement states
        movement_states = [
            "MOVE_TO_SCANNER", "MOVE_TO_BOX", "RETURN_HOME",
            "MOVE_TO_START", "RETURN_TO_START", "RETURN_TO_HOME_WITH_DIAMOND",
            "MOVE_OUT_OF_WAY_AFTER_RIGHT_PICKUP", "MOVE_OUT_OF_WAY_AFTER_RIGHT_LOAD",
            "MOVE_TO_BOX_THEN_RIGHT_SCANNER", "MOVE_TO_HOME_EMPTY"
        ]

        both_moving = (self.state in movement_states and other_crane.state in movement_states)

        if not both_moving:
            return False

        # CRITICAL: If blue crane is actively working (loading diamonds),
        # this is NOT a deadlock - red crane must always yield
        if other_crane.color == '#1f77b4':  # Blue crane
            blue_working_states = [
                "PICK_AT_START",              # Blue picking up diamond
                "DROP_AT_SCANNER",            # Blue loading scanner
                "MOVE_TO_SCANNER",            # Blue going to load
                "RETURN_TO_START",            # Blue returning after loading
                "RETURN_TO_HOME_WITH_DIAMOND" # Blue returning home with diamond
            ]
            if other_crane.state in blue_working_states:
                return False  # Not a deadlock, red must yield

        return both_moving

    def has_priority_over(self, other_crane):
        """
        Determine if this crane has priority over another crane in a deadlock

        Priority rules:
        1. Crane WITHOUT diamond has priority over crane WITH diamond
        2. If both have diamonds OR both don't have diamonds: Blue crane has priority

        Returns: Boolean (True if this crane has priority)
        """
        # Rule 1: Check diamond status
        if self.has_diamond and not other_crane.has_diamond:
            # Other crane has priority (doesn't have diamond)
            return False
        elif not self.has_diamond and other_crane.has_diamond:
            # This crane has priority (doesn't have diamond)
            return True

        # Rule 2: Both have same diamond status - blue crane has priority
        # Blue crane color is '#1f77b4', Red crane color is '#d62728'
        if self.color == '#1f77b4':  # Blue crane
            return True
        else:  # Red crane
            return False

    def should_yield_to(self, other_crane):
        """
        Check if this crane should yield to another crane
        Used for collision avoidance with priority system

        Returns: Boolean (True if this crane should wait)
        """
        # First check if we're in a deadlock situation
        in_deadlock = self.is_in_deadlock_with(other_crane)

        if not in_deadlock:
            # Not in deadlock - use simple collision check
            # Both cranes wait for each other equally
            result = self.would_collide_with(other_crane)
            if result:
                print(f"🚦 {self.color} crane YIELDING (simple collision):")
                print(f"   Not a deadlock, just too close")
            return result

        # In deadlock - use priority system
        # Should yield if OTHER crane has priority
        has_priority = self.has_priority_over(other_crane)
        should_yield = not has_priority

        if should_yield:
            print(f"🚦 {self.color} crane YIELDING (priority system):")
            print(f"   In deadlock, {other_crane.color} has priority")
        else:
            print(f"🚦 {self.color} crane HAS PRIORITY:")
            print(f"   In deadlock, this crane proceeds")

        return should_yield

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
            # Check for collision with red crane - use priority system
            if self.should_yield_to(red_crane):
                # CRITICAL FIX: Reset movement tracking and recalculate time
                if hasattr(self, '_move_start_x'):
                    del self._move_start_x
                    del self._move_start_y
                    del self._move_total_time

                # Recalculate travel time from current position
                pickup_x, pickup_y = config.get_pickup_position()
                self.action_timer = self.travel_time_2d(self.x, self.y, pickup_x, pickup_y)
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

            # Check for collision with red crane - use priority system
            if self.should_yield_to(red_crane):
                # CRITICAL FIX: Reset movement tracking and recalculate time
                if hasattr(self, '_move_start_x'):
                    del self._move_start_x
                    del self._move_start_y
                    del self._move_total_time

                # Recalculate travel time from current position
                target_x, target_y = self.scanner_list[self.target_i].get_drop_zone_position()
                self.action_timer = self.travel_time_2d(self.x, self.y, target_x, target_y)
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

                    print(f"🔵 BLUE crane finished DROP_AT_SCANNER")
                    print(f"   Position: X={self.x:.1f}, Y={self.y:.1f}")
                    print(f"   Has diamond: {self.has_diamond}")
                    print(f"   About to transition to RETURN_TO_START")

                    # Check if we just loaded the right scanner while red crane is waiting
                    if (self.target_i == 1 and
                            red_crane.state == "WAIT_FOR_BLUE_TO_LOAD_RIGHT"):
                        # We loaded right scanner, now go pick up another diamond and move out of way
                        self.state = "RETURN_TO_START"
                        pickup_x, pickup_y = config.get_pickup_position()
                        self.action_timer = self.travel_time_2d(self.x, self.y, pickup_x, pickup_y)
                        # Set flag so we know to move out of way after picking up diamond
                        self.waiting_for_red_to_clear = True
                        print(f"   → Transitioning to RETURN_TO_START (special: red waiting)")
                        return

                    # Always return to start for next diamond
                    self.state = "RETURN_TO_START"
                    pickup_x, pickup_y = config.get_pickup_position()
                    self.action_timer = self.travel_time_2d(self.x, self.y, pickup_x, pickup_y)
                    print(f"   → Transitioned to RETURN_TO_START")
                    print(f"   → Timer set to {self.action_timer:.2f}s")
                    print(f"   → Current position AFTER transition: X={self.x:.1f}, Y={self.y:.1f}")
                    print(f"   → Red crane position: X={red_crane.x:.1f}, Y={red_crane.y:.1f}, State={red_crane.state}")
                    print(f"   → Distance to red: {abs(self.x - red_crane.x):.1f}mm")

        elif self.state == "RETURN_TO_START":
            # Move crane back to pickup zone
            # Check for collision with red crane - use priority system
            if self.should_yield_to(red_crane):
                # CRITICAL FIX: Reset movement tracking and recalculate time
                if hasattr(self, '_move_start_x'):
                    del self._move_start_x
                    del self._move_start_y
                    del self._move_total_time

                # Recalculate travel time from current position
                pickup_x, pickup_y = config.get_pickup_position()
                self.action_timer = self.travel_time_2d(self.x, self.y, pickup_x, pickup_y)
                return

            if self.action_timer > 0:
                pickup_x, pickup_y = config.get_pickup_position()

                # Store initial position at start of movement
                if not hasattr(self, '_move_start_x'):
                    self._move_start_x = self.x
                    self._move_start_y = self.y
                    self._move_total_time = self.action_timer + dt
                    print(f"🔵 BLUE crane starting RETURN_TO_START movement")
                    print(f"   From: ({self.x:.1f}, {self.y:.1f}) To: ({pickup_x:.1f}, {pickup_y:.1f})")
                    print(f"   Total time: {self._move_total_time:.2f}s")

                # Calculate progress (0 to 1)
                progress = 1.0 - (self.action_timer / self._move_total_time)

                old_x = self.x
                # Interpolate position
                self.x = self._move_start_x + (pickup_x - self._move_start_x) * progress
                self.y = self._move_start_y + (pickup_y - self._move_start_y) * progress

                # Log significant movement
                if abs(old_x - self.x) > 10:  # Moved more than 10mm
                    print(f"🔵 BLUE crane RETURN_TO_START: X={old_x:.1f} → {self.x:.1f} (progress={progress*100:.1f}%)")

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
            # Check for collision with red crane - use priority system
            if self.should_yield_to(red_crane):
                # CRITICAL FIX: Reset movement tracking and recalculate time
                if hasattr(self, '_move_start_x'):
                    del self._move_start_x
                    del self._move_start_y
                    del self._move_total_time

                # Recalculate travel time from current position
                self.action_timer = self.travel_time_2d(self.x, self.y, self.initial_x, self.initial_y)
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
                        # STRICT CHECK: Don't depart if blue crane is anywhere near the path
                        if self.would_collide_with(blue_crane):
                            # Currently too close to blue crane - wait
                            print(f"🔴 RED crane WAIT: Can't depart (collision with blue)")
                            print(f"   Red X={self.x:.1f}, Blue X={blue_crane.x:.1f}")
                            continue

                        if not self.can_move_to_x(scanner_x, blue_crane):
                            # Destination would be too close to blue crane - wait
                            print(f"🔴 RED crane WAIT: Can't depart (destination unsafe)")
                            print(f"   Target X={scanner_x:.1f}, Blue X={blue_crane.x:.1f}")
                            continue

                        # Both checks passed - safe to depart
                        print(f"🔴 RED crane WAIT: DEPARTING to scanner {i}")
                        print(f"   Red X={self.x:.1f}, Blue X={blue_crane.x:.1f}")
                        print(f"   Blue state={blue_crane.state}, Blue has_diamond={blue_crane.has_diamond}")
                        print(f"   Target scanner X={scanner_x:.1f}")
                        self.target_i = i
                        self.target_box = scanner.get_target_box()
                        self.state = "MOVE_TO_SCANNER"
                        self.action_timer = travel_time
                        # Clear stored prediction
                        self.departure_times.pop(i, None)
                        # Track if this is the right scanner
                        self.from_rightmost = (i == 1)
                        break

            # Fallback: if no scheduled run and a scanner is already ready
            if self.target_i is None:
                ready_scanners = [i for i, s in enumerate(self.scanner_list) if s.state == "ready"]
                if ready_scanners:
                    target_i = self.nearest_ready_scanner()
                    if target_i is not None:
                        target_x, target_y = self.scanner_list[target_i].get_drop_zone_position()

                        # STRICT CHECK: Don't depart if blue crane is anywhere near
                        if self.would_collide_with(blue_crane):
                            # Currently too close - don't move
                            pass
                        elif not self.can_move_to_x(target_x, blue_crane):
                            # Destination would be too close - don't move
                            pass
                        else:
                            # Safe to depart
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

            # Collision with blue crane - use priority system
            if self.should_yield_to(blue_crane):
                print(f"🛑 RED crane MOVE_TO_SCANNER blocked by blue crane")
                print(f"   Red X={self.x:.1f}, Blue X={blue_crane.x:.1f}, Distance={abs(self.x - blue_crane.x):.1f}mm")
                # CRITICAL FIX: Reset movement tracking and recalculate time
                if hasattr(self, '_move_start_x'):
                    del self._move_start_x
                    del self._move_start_y
                    del self._move_total_time

                # Recalculate travel time from current position
                target_x, target_y = self.scanner_list[self.target_i].get_drop_zone_position()
                self.action_timer = self.travel_time_2d(self.x, self.y, target_x, target_y)
                return
            else:
                # Log when red crane is allowed to proceed
                if abs(self.x - blue_crane.x) < 150:  # Log if within 150mm
                    print(f"✅ RED crane MOVE_TO_SCANNER proceeding (not yielding)")
                    print(f"   Red X={self.x:.1f}, Blue X={blue_crane.x:.1f}, Distance={abs(self.x - blue_crane.x):.1f}mm")
                    print(f"   Blue state={blue_crane.state}, Blue has_diamond={blue_crane.has_diamond}")

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

            # SPECIAL CASE: If we're here with no timer and no phase, we finished picking
            # but couldn't move because blue crane was blocking. Retry the transition.
            if self.action_timer <= 0 and self.pick_phase is None:
                if self.target_box is None:
                    self.target_box = 0

                # From left scanner - check if should go to right scanner or to box
                if not self.from_rightmost:
                    if len(self.scanner_list) > 1:
                        right_scanner = self.scanner_list[1]
                        if right_scanner.state in ("ready", "scanning"):
                            target_x, target_y = right_scanner.get_drop_zone_position()

                            if not self.would_collide_with(blue_crane) and self.can_move_to_x(target_x, blue_crane):
                                # Now safe to go to right scanner
                                self.target_i = 1
                                self.target_box = right_scanner.get_target_box()
                                self.state = "MOVE_TO_BOX_THEN_RIGHT_SCANNER"
                                box_x, box_y = self.box_list[self.target_box].get_position()
                                self.action_timer = self.travel_time_2d(self.x, self.y, box_x, box_y)
                                return

                # Try to go to box
                if self.target_box is not None and self.target_box < len(self.box_list):
                    target_x, target_y = self.box_list[self.target_box].get_position()

                    if not self.would_collide_with(blue_crane):
                        # Now safe to go to box
                        self.state = "MOVE_TO_BOX"
                        self.action_timer = self.travel_time_2d(self.x, self.y, target_x, target_y)
                        return

                # Still blocked - just wait here (will retry next frame)
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
                        # From left scanner - check if should go to right scanner or to box
                        # STRICT CHECK: Only proceed if blue crane is not in the way
                        if len(self.scanner_list) > 1:
                            right_scanner = self.scanner_list[1]
                            if right_scanner.state in ("ready", "scanning"):
                                # Check if blue crane blocks the path
                                target_x, target_y = right_scanner.get_drop_zone_position()

                                # CRITICAL: Check collision before committing to movement
                                if not self.would_collide_with(blue_crane) and self.can_move_to_x(target_x, blue_crane):
                                    # Safe to go to right scanner
                                    self.target_i = 1
                                    self.target_box = right_scanner.get_target_box()
                                    self.state = "MOVE_TO_BOX_THEN_RIGHT_SCANNER"
                                    # First go to box to drop current diamond
                                    box_x, box_y = self.box_list[self.target_box].get_position()
                                    self.action_timer = self.travel_time_2d(self.x, self.y, box_x, box_y)
                                    return

                        # Default behavior: go to box
                        # STRICT CHECK: Ensure path to box is clear
                        if self.target_box is not None and self.target_box < len(self.box_list):
                            target_x, target_y = self.box_list[self.target_box].get_position()

                            # Check collision before going to box
                            if not self.would_collide_with(blue_crane):
                                self.state = "MOVE_TO_BOX"
                                self.action_timer = self.travel_time_2d(self.x, self.y, target_x, target_y)
                            else:
                                # Blue crane in the way - stay here and check next frame
                                # Don't transition to movement state yet
                                pass
                        else:
                            # No valid box - return home
                            self.state = "RETURN_HOME"
                            self.action_timer = self.travel_time_2d(self.x, self.y, self.initial_x, self.initial_y)

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

            if self.should_yield_to(blue_crane):
                # CRITICAL FIX: Reset movement tracking and recalculate time
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

            # SPECIAL CASE: If we're here with no timer and no phase, we finished dropping
            # but couldn't move because blue crane was blocking. Retry the transition.
            if self.action_timer <= 0 and self.drop_phase is None:
                if len(self.scanner_list) > 1:
                    target_x, target_y = self.scanner_list[1].get_drop_zone_position()

                    if not self.would_collide_with(blue_crane) and self.can_move_to_x(target_x, blue_crane):
                        # Now safe to proceed to right scanner
                        self.target_i = 1
                        self.from_rightmost = True
                        self.state = "MOVE_TO_SCANNER"
                        self.action_timer = self.travel_time_2d(self.x, self.y, target_x, target_y)
                        return
                    else:
                        # Still blocked - try going home instead
                        if not self.would_collide_with(blue_crane):
                            self.state = "RETURN_HOME"
                            self.action_timer = self.travel_time_2d(self.x, self.y, self.initial_x, self.initial_y)
                            return
                else:
                    # No right scanner
                    self.state = "RETURN_HOME"
                    self.action_timer = self.travel_time_2d(self.x, self.y, self.initial_x, self.initial_y)
                    return

                # Still blocked - wait here (will retry next frame)
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

                        # STRICT CHECK: Verify path to right scanner is clear
                        if not self.would_collide_with(blue_crane) and self.can_move_to_x(target_x, blue_crane):
                            # Safe to proceed to right scanner
                            self.target_i = 1
                            self.from_rightmost = True
                            self.state = "MOVE_TO_SCANNER"
                            self.action_timer = self.travel_time_2d(self.x, self.y, target_x, target_y)
                        else:
                            # Blue crane blocking - go home instead
                            self.state = "RETURN_HOME"
                            self.action_timer = self.travel_time_2d(self.x, self.y, self.initial_x, self.initial_y)
                    else:
                        # No right scanner, return home
                        self.state = "RETURN_HOME"
                        self.action_timer = self.travel_time_2d(self.x, self.y, self.initial_x, self.initial_y)

        elif self.state == "MOVE_TO_BOX":
            if self.target_box is None or self.target_box >= len(self.box_list):
                self.state = "RETURN_HOME"
                self.action_timer = self.travel_time_2d(self.x, self.y, self.initial_x, self.initial_y)
                return

            # Check for collision with blue crane - use priority system
            if self.should_yield_to(blue_crane):
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

            # SPECIAL CASE: If we're here with no timer and no phase, we finished dropping
            # but couldn't move because blue crane was blocking. Retry the transition.
            if self.action_timer <= 0 and self.drop_phase is None:
                # After dropping, check what to do next
                if self.from_rightmost:
                    # Check if left scanner has a diamond ready
                    if len(self.scanner_list) > 0:
                        left_scanner = self.scanner_list[0]
                        if left_scanner.state in ("ready", "scanning"):
                            target_x, target_y = left_scanner.get_drop_zone_position()

                            if not self.would_collide_with(blue_crane) and self.can_move_to_x(target_x, blue_crane):
                                # Now safe to go to left scanner
                                self.target_i = 0
                                self.target_box = left_scanner.get_target_box()
                                self.from_rightmost = False
                                self.state = "MOVE_TO_SCANNER"
                                self.action_timer = self.travel_time_2d(self.x, self.y, target_x, target_y)
                                return

                    # Left scanner not ready or still blocked - try going home
                    self.from_rightmost = False
                    if not self.would_collide_with(blue_crane):
                        self.state = "RETURN_HOME"
                        self.action_timer = self.travel_time_2d(self.x, self.y, self.initial_x, self.initial_y)
                        return
                else:
                    # Try to return home
                    if not self.would_collide_with(blue_crane):
                        self.state = "RETURN_HOME"
                        self.action_timer = self.travel_time_2d(self.x, self.y, self.initial_x, self.initial_y)
                        return

                # Still blocked - wait here (will retry next frame)
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
                                # STRICT CHECK: Verify path is clear before committing
                                target_x, target_y = left_scanner.get_drop_zone_position()

                                if not self.would_collide_with(blue_crane) and self.can_move_to_x(target_x, blue_crane):
                                    # Safe to go to left scanner
                                    self.target_i = 0
                                    self.target_box = left_scanner.get_target_box()
                                    self.from_rightmost = False  # Reset flag
                                    self.state = "MOVE_TO_SCANNER"
                                    self.action_timer = self.travel_time_2d(self.x, self.y, target_x, target_y)
                                    return

                        # If left scanner not ready or path blocked, reset flag and go home
                        self.from_rightmost = False

                        # STRICT CHECK: Only go home if path is clear
                        if not self.would_collide_with(blue_crane):
                            self.state = "RETURN_HOME"
                            self.action_timer = self.travel_time_2d(self.x, self.y, self.initial_x, self.initial_y)
                        # else: stay here until path clears
                    else:
                        # Default: return home
                        # STRICT CHECK: Only go home if path is clear
                        if not self.would_collide_with(blue_crane):
                            self.state = "RETURN_HOME"
                            self.action_timer = self.travel_time_2d(self.x, self.y, self.initial_x, self.initial_y)
                        # else: stay here until path clears

        elif self.state == "RETURN_HOME":
            if self.should_yield_to(blue_crane):
                # CRITICAL FIX: Reset movement tracking and recalculate time
                if hasattr(self, '_move_start_x'):
                    del self._move_start_x
                    del self._move_start_y
                    del self._move_total_time

                # Recalculate travel time from current position
                self.action_timer = self.travel_time_2d(self.x, self.y, self.initial_x, self.initial_y)
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