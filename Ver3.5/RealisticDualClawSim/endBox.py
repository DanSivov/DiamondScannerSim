# Ver3.5/RealisticDualClawSim/endBox.py
"""
End Box class for Ver3.5 Realistic Dual-Claw Simulation

Handles collection boxes where sorted diamonds are deposited.
(Copied from Ver3 - works identically)
"""

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


class Box:
    """
    End Box class for collecting sorted diamonds

    Each box tracks:
    - Position in 2D space (x, y)
    - Count of diamonds delivered
    - Visual representation of accumulated diamonds
    """

    def __init__(self, box_id, x_pos, y_pos):
        """
        Initialize end box

        Args:
            box_id: Unique identifier (0 to N_BOXES-1)
            x_pos: X position in mm
            y_pos: Y position in mm
        """
        self.box_id = box_id
        self.x_pos = x_pos
        self.y_pos = y_pos
        self.diamond_count = 0
        self.delivered_diamonds = []  # Visual diamonds in this box

    def add_diamond(self):
        """
        Add a diamond to this box

        Returns: diamond patch object for matplotlib
        """
        self.diamond_count += 1

        # Create visual representation - offset by box_id to prevent complete overlap
        idx = len(self.delivered_diamonds)
        cols = 5

        # Convert to display units
        display_x = config.mm_to_display(self.x_pos)
        display_y = config.mm_to_display(self.y_pos)

        # Calculate offset for visual stacking (in display units)
        dx = (idx % cols) * 0.12 - 0.24 + (self.box_id * 0.02)  # Slight offset per box
        dy = (idx // cols) * 0.12 + (self.box_id * 0.02)        # Slight offset per box

        diamond = make_diamond(
            display_x + dx,
            display_y + dy,
            '#66bb6a',  # Green for delivered diamonds
            size=0.16,
            z=3
        )
        self.delivered_diamonds.append(diamond)
        return diamond

    def get_position(self):
        """
        Get the position of this box in mm

        Returns: (x, y) tuple
        """
        return (self.x_pos, self.y_pos)

    def get_coordinates(self):
        """
        Get the coordinates where this box is located - key method for crane targeting

        Returns: (x, y) tuple in mm
        """
        return (self.x_pos, self.y_pos)

    def get_drop_zone_position(self):
        """
        Get the position where crane should drop diamonds for this box.
        This is the center of the box.

        Returns: (x, y) tuple in mm
        """
        return (self.x_pos, self.y_pos)

    def get_count(self):
        """
        Get the number of diamonds in this box

        Returns: int
        """
        return self.diamond_count

    def reset(self):
        """Reset the box to empty state"""
        self.diamond_count = 0
        # Remove visual diamonds (if they were added to axes)
        for diamond in self.delivered_diamonds:
            if diamond.axes is not None and diamond in diamond.axes.patches:
                diamond.remove()
        self.delivered_diamonds.clear()

    def __repr__(self):
        """String representation for debugging"""
        return f"Box(id={self.box_id}, pos=({self.x_pos}, {self.y_pos}), count={self.diamond_count})"
