# Diamond Scanner Simulation

The code contains three versions. Ver1 is purely for legacy. While Ver2 and Ver3 are made around different ways
to position the start/end locations in relation to the scanners.

## Overview

This simulation models a diamond processing machine where:
- **Red & Blue Cranes**: Automated robotic arms that pick and place diamonds
- **Scanner**: Diamond analysis system
- **Start Point**: where un-scanned diamonds are taken from 
- **End Boxes**: End destination of scanned diamonds
- **Rail**: Provides movement for the cranes

## Usage

The code for both versions is isolated and is run separately: 
- To run Ver2, open the Ver2 folder and go to `main.py`,
this will pop up a window where you can choose to run with 1 or 2 scanners. As well as being able to change the config values through another pop-up.


- To run Ver3, open the Ver3 folder and go to `main.py`, this will pop up a window where you can choose the simulation speed.
It is recommended to use the Recommended setting, in it each second is around 2 seconds in the real world (depends on machine). 
Such delay is caused by overhead and by running it in the realistic speed mode there is a possibility of bugs happening, especially with the skip button.
I am working on fixing it, most likely the culprit is the crane.py file in Ver3. You can also choose to select if you want to view
the side view of the simulation, to be able to view the lowering and raising of the cranes. 

## Architecture

Both simulations use object-oriented design with:
- `crane` class for robotic arm logic
- State-based movement control
- Event-driven crane coordination
- Matplotlib-based real-time display
