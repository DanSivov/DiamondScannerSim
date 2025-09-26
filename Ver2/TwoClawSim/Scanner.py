# Scanner.py
import random
import matplotlib.pyplot as plt
from matplotlib.patches import RegularPolygon
import math
import config

from Ver2.TwoClawSim.config import N_BOXES, T_SCAN


def make_diamond(x, y, color, size=0.18, z=6):
    return RegularPolygon(
        (x, y), numVertices=4, radius=size, orientation=math.pi/4,
        facecolor=color, edgecolor='black', lw=1.0, zorder=z
    )

class DScanner:
    def __init__(self, POS_X):
        self.POS_X = POS_X
        self.scans_done = 0
        self.state = "empty"  # possible states: empty, scanning, ready
        self.ready_time = None  # when it entered ready state
        self.timer = 0.0
        self.target_box_id = None  # Which box this diamond should go to
        self.scan_time = getattr(config, 'T_SCAN', T_SCAN)

        # Visual diamond for this scanner
        self.diamond = make_diamond(POS_X, 7.5, '#ffd54f')
        self.diamond.set_visible(False)

    def scan(self, diamond):
        """Trigger scan when diamond is loaded."""
        if self.state != "empty":
            print("Scan triggered, but scanner not in empty state")
            return

        self.state = "scanning"
        self.timer = self.scan_time
        self.diamond.set_visible(True)
        self.diamond.set_facecolor('#ffd54f')  # Yellow during scanning

        # Randomly assign a target box
        self.target_box_id = random.randint(0, N_BOXES - 1)

    def update(self, dt, current_time):
        """Update scanner state for simulation"""
        if self.state == "scanning":
            self.timer -= dt
            if self.timer <= 0:
                self.state = "ready"
                self.ready_time = current_time
                self.diamond.set_facecolor('#66bb6a')  # Green when ready

    def pickup(self):
        """Trigger pickup when claw picks up diamond."""
        if self.state != "ready":
            print("Pickup triggered, but scanner not in ready state")
            return 0

        wait_time = 0
        if self.ready_time is not None:
            # In simulation, we don't use real time, so return 0 for now
            wait_time = 0

        self.state = "empty"
        self.ready_time = None
        self.target_box_id = None
        self.diamond.set_visible(False)
        self.scans_done += 1
        return wait_time

    def get_target_box(self):
        """Get the target box for this scanner's diamond"""
        return self.target_box_id

    def add_diamond_to_plot(self, ax):
        """Add the diamond visual element to the plot"""
        ax.add_patch(self.diamond)