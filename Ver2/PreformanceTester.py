import matplotlib.pyplot as plt
import numpy as np
from TwoClawSim import config
import time
import random

def run_simulation_headless(n_scanners, scan_time, loading_strategy, test_duration=300):
    """
    Run simulation headlessly and return diamonds per minute

    Args:
        n_scanners: Number of scanners
        scan_time: Scan time in seconds
        loading_strategy: "closest" or "furthest"
        test_duration: How long to run simulation in seconds

    Returns:
        diamonds_per_minute: Performance metric
    """
    # Set fixed random seed for reproducibility
    random.seed(42)

    # Temporarily set scan time in config
    original_scan_time = config.T_SCAN
    config.T_SCAN = scan_time

    print(f"Starting simulation with scan_time={scan_time}, strategy={loading_strategy}")
    print(f"Config T_SCAN is now: {config.T_SCAN}")

    try:
        # Import necessary modules
        import matplotlib
        matplotlib.use('Agg')  # Use non-interactive backend

        import matplotlib.pyplot as plt
        from TwoClawSim.Scanner import DScanner
        from TwoClawSim.endBox import Box
        from TwoClawSim.crane import BlueCrane, RedCrane, make_diamond
        from matplotlib.patches import Circle, Rectangle

        # Setup simulation without display
        fig, ax = plt.subplots(figsize=(15, 5.5))
        ax.set_xlim(0, 15)
        ax.set_ylim(0, 9.6)
        ax.axis('off')

        # Layout constants
        TOP_Y = 7.5
        RAIL_Y = 1.0
        CARRY_Y = 4.0
        START_X = 1.2
        END_X = 10

        # Create scanners
        center = 5.5
        spacing = 1.2
        scanner_List = []

        if n_scanners == 1:
            scanner_List.append(DScanner(center))
        else:
            total_span = spacing * (n_scanners - 1)
            left = center - total_span / 2
            for i in range(n_scanners):
                x_pos = left + i * spacing
                scanner_List.append(DScanner(x_pos))

        # Update scanner scan times to use the test parameter
        for scanner in scanner_List:
            scanner.scan_time = scan_time

        print(f"Scanner positions: {[s.POS_X for s in scanner_List]}")
        print(f"Scanner scan_time after update: {scanner_List[0].scan_time}")

        # Create boxes
        box_list = []
        END_BOX_X = END_X
        for i in range(config.N_BOXES):
            box_list.append(Box(i, END_BOX_X, TOP_Y))

        # Create cranes
        blue_crane = BlueCrane(ax, START_X, scanner_List, loading_strategy=loading_strategy,
                               rail_y=RAIL_Y, carry_y=CARRY_Y, top_y=TOP_Y)
        red_crane = RedCrane(ax, END_X, scanner_List, box_list,
                             rail_y=RAIL_Y, carry_y=CARRY_Y, top_y=TOP_Y)

        print(f"Blue crane strategy: {blue_crane.loading_strategy}")
        print(f"Blue crane start position: {blue_crane.x}")
        print(f"Red crane start position: {red_crane.x}")

        # Simulation variables
        t_elapsed = 0.0
        delivered_total = 0
        FPS = 60
        DT = 1.0 / FPS
        ready_wait_start = [None for _ in range(n_scanners)]
        total_ready_wait = 0.0

        # Debug tracking
        scan_events = []
        delivery_events = []
        target_selections = []

        # Helper functions
        def add_delivered_marker():
            nonlocal delivered_total
            delivered_total += 1
            delivery_events.append({
                'time': t_elapsed,
                'count': delivered_total,
                'box_id': red_crane.target_box.box_id if red_crane.target_box else None
            })

        def close_ready_wait(i):
            nonlocal total_ready_wait
            if ready_wait_start[i] is not None:
                total_ready_wait += (t_elapsed - ready_wait_start[i])
                ready_wait_start[i] = None

        def schedule_red_departure():
            red_crane.schedule_departure(t_elapsed)

        # Modified blue crane step to track target selections
        original_blue_step = blue_crane.step
        def debug_blue_step(dt, red_crane, schedule_red_callback=None):
            # Track when blue crane selects a target
            if blue_crane.state == "PICK_AT_START" and blue_crane.action_timer <= dt:
                target_i = blue_crane.get_target_scanner()
                if target_i is not None:
                    target_selections.append({
                        'time': t_elapsed,
                        'target_scanner': target_i,
                        'scanner_pos': scanner_List[target_i].POS_X,
                        'strategy': loading_strategy,
                        'available_scanners': [i for i, s in enumerate(scanner_List) if s.state == "empty"]
                    })
            return original_blue_step(dt, red_crane, schedule_red_callback)

        blue_crane.step = debug_blue_step

        # Run simulation loop
        loop_count = 0
        last_print_time = 0

        while t_elapsed < test_duration:
            t_elapsed += DT
            loop_count += 1

            # Debug print every 60 seconds
            if int(t_elapsed) >= last_print_time + 60:
                print(f"  Time: {t_elapsed:.1f}s, Delivered: {delivered_total}, Loop count: {loop_count}")
                last_print_time = int(t_elapsed)

            # Update scanners and track scan events
            for i, scanner in enumerate(scanner_List):
                old_state = scanner.state
                scanner.update(DT, t_elapsed)

                # Track scan completion events
                if old_state == "scanning" and scanner.state == "ready":
                    scan_events.append({
                        'time': t_elapsed,
                        'scanner': i,
                        'target_box': scanner.get_target_box()
                    })

                # Track ready wait times
                if scanner.state == "ready" and ready_wait_start[i] is None:
                    ready_wait_start[i] = t_elapsed
                elif scanner.state != "ready" and ready_wait_start[i] is not None:
                    ready_wait_start[i] = None

            # Early departure logic for red crane
            if (all(scanner.state == "scanning" for scanner in scanner_List) and
                    red_crane.earliest_ready_scanner() is None and
                    red_crane.state == "WAIT" and
                    red_crane.departure_time == float('inf')):
                i_scan = red_crane.earliest_finishing_scan()
                if i_scan is not None:
                    rem = scanner_List[i_scan].timer
                    tt = red_crane.travel_time(red_crane.x, scanner_List[i_scan].POS_X)
                    red_crane.target_i = i_scan
                    t_ready = t_elapsed + rem
                    red_crane.lower_start_time = t_ready - red_crane.lower_time
                    red_crane.lower_planned_for_i = i_scan
                    red_crane.departure_time = max(red_crane.lower_start_time - tt, t_elapsed)

            # Step cranes
            blue_crane.step(DT, red_crane, schedule_red_departure)
            red_crane.step(DT, t_elapsed, blue_crane, close_ready_wait, add_delivered_marker)

        print(f"  Simulation completed: {t_elapsed:.1f}s, Final delivered: {delivered_total}")

        # Print debug summary
        print(f"\nDEBUG SUMMARY for {loading_strategy} strategy, {scan_time}s scan:")
        print(f"Total target selections: {len(target_selections)}")
        if target_selections:
            print("Target selections:")
            for i, sel in enumerate(target_selections[:5]):  # Show first 5
                print(f"  {i+1}. Time {sel['time']:.1f}s -> Scanner {sel['target_scanner']} (pos {sel['scanner_pos']:.1f})")
            if len(target_selections) > 5:
                print(f"  ... and {len(target_selections) - 5} more")

        print(f"Total scan completions: {len(scan_events)}")
        print(f"Total deliveries: {len(delivery_events)}")

        if delivery_events:
            delivery_times = [d['time'] for d in delivery_events]
            intervals = [delivery_times[i] - delivery_times[i-1] for i in range(1, len(delivery_times))]
            if intervals:
                print(f"Average delivery interval: {np.mean(intervals):.1f}s")

        # Calculate diamonds per minute
        diamonds_per_minute = delivered_total / (test_duration / 60.0)

        plt.close(fig)  # Clean up
        return diamonds_per_minute

    finally:
        # Restore original scan time
        config.T_SCAN = original_scan_time
        print(f"Restored config T_SCAN to: {config.T_SCAN}")

def run_performance_comparison():
    """
    Run performance comparison between closest and furthest loading strategies
    """
    scan_times = [10, 15, 20, 30]  # Full range of scan times
    strategies = ["closest", "furthest"]  # Both strategies
    n_scanners = 2
    test_duration = 3000  # 25 minutes for accurate results

    print("Starting performance comparison...")
    print(f"Testing with {n_scanners} scanners for {test_duration} seconds each")
    print("Scan times:", scan_times)
    print("Strategies:", strategies)
    print()

    results = {}

    for strategy in strategies:
        results[strategy] = []
        print(f"Testing {strategy} strategy...")

        for scan_time in scan_times:
            print(f"  Running scan time {scan_time}s...", end="")
            start_time = time.time()

            diamonds_per_min = run_simulation_headless(n_scanners, scan_time, strategy, test_duration)

            end_time = time.time()
            results[strategy].append(diamonds_per_min)
            print(f" {diamonds_per_min:.2f} diamonds/min (took {end_time-start_time:.1f}s)")

        print()

    # Create comparison chart
    plt.figure(figsize=(12, 6))

    x = np.arange(len(scan_times))
    width = 0.35

    plt.bar(x - width/2, results["closest"], width, label="Closest First", alpha=0.8, color='skyblue')
    plt.bar(x + width/2, results["furthest"], width, label="Furthest First", alpha=0.8, color='lightcoral')

    plt.xlabel('Scan Time (seconds)')
    plt.ylabel('Diamonds per Minute')
    plt.title('Loading Strategy Performance Comparison\n(2 Scanners, 25-minute test duration)')
    plt.xticks(x, scan_times)
    plt.legend()
    plt.grid(axis='y', alpha=0.3)

    # Add value labels on bars
    for i, (closest_val, furthest_val) in enumerate(zip(results["closest"], results["furthest"])):
        plt.text(i - width/2, closest_val + 0.01, f'{closest_val:.2f}',
                 ha='center', va='bottom', fontsize=9)
        plt.text(i + width/2, furthest_val + 0.01, f'{furthest_val:.2f}',
                 ha='center', va='bottom', fontsize=9)

    plt.tight_layout()
    plt.show()

    # Print summary
    print("\nRESULTS SUMMARY:")
    print("="*60)
    print(f"{'Scan Time':<12} {'Closest':<12} {'Furthest':<12} {'Difference':<15} {'% Diff'}")
    print("-"*60)

    for i, scan_time in enumerate(scan_times):
        closest = results["closest"][i]
        furthest = results["furthest"][i]
        diff = furthest - closest
        diff_pct = (diff / closest) * 100 if closest > 0 else 0

        print(f"{scan_time}s{'':<10} {closest:<12.2f} {furthest:<12.2f} {diff:+.2f}{'':<11} {diff_pct:+.1f}%")

    print()
    print("Summary:")
    closest_avg = np.mean(results["closest"])
    furthest_avg = np.mean(results["furthest"])
    overall_diff = furthest_avg - closest_avg
    overall_pct = (overall_diff / closest_avg) * 100 if closest_avg > 0 else 0

    print(f"Average performance - Closest: {closest_avg:.2f}, Furthest: {furthest_avg:.2f}")
    print(f"Overall difference: {overall_diff:+.2f} diamonds/min ({overall_pct:+.1f}%)")

    if abs(overall_pct) < 1.0:
        print("Both strategies perform essentially equally.")
    elif overall_diff > 0:
        print("Furthest-first strategy performs better on average.")
    else:
        print("Closest-first strategy performs better on average.")

    return results

if __name__ == "__main__":
    results = run_performance_comparison()