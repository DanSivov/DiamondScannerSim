# Ver3/RealisticTwoClawSim/__init__.py
"""
RealisticTwoClawSim - A realistic diamond sorting simulation package

This package contains:
- config: All measurements, positions, and configuration
- scanner: Scanner class for diamond scanning
- endBox: Box class for collection containers
- crane: Crane classes (BlueCrane, RedCrane) for 2D movement
- display: Visualization module
- simulation: Main simulation controller
"""

from . import config
from .scanner import DScanner
from .endBox import Box
from .crane import Crane, BlueCrane, RedCrane
from .display import SimulationDisplay, display_simulation
from .simulation import SimulationController, run_simulation

__version__ = "3.0.0"
__all__ = [
    'config',
    'DScanner',
    'Box',
    'Crane',
    'BlueCrane',
    'RedCrane',
    'SimulationDisplay',
    'display_simulation',
    'SimulationController',
    'run_simulation'
]