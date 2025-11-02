# Ver3/RealisticTwoClawSim/scanner.py
"""
Scanner class for Ver3 Realistic Two-Claw Simulation

Handles diamond scanning with state management and target box assignment.
"""

import random
import matplotlib.pyplot as plt
from matplotlib.patches import RegularPolygon
import math

from . import config


def make_diamond(x, y, color, size=0.18, z=6):
    """Create a diamond visual element for matplotlib"""
    return RegularPolygon(
        (x, y), numVertices=4, radius=size, orientation=math.pi/4,
        facecolor=color, edgecolor='black', lw=1.0, zorder=z
    )


class DScanner:
    """
    Diamond Scanner class

    States:
    - "empty": Ready to receive a diamond
    - "scanning": Currently scanning a diamond
    - "ready": Scan complete, diamond ready for pickup
    """

    def __init__(self, x_pos, y_pos):
        """
        Initialize scanner

        Args:
            x_pos: X position in mm
            y_pos: Y position in mm
        """
        self.x_pos = x_pos
        self.y_pos = y_pos
        self.scans_done = 0
        self.state = "empty"  # possible states: empty, scanning, ready
        self.ready_time = None  # when it entered ready state
        self.timer = 0.0
        self.target_box_id = None  # Which box this diamond should go to
        self.scan_time = config.T_SCAN
        self.state_text = None

        # Visual diamond for this scanner (convert to display units)
        display_x = config.mm_to_display(x_pos)
        display_y = config.mm_to_display(y_pos)
        self.diamond = make_diamond(display_x, display_y, '#ffd54f', size=0.18)
        self.diamond.set_visible(False)

    def get_position(self):
        """Get the (x, y) position of this scanner in mm"""
        return (self.x_pos, self.y_pos)

    def get_drop_zone_position(self):
        """
        Get the position where crane should drop diamonds for this scanner.
        This is the center of the scanner's input area.

        Returns: (x, y) tuple in mm
        """
        return (self.x_pos, self.y_pos)

    def scan(self, diamond=None):
        """
        Trigger scan when diamond is loaded.

        Args:
            diamond: Optional diamond object (for compatibility)
        """
        if self.state != "empty":
            print(f"Scanner at ({self.x_pos}, {self.y_pos}): Scan triggered, but scanner not in empty state")
            return

        self.state = "scanning"
        self.timer = self.scan_time
        self.diamond.set_visible(True)
        self.diamond.set_facecolor('#ffd54f')  # Yellow during scanning

        # Randomly assign a target box
        self.target_box_id = random.randint(0, config.N_BOXES - 1)

    def update(self, dt, current_time):
        """
        Update scanner state for simulation

        Args:
            dt: Time step in seconds
            current_time: Current simulation time in seconds
        """
        if self.state == "scanning":
            self.timer -= dt
            if self.timer <= 0:
                self.state = "ready"
                self.ready_time = current_time
                self.diamond.set_facecolor('#66bb6a')  # Green when ready

    def pickup(self):
        """
        Trigger pickup when claw picks up diamond.

        Returns: wait_time (always 0 in simulation mode)
        """
        if self.state != "ready":
            print(f"Scanner at ({self.x_pos}, {self.y_pos}): Pickup triggered, but scanner not in ready state")
            return 0

        wait_time = 0
        if self.ready_time is not None:
            # In simulation, we don't use real time, so return 0 for now
            wait_time = 0

        box_id = self.target_box_id

        self.state = "empty"
        self.ready_time = None
        self.target_box_id = None
        self.diamond.set_visible(False)
        self.scans_done += 1
        return box_id

    def get_target_box(self):
        """
        Get the target box ID for this scanner's diamond

        Returns: box_id (0 to N_BOXES-1) or None if no target assigned
        """
        return self.target_box_id

    def get_target_box_position(self):
        """
        Get the (x, y) position of the target box for this scanner's diamond

        Returns: (x, y) tuple in mm, or None if no target assigned
        """
        if self.target_box_id is None:
            return None
        return config.get_end_box_by_index(self.target_box_id)

    def add_diamond_to_plot(self, ax):
        """Add the diamond visual element to the matplotlib axes"""
        ax.add_patch(self.diamond)

    def add_state_label(self, ax):
        """Add a text label under the scanner to show its current state"""
        display_x = config.mm_to_display(self.x_pos)
        display_y = config.mm_to_display(self.y_pos - config.S_H_SCANNER/2 - config.SCANNER_STATE_LABEL_OFFSET)

        self.state_text = ax.text(
            display_x,
            display_y,
            "Empty",
            ha='center', va='top',
            fontsize=9, fontweight='bold',
            color='black'
        )

    def update_state_label(self):
        """Update the state label text based on current state"""
        if self.state_text is None:
            return

        if self.state == "empty":
            self.state_text.set_text("Empty")
            self.state_text.set_color("gray")
        elif self.state == "scanning":
            self.state_text.set_text(f"Scanning: {self.timer:.1f}s")
            self.state_text.set_color("orange")
        elif self.state == "ready":
            self.state_text.set_text("Ready")
            self.state_text.set_color("green")

    def reset(self):
        """Reset scanner to initial empty state"""
        self.state = "empty"
        self.ready_time = None
        self.timer = 0.0
        self.target_box_id = None
        self.diamond.set_visible(False)
