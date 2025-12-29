"""
Soccer Drill Generation System

A production-ready system for generating soccer training drills
with AI-powered content and accurate diagram rendering.

Quick Start:
    from drill_system import DrillPipeline
    
    pipeline = DrillPipeline()
    result = pipeline.generate(
        goal="Finishing under pressure",
        num_players=6,
        output_svg="drill.svg"
    )

Manual Drill Creation:
    from drill_system import Drill, Player, Position, render
    
    drill = Drill(
        name="My Drill",
        description="A custom drill",
        players=[
            Player(id="A1", role="ATTACKER", position=Position(x=50, y=50))
        ]
    )
    render(drill, "output.svg")
"""

from schema import (
    # Enums
    FieldType,
    AttackingDirection,
    PlayerRole,
    GateOrientation,
    
    # Core types
    Position,
    FieldConfig,
    
    # Entities
    Player,
    Cone,
    ConeGate,
    Ball,
    
    # Actions
    PassAction,
    RunAction,
    DribbleAction,
    ShotAction,
    Action,
    
    # Main drill type
    Drill,
    
    # Coach input
    CoachConstraints,
    CoachRequest,
    
    # Utilities
    get_reference_positions,
)

from renderer import render, render_to_png
from validator import validate_drill, ValidationResult
from generator import DrillGenerator, generate_drill
from pipeline import DrillPipeline, PipelineResult

__all__ = [
    # Enums
    "FieldType",
    "AttackingDirection", 
    "PlayerRole",
    "GateOrientation",
    
    # Core types
    "Position",
    "FieldConfig",
    
    # Entities
    "Player",
    "Cone",
    "ConeGate",
    "Ball",
    
    # Actions
    "PassAction",
    "RunAction",
    "DribbleAction",
    "ShotAction",
    "Action",
    
    # Main drill type
    "Drill",
    
    # Coach input
    "CoachConstraints",
    "CoachRequest",
    
    # Functions
    "get_reference_positions",
    "render",
    "render_to_png",
    "validate_drill",
    "generate_drill",
    
    # Classes
    "DrillGenerator",
    "DrillPipeline",
    "ValidationResult",
    "PipelineResult",
]

__version__ = "1.0.0"
