"""
Drill Validation - Structural and semantic validation for drills.

This module provides:
1. Structural validation (positions, spacing, references)
2. Semantic validation (drill matches stated goal)
3. Ball possession tracking
"""

import math
from typing import List, Optional
from dataclasses import dataclass, field

from schema import (
    Drill, Player, Position, Action,
    PassAction, RunAction, DribbleAction, ShotAction,
    AttackingDirection, PlayerRole
)


# ============================================================
# UTILITIES
# ============================================================

def distance(p1: Position, p2: Position) -> float:
    """Euclidean distance between two positions"""
    return math.sqrt((p1.x - p2.x)**2 + (p1.y - p2.y)**2)


def is_in_penalty_box(pos: Position, attacking_dir: AttackingDirection) -> bool:
    """Check if position is inside the 18-yard box"""
    if attacking_dir == AttackingDirection.NORTH:
        return 30 <= pos.x <= 70 and pos.y >= 82
    else:
        return 30 <= pos.x <= 70 and pos.y <= 18


def is_in_six_yard_box(pos: Position, attacking_dir: AttackingDirection) -> bool:
    """Check if position is inside the 6-yard box"""
    if attacking_dir == AttackingDirection.NORTH:
        return 42 <= pos.x <= 58 and pos.y >= 94
    else:
        return 42 <= pos.x <= 58 and pos.y <= 6


def get_goal_center(attacking_dir: AttackingDirection) -> Position:
    """Get the center of the attacking goal"""
    y = 100 if attacking_dir == AttackingDirection.NORTH else 0
    return Position(x=50, y=y)


# ============================================================
# VALIDATION RESULT
# ============================================================

@dataclass
class ValidationIssue:
    """A single validation issue"""
    message: str
    severity: str = "error"  # "error", "warning", "info"
    
    @property
    def is_error(self) -> bool:
        return self.severity == "error"


@dataclass
class ValidationResult:
    """Complete validation result"""
    issues: List[ValidationIssue] = field(default_factory=list)
    
    @property
    def is_valid(self) -> bool:
        """True if no errors (warnings are OK)"""
        return not any(issue.is_error for issue in self.issues)
    
    @property
    def errors(self) -> List[ValidationIssue]:
        return [i for i in self.issues if i.severity == "error"]
    
    @property
    def warnings(self) -> List[ValidationIssue]:
        return [i for i in self.issues if i.severity == "warning"]
    
    def add(self, message: str, severity: str = "error"):
        self.issues.append(ValidationIssue(message, severity))
    
    def add_error(self, message: str):
        self.add(message, "error")
    
    def add_warning(self, message: str):
        self.add(message, "warning")
    
    def add_info(self, message: str):
        self.add(message, "info")


# ============================================================
# STRUCTURAL VALIDATOR
# ============================================================

class StructuralValidator:
    """
    Validates the structural correctness of a drill.
    
    Checks:
    - All positions are within bounds
    - Players have reasonable spacing
    - All action references are valid
    - Goalkeeper is positioned correctly
    """
    
    MIN_PLAYER_SPACING = 3  # Minimum units between players
    
    def __init__(self, drill: Drill):
        self.drill = drill
        self.players_by_id = {p.id: p for p in drill.players}
    
    def validate(self) -> ValidationResult:
        """Run all structural validations"""
        result = ValidationResult()
        
        self._check_positions(result)
        self._check_spacing(result)
        self._check_goalkeeper(result)
        self._check_ball_placement(result)
        
        return result
    
    def _check_positions(self, result: ValidationResult):
        """Verify all positions are within field bounds"""
        for player in self.drill.players:
            if not (0 <= player.position.x <= 100 and 0 <= player.position.y <= 100):
                result.add_error(
                    f"Player {player.id} is out of bounds: ({player.position.x}, {player.position.y})"
                )
        
        for i, cone in enumerate(self.drill.cones):
            if not (0 <= cone.position.x <= 100 and 0 <= cone.position.y <= 100):
                result.add_error(
                    f"Cone {i+1} is out of bounds: ({cone.position.x}, {cone.position.y})"
                )
    
    def _check_spacing(self, result: ValidationResult):
        """Verify players have reasonable spacing"""
        players = self.drill.players
        for i, p1 in enumerate(players):
            for p2 in players[i+1:]:
                dist = distance(p1.position, p2.position)
                if dist < self.MIN_PLAYER_SPACING:
                    result.add_warning(
                        f"Players {p1.id} and {p2.id} are very close ({dist:.1f} units)"
                    )
    
    def _check_goalkeeper(self, result: ValidationResult):
        """Verify goalkeeper is positioned near goal"""
        gk = next(
            (p for p in self.drill.players if p.role == PlayerRole.GOALKEEPER),
            None
        )
        if not gk:
            return
        
        goal_y = 100 if self.drill.field.attacking_direction == AttackingDirection.NORTH else 0
        y_dist = abs(gk.position.y - goal_y)
        
        if y_dist > 15:
            result.add_warning(
                f"Goalkeeper {gk.id} is far from goal line ({y_dist:.1f} units)"
            )
    
    def _check_ball_placement(self, result: ValidationResult):
        """Verify ball is placed with a player"""
        if not self.drill.balls:
            if self.drill.actions:
                result.add_warning("Drill has actions but no ball defined")
            return
        
        ball_pos = self.drill.balls[0].position
        min_dist = min(
            distance(ball_pos, p.position) for p in self.drill.players
        )
        
        if min_dist > 5:
            result.add_warning(
                f"Ball is {min_dist:.1f} units from nearest player (should be < 5)"
            )


# ============================================================
# BALL POSSESSION TRACKER
# ============================================================

class BallTracker:
    """
    Tracks ball possession through the action sequence.
    
    This helps validate that:
    - Only the ball holder can pass/dribble/shoot
    - Passes correctly transfer possession
    """
    
    def __init__(self, drill: Drill):
        self.drill = drill
        self.players_by_id = {p.id: p for p in drill.players}
        self.holder: Optional[str] = None
        self._find_initial_holder()
    
    def _find_initial_holder(self):
        """Find which player starts with the ball"""
        if not self.drill.balls:
            return
        
        ball_pos = self.drill.balls[0].position
        min_dist = float('inf')
        
        for player in self.drill.players:
            d = distance(ball_pos, player.position)
            if d < min_dist:
                min_dist = d
                self.holder = player.id
    
    def validate_actions(self) -> ValidationResult:
        """Validate ball possession through all actions"""
        result = ValidationResult()
        
        for i, action in enumerate(self.drill.actions):
            action_num = i + 1
            
            if isinstance(action, PassAction):
                if self.holder and self.holder != action.from_player:
                    result.add_warning(
                        f"Action {action_num}: {action.from_player} passes but "
                        f"{self.holder} has the ball"
                    )
                self.holder = action.to_player
            
            elif isinstance(action, DribbleAction):
                if self.holder and self.holder != action.player:
                    result.add_warning(
                        f"Action {action_num}: {action.player} dribbles but "
                        f"{self.holder} has the ball"
                    )
                # Player still has ball after dribble
            
            elif isinstance(action, ShotAction):
                if self.holder and self.holder != action.player:
                    result.add_warning(
                        f"Action {action_num}: {action.player} shoots but "
                        f"{self.holder} has the ball"
                    )
                self.holder = None  # Ball is shot
            
            # RUN doesn't affect ball possession
        
        return result


# ============================================================
# SEMANTIC VALIDATOR
# ============================================================

class SemanticValidator:
    """
    Validates that a drill matches its stated goal.
    
    For example, a "finishing drill" should have:
    - At least one SHOT action
    - Shooter positioned to score
    - Ball reaching the shooter
    """
    
    def __init__(self, drill: Drill):
        self.drill = drill
        self.players_by_id = {p.id: p for p in drill.players}
    
    def validate_goal(self, goal: str) -> ValidationResult:
        """
        Validate drill against a stated goal.
        
        Automatically detects goal type and runs appropriate checks.
        """
        result = ValidationResult()
        goal_lower = goal.lower()
        
        if any(word in goal_lower for word in ["finish", "shoot", "scoring", "strike"]):
            self._validate_finishing(result)
        
        if any(word in goal_lower for word in ["pass", "passing", "combination", "one-two"]):
            self._validate_passing(result)
        
        if any(word in goal_lower for word in ["dribbl", "1v1", "take on", "beat"]):
            self._validate_dribbling(result)
        
        if any(word in goal_lower for word in ["cross", "crossing", "wide play"]):
            self._validate_crossing(result)
        
        if any(word in goal_lower for word in ["defend", "pressure", "pressing"]):
            self._validate_defending(result)
        
        return result
    
    def _validate_finishing(self, result: ValidationResult):
        """Validate finishing drill requirements"""
        shots = [a for a in self.drill.actions if isinstance(a, ShotAction)]
        
        if not shots:
            result.add_error("Finishing drill has no SHOT action")
            return
        
        attacking_dir = self.drill.field.attacking_direction
        
        for shot in shots:
            player = self.players_by_id.get(shot.player)
            if player:
                in_box = is_in_penalty_box(player.position, attacking_dir)
                if not in_box:
                    result.add_warning(
                        f"Shooter {shot.player} starts outside penalty box"
                    )
    
    def _validate_passing(self, result: ValidationResult):
        """Validate passing drill requirements"""
        passes = [a for a in self.drill.actions if isinstance(a, PassAction)]
        
        if len(passes) < 2:
            result.add_warning("Passing drill has fewer than 2 PASS actions")
        
        # Check pass distances
        for i, pass_action in enumerate(passes):
            from_player = self.players_by_id.get(pass_action.from_player)
            to_player = self.players_by_id.get(pass_action.to_player)
            
            if from_player and to_player:
                dist = distance(from_player.position, to_player.position)
                if dist > 50:
                    result.add_warning(
                        f"Pass {i+1} is very long ({dist:.1f} units)"
                    )
    
    def _validate_dribbling(self, result: ValidationResult):
        """Validate dribbling drill requirements"""
        dribbles = [a for a in self.drill.actions if isinstance(a, DribbleAction)]
        
        if not dribbles:
            result.add_warning("Dribbling drill has no DRIBBLE action")
    
    def _validate_crossing(self, result: ValidationResult):
        """Validate crossing drill requirements"""
        # Check for wide positions
        wide_players = [
            p for p in self.drill.players
            if p.position.x < 25 or p.position.x > 75
        ]
        
        if not wide_players:
            result.add_warning("Crossing drill has no wide players")
    
    def _validate_defending(self, result: ValidationResult):
        """Validate defending drill requirements"""
        defenders = [
            p for p in self.drill.players
            if p.role == PlayerRole.DEFENDER
        ]
        
        if not defenders:
            result.add_warning("Defending drill has no defenders")


# ============================================================
# COMBINED VALIDATOR
# ============================================================

def validate_drill(drill: Drill, goal: Optional[str] = None) -> ValidationResult:
    """
    Run all validations on a drill.
    
    Args:
        drill: The drill to validate
        goal: Optional goal string for semantic validation
    
    Returns:
        Combined ValidationResult
    """
    combined = ValidationResult()
    
    # Structural validation
    structural = StructuralValidator(drill).validate()
    combined.issues.extend(structural.issues)
    
    # Ball possession validation
    ball = BallTracker(drill).validate_actions()
    combined.issues.extend(ball.issues)
    
    # Semantic validation (if goal provided)
    if goal:
        semantic = SemanticValidator(drill).validate_goal(goal)
        combined.issues.extend(semantic.issues)
    
    return combined
