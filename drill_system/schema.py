"""
Soccer Drill Schema - Core data models using Pydantic.

This module defines the complete type system for soccer drills.
All drill definitions must conform to these schemas.
"""

from pydantic import BaseModel, Field, field_validator, model_validator
from typing import List, Optional, Literal, Union
from enum import Enum


# ============================================================
# ENUMS
# ============================================================

class FieldType(str, Enum):
    HALF = "HALF"
    FULL = "FULL"


class AttackingDirection(str, Enum):
    NORTH = "NORTH"  # Attacking toward top of diagram (y=100)
    SOUTH = "SOUTH"  # Attacking toward bottom of diagram (y=0)


class PlayerRole(str, Enum):
    ATTACKER = "ATTACKER"
    DEFENDER = "DEFENDER"
    GOALKEEPER = "GOALKEEPER"
    NEUTRAL = "NEUTRAL"


class GateOrientation(str, Enum):
    HORIZONTAL = "HORIZONTAL"
    VERTICAL = "VERTICAL"


# ============================================================
# CORE TYPES
# ============================================================

class Position(BaseModel):
    """
    Absolute position on the field using normalized 0-100 coordinates.
    
    Coordinate system:
    - x: 0 = left sideline, 100 = right sideline, 50 = center
    - y: 0 = bottom of diagram, 100 = top of diagram
    """
    x: float = Field(ge=0, le=100, description="X position (0=left, 100=right)")
    y: float = Field(ge=0, le=100, description="Y position (0=bottom, 100=top)")


class FieldConfig(BaseModel):
    """Soccer field configuration"""
    type: FieldType = Field(default=FieldType.HALF)
    attacking_direction: AttackingDirection = Field(default=AttackingDirection.NORTH)
    markings: bool = Field(default=True)
    goals: Literal[0, 1, 2] = Field(default=1)


# ============================================================
# ENTITIES
# ============================================================

class Player(BaseModel):
    """A player on the field"""
    id: str = Field(
        pattern=r"^[A-Z]+[0-9]*$",
        description="Player ID (e.g., A1, D2, GK)"
    )
    role: PlayerRole
    position: Position
    label: Optional[str] = Field(default=None, description="Optional display label")

    @field_validator('id')
    @classmethod
    def uppercase_id(cls, v):
        return v.upper()


class Cone(BaseModel):
    """A single training cone"""
    position: Position


class ConeGate(BaseModel):
    """A gate formed by two cones"""
    id: str = Field(pattern=r"^[A-Z]+[0-9]*$")
    center: Position
    width: float = Field(gt=0, le=30, description="Width of gate in units")
    orientation: GateOrientation

    @field_validator('id')
    @classmethod
    def uppercase_id(cls, v):
        return v.upper()


class Ball(BaseModel):
    """Ball position"""
    position: Position


class Mannequin(BaseModel):
    """A training mannequin/dummy for simulating defenders"""
    id: str = Field(pattern=r"^[A-Z]+[0-9]*$", description="Mannequin ID (e.g., M1, M2)")
    position: Position

    @field_validator('id')
    @classmethod
    def uppercase_id(cls, v):
        return v.upper()


# ============================================================
# ACTIONS
# ============================================================

class PassAction(BaseModel):
    """Ball pass from one player to another"""
    type: Literal["PASS"] = "PASS"
    from_player: str = Field(description="Player ID passing the ball")
    to_player: str = Field(description="Player ID receiving the ball")

    @field_validator('from_player', 'to_player')
    @classmethod
    def uppercase_players(cls, v):
        return v.upper()


class RunAction(BaseModel):
    """Player movement without the ball"""
    type: Literal["RUN"] = "RUN"
    player: str = Field(description="Player ID making the run")
    to_position: Position = Field(description="Destination position")

    @field_validator('player')
    @classmethod
    def uppercase_player(cls, v):
        return v.upper()


class DribbleAction(BaseModel):
    """Player dribbling with the ball"""
    type: Literal["DRIBBLE"] = "DRIBBLE"
    player: str = Field(description="Player ID dribbling")
    to_position: Position = Field(description="Destination position")
    through_gate: Optional[str] = Field(default=None, description="Cone gate ID if dribbling through one")

    @field_validator('player')
    @classmethod
    def uppercase_player(cls, v):
        return v.upper()

    @field_validator('through_gate')
    @classmethod
    def uppercase_gate(cls, v):
        return v.upper() if v else None


class ShotAction(BaseModel):
    """Shot on goal"""
    type: Literal["SHOT"] = "SHOT"
    player: str = Field(description="Player ID taking the shot")
    target: Literal["GOAL"] = "GOAL"

    @field_validator('player')
    @classmethod
    def uppercase_player(cls, v):
        return v.upper()


# Union type for all actions
Action = Union[PassAction, RunAction, DribbleAction, ShotAction]


# ============================================================
# COMPLETE DRILL
# ============================================================

class Drill(BaseModel):
    """
    Complete drill definition.
    
    This is the primary data structure that represents a soccer drill.
    It contains all information needed to render the diagram and
    provide coaching instructions.
    """
    name: str = Field(description="Name of the drill")
    description: str = Field(description="Brief description of drill purpose")
    
    # Field setup
    field: FieldConfig = Field(default_factory=FieldConfig)
    
    # Entities
    players: List[Player] = Field(min_length=1)
    cones: List[Cone] = Field(default_factory=list)
    cone_gates: List[ConeGate] = Field(default_factory=list)
    balls: List[Ball] = Field(default_factory=list)
    mannequins: List[Mannequin] = Field(default_factory=list)
    
    # Movement sequence
    actions: List[Action] = Field(default_factory=list)
    
    # Coaching information
    coaching_points: List[str] = Field(default_factory=list)
    variations: List[str] = Field(default_factory=list)
    
    @model_validator(mode='after')
    def validate_references(self):
        """Ensure all player/gate references in actions exist"""
        player_ids = {p.id for p in self.players}
        gate_ids = {g.id for g in self.cone_gates}
        
        for i, action in enumerate(self.actions):
            if isinstance(action, PassAction):
                if action.from_player not in player_ids:
                    raise ValueError(
                        f"Action {i+1}: from_player '{action.from_player}' not found in players"
                    )
                if action.to_player not in player_ids:
                    raise ValueError(
                        f"Action {i+1}: to_player '{action.to_player}' not found in players"
                    )
            
            elif isinstance(action, (RunAction, DribbleAction)):
                if action.player not in player_ids:
                    raise ValueError(
                        f"Action {i+1}: player '{action.player}' not found in players"
                    )
                if isinstance(action, DribbleAction) and action.through_gate:
                    if action.through_gate not in gate_ids:
                        raise ValueError(
                            f"Action {i+1}: through_gate '{action.through_gate}' not found in cone_gates"
                        )
            
            elif isinstance(action, ShotAction):
                if action.player not in player_ids:
                    raise ValueError(
                        f"Action {i+1}: player '{action.player}' not found in players"
                    )
        
        return self


# ============================================================
# COACH INPUT
# ============================================================

class CoachConstraints(BaseModel):
    """Constraints specified by the coach for drill generation"""
    num_players: int = Field(ge=2, le=22, description="Total number of players")
    num_attackers: Optional[int] = Field(default=None, ge=0)
    num_defenders: Optional[int] = Field(default=None, ge=0)
    has_goalkeeper: bool = Field(default=False)
    
    has_cones: bool = Field(default=True)
    num_cones: Optional[int] = Field(default=None, ge=0)
    
    field_size: FieldType = Field(default=FieldType.HALF)
    
    age_group: Optional[str] = Field(default=None, description="e.g., U10, U14, Adult")
    skill_level: Optional[Literal["beginner", "intermediate", "advanced"]] = None
    
    duration_minutes: Optional[int] = Field(default=None, ge=5, le=60)


class CoachRequest(BaseModel):
    """Complete request from a coach to generate a drill"""
    goal: str = Field(description="Primary goal (e.g., 'finishing under pressure')")
    secondary_goals: List[str] = Field(default_factory=list)
    constraints: CoachConstraints
    additional_notes: Optional[str] = None


# ============================================================
# REFERENCE POSITIONS
# ============================================================

def get_reference_positions(attacking_direction: AttackingDirection) -> dict:
    """
    Returns common reference positions for the LLM to use.
    
    These positions help the LLM place entities correctly without
    needing to calculate coordinates manually.
    """
    if attacking_direction == AttackingDirection.NORTH:
        return {
            "goal_line_center": {"x": 50, "y": 100},
            "penalty_spot": {"x": 50, "y": 88},
            "top_of_18_yard_box": {"x": 50, "y": 82},
            "top_of_6_yard_box": {"x": 50, "y": 94},
            "left_post": {"x": 44, "y": 100},
            "right_post": {"x": 56, "y": 100},
            "left_edge_18": {"x": 30, "y": 82},
            "right_edge_18": {"x": 70, "y": 82},
            "center_circle": {"x": 50, "y": 50},
            "halfway_line_center": {"x": 50, "y": 50},
            "own_goal": {"x": 50, "y": 0},
            "own_penalty_spot": {"x": 50, "y": 12},
        }
    else:  # SOUTH
        return {
            "goal_line_center": {"x": 50, "y": 0},
            "penalty_spot": {"x": 50, "y": 12},
            "top_of_18_yard_box": {"x": 50, "y": 18},
            "top_of_6_yard_box": {"x": 50, "y": 6},
            "left_post": {"x": 44, "y": 0},
            "right_post": {"x": 56, "y": 0},
            "left_edge_18": {"x": 30, "y": 18},
            "right_edge_18": {"x": 70, "y": 18},
            "center_circle": {"x": 50, "y": 50},
            "halfway_line_center": {"x": 50, "y": 50},
            "own_goal": {"x": 50, "y": 100},
            "own_penalty_spot": {"x": 50, "y": 88},
        }
