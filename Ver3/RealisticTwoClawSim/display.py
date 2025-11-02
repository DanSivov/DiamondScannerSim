# Ver3/RealisticTwoClawSim/display.py
# Visualization module for diamond sorting simulation

import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, Circle, FancyBboxPatch
from matplotlib.lines import Line2D
from . import config

class SimulationDisplay:
    def __init__(self):
        """Initialize the display"""
        self.fig, self.ax = plt.subplots(figsize=(config.DISPLAY_WIDTH, config.DISPLAY_HEIGHT))

        # Make window resizable and movable
        manager = plt.get_current_fig_manager()
        try:
            # Try to set resizable (works for most backends)
            manager.window.resizable(True, True)
        except:
            pass

        # Position window at top left of screen
        try:
            manager.window.update_idletasks()

            # Top left position with small margins
            x = 10  # 10px from left edge
            y = 10  # 10px from top

            manager.window.wm_geometry(f"+{x}+{y}")
        except Exception as e:
            print(f"Could not position window: {e}")

        self.setup_axes()
        self.draw_static_elements()

    def setup_axes(self):
        """Setup matplotlib axes with proper scaling and limits"""
        # Calculate display bounds (with margins)
        margin = 50  # mm
        x_min = config.RAIL_X_MIN - margin
        x_max = config.RAIL_X_MAX + margin
        y_min = config.PICKUP_Y - margin
        y_max = config.RAIL_Y + margin

        # Convert to display units
        self.ax.set_xlim(config.mm_to_display(x_min), config.mm_to_display(x_max))
        self.ax.set_ylim(config.mm_to_display(y_min), config.mm_to_display(y_max))

        # Equal aspect ratio
        self.ax.set_aspect('equal')

        # Grid and labels
        self.ax.grid(True, alpha=0.3, linestyle='--')
        self.ax.set_xlabel(f'X Position (display units = mm × {config.DISPLAY_SCALE})')
        self.ax.set_ylabel(f'Y Position (display units = mm × {config.DISPLAY_SCALE})')
        self.ax.set_title('Diamond Sorting Simulation - Ver3\n(Default Positions)',
                          fontsize=14, fontweight='bold')

        # Style
        plt.style.use('ggplot')

    def draw_static_elements(self):
        """Draw all static elements (rail, scanners, zones, boxes)"""
        self.draw_rail()
        self.draw_scanners()
        self.draw_pickup_zone()
        self.draw_end_boxes()

    def draw_rail(self):
        """Draw the rail that claws travel on"""
        x_start = config.mm_to_display(config.RAIL_X_MIN)
        x_end = config.mm_to_display(config.RAIL_X_MAX)
        y = config.mm_to_display(config.RAIL_Y)

        # Main rail line (thick)
        rail = Line2D([x_start, x_end], [y, y],
                      linewidth=6, color=config.COLOR_RAIL,
                      solid_capstyle='round', zorder=1)
        self.ax.add_line(rail)

        # Rail support lines (thinner, going down slightly)
        support_offset = config.mm_to_display(10)
        for x in [x_start, x_end]:
            support = Line2D([x, x], [y, y - support_offset],
                             linewidth=4, color=config.COLOR_RAIL,
                             zorder=1)
            self.ax.add_line(support)

        # Label
        self.ax.text(config.mm_to_display(0), y + config.mm_to_display(15),
                     'RAIL', ha='center', va='bottom',
                     fontsize=10, fontweight='bold', color=config.COLOR_RAIL)

    def draw_scanners(self):
        """Draw both scanners with drop zones"""
        for i, (x, y) in enumerate(config.get_scanner_positions()):
            label = "Scanner 1" if i == 0 else "Scanner 2"
            self.draw_scanner(x, y, label)

    def draw_scanner(self, x_mm, y_mm, label):
        """Draw a single scanner"""
        # Convert to display units
        x = config.mm_to_display(x_mm)
        y = config.mm_to_display(y_mm)
        w = config.mm_to_display(config.S_W_SCANNER)
        h = config.mm_to_display(config.S_H_SCANNER)

        # Scanner body (fancy box with rounded corners)
        scanner_body = FancyBboxPatch(
            (x - w/2, y - h/2), w, h,
            boxstyle="round,pad=0.02",
            facecolor=config.COLOR_SCANNER,
            edgecolor='black',
            linewidth=2,
            alpha=0.7,
            zorder=3
        )
        self.ax.add_patch(scanner_body)

        # Drop zone (small circle in center where diamonds are placed)
        drop_radius = config.mm_to_display(config.SCANNER_DROP_RADIUS)
        drop_zone = Circle((x, y), drop_radius,
                           facecolor='red', edgecolor='darkred',
                           linewidth=2, zorder=4)
        self.ax.add_patch(drop_zone)

        # Label
        self.ax.text(x, y - h/2 - config.mm_to_display(10),
                     label, ha='center', va='top',
                     fontsize=11, fontweight='bold')

    def draw_pickup_zone(self):
        """Draw the pickup zone (START)"""
        x = config.mm_to_display(config.PICKUP_X)
        y = config.mm_to_display(config.PICKUP_Y)
        size = config.mm_to_display(config.PICKUP_RADIUS)

        # Pickup zone square
        pickup = Rectangle(
            (x - size/2, y - size/2), size, size,
            facecolor=config.COLOR_PICKUP,
            edgecolor='darkgreen',
            linewidth=2.5,
            alpha=0.8,
            zorder=2
        )
        self.ax.add_patch(pickup)

        # Center crosshair
        cross_size = size * 0.3
        self.ax.plot([x - cross_size/2, x + cross_size/2], [y, y],
                     'k-', linewidth=2, zorder=3)
        self.ax.plot([x, x], [y - cross_size/2, y + cross_size/2],
                     'k-', linewidth=2, zorder=3)

        # Label
        self.ax.text(x, y - size/2 - config.mm_to_display(8),
                     'PICKUP\n(START)', ha='center', va='top',
                     fontsize=10, fontweight='bold', color='darkgreen')

    def draw_end_boxes(self):
        """Draw all end boxes in the grid"""
        positions = config.get_end_box_positions()
        for i, (x_mm, y_mm) in enumerate(positions):
            x = config.mm_to_display(x_mm)
            y = config.mm_to_display(y_mm)
            r = config.mm_to_display(config.BOX_RADIUS)

            # End box circle
            box = Circle((x, y), r,
                         facecolor=config.COLOR_END_BOX,
                         edgecolor='darkorange',
                         linewidth=1.5,
                         alpha=0.8,
                         zorder=2)
            self.ax.add_patch(box)

            # Box number (small text)
            self.ax.text(x, y, str(i+1),
                         ha='center', va='center',
                         fontsize=7, fontweight='bold',
                         color='black')

        # Label for end boxes region
        center_x = sum(x for x, y in positions) / len(positions)
        max_y = max(y for x, y in positions)

        self.ax.text(config.mm_to_display(center_x),
                     config.mm_to_display(max_y + 15),
                     'END BOXES (1-8)',
                     ha='center', va='bottom',
                     fontsize=10, fontweight='bold',
                     color='darkorange')

    def draw_claws(self, blue_x_mm=None, blue_y_mm=None,
                   red_x_mm=None, red_y_mm=None):
        """Draw both claws at specified positions (defaults to home)"""
        # Use home positions if not specified
        if blue_x_mm is None:
            blue_x_mm = config.BLUE_CRANE_HOME_X
        if blue_y_mm is None:
            blue_y_mm = config.BLUE_CRANE_HOME_Y
        if red_x_mm is None:
            red_x_mm = config.RED_CRANE_HOME_X
        if red_y_mm is None:
            red_y_mm = config.RED_CRANE_HOME_Y

        self.draw_claw(blue_x_mm, blue_y_mm, config.COLOR_BLUE_CLAW, "Blue Claw")
        self.draw_claw(red_x_mm, red_y_mm, config.COLOR_RED_CLAW, "Red Claw")

    def draw_claw(self, x_mm, y_mm, color, label):
        """Draw a single claw"""
        x = config.mm_to_display(x_mm)
        y = config.mm_to_display(y_mm)
        w = config.mm_to_display(config.CRANE_WIDTH)
        h = config.mm_to_display(config.CRANE_HEIGHT)

        # Claw body (square)
        claw_body = Rectangle(
            (x - w/2, y - h/2), w, h,
            facecolor=color,
            edgecolor='black',
            linewidth=2,
            alpha=0.85,
            zorder=5
        )
        self.ax.add_patch(claw_body)

        # Connection to rail (thin line going up)
        rail_y = config.mm_to_display(config.RAIL_Y)
        connection = Line2D([x, x], [y + h/2, rail_y],
                            linewidth=2, color=color,
                            linestyle='--', alpha=0.6, zorder=4)
        self.ax.add_line(connection)

        # Gripper indicator at bottom center
        gripper_size = w * 0.2
        gripper_y = y - h/2
        self.ax.plot([x - gripper_size/2, x + gripper_size/2],
                     [gripper_y, gripper_y],
                     color='black', linewidth=4,
                     solid_capstyle='round', zorder=6)

        # Label
        self.ax.text(x, y, label,
                     ha='center', va='center',
                     fontsize=9, fontweight='bold',
                     color='white')

    def show(self):
        """Display the plot"""
        # Draw claws at default positions
        self.draw_claws()

        # Add legend
        legend_elements = [
            Line2D([0], [0], marker='s', color='w',
                   markerfacecolor=config.COLOR_BLUE_CLAW, markersize=10, label='Blue Claw'),
            Line2D([0], [0], marker='s', color='w',
                   markerfacecolor=config.COLOR_RED_CLAW, markersize=10, label='Red Claw'),
            Line2D([0], [0], marker='s', color='w',
                   markerfacecolor=config.COLOR_SCANNER, markersize=10, label='Scanner'),
            Line2D([0], [0], marker='s', color='w',
                   markerfacecolor=config.COLOR_PICKUP, markersize=10, label='Pickup Zone'),
            Line2D([0], [0], marker='o', color='w',
                   markerfacecolor=config.COLOR_END_BOX, markersize=10, label='End Boxes'),
        ]
        self.ax.legend(handles=legend_elements, loc='upper right', fontsize=9)

        plt.tight_layout()
        plt.show()

def display_simulation():
    """Main function to display the simulation"""
    display = SimulationDisplay()
    display.show()

if __name__ == "__main__":
    # Print config summary
    config.print_config_summary()
    print("\nDisplaying visualization...")

    # Show display
    display_simulation()
