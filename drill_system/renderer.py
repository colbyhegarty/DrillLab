"""
Drill Renderer - Generates SVG diagrams from drill definitions.

This module renders:
- Soccer field with markings
- Players with role-based colors
- Cones and cone gates
- Balls
- Action arrows (pass, run, dribble, shot)

IMPORTANT: Actions are chained - each action starts from where the 
previous action ended, not from the player's starting position.
"""

import matplotlib
matplotlib.use('Agg')  # Non-interactive backend

import matplotlib.pyplot as plt
import matplotlib.patches as patches
import numpy as np
from pathlib import Path
from typing import Optional, Dict, Tuple

from schema import (
    Drill, Player, Position, FieldType, Mannequin,
    PassAction, RunAction, DribbleAction, ShotAction,
    AttackingDirection, PlayerRole, GateOrientation
)


# ============================================================
# STYLING
# ============================================================

ROLE_COLORS = {
    PlayerRole.ATTACKER: "#e63946",     # Red
    PlayerRole.DEFENDER: "#457b9d",     # Blue
    PlayerRole.GOALKEEPER: "#f1fa3c",   # Yellow
    PlayerRole.NEUTRAL: "#f4a261",      # Orange
}

GRASS_LIGHT = "#6fbf4a"
GRASS_DARK = "#63b043"
LINE_COLOR = "white"
CONE_COLOR = "#f4a261"
MANNEQUIN_COLOR = "#2d3436"  # Dark gray for mannequins


# ============================================================
# FIELD RENDERER
# ============================================================

class FieldRenderer:
    """Renders the soccer field"""
    
    def __init__(self, ax, drill: Drill, padding: float = 8.0):
        self.ax = ax
        self.drill = drill
        self.field = drill.field
        self.padding = padding
        self.attacking_goal_y = 100 if self.field.attacking_direction == AttackingDirection.NORTH else 0
        
        # Calculate content bounds
        self._calculate_bounds()
    
    def _calculate_bounds(self):
        """Calculate the bounding box of all drill content"""
        x_coords = []
        y_coords = []
        
        # Collect all entity positions
        for player in self.drill.players:
            x_coords.append(player.position.x)
            y_coords.append(player.position.y)
        
        for cone in self.drill.cones:
            x_coords.append(cone.position.x)
            y_coords.append(cone.position.y)
        
        for gate in self.drill.cone_gates:
            x_coords.append(gate.center.x - gate.width/2)
            x_coords.append(gate.center.x + gate.width/2)
            y_coords.append(gate.center.y)
        
        for ball in self.drill.balls:
            x_coords.append(ball.position.x)
            y_coords.append(ball.position.y)
        
        for mannequin in self.drill.mannequins:
            x_coords.append(mannequin.position.x)
            y_coords.append(mannequin.position.y)
        
        # Collect action endpoints
        for action in self.drill.actions:
            action_type = getattr(action, 'type', None)
            if action_type in ["RUN", "DRIBBLE"]:
                x_coords.append(action.to_position.x)
                y_coords.append(action.to_position.y)
            elif action_type == "SHOT":
                # Shot goes to goal - include goal position
                y_coords.append(self.attacking_goal_y)
                x_coords.append(50)  # Goal center
        
        # Default bounds if no content
        if not x_coords:
            x_coords = [25, 75]
        if not y_coords:
            y_coords = [25, 75]
        
        # Calculate raw bounds
        self.content_x_min = min(x_coords)
        self.content_x_max = max(x_coords)
        self.content_y_min = min(y_coords)
        self.content_y_max = max(y_coords)
        
        # Apply padding
        self.x_min = max(0, self.content_x_min - self.padding)
        self.x_max = min(100, self.content_x_max + self.padding)
        self.y_min = max(0, self.content_y_min - self.padding)
        self.y_max = min(100, self.content_y_max + self.padding)
        
        # Handle goals - expand to show goal areas if needed
        if self.field.goals > 0:
            # Check if content is near the attacking goal (NORTH = 100, SOUTH = 0)
            if self.field.attacking_direction == AttackingDirection.NORTH:
                if self.content_y_max > 70:  # Content is near top goal
                    self.y_max = 100
                    # Only expand y_min to show 18-yard box if not already showing more
                    if self.y_min > 78:
                        self.y_min = 78
            else:  # SOUTH
                if self.content_y_min < 30:  # Content is near bottom goal
                    self.y_min = 0
                    if self.y_max < 22:
                        self.y_max = 22
        
        # Handle second goal for 2-goal drills (small-sided games)
        if self.field.goals > 1:
            other_goal_y = 0 if self.attacking_goal_y == 100 else 100
            
            # Check if content extends toward the other goal
            if other_goal_y == 0 and self.content_y_min < 30:
                self.y_min = 0
                # Ensure we show the 18-yard box area
                if self.content_y_min < 22:
                    pass  # Already showing goal area
            elif other_goal_y == 100 and self.content_y_max > 70:
                self.y_max = 100
            
            # For small-sided games with 2 goals, check if there are goalkeepers
            # and expand to show both goal areas
            has_gk_top = any(p.position.y > 90 for p in self.drill.players if p.role.value == "GOALKEEPER")
            has_gk_bottom = any(p.position.y < 10 for p in self.drill.players if p.role.value == "GOALKEEPER")
            
            if has_gk_top:
                self.y_max = 100
            if has_gk_bottom:
                self.y_min = 0
        
        # Ensure minimum view size (at least 30x30)
        min_size = 30
        x_size = self.x_max - self.x_min
        y_size = self.y_max - self.y_min
        
        if x_size < min_size:
            center_x = (self.x_min + self.x_max) / 2
            self.x_min = max(0, center_x - min_size/2)
            self.x_max = min(100, center_x + min_size/2)
        
        if y_size < min_size:
            center_y = (self.y_min + self.y_max) / 2
            self.y_min = max(0, center_y - min_size/2)
            self.y_max = min(100, center_y + min_size/2)
    
    def draw(self):
        """Draw the complete field"""
        self.ax.set_xlim(self.x_min, self.x_max)
        self.ax.set_ylim(self.y_min, self.y_max)
        
        self._draw_grass()
        self._draw_outline()
        
        if self.field.markings:
            # Draw halfway line if it's visible
            if self.y_min <= 50 <= self.y_max:
                self._draw_halfway_line()
            
            # Draw center circle if visible (full field and center is in view)
            if self.field.type == FieldType.FULL:
                if self.y_min <= 50 <= self.y_max and self.x_min <= 50 <= self.x_max:
                    self._draw_center_circle()
            
            # Draw goal areas with markings (18-yard box, etc.) at actual goal lines
            if self.field.goals >= 1:
                # Top goal (y=100) - draw if visible
                if self.y_max >= 85:
                    self._draw_goal_area(100)
                
                # Bottom goal (y=0) - draw if visible and we have 2 goals
                if self.field.goals >= 2 and self.y_min <= 15:
                    self._draw_goal_area(0)
        
        elif self.field.goals > 0:
            # No markings but has goals = small-sided game
            # Draw goals at the FIELD BOUNDARIES (content bounds), not at y=0/100
            
            # Top goal at the top boundary of the content
            if self.field.goals >= 1:
                # Use content_y_max (where cones/players are) as the goal line
                top_goal_y = self.content_y_max
                self._draw_field_goal(top_goal_y, goal_width=8)
            
            # Bottom goal at the bottom boundary
            if self.field.goals >= 2:
                bottom_goal_y = self.content_y_min
                self._draw_field_goal(bottom_goal_y, goal_width=8)
        
        self.ax.set_aspect("equal")
        self.ax.axis("off")
    
    def _draw_grass(self):
        """Draw striped grass covering the visible area"""
        stripe_width = 10
        # Start from the beginning of the stripe that contains x_min
        start_x = int(self.x_min // stripe_width) * stripe_width
        # End at the stripe that contains x_max
        end_x = int(self.x_max // stripe_width + 1) * stripe_width + stripe_width
        
        for i in range(start_x, end_x, stripe_width):
            color = GRASS_LIGHT if (i // stripe_width) % 2 == 0 else GRASS_DARK
            self.ax.add_patch(patches.Rectangle(
                (i, self.y_min - 5), stripe_width, (self.y_max - self.y_min) + 10, 
                color=color, zorder=0
            ))
    
    def _draw_outline(self):
        """Draw field outline for the visible area"""
        # Draw a subtle border around the view area
        self.ax.plot(
            [self.x_min, self.x_max, self.x_max, self.x_min, self.x_min], 
            [self.y_min, self.y_min, self.y_max, self.y_max, self.y_min], 
            color=LINE_COLOR, lw=1.5, alpha=0.5, zorder=1
        )
    
    def _draw_halfway_line(self):
        """Draw halfway line within visible area"""
        self.ax.plot([self.x_min, self.x_max], [50, 50], color=LINE_COLOR, lw=1.5, zorder=1)
    
    def _draw_center_circle(self):
        """Draw center circle"""
        self.ax.add_patch(patches.Circle(
            (50, 50), 10, fill=False, edgecolor=LINE_COLOR, lw=1.5, zorder=1
        ))
        self.ax.scatter(50, 50, s=20, c=LINE_COLOR, zorder=2)
    
    def _draw_goal_area(self, goal_y: float):
        """Draw penalty box, 6-yard box, and goal at the actual goal line (y=0 or y=100)"""
        into = -1 if goal_y == 100 else 1
        
        pen_y = goal_y + into * 18
        six_y = goal_y + into * 6
        pen_spot_y = goal_y + into * 12
        
        # 18-yard box
        self.ax.plot([30, 70], [pen_y, pen_y], color=LINE_COLOR, lw=1.5, zorder=1)
        self.ax.plot([30, 30], [pen_y, goal_y], color=LINE_COLOR, lw=1.5, zorder=1)
        self.ax.plot([70, 70], [pen_y, goal_y], color=LINE_COLOR, lw=1.5, zorder=1)
        
        # 6-yard box
        self.ax.plot([42, 58], [six_y, six_y], color=LINE_COLOR, lw=1.5, zorder=1)
        self.ax.plot([42, 42], [six_y, goal_y], color=LINE_COLOR, lw=1.5, zorder=1)
        self.ax.plot([58, 58], [six_y, goal_y], color=LINE_COLOR, lw=1.5, zorder=1)
        
        # Penalty spot
        self.ax.scatter(50, pen_spot_y, s=30, c=LINE_COLOR, zorder=2)
        
        # Goal with net
        self._draw_goal_with_net(50, goal_y, width=8)
    
    def _draw_goal_with_net(self, cx: float, goal_line_y: float, width: float = 8):
        """
        Draw a goal with posts, crossbar, and net.
        The gray back line sits ON goal_line_y, net extends INTO the field.
        
        Args:
            cx: Center x position of goal
            goal_line_y: Y position where the goal line is (gray back line sits here)
            width: Width of goal
        """
        goal_color = "white"
        post_width = 3.0
        goal_depth = 3  # How far the net extends into the field
        
        # Net extends INTO the field (toward center)
        # If goal_line is at top (high y), net goes DOWN (negative)
        # If goal_line is at bottom (low y), net goes UP (positive)
        net_direction = -1 if goal_line_y >= 50 else 1
        
        # Crossbar position (front of goal, inside the field)
        crossbar_y = goal_line_y + net_direction * goal_depth
        
        # Posts (vertical lines from crossbar back to goal line)
        self.ax.plot([cx - width/2, cx - width/2], [crossbar_y, goal_line_y], 
                    color=goal_color, lw=post_width, solid_capstyle='round', zorder=6)
        self.ax.plot([cx + width/2, cx + width/2], [crossbar_y, goal_line_y], 
                    color=goal_color, lw=post_width, solid_capstyle='round', zorder=6)
        
        # Crossbar (front of goal, inside field)
        self.ax.plot([cx - width/2, cx + width/2], [crossbar_y, crossbar_y], 
                    color=goal_color, lw=post_width, solid_capstyle='round', zorder=6)
        
        # Back of net (ON the goal line)
        self.ax.plot([cx - width/2, cx + width/2], [goal_line_y, goal_line_y], 
                    color='gray', lw=1.5, alpha=0.6, zorder=5)
        
        # Net lines (vertical strings)
        num_strings = int(width) + 1
        for i in range(num_strings):
            net_x = cx - width/2 + i * (width / (num_strings - 1)) if num_strings > 1 else cx
            self.ax.plot([net_x, net_x], [crossbar_y, goal_line_y],
                        color='gray', lw=0.5, alpha=0.4, zorder=5)
    
    def _draw_field_goal(self, goal_line_y: float, goal_width: float = 8):
        """
        Draw just a goal (no markings) at a specific y position.
        Used for small-sided games where goals are at the field boundary.
        """
        self._draw_goal_with_net(50, goal_line_y, width=goal_width)


# ============================================================
# ENTITY RENDERER
# ============================================================

class EntityRenderer:
    """Renders players, cones, and balls"""
    
    def __init__(self, ax):
        self.ax = ax
    
    def draw_player(self, player: Player):
        """Draw a player marker"""
        color = ROLE_COLORS.get(player.role, ROLE_COLORS[PlayerRole.NEUTRAL])
        
        self.ax.scatter(
            player.position.x, player.position.y,
            s=150, c=color, edgecolors="white",
            linewidths=1.5, zorder=10
        )
        
        # Draw player label
        self.ax.annotate(
            player.id,
            (player.position.x, player.position.y),
            textcoords="offset points",
            xytext=(0, -16),
            ha='center',
            fontsize=7,
            fontweight='bold',
            color='white',
            zorder=11
        )
    
    def draw_cone(self, x: float, y: float):
        """Draw a cone marker"""
        self.ax.scatter(
            x, y, s=80, marker="^",
            c=CONE_COLOR, edgecolors="black",
            linewidths=0.8, zorder=4
        )
    
    def draw_ball(self, x: float, y: float):
        """Draw a realistic soccer ball"""
        # White base circle
        self.ax.scatter(
            x, y, s=120, c="white",
            edgecolors="black", linewidths=1.5,
            zorder=12
        )
        # Add black pentagon pattern in center
        self.ax.scatter(
            x, y, s=35, c="black",
            marker='p',  # pentagon marker
            zorder=13
        )
    
    def draw_mannequin(self, mannequin: Mannequin):
        """Draw a training mannequin/dummy"""
        x, y = mannequin.position.x, mannequin.position.y
        
        # Draw mannequin body (elongated shape like a silhouette)
        # Base/stand
        self.ax.scatter(
            x, y, s=100, c=MANNEQUIN_COLOR,
            edgecolors="black", linewidths=1,
            marker='o', zorder=8
        )
        # Upper body/torso (taller rectangle-ish shape)
        body_height = 2.5
        self.ax.plot(
            [x, x], [y, y + body_height],
            color=MANNEQUIN_COLOR, lw=4,
            solid_capstyle='round', zorder=8
        )
        # Head
        self.ax.scatter(
            x, y + body_height + 0.8, s=60,
            c=MANNEQUIN_COLOR, edgecolors="black",
            linewidths=0.8, zorder=8
        )
        
        # Draw mannequin label
        self.ax.annotate(
            mannequin.id,
            (x, y),
            textcoords="offset points",
            xytext=(0, -14),
            ha='center',
            fontsize=6,
            fontweight='bold',
            color='white',
            zorder=9
        )


# ============================================================
# ACTION RENDERER
# ============================================================

class ActionRenderer:
    """Renders movement arrows with consistent styling"""
    
    # Consistent styling across all action types - SMALLER arrows
    LINE_WIDTH = 1.8
    ARROW_HEAD_WIDTH = 1.2  # Reduced from 1.8
    ARROW_HEAD_LENGTH = 1.0  # Reduced from 1.5
    
    # Offset from player circles (larger to clear the circle)
    PLAYER_OFFSET = 2.5
    # Offset between chained actions (smaller, just a small gap)
    ACTION_GAP = 0.8
    
    def __init__(self, ax, goal_y: float):
        self.ax = ax
        self.goal_y = goal_y
    
    def _get_offset_points(self, x1: float, y1: float, x2: float, y2: float, 
                           start_is_player: bool = True, end_is_player: bool = True) -> tuple:
        """
        Calculate offset start and end points.
        
        Args:
            start_is_player: If True, use larger offset (clearing player circle)
            end_is_player: If True, use larger offset (clearing player circle)
        
        Returns (start_x, start_y, end_x, end_y) with offsets applied.
        """
        dx = x2 - x1
        dy = y2 - y1
        dist = np.sqrt(dx**2 + dy**2)
        
        if dist == 0:
            return x1, y1, x2, y2
        
        # Unit vector in direction of movement
        ux = dx / dist
        uy = dy / dist
        
        # Choose offset based on whether connecting to player or another action
        start_offset = self.PLAYER_OFFSET if start_is_player else self.ACTION_GAP
        end_offset = self.PLAYER_OFFSET if end_is_player else self.ACTION_GAP
        
        # Offset start point forward, end point backward
        start_x = x1 + ux * start_offset
        start_y = y1 + uy * start_offset
        end_x = x2 - ux * end_offset
        end_y = y2 - uy * end_offset
        
        return start_x, start_y, end_x, end_y
    
    def draw_pass(self, x1: float, y1: float, x2: float, y2: float,
                  start_is_player: bool = True, end_is_player: bool = True):
        """Draw a solid arrow for passes"""
        start_x, start_y, end_x, end_y = self._get_offset_points(
            x1, y1, x2, y2, start_is_player, end_is_player
        )
        dx = end_x - start_x
        dy = end_y - start_y
        dist = np.sqrt(dx**2 + dy**2)
        
        if dist == 0:
            return
        
        # Draw line (stop before arrowhead)
        arrow_length = self.ARROW_HEAD_LENGTH
        line_end_ratio = (dist - arrow_length) / dist
        
        t = np.linspace(0, line_end_ratio, 50)
        x_line = start_x + dx * t
        y_line = start_y + dy * t
        
        self.ax.plot(
            x_line, y_line,
            color='white', lw=self.LINE_WIDTH, zorder=4,
            solid_capstyle='round'
        )
        
        # Arrowhead at the end
        self.ax.arrow(
            start_x + dx * line_end_ratio, start_y + dy * line_end_ratio,
            dx * (1 - line_end_ratio), dy * (1 - line_end_ratio),
            head_width=self.ARROW_HEAD_WIDTH,
            head_length=self.ARROW_HEAD_LENGTH,
            fc="white", ec="white", lw=0,
            length_includes_head=True, zorder=5
        )
    
    def draw_run(self, x1: float, y1: float, x2: float, y2: float,
                 start_is_player: bool = True, end_is_player: bool = True):
        """Draw a dashed arrow for runs"""
        start_x, start_y, end_x, end_y = self._get_offset_points(
            x1, y1, x2, y2, start_is_player, end_is_player
        )
        dx = end_x - start_x
        dy = end_y - start_y
        dist = np.sqrt(dx**2 + dy**2)
        
        if dist == 0:
            return
        
        # Dashed line (stop before arrowhead)
        arrow_length = self.ARROW_HEAD_LENGTH
        line_end_ratio = (dist - arrow_length) / dist
        
        t = np.linspace(0, line_end_ratio, 50)
        x_line = start_x + dx * t
        y_line = start_y + dy * t
        
        self.ax.plot(
            x_line, y_line, '--',
            color='white', lw=self.LINE_WIDTH, zorder=4,
            dashes=(5, 3)
        )
        
        # Arrowhead at the end
        self.ax.arrow(
            start_x + dx * line_end_ratio, start_y + dy * line_end_ratio,
            dx * (1 - line_end_ratio), dy * (1 - line_end_ratio),
            head_width=self.ARROW_HEAD_WIDTH,
            head_length=self.ARROW_HEAD_LENGTH,
            fc="white", ec="white", lw=0,
            length_includes_head=True, zorder=5
        )
    
    def draw_dribble(self, x1: float, y1: float, x2: float, y2: float,
                     start_is_player: bool = True, end_is_player: bool = True):
        """Draw a wavy line for dribbling"""
        start_x, start_y, end_x, end_y = self._get_offset_points(
            x1, y1, x2, y2, start_is_player, end_is_player
        )
        dx = end_x - start_x
        dy = end_y - start_y
        dist = np.sqrt(dx**2 + dy**2)
        
        if dist == 0:
            return
        
        # Calculate where the wavy line should stop (before the arrowhead)
        arrow_length = self.ARROW_HEAD_LENGTH
        line_end_ratio = (dist - arrow_length) / dist
        
        # Wavy path (only up to where arrow starts)
        t = np.linspace(0, line_end_ratio, 80)
        x_base = start_x + dx * t
        y_base = start_y + dy * t
        
        # Perpendicular direction
        perp_x = -dy / dist
        perp_y = dx / dist
        
        # Wave with reduced amplitude (was 1.5, now 1.0)
        wave = np.sin(t / line_end_ratio * 4 * np.pi) * 1.0
        x = x_base + perp_x * wave
        y = y_base + perp_y * wave
        
        self.ax.plot(x, y, lw=self.LINE_WIDTH, color="white", zorder=4)
        
        # Arrowhead starting from where line ends
        arrow_start_x = start_x + dx * line_end_ratio
        arrow_start_y = start_y + dy * line_end_ratio
        
        self.ax.arrow(
            arrow_start_x, arrow_start_y,
            end_x - arrow_start_x, end_y - arrow_start_y,
            head_width=self.ARROW_HEAD_WIDTH,
            head_length=self.ARROW_HEAD_LENGTH,
            fc="white", ec="white", lw=0,
            length_includes_head=True, zorder=5
        )
    
    def draw_shot(self, x1: float, y1: float, start_is_player: bool = True):
        """Draw a shot arrow toward goal"""
        goal_x = 50
        goal_y = self.goal_y
        
        dx = goal_x - x1
        dy = goal_y - y1
        dist = np.sqrt(dx**2 + dy**2)
        
        if dist == 0:
            return
        
        # Offset the start point
        ux = dx / dist
        uy = dy / dist
        start_offset = self.PLAYER_OFFSET if start_is_player else self.ACTION_GAP
        start_x = x1 + ux * start_offset
        start_y = y1 + uy * start_offset
        
        # Recalculate for the offset start
        dx = goal_x - start_x
        dy = goal_y - start_y
        dist = np.sqrt(dx**2 + dy**2)
        
        if dist == 0:
            return
        
        # Draw line (stop before arrowhead)
        arrow_length = self.ARROW_HEAD_LENGTH
        line_end_ratio = (dist - arrow_length) / dist
        
        t = np.linspace(0, line_end_ratio, 50)
        x_line = start_x + dx * t
        y_line = start_y + dy * t
        
        self.ax.plot(
            x_line, y_line,
            color='red', lw=self.LINE_WIDTH, zorder=4,
            solid_capstyle='round'
        )
        
        # Arrowhead at the end
        self.ax.arrow(
            start_x + dx * line_end_ratio, start_y + dy * line_end_ratio,
            dx * (1 - line_end_ratio), dy * (1 - line_end_ratio),
            head_width=self.ARROW_HEAD_WIDTH,
            head_length=self.ARROW_HEAD_LENGTH,
            fc="red", ec="red", lw=0,
            length_includes_head=True, zorder=5
        )


# ============================================================
# POSITION TRACKER
# ============================================================

class PositionTracker:
    """
    Tracks the current position of each player and the ball.
    
    This is crucial for action chaining - when a player dribbles
    then passes, the pass should start from where the dribble ended,
    not from the player's original position.
    
    Also tracks whether each player has moved from their starting position,
    which determines the offset type for action lines.
    """
    
    def __init__(self, drill: Drill):
        self.drill = drill
        
        # Track current position of each player (changes with RUN, DRIBBLE)
        self.player_positions: Dict[str, Tuple[float, float]] = {}
        # Track whether player has moved from starting position
        self.player_has_moved: Dict[str, bool] = {}
        
        for player in drill.players:
            self.player_positions[player.id] = (player.position.x, player.position.y)
            self.player_has_moved[player.id] = False
        
        # Track current ball position and holder
        self.ball_position: Optional[Tuple[float, float]] = None
        self.ball_holder: Optional[str] = None
        
        # Determine ball holder from the FIRST action (most reliable method)
        # If first action is PASS or DRIBBLE, that player has the ball
        if drill.actions:
            first_action = drill.actions[0]
            action_type = getattr(first_action, 'type', None)
            
            if action_type == "PASS":
                self.ball_holder = first_action.from_player
            elif action_type in ["DRIBBLE", "SHOT"]:
                self.ball_holder = first_action.player
        
        # Fallback: if no actions, find player closest to ball position
        if not self.ball_holder and drill.balls:
            ball = drill.balls[0]
            min_dist = float('inf')
            for player in drill.players:
                dx = player.position.x - ball.position.x
                dy = player.position.y - ball.position.y
                dist = np.sqrt(dx**2 + dy**2)
                if dist < min_dist:
                    min_dist = dist
                    self.ball_holder = player.id
        
        # Set ball position at the holder's position
        if self.ball_holder and self.ball_holder in self.player_positions:
            self.ball_position = self.player_positions[self.ball_holder]
        elif drill.balls:
            self.ball_position = (drill.balls[0].position.x, drill.balls[0].position.y)
    
    def get_player_position(self, player_id: str) -> Tuple[float, float]:
        """Get the current position of a player"""
        return self.player_positions.get(player_id, (0, 0))
    
    def is_at_starting_position(self, player_id: str) -> bool:
        """Check if player is still at their starting position"""
        return not self.player_has_moved.get(player_id, False)
    
    def get_ball_position(self) -> Tuple[float, float]:
        """Get the current ball position"""
        if self.ball_holder:
            return self.player_positions[self.ball_holder]
        return self.ball_position or (50, 50)
    
    def update_player_position(self, player_id: str, x: float, y: float):
        """Update a player's position after movement"""
        self.player_positions[player_id] = (x, y)
        self.player_has_moved[player_id] = True
        
        # If this player has the ball, ball moves with them
        if self.ball_holder == player_id:
            self.ball_position = (x, y)
    
    def transfer_ball(self, to_player_id: str):
        """Transfer ball possession to another player"""
        self.ball_holder = to_player_id
        self.ball_position = self.player_positions[to_player_id]


# ============================================================
# HELPER FUNCTION FOR BALL OFFSET
# ============================================================

def _get_first_action_direction(drill: Drill, ball_holder: str) -> Optional[Tuple[float, float]]:
    """
    Find the direction of the first action by the ball holder.
    Returns unit vector (dx, dy) or None if no relevant action found.
    """
    for action in drill.actions:
        action_type = getattr(action, 'type', None)
        
        if action_type == "PASS" and action.from_player == ball_holder:
            # Direction toward the receiver
            holder_pos = next(p for p in drill.players if p.id == ball_holder).position
            receiver_pos = next(p for p in drill.players if p.id == action.to_player).position
            dx = receiver_pos.x - holder_pos.x
            dy = receiver_pos.y - holder_pos.y
            dist = np.sqrt(dx**2 + dy**2)
            if dist > 0:
                return (dx / dist, dy / dist)
        elif action_type == "DRIBBLE" and action.player == ball_holder:
            # Direction toward dribble destination
            holder_pos = next(p for p in drill.players if p.id == ball_holder).position
            dx = action.to_position.x - holder_pos.x
            dy = action.to_position.y - holder_pos.y
            dist = np.sqrt(dx**2 + dy**2)
            if dist > 0:
                return (dx / dist, dy / dist)
        elif action_type == "SHOT" and action.player == ball_holder:
            # Direction toward goal
            holder_pos = next(p for p in drill.players if p.id == ball_holder).position
            goal_y = 100 if drill.field.attacking_direction == AttackingDirection.NORTH else 0
            dx = 50 - holder_pos.x
            dy = goal_y - holder_pos.y
            dist = np.sqrt(dx**2 + dy**2)
            if dist > 0:
                return (dx / dist, dy / dist)
    return None


# ============================================================
# MAIN RENDER FUNCTION
# ============================================================

BALL_OFFSET = 1.8  # Offset ball from player center - small enough to still overlap player circle slightly

def render(
    drill: Drill,
    output_path: str,
    figsize: tuple = (8, 12),
    dpi: int = 100
) -> str:
    """
    Render a drill to an SVG file.
    
    Actions are chained - each action starts from where the previous
    action for that player/ball ended, not from the starting position.
    
    Args:
        drill: The Drill object to render
        output_path: Path to save the SVG
        figsize: Figure dimensions (width, height) in inches
        dpi: Resolution for raster elements
    
    Returns:
        The output path
    """
    fig, ax = plt.subplots(figsize=figsize)
    
    # Draw field
    field_renderer = FieldRenderer(ax, drill)
    field_renderer.draw()
    
    # Draw entities
    entity_renderer = EntityRenderer(ax)
    
    # Expand cone gates to individual cones
    for gate in drill.cone_gates:
        cx, cy = gate.center.x, gate.center.y
        w = gate.width
        if gate.orientation == GateOrientation.HORIZONTAL:
            entity_renderer.draw_cone(cx - w/2, cy)
            entity_renderer.draw_cone(cx + w/2, cy)
        else:
            entity_renderer.draw_cone(cx, cy - w/2)
            entity_renderer.draw_cone(cx, cy + w/2)
    
    # Draw individual cones
    for cone in drill.cones:
        entity_renderer.draw_cone(cone.position.x, cone.position.y)
    
    # Draw mannequins
    for mannequin in drill.mannequins:
        entity_renderer.draw_mannequin(mannequin)
    
    # Draw players (at starting positions)
    for player in drill.players:
        entity_renderer.draw_player(player)
    
    # Initialize position tracker (need this before drawing ball)
    tracker = PositionTracker(drill)
    
    # Draw balls - if a player is holding the ball, draw it at their position with slight offset
    for ball in drill.balls:
        # Default to ball's specified position
        ball_x, ball_y = ball.position.x, ball.position.y
        
        # If a player is holding the ball, use the PLAYER's position (not ball position)
        if tracker.ball_holder:
            # Get the player's actual position
            holder = next((p for p in drill.players if p.id == tracker.ball_holder), None)
            if holder:
                ball_x, ball_y = holder.position.x, holder.position.y
            
            # Offset slightly toward first action direction
            direction = _get_first_action_direction(drill, tracker.ball_holder)
            if direction:
                ball_x += direction[0] * BALL_OFFSET
                ball_y += direction[1] * BALL_OFFSET
        
        entity_renderer.draw_ball(ball_x, ball_y)
    
    # Draw actions with position tracking
    goal_y = 100 if drill.field.attacking_direction == AttackingDirection.NORTH else 0
    action_renderer = ActionRenderer(ax, goal_y)
    
    for action in drill.actions:
        # Use action.type string instead of isinstance() for reliable type checking
        # This works better with Pydantic discriminated unions
        action_type = getattr(action, 'type', None)
        
        if action_type == "PASS":
            from_x, from_y = tracker.get_player_position(action.from_player)
            to_x, to_y = tracker.get_player_position(action.to_player)
            
            # Determine if start/end are at player starting positions or action endpoints
            start_is_player = tracker.is_at_starting_position(action.from_player)
            end_is_player = tracker.is_at_starting_position(action.to_player)
            
            action_renderer.draw_pass(from_x, from_y, to_x, to_y, start_is_player, end_is_player)
            
            tracker.transfer_ball(action.to_player)
        
        elif action_type == "RUN":
            start_x, start_y = tracker.get_player_position(action.player)
            end_x, end_y = action.to_position.x, action.to_position.y
            
            start_is_player = tracker.is_at_starting_position(action.player)
            
            action_renderer.draw_run(start_x, start_y, end_x, end_y, start_is_player, end_is_player=False)
            
            tracker.update_player_position(action.player, end_x, end_y)
        
        elif action_type == "DRIBBLE":
            start_x, start_y = tracker.get_player_position(action.player)
            end_x, end_y = action.to_position.x, action.to_position.y
            
            start_is_player = tracker.is_at_starting_position(action.player)
            
            action_renderer.draw_dribble(start_x, start_y, end_x, end_y, start_is_player, end_is_player=False)
            
            tracker.update_player_position(action.player, end_x, end_y)
        
        elif action_type == "SHOT":
            start_x, start_y = tracker.get_player_position(action.player)
            
            start_is_player = tracker.is_at_starting_position(action.player)
            
            action_renderer.draw_shot(start_x, start_y, start_is_player)
    
    # Save
    plt.savefig(output_path, format="svg", bbox_inches="tight", dpi=dpi)
    plt.close()
    
    return output_path


def render_to_png(
    drill: Drill,
    output_path: str,
    figsize: tuple = (8, 12),
    dpi: int = 150
) -> str:
    """Render a drill to a PNG file"""
    fig, ax = plt.subplots(figsize=figsize)
    
    # Draw field
    field_renderer = FieldRenderer(ax, drill)
    field_renderer.draw()
    
    # Draw entities
    entity_renderer = EntityRenderer(ax)
    
    for gate in drill.cone_gates:
        cx, cy = gate.center.x, gate.center.y
        w = gate.width
        if gate.orientation == GateOrientation.HORIZONTAL:
            entity_renderer.draw_cone(cx - w/2, cy)
            entity_renderer.draw_cone(cx + w/2, cy)
        else:
            entity_renderer.draw_cone(cx, cy - w/2)
            entity_renderer.draw_cone(cx, cy + w/2)
    
    for cone in drill.cones:
        entity_renderer.draw_cone(cone.position.x, cone.position.y)
    
    for mannequin in drill.mannequins:
        entity_renderer.draw_mannequin(mannequin)
    
    for player in drill.players:
        entity_renderer.draw_player(player)
    
    # Initialize position tracker
    tracker = PositionTracker(drill)
    
    # Draw balls with offset toward first action direction
    for ball in drill.balls:
        ball_x, ball_y = ball.position.x, ball.position.y
        
        if tracker.ball_holder:
            direction = _get_first_action_direction(drill, tracker.ball_holder)
            if direction:
                ball_x += direction[0] * BALL_OFFSET
                ball_y += direction[1] * BALL_OFFSET
        
        entity_renderer.draw_ball(ball_x, ball_y)
    
    goal_y = 100 if drill.field.attacking_direction == AttackingDirection.NORTH else 0
    action_renderer = ActionRenderer(ax, goal_y)
    
    for action in drill.actions:
        if isinstance(action, PassAction):
            from_x, from_y = tracker.get_player_position(action.from_player)
            to_x, to_y = tracker.get_player_position(action.to_player)
            start_is_player = tracker.is_at_starting_position(action.from_player)
            end_is_player = tracker.is_at_starting_position(action.to_player)
            action_renderer.draw_pass(from_x, from_y, to_x, to_y, start_is_player, end_is_player)
            tracker.transfer_ball(action.to_player)
        
        elif isinstance(action, RunAction):
            start_x, start_y = tracker.get_player_position(action.player)
            end_x, end_y = action.to_position.x, action.to_position.y
            start_is_player = tracker.is_at_starting_position(action.player)
            action_renderer.draw_run(start_x, start_y, end_x, end_y, start_is_player, end_is_player=False)
            tracker.update_player_position(action.player, end_x, end_y)
        
        elif isinstance(action, DribbleAction):
            start_x, start_y = tracker.get_player_position(action.player)
            end_x, end_y = action.to_position.x, action.to_position.y
            start_is_player = tracker.is_at_starting_position(action.player)
            action_renderer.draw_dribble(start_x, start_y, end_x, end_y, start_is_player, end_is_player=False)
            tracker.update_player_position(action.player, end_x, end_y)
        
        elif isinstance(action, ShotAction):
            start_x, start_y = tracker.get_player_position(action.player)
            start_is_player = tracker.is_at_starting_position(action.player)
            action_renderer.draw_shot(start_x, start_y, start_is_player)
    
    plt.savefig(output_path, format="png", bbox_inches="tight", dpi=dpi)
    plt.close()
    
    return output_path
