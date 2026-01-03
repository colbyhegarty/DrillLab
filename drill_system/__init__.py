# drill_system package
"""
Soccer Drill System - Core components for drill generation and rendering.
"""

from .schema import Drill
from .renderer import render

__all__ = ['Drill', 'render']
