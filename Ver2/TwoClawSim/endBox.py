import matplotlib.pyplot as plt
from matplotlib.patches import RegularPolygon
import math

def make_diamond(x, y, color, size=0.18, z=6):
    return RegularPolygon(
        (x, y), numVertices=4, radius=size, orientation=math.pi/4,
        facecolor=color, edgecolor='black', lw=1.0, zorder=z
    )

class Box:
    def __init__(self, box_id, x_pos, y_pos):
        self.box_id = box_id
        self.x_pos = x_pos
        self.y_pos = y_pos
        self.diamond_count = 0
        self.delivered_diamonds = []  # Visual diamonds in this box

    def add_diamond(self):
        """Add a diamond to this box"""
        self.diamond_count += 1

        # Create visual representation - offset by box_id to prevent complete overlap
        idx = len(self.delivered_diamonds)
        cols = 5
        dx = (idx % cols) * 0.12 - 0.24 + (self.box_id * 0.02)  # Slight offset per box
        dy = (idx // cols) * 0.12 + (self.box_id * 0.02)        # Slight offset per box

        diamond = make_diamond(
            self.x_pos + dx,
            self.y_pos + dy,
            '#66bb6a',
            size=0.16,
            z=3
        )
        self.delivered_diamonds.append(diamond)
        return diamond

    def get_coordinates(self):
        """Get the coordinates where this box is located - key method for crane targeting"""
        return self.x_pos, self.y_pos

    def get_count(self):
        """Get the number of diamonds in this box"""
        return self.diamond_count

    def reset(self):
        """Reset the box to empty state"""
        self.diamond_count = 0
        # Remove visual diamonds
        for diamond in self.delivered_diamonds:
            diamond.remove()
        self.delivered_diamonds.clear()