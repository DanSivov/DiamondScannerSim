"""
Side View Controller for Ver3 Realistic Two-Claw Diamond Sorting System

Displays side view showing vertical (Z-axis) crane movements
"""

import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, Circle, FancyBboxPatch
from matplotlib.lines import Line2D
import sys
import os

# Import from parent package
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from .. import config


class SideViewController:
    """Controls the side view visualization window"""

    def __init__(self, scanner_list, blue_crane, red_crane, box_list):
        """
        Initialize side view

        Args:
            scanner_list: List of scanner objects from main simulation
            blue_crane: Blue crane object from main simulation
            red_crane: Red crane object from main simulation
            box_list: List of box objects from main simulation
        """
        self.scanner_list = scanner_list
        self.blue_crane = blue_crane
        self.red_crane = red_crane
        self.box_list = box_list

        # Create figure
        self.fig, self.ax = plt.subplots(figsize=(12, 6))
        self.fig.canvas.manager.set_window_title('Side View - Vertical Movement')

        # Position window to the right of main window
        manager = plt.get_current_fig_manager()
        try:
            # Position at top right
            x = 800  # Offset from left
            y = 10   # 10px from top
            manager.window.wm_geometry(f"+{x}+{y}")
        except:
            pass

        self.setup_axes()
        self.create_static_elements()
        self.create_dynamic_elements()

        # Force redraw to ensure everything is visible
        self.fig.canvas.draw()
        plt.show(block=False)
        self.fig.canvas.flush_events()

        print("Side view initialization complete")

    def setup_axes(self):
        """Setup axes for side view"""
        # X-axis: horizontal position (mm)
        # Y-axis: vertical position/height (mm)

        margin = 50
        x_min = config.RAIL_X_MIN - margin
        x_max = config.RAIL_X_MAX + margin

        # Vertical range: from below scanners to above rail
        y_min = config.PICKUP_Y - margin
        y_max = config.RAIL_Y + margin

        self.ax.set_xlim(config.mm_to_display(x_min), config.mm_to_display(x_max))
        self.ax.set_ylim(config.mm_to_display(y_min), config.mm_to_display(y_max))

        self.ax.set_aspect('equal')
        self.ax.grid(True, alpha=0.3, linestyle='--')
        self.ax.set_xlabel('Horizontal Position (mm × 0.1)', fontsize=10)
        self.ax.set_ylabel('Vertical Height (mm × 0.1)', fontsize=10)
        self.ax.set_title('Side View - Crane Vertical Movement', fontsize=12, fontweight='bold')

        plt.style.use('ggplot')

    def create_static_elements(self):
        """Draw static elements (rail, scanners, end boxes, pickup zone)"""
        print("Creating side view static elements...")

        # Rail (at the top)
        x_start = config.mm_to_display(config.RAIL_X_MIN)
        x_end = config.mm_to_display(config.RAIL_X_MAX)
        y_rail = config.mm_to_display(config.RAIL_Y)

        self.ax.plot([x_start, x_end], [y_rail, y_rail],
                     linewidth=4, color=config.COLOR_RAIL,
                     solid_capstyle='round', zorder=1, label='Rail')
        print(f"  Rail drawn at y={y_rail}")

        # Calculate the height where scanners sit (where cranes lower to)
        # This is rail height minus the lowering distance
        scanner_platform_height = config.RAIL_Y - config.D_Z
        y_scanner = config.mm_to_display(scanner_platform_height)

        print(f"  Scanner platform height: {scanner_platform_height:.1f}mm (display: {y_scanner:.1f})")

        # Scanners (as boxes that arms lower to)
        print(f"  Drawing {len(self.scanner_list)} scanners...")
        for i, scanner in enumerate(self.scanner_list):
            try:
                # Get scanner X position (horizontal)
                scanner_x = scanner.x_pos  # X position in mm

                x_display = config.mm_to_display(scanner_x)

                # Scanner dimensions
                width = config.mm_to_display(config.S_W_SCANNER)
                height = config.mm_to_display(config.S_H_SCANNER)

                # Draw scanner as a box at the platform height
                # Center the scanner vertically at the platform height
                scanner_rect = Rectangle(
                    (x_display - width/2, y_scanner - height/2),
                    width, height,
                    facecolor=config.COLOR_SCANNER,
                    edgecolor='black',
                    linewidth=2.5,
                    alpha=0.8,
                    zorder=2
                )
                self.ax.add_patch(scanner_rect)

                # Drop zone indicator line (where crane lowers to) - top of scanner
                drop_y = y_scanner + height/2
                self.ax.plot([x_display - width/2, x_display + width/2],
                             [drop_y, drop_y],
                             'r-', linewidth=3, zorder=3, alpha=0.9)

                # Label
                self.ax.text(x_display, y_scanner - height/2 - config.mm_to_display(15),
                             f"Scanner {i+1}",
                             ha='center', va='top', fontsize=10, fontweight='bold',
                             bbox=dict(boxstyle='round,pad=0.3', facecolor='white', alpha=0.7))

                print(f"    Scanner {i+1} at x={scanner_x:.1f}mm, height={scanner_platform_height:.1f}mm")
            except Exception as e:
                print(f"    Error drawing scanner {i}: {e}")
                import traceback
                traceback.print_exc()

        # End boxes (ONLY first row - boxes 0-3)
        print("  Drawing end boxes (first row only)...")
        try:
            # Get all box positions
            box_positions = config.get_end_box_positions()

            # First row is boxes 0-3 (indices 0, 1, 2, 3)
            first_row_indices = [0, 1, 2, 3]

            # End boxes sit at the same height as scanners (where cranes drop to)
            box_platform_height = scanner_platform_height
            y_box = config.mm_to_display(box_platform_height)

            for idx in first_row_indices:
                if idx < len(box_positions):
                    box_x, box_y = box_positions[idx]

                    x_display = config.mm_to_display(box_x)

                    # Box size
                    box_radius = config.mm_to_display(config.BOX_RADIUS)

                    # Draw box as circle at scanner platform height
                    box_circle = Circle(
                        (x_display, y_box),
                        box_radius,
                        facecolor=config.COLOR_END_BOX,
                        edgecolor='darkorange',
                        linewidth=2,
                        alpha=0.7,
                        zorder=2
                    )
                    self.ax.add_patch(box_circle)

                    # Label
                    self.ax.text(x_display, y_box,
                                 str(idx + 1),
                                 ha='center', va='center',
                                 fontsize=9, fontweight='bold',
                                 color='black')

                    print(f"    Box {idx + 1} at x={box_x:.1f}, height={box_platform_height:.1f}mm")
        except Exception as e:
            print(f"  Error drawing end boxes: {e}")
            import traceback
            traceback.print_exc()

        # START box (Pickup zone) - where diamonds come from
        print("  Drawing START box (pickup zone)...")
        try:
            pickup_x = config.mm_to_display(config.PICKUP_X)
            # Pickup zone is at the ground level (PICKUP_Y)
            pickup_height = config.PICKUP_Y
            pickup_y = config.mm_to_display(pickup_height)

            size = config.mm_to_display(config.PICKUP_RADIUS)

            # Draw as a rectangle (box) at ground level
            pickup_rect = Rectangle(
                (pickup_x - size/2, pickup_y - size/2), size, size,
                facecolor=config.COLOR_PICKUP,
                edgecolor='darkgreen',
                linewidth=2.5,
                alpha=0.8,
                zorder=2
            )
            self.ax.add_patch(pickup_rect)

            # Draw crosshair on the pickup box
            cross = size * 0.3
            self.ax.plot([pickup_x - cross/2, pickup_x + cross/2], [pickup_y, pickup_y],
                         'darkgreen', linewidth=2, zorder=3)
            self.ax.plot([pickup_x, pickup_x], [pickup_y - cross/2, pickup_y + cross/2],
                         'darkgreen', linewidth=2, zorder=3)

            # Label
            self.ax.text(pickup_x, pickup_y - size/2 - config.mm_to_display(10),
                         'START', ha='center', va='top',
                         fontsize=10, fontweight='bold', color='darkgreen',
                         bbox=dict(boxstyle='round,pad=0.3', facecolor='lightgreen', alpha=0.7))

            print(f"  START box at x={config.PICKUP_X:.1f}mm, height={pickup_height:.1f}mm")
        except Exception as e:
            print(f"  Error drawing START box: {e}")
            import traceback
            traceback.print_exc()

        print("Static elements created")

    def create_dynamic_elements(self):
        """Create visual elements that will be updated each frame"""
        print("Creating side view dynamic elements...")

        w = config.mm_to_display(config.CRANE_WIDTH)
        h = config.mm_to_display(config.CRANE_HEIGHT)

        # Blue crane
        try:
            blue_x = config.mm_to_display(self.blue_crane.x)
            blue_z = config.mm_to_display(self.blue_crane.z)

            self.blue_crane_rect = Rectangle(
                (blue_x - w/2, blue_z - h/2), w, h,
                fc=config.COLOR_BLUE_CLAW, ec='black', lw=1.5, zorder=5
            )
            self.ax.add_patch(self.blue_crane_rect)

            # Blue crane hoist/cable
            self.blue_hoist, = self.ax.plot([], [], color=config.COLOR_BLUE_CLAW,
                                            lw=2, zorder=4, linestyle='--')

            # Blue crane hand/gripper
            self.blue_hand = Circle((blue_x, blue_z), config.mm_to_display(15),
                                    fc=config.COLOR_BLUE_CLAW, ec='black',
                                    lw=1, zorder=6)
            self.ax.add_patch(self.blue_hand)

            # Blue diamond
            self.blue_diamond = Circle((blue_x, blue_z), config.mm_to_display(10),
                                       fc='#33a3ff', ec='black', lw=1, zorder=7)
            self.blue_diamond.set_visible(False)
            self.ax.add_patch(self.blue_diamond)

            print(f"  Blue crane at x={self.blue_crane.x:.1f}, z={self.blue_crane.z:.1f}")
        except Exception as e:
            print(f"  Error creating blue crane: {e}")
            import traceback
            traceback.print_exc()

        # Red crane
        try:
            red_x = config.mm_to_display(self.red_crane.x)
            red_z = config.mm_to_display(self.red_crane.z)

            self.red_crane_rect = Rectangle(
                (red_x - w/2, red_z - h/2), w, h,
                fc=config.COLOR_RED_CLAW, ec='black', lw=1.5, zorder=5
            )
            self.ax.add_patch(self.red_crane_rect)

            # Red crane hoist/cable
            self.red_hoist, = self.ax.plot([], [], color=config.COLOR_RED_CLAW,
                                           lw=2, zorder=4, linestyle='--')

            # Red crane hand/gripper
            self.red_hand = Circle((red_x, red_z), config.mm_to_display(15),
                                   fc=config.COLOR_RED_CLAW, ec='black',
                                   lw=1, zorder=6)
            self.ax.add_patch(self.red_hand)

            # Red diamond
            self.red_diamond = Circle((red_x, red_z), config.mm_to_display(10),
                                      fc='#ff6b6b', ec='black', lw=1, zorder=7)
            self.red_diamond.set_visible(False)
            self.ax.add_patch(self.red_diamond)

            print(f"  Red crane at x={self.red_crane.x:.1f}, z={self.red_crane.z:.1f}")
        except Exception as e:
            print(f"  Error creating red crane: {e}")
            import traceback
            traceback.print_exc()

        print("Dynamic elements created")

    def update(self):
        """Update side view based on current crane positions"""
        # Update blue crane
        blue_x = config.mm_to_display(self.blue_crane.x)
        blue_z_crane = config.mm_to_display(self.blue_crane.z)
        w = config.mm_to_display(config.CRANE_WIDTH)
        h = config.mm_to_display(config.CRANE_HEIGHT)

        self.blue_crane_rect.set_xy((blue_x - w/2, blue_z_crane - h/2))

        # Calculate hand position based on state
        blue_hand_z = self.get_hand_z_position(self.blue_crane)
        blue_hand_z_display = config.mm_to_display(blue_hand_z)

        # Update hoist line
        if blue_hand_z < self.blue_crane.z - 10:  # Show cable if lowered
            self.blue_hoist.set_data([blue_x, blue_x],
                                     [blue_z_crane, blue_hand_z_display])
            self.blue_hoist.set_visible(True)
        else:
            self.blue_hoist.set_visible(False)

        # Update hand
        self.blue_hand.center = (blue_x, blue_hand_z_display)

        # Update diamond
        if self.blue_crane.has_diamond:
            self.blue_diamond.center = (blue_x, blue_hand_z_display)
            self.blue_diamond.set_visible(True)
        else:
            self.blue_diamond.set_visible(False)

        # Update red crane
        red_x = config.mm_to_display(self.red_crane.x)
        red_z_crane = config.mm_to_display(self.red_crane.z)

        self.red_crane_rect.set_xy((red_x - w/2, red_z_crane - h/2))

        # Calculate hand position
        red_hand_z = self.get_hand_z_position(self.red_crane)
        red_hand_z_display = config.mm_to_display(red_hand_z)

        # Update hoist line
        if red_hand_z < self.red_crane.z - 10:  # Show cable if lowered
            self.red_hoist.set_data([red_x, red_x],
                                    [red_z_crane, red_hand_z_display])
            self.red_hoist.set_visible(True)
        else:
            self.red_hoist.set_visible(False)

        # Update hand
        self.red_hand.center = (red_x, red_hand_z_display)

        # Update diamond
        if self.red_crane.has_diamond:
            self.red_diamond.center = (red_x, red_hand_z_display)
            self.red_diamond.set_visible(True)
        else:
            self.red_diamond.set_visible(False)

        # Redraw
        self.fig.canvas.draw_idle()
        self.fig.canvas.flush_events()

    def get_hand_z_position(self, crane):
        """Calculate the Z position of the crane's hand based on its state"""
        # At rail height by default
        hand_z = crane.z

        # If in pick or drop phase, calculate lowered position
        if crane.pick_phase == "LOWER":
            # Lowering
            if crane.action_timer > 0:
                progress = 1.0 - (crane.action_timer / crane.lower_time)
                hand_z = crane.rail_y - (crane.rail_y - crane.top_y) * progress
            else:
                hand_z = crane.top_y
        elif crane.pick_phase == "RAISE":
            # Raising
            if crane.action_timer > 0:
                progress = crane.action_timer / crane.raise_time
                hand_z = crane.rail_y - (crane.rail_y - crane.top_y) * progress
            else:
                hand_z = crane.rail_y
        elif crane.drop_phase == "LOWER":
            # Lowering
            if crane.action_timer > 0:
                progress = 1.0 - (crane.action_timer / crane.lower_time)
                hand_z = crane.rail_y - (crane.rail_y - crane.top_y) * progress
            else:
                hand_z = crane.top_y
        elif crane.drop_phase == "RAISE":
            # Raising
            if crane.action_timer > 0:
                progress = crane.action_timer / crane.raise_time
                hand_z = crane.rail_y - (crane.rail_y - crane.top_y) * progress
            else:
                hand_z = crane.rail_y

        return hand_z

    def close(self):
        """Close the side view window"""
        plt.close(self.fig)