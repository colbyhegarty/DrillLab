"""
Drill Renderer - Generates SVG diagrams from drill definitions.

UPDATES:
1. Mini goals support with rotation
2. Full-size goals with proper rotation handling
3. Shots can target any position (not just auto-aim at goal)
4. Multiple balls support
5. Field markings consistency fixes

This module renders:
- Soccer field with markings
- Players with role-based colors
- Cones and cone gates
- Balls (multiple supported)
- Mini goals and full-size goals at any position/rotation
- Action arrows (pass, run, dribble, shot)
"""

import matplotlib
matplotlib.use('Agg')  # Non-interactive backend

import matplotlib.pyplot as plt
import matplotlib.patches as patches
import numpy as np
from pathlib import Path
from typing import Optional, Dict, Tuple, List

from schema import (
    Drill, Player, Position, FieldType, Mannequin,
    PassAction, RunAction, DribbleAction, ShotAction,
    AttackingDirection, PlayerRole, GateOrientation,
    MiniGoal, Goal
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
MINI_GOAL_COLOR = "#32CD32"  # Lime green for mini goals
GOAL_COLOR = "white"


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
        
        # Include mini goals in bounds
        for mini_goal in self.drill.mini_goals:
            x_coords.append(mini_goal.position.x)
            y_coords.append(mini_goal.position.y)
        
        # Include full-size goals in bounds
        for goal in self.drill.goals:
            x_coords.append(goal.position.x)
            y_coords.append(goal.position.y)
        
        # Collect action endpoints
        for action in self.drill.actions:
            action_type = getattr(action, 'type', None)
            if action_type in ["RUN", "DRIBBLE"]:
                x_coords.append(action.to_position.x)
                y_coords.append(action.to_position.y)
            elif action_type == "SHOT":
                # Check if shot has a specific target position
                if hasattr(action, 'to_position') and action.to_position:
                    x_coords.append(action.to_position.x)
                    y_coords.append(action.to_position.y)
                else:
                    # Legacy: shot goes to goal
                    y_coords.append(self.attacking_goal_y)
                    x_coords.append(50)
        
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
        
        # Handle field.goals (legacy built-in goals at y=0/100)
        if self.field.goals > 0:
            if self.field.attacking_direction == AttackingDirection.NORTH:
                if self.content_y_max > 70:
                    self.y_max = 100
                    if self.y_min > 78:
                        self.y_min = 78
            else:
                if self.content_y_min < 30:
                    self.y_min = 0
                    if self.y_max < 22:
                        self.y_max = 22
        
        if self.field.goals > 1:
            other_goal_y = 0 if self.attacking_goal_y == 100 else 100
            
            if other_goal_y == 0 and self.content_y_min < 30:
                self.y_min = 0
            elif other_goal_y == 100 and self.content_y_max > 70:
                self.y_max = 100
            
            has_gk_top = any(p.position.y > 90 for p in self.drill.players if p.role.value == "GOALKEEPER")
            has_gk_bottom = any(p.position.y < 10 for p in self.drill.players if p.role.value == "GOALKEEPER")
            
            if has_gk_top:
                self.y_max = 100
            if has_gk_bottom:
                self.y_min = 0
        
        # Ensure minimum view size
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
        
        # Check if explicit goals are provided in the drill
        has_explicit_goals = len(self.drill.goals) > 0
        
        if self.field.markings:
            # Draw halfway line if visible
            if self.y_min <= 50 <= self.y_max:
                self._draw_halfway_line()
            
            # Draw center circle if visible
            if self.field.type == FieldType.FULL:
                if self.y_min <= 50 <= self.y_max and self.x_min <= 50 <= self.x_max:
                    self._draw_center_circle()
            
            # ALWAYS draw penalty area markings when markings=true and area is visible
            # The goal is only drawn when field.goals >= 1
            if self.field.attacking_direction == AttackingDirection.NORTH:
                # Attacking end is at y=100
                if self.y_max >= 85:
                    draw_goal = (self.field.goals >= 1)
                    self._draw_goal_area(100, draw_goal=draw_goal)
                # Defending end at y=0 (only for FULL field or when goals >= 2)
                if self.field.type == FieldType.FULL and self.y_min <= 15:
                    draw_goal = (self.field.goals >= 2)
                    self._draw_goal_area(0, draw_goal=draw_goal)
            else:  # SOUTH
                # Attacking end is at y=0
                if self.y_min <= 15:
                    draw_goal = (self.field.goals >= 1)
                    self._draw_goal_area(0, draw_goal=draw_goal)
                # Defending end at y=100 (only for FULL field or when goals >= 2)
                if self.field.type == FieldType.FULL and self.y_max >= 85:
                    draw_goal = (self.field.goals >= 2)
                    self._draw_goal_area(100, draw_goal=draw_goal)
        
        elif self.field.goals > 0 and not has_explicit_goals:
            # No markings but has built-in goals (only if no explicit goals)
            # When markings are OFF and explicit goals exist, skip built-in goals entirely
            if self.field.goals >= 1:
                if self.field.attacking_direction == AttackingDirection.NORTH:
                    self._draw_field_goal(100, goal_width=8)
                else:
                    self._draw_field_goal(0, goal_width=8)
            
            if self.field.goals >= 2:
                if self.field.attacking_direction == AttackingDirection.NORTH:
                    self._draw_field_goal(0, goal_width=8)
                else:
                    self._draw_field_goal(100, goal_width=8)
        
        self.ax.set_aspect("equal")
        self.ax.axis("off")
    
    def _draw_grass(self):
        """Draw striped grass"""
        stripe_width = 10
        start_x = int(self.x_min // stripe_width) * stripe_width
        end_x = int(self.x_max // stripe_width + 1) * stripe_width + stripe_width
        
        for i in range(start_x, end_x, stripe_width):
            color = GRASS_LIGHT if (i // stripe_width) % 2 == 0 else GRASS_DARK
            self.ax.add_patch(patches.Rectangle(
                (i, self.y_min - 5), stripe_width, (self.y_max - self.y_min) + 10, 
                color=color, zorder=0
            ))
    
    def _draw_outline(self):
        """Draw field outline"""
        self.ax.plot(
            [self.x_min, self.x_max, self.x_max, self.x_min, self.x_min], 
            [self.y_min, self.y_min, self.y_max, self.y_max, self.y_min], 
            color=LINE_COLOR, lw=1.5, alpha=0.5, zorder=1
        )
    
    def _draw_halfway_line(self):
        """Draw halfway line"""
        self.ax.plot([self.x_min, self.x_max], [50, 50], color=LINE_COLOR, lw=1.5, zorder=1)
    
    def _draw_center_circle(self):
        """Draw center circle"""
        self.ax.add_patch(patches.Circle(
            (50, 50), 10, fill=False, edgecolor=LINE_COLOR, lw=1.5, zorder=1
        ))
        self.ax.scatter(50, 50, s=20, c=LINE_COLOR, zorder=2)
    
    def _draw_goal_area(self, goal_y: float, draw_goal: bool = True):
        """Draw penalty box, 6-yard box, and optionally the goal"""
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
        
        # Goal (only if draw_goal is True)
        if draw_goal:
            self._draw_goal_with_net(50, goal_y, width=8)
    
    def _draw_goal_with_net(self, cx: float, goal_line_y: float, width: float = 8):
        """Draw a goal with posts, crossbar, and net at a fixed y position"""
        post_width = 3.0
        goal_depth = 3
        
        net_direction = -1 if goal_line_y >= 50 else 1
        crossbar_y = goal_line_y + net_direction * goal_depth
        
        # Posts
        self.ax.plot([cx - width/2, cx - width/2], [crossbar_y, goal_line_y], 
                    color=GOAL_COLOR, lw=post_width, solid_capstyle='round', zorder=6)
        self.ax.plot([cx + width/2, cx + width/2], [crossbar_y, goal_line_y], 
                    color=GOAL_COLOR, lw=post_width, solid_capstyle='round', zorder=6)
        
        # Crossbar
        self.ax.plot([cx - width/2, cx + width/2], [crossbar_y, crossbar_y], 
                    color=GOAL_COLOR, lw=post_width, solid_capstyle='round', zorder=6)
        
        # Back line
        self.ax.plot([cx - width/2, cx + width/2], [goal_line_y, goal_line_y], 
                    color='gray', lw=1.5, alpha=0.6, zorder=5)
        
        # Net strings
        num_strings = int(width) + 1
        for i in range(num_strings):
            net_x = cx - width/2 + i * (width / (num_strings - 1)) if num_strings > 1 else cx
            self.ax.plot([net_x, net_x], [crossbar_y, goal_line_y],
                        color='gray', lw=0.5, alpha=0.4, zorder=5)
    
    def _draw_field_goal(self, goal_line_y: float, goal_width: float = 8):
        """Draw a goal without markings"""
        self._draw_goal_with_net(50, goal_line_y, width=goal_width)


# ============================================================
# ENTITY RENDERER
# ============================================================

class EntityRenderer:
    """Renders players, cones, balls, mini goals, and full-size goals"""
    
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
        """Draw a soccer ball"""
        self.ax.scatter(
            x, y, s=120, c="white",
            edgecolors="black", linewidths=1.5,
            zorder=12
        )
        self.ax.scatter(
            x, y, s=35, c="black",
            marker='p',
            zorder=13
        )
    
    def draw_mannequin(self, mannequin: Mannequin):
        """Draw a training mannequin"""
        x, y = mannequin.position.x, mannequin.position.y
        
        self.ax.scatter(
            x, y, s=100, c=MANNEQUIN_COLOR,
            edgecolors="black", linewidths=1,
            marker='o', zorder=8
        )
        
        body_height = 2.5
        self.ax.plot(
            [x, x], [y, y + body_height],
            color=MANNEQUIN_COLOR, lw=4,
            solid_capstyle='round', zorder=8
        )
        
        self.ax.scatter(
            x, y + body_height + 0.8, s=60,
            c=MANNEQUIN_COLOR, edgecolors="black",
            linewidths=0.8, zorder=8
        )
        
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
    
    def draw_mini_goal(self, mini_goal):
        """
        Draw a mini/pugg goal at the specified position with rotation.
        Looks like a smaller version of the full-size goal (rectangular with posts and net).
        Color is white to match full-size goals.
        
        Rotation (flipped 180° from input - so 0° input means opening faces SOUTH):
        - 0° input: Opening faces SOUTH (down) - net at top
        - 90° input: Opening faces WEST (left) - net at right  
        - 180° input: Opening faces NORTH (up) - net at bottom
        - 270° input: Opening faces EAST (right) - net at left
        """
        x, y = mini_goal.position.x, mini_goal.position.y
        # Flip rotation by 180 degrees
        rotation = (mini_goal.rotation + 180) % 360
        
        width = 4  # Mini goal width
        depth = 2  # Mini goal depth
        post_width = 2.0
        
        # Use white for mini goals (same as full-size goals)
        frame_color = GOAL_COLOR  # white
        net_color = 'gray'
        
        if rotation == 0:  # Faces NORTH (opening at top)
            # Posts (vertical)
            self.ax.plot([x - width/2, x - width/2], [y, y + depth], 
                        color=frame_color, lw=post_width, solid_capstyle='round', zorder=6)
            self.ax.plot([x + width/2, x + width/2], [y, y + depth], 
                        color=frame_color, lw=post_width, solid_capstyle='round', zorder=6)
            # Back bar
            self.ax.plot([x - width/2, x + width/2], [y, y], 
                        color=frame_color, lw=post_width, solid_capstyle='round', zorder=6)
            # Net strings (vertical)
            num_strings = 5
            for i in range(num_strings):
                net_x = x - width/2 + i * (width / (num_strings - 1))
                self.ax.plot([net_x, net_x], [y, y + depth], 
                            color=net_color, lw=0.5, alpha=0.4, zorder=5)
                            
        elif rotation == 90:  # Faces EAST (opening at right)
            # Posts (horizontal)
            self.ax.plot([x, x + depth], [y - width/2, y - width/2], 
                        color=frame_color, lw=post_width, solid_capstyle='round', zorder=6)
            self.ax.plot([x, x + depth], [y + width/2, y + width/2], 
                        color=frame_color, lw=post_width, solid_capstyle='round', zorder=6)
            # Back bar
            self.ax.plot([x, x], [y - width/2, y + width/2], 
                        color=frame_color, lw=post_width, solid_capstyle='round', zorder=6)
            # Net strings (horizontal)
            num_strings = 5
            for i in range(num_strings):
                net_y = y - width/2 + i * (width / (num_strings - 1))
                self.ax.plot([x, x + depth], [net_y, net_y], 
                            color=net_color, lw=0.5, alpha=0.4, zorder=5)
                            
        elif rotation == 180:  # Faces SOUTH (opening at bottom)
            # Posts (vertical)
            self.ax.plot([x - width/2, x - width/2], [y, y - depth], 
                        color=frame_color, lw=post_width, solid_capstyle='round', zorder=6)
            self.ax.plot([x + width/2, x + width/2], [y, y - depth], 
                        color=frame_color, lw=post_width, solid_capstyle='round', zorder=6)
            # Back bar
            self.ax.plot([x - width/2, x + width/2], [y, y], 
                        color=frame_color, lw=post_width, solid_capstyle='round', zorder=6)
            # Net strings (vertical)
            num_strings = 5
            for i in range(num_strings):
                net_x = x - width/2 + i * (width / (num_strings - 1))
                self.ax.plot([net_x, net_x], [y, y - depth], 
                            color=net_color, lw=0.5, alpha=0.4, zorder=5)
                            
        else:  # 270° - Faces WEST (opening at left)
            # Posts (horizontal)
            self.ax.plot([x, x - depth], [y - width/2, y - width/2], 
                        color=frame_color, lw=post_width, solid_capstyle='round', zorder=6)
            self.ax.plot([x, x - depth], [y + width/2, y + width/2], 
                        color=frame_color, lw=post_width, solid_capstyle='round', zorder=6)
            # Back bar
            self.ax.plot([x, x], [y - width/2, y + width/2], 
                        color=frame_color, lw=post_width, solid_capstyle='round', zorder=6)
            # Net strings (horizontal)
            num_strings = 5
            for i in range(num_strings):
                net_y = y - width/2 + i * (width / (num_strings - 1))
                self.ax.plot([x, x - depth], [net_y, net_y], 
                            color=net_color, lw=0.5, alpha=0.4, zorder=5)
    
    def draw_full_goal(self, goal):
        """
        Draw a full-size goal at the specified position with rotation.
        
        Rotation:
        - 0°: Opening faces NORTH (up)
        - 90°: Opening faces EAST (right)
        - 180°: Opening faces SOUTH (down)
        - 270°: Opening faces WEST (left)
        """
        x, y = goal.position.x, goal.position.y
        rotation = goal.rotation
        
        width = 8  # Goal width
        depth = 3  # Goal depth
        post_width = 3.0
        
        if rotation == 0:  # Faces NORTH
            # Posts
            self.ax.plot([x - width/2, x - width/2], [y, y + depth], 
                        color=GOAL_COLOR, lw=post_width, solid_capstyle='round', zorder=6)
            self.ax.plot([x + width/2, x + width/2], [y, y + depth], 
                        color=GOAL_COLOR, lw=post_width, solid_capstyle='round', zorder=6)
            # Crossbar (front)
            self.ax.plot([x - width/2, x + width/2], [y + depth, y + depth], 
                        color=GOAL_COLOR, lw=post_width, solid_capstyle='round', zorder=6)
            # Back line
            self.ax.plot([x - width/2, x + width/2], [y, y], 
                        color='gray', lw=1.5, alpha=0.6, zorder=5)
            # Net strings
            for i in range(int(width) + 1):
                net_x = x - width/2 + i * (width / int(width))
                self.ax.plot([net_x, net_x], [y, y + depth], color='gray', lw=0.5, alpha=0.4, zorder=5)
        
        elif rotation == 90:  # Faces EAST
            # Posts
            self.ax.plot([x, x + depth], [y - width/2, y - width/2], 
                        color=GOAL_COLOR, lw=post_width, solid_capstyle='round', zorder=6)
            self.ax.plot([x, x + depth], [y + width/2, y + width/2], 
                        color=GOAL_COLOR, lw=post_width, solid_capstyle='round', zorder=6)
            # Crossbar (front)
            self.ax.plot([x + depth, x + depth], [y - width/2, y + width/2], 
                        color=GOAL_COLOR, lw=post_width, solid_capstyle='round', zorder=6)
            # Back line
            self.ax.plot([x, x], [y - width/2, y + width/2], 
                        color='gray', lw=1.5, alpha=0.6, zorder=5)
            # Net strings
            for i in range(int(width) + 1):
                net_y = y - width/2 + i * (width / int(width))
                self.ax.plot([x, x + depth], [net_y, net_y], color='gray', lw=0.5, alpha=0.4, zorder=5)
        
        elif rotation == 180:  # Faces SOUTH
            # Posts
            self.ax.plot([x - width/2, x - width/2], [y, y - depth], 
                        color=GOAL_COLOR, lw=post_width, solid_capstyle='round', zorder=6)
            self.ax.plot([x + width/2, x + width/2], [y, y - depth], 
                        color=GOAL_COLOR, lw=post_width, solid_capstyle='round', zorder=6)
            # Crossbar (front)
            self.ax.plot([x - width/2, x + width/2], [y - depth, y - depth], 
                        color=GOAL_COLOR, lw=post_width, solid_capstyle='round', zorder=6)
            # Back line
            self.ax.plot([x - width/2, x + width/2], [y, y], 
                        color='gray', lw=1.5, alpha=0.6, zorder=5)
            # Net strings
            for i in range(int(width) + 1):
                net_x = x - width/2 + i * (width / int(width))
                self.ax.plot([net_x, net_x], [y, y - depth], color='gray', lw=0.5, alpha=0.4, zorder=5)
        
        else:  # 270° - Faces WEST
            # Posts
            self.ax.plot([x, x - depth], [y - width/2, y - width/2], 
                        color=GOAL_COLOR, lw=post_width, solid_capstyle='round', zorder=6)
            self.ax.plot([x, x - depth], [y + width/2, y + width/2], 
                        color=GOAL_COLOR, lw=post_width, solid_capstyle='round', zorder=6)
            # Crossbar (front)
            self.ax.plot([x - depth, x - depth], [y - width/2, y + width/2], 
                        color=GOAL_COLOR, lw=post_width, solid_capstyle='round', zorder=6)
            # Back line
            self.ax.plot([x, x], [y - width/2, y + width/2], 
                        color='gray', lw=1.5, alpha=0.6, zorder=5)
            # Net strings
            for i in range(int(width) + 1):
                net_y = y - width/2 + i * (width / int(width))
                self.ax.plot([x, x - depth], [net_y, net_y], color='gray', lw=0.5, alpha=0.4, zorder=5)


# ============================================================
# ACTION RENDERER
# ============================================================

class ActionRenderer:
    """Renders movement arrows"""
    
    LINE_WIDTH = 1.8
    ARROW_HEAD_WIDTH = 1.2
    ARROW_HEAD_LENGTH = 1.0
    PLAYER_OFFSET = 2.5
    ACTION_GAP = 0.8
    
    def __init__(self, ax, goal_y: float):
        self.ax = ax
        self.goal_y = goal_y
    
    def _get_offset_points(self, x1: float, y1: float, x2: float, y2: float, 
                           start_is_player: bool = True, end_is_player: bool = True) -> tuple:
        """Calculate offset start and end points"""
        dx = x2 - x1
        dy = y2 - y1
        dist = np.sqrt(dx**2 + dy**2)
        
        if dist == 0:
            return x1, y1, x2, y2
        
        ux = dx / dist
        uy = dy / dist
        
        start_offset = self.PLAYER_OFFSET if start_is_player else self.ACTION_GAP
        end_offset = self.PLAYER_OFFSET if end_is_player else self.ACTION_GAP
        
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
        
        arrow_length = self.ARROW_HEAD_LENGTH
        line_end_ratio = (dist - arrow_length) / dist
        
        t = np.linspace(0, line_end_ratio, 80)
        x_base = start_x + dx * t
        y_base = start_y + dy * t
        
        perp_x = -dy / dist
        perp_y = dx / dist
        
        wave = np.sin(t / line_end_ratio * 4 * np.pi) * 1.0
        x = x_base + perp_x * wave
        y = y_base + perp_y * wave
        
        self.ax.plot(x, y, lw=self.LINE_WIDTH, color="white", zorder=4)
        
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
    
    def draw_shot(self, x1: float, y1: float, target_x: float, target_y: float, 
                  start_is_player: bool = True):
        """
        Draw a shot arrow toward a specific target position.
        
        Args:
            x1, y1: Starting position
            target_x, target_y: Target position (can be any point, not just goal)
            start_is_player: Whether starting from a player position
        """
        dx = target_x - x1
        dy = target_y - y1
        dist = np.sqrt(dx**2 + dy**2)
        
        if dist == 0:
            return
        
        ux = dx / dist
        uy = dy / dist
        start_offset = self.PLAYER_OFFSET if start_is_player else self.ACTION_GAP
        start_x = x1 + ux * start_offset
        start_y = y1 + uy * start_offset
        
        dx = target_x - start_x
        dy = target_y - start_y
        dist = np.sqrt(dx**2 + dy**2)
        
        if dist == 0:
            return
        
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
    """Tracks player and ball positions through actions"""
    
    def __init__(self, drill: Drill):
        self.drill = drill
        self.player_positions: Dict[str, Tuple[float, float]] = {}
        self.player_has_moved: Dict[str, bool] = {}
        
        for player in drill.players:
            self.player_positions[player.id] = (player.position.x, player.position.y)
            self.player_has_moved[player.id] = False
        
        self.ball_position: Optional[Tuple[float, float]] = None
        self.ball_holder: Optional[str] = None
        
        if drill.actions:
            first_action = drill.actions[0]
            action_type = getattr(first_action, 'type', None)
            
            if action_type == "PASS":
                self.ball_holder = first_action.from_player
            elif action_type in ["DRIBBLE", "SHOT"]:
                self.ball_holder = first_action.player
        
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
        
        if self.ball_holder and self.ball_holder in self.player_positions:
            self.ball_position = self.player_positions[self.ball_holder]
        elif drill.balls:
            self.ball_position = (drill.balls[0].position.x, drill.balls[0].position.y)
    
    def get_player_position(self, player_id: str) -> Tuple[float, float]:
        return self.player_positions.get(player_id, (0, 0))
    
    def is_at_starting_position(self, player_id: str) -> bool:
        return not self.player_has_moved.get(player_id, False)
    
    def get_ball_position(self) -> Tuple[float, float]:
        if self.ball_holder:
            return self.player_positions[self.ball_holder]
        return self.ball_position or (50, 50)
    
    def update_player_position(self, player_id: str, x: float, y: float):
        self.player_positions[player_id] = (x, y)
        self.player_has_moved[player_id] = True
        if self.ball_holder == player_id:
            self.ball_position = (x, y)
    
    def transfer_ball(self, to_player_id: str):
        self.ball_holder = to_player_id
        self.ball_position = self.player_positions[to_player_id]


# ============================================================
# HELPER FUNCTIONS
# ============================================================

BALL_OFFSET = 1.8

def _get_first_action_direction(drill: Drill, ball_holder: str) -> Optional[Tuple[float, float]]:
    """Find direction of first action by ball holder"""
    for action in drill.actions:
        action_type = getattr(action, 'type', None)
        
        if action_type == "PASS" and action.from_player == ball_holder:
            holder_pos = next(p for p in drill.players if p.id == ball_holder).position
            receiver_pos = next(p for p in drill.players if p.id == action.to_player).position
            dx = receiver_pos.x - holder_pos.x
            dy = receiver_pos.y - holder_pos.y
            dist = np.sqrt(dx**2 + dy**2)
            if dist > 0:
                return (dx / dist, dy / dist)
        elif action_type == "DRIBBLE" and action.player == ball_holder:
            holder_pos = next(p for p in drill.players if p.id == ball_holder).position
            dx = action.to_position.x - holder_pos.x
            dy = action.to_position.y - holder_pos.y
            dist = np.sqrt(dx**2 + dy**2)
            if dist > 0:
                return (dx / dist, dy / dist)
        elif action_type == "SHOT" and action.player == ball_holder:
            holder_pos = next(p for p in drill.players if p.id == ball_holder).position
            # Check for to_position first
            if hasattr(action, 'to_position') and action.to_position:
                dx = action.to_position.x - holder_pos.x
                dy = action.to_position.y - holder_pos.y
            else:
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

def render(
    drill: Drill,
    output_path: str,
    figsize: tuple = (8, 12),
    dpi: int = 100
) -> str:
    """Render a drill to an SVG file"""
    fig, ax = plt.subplots(figsize=figsize)
    
    # Draw field
    field_renderer = FieldRenderer(ax, drill)
    field_renderer.draw()
    
    # Draw entities
    entity_renderer = EntityRenderer(ax)
    
    # Cone gates
    for gate in drill.cone_gates:
        cx, cy = gate.center.x, gate.center.y
        w = gate.width
        if gate.orientation == GateOrientation.HORIZONTAL:
            entity_renderer.draw_cone(cx - w/2, cy)
            entity_renderer.draw_cone(cx + w/2, cy)
        else:
            entity_renderer.draw_cone(cx, cy - w/2)
            entity_renderer.draw_cone(cx, cy + w/2)
    
    # Individual cones
    for cone in drill.cones:
        entity_renderer.draw_cone(cone.position.x, cone.position.y)
    
    # Mannequins
    for mannequin in drill.mannequins:
        entity_renderer.draw_mannequin(mannequin)
    
    # Mini goals (NEW)
    for mini_goal in drill.mini_goals:
        entity_renderer.draw_mini_goal(mini_goal)
    
    # Full-size goals at custom positions (NEW)
    for goal in drill.goals:
        entity_renderer.draw_full_goal(goal)
    
    # Players
    for player in drill.players:
        entity_renderer.draw_player(player)
    
    # Position tracker
    tracker = PositionTracker(drill)
    
    # Draw ALL balls (FIX: support multiple balls)
    for i, ball in enumerate(drill.balls):
        ball_x, ball_y = ball.position.x, ball.position.y
        
        # Only apply holder offset to first ball
        if i == 0 and tracker.ball_holder:
            holder = next((p for p in drill.players if p.id == tracker.ball_holder), None)
            if holder:
                ball_x, ball_y = holder.position.x, holder.position.y
            
            direction = _get_first_action_direction(drill, tracker.ball_holder)
            if direction:
                ball_x += direction[0] * BALL_OFFSET
                ball_y += direction[1] * BALL_OFFSET
        
        entity_renderer.draw_ball(ball_x, ball_y)
    
    # Draw actions
    goal_y = 100 if drill.field.attacking_direction == AttackingDirection.NORTH else 0
    action_renderer = ActionRenderer(ax, goal_y)
    
    for action in drill.actions:
        action_type = getattr(action, 'type', None)
        
        if action_type == "PASS":
            from_x, from_y = tracker.get_player_position(action.from_player)
            to_x, to_y = tracker.get_player_position(action.to_player)
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
            
            # FIX: Check for to_position first, fall back to goal
            if hasattr(action, 'to_position') and action.to_position:
                target_x = action.to_position.x
                target_y = action.to_position.y
            else:
                # Legacy behavior: shoot at goal center
                target_x = 50
                target_y = goal_y
            
            action_renderer.draw_shot(start_x, start_y, target_x, target_y, start_is_player)
    
    # Save
    plt.savefig(output_path, format="svg", bbox_inches="tight", dpi=dpi)
    plt.close()
    
    return output_path
