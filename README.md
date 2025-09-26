# Diamond Scanner Simulation

The code contains two version. Ver1 for the original base implementation of the idea
and Ver2 a refactored and more optimised version. Bellow I outline the overview for Ver2

## Overview

This simulation models a diamond processing facility where:
- **Red & Blue Cranes**: Automated robotic arms that pick and place diamonds
- **Scanner**: Diamond detection and analysis system
- **End Boxes**: Sorts diamonds into respective boxes
- **Rail**: Provides movement for the cranes 
## Key Features

- **Optimized Crane Movement**: Pre-emptive positioning saves >1.8s per cycle
- **Real-time Visualization**: Live simulation with ggplot-style graphics
- **State Machine Logic**: Crane coordination and timing
- **Configurable Parameters**: Adjustable speeds, timing, and positions

## Usage

There are two runnable options: 
- `Main.py` will run the simulation with two cranes and 1-4 scanners. Using the "First" logic
- `PreformanceTester.py` will run a tester function, currently programmed to compare the difference in "First" and "Last" Logic

## Architecture

The simulation uses object-oriented design with:
- `Crane` class for robotic arm logic
- State-based movement control
- Event-driven scanner coordination
- Matplotlib-based real-time display

## Performance

Optimizations include early crane extension and intelligent timing coordination between multiple automated systems.