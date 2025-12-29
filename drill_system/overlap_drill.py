"""
Overlap and Cross Drill
"""
import sys
sys.path.insert(0, '/home/claude/drill_system')

from schema import Drill
from renderer import render

OVERLAP_AND_CROSS = {
    "name": "Overlap and Cross",
    "description": "Wing play drill focusing on overlapping runs and crossing",
    "field": {
        "type": "HALF",
        "attacking_direction": "NORTH",
        "markings": True,
        "goals": 1
    },
    "players": [
        {"id": "GK", "role": "GOALKEEPER", "position": {"x": 50, "y": 98}},
        {"id": "A1", "role": "ATTACKER", "position": {"x": 25, "y": 55}},
        {"id": "A2", "role": "ATTACKER", "position": {"x": 15, "y": 65}},
        {"id": "A3", "role": "ATTACKER", "position": {"x": 50, "y": 70}},
        {"id": "D1", "role": "DEFENDER", "position": {"x": 30, "y": 78}}
    ],
    "cones": [
        {"id": "C1", "position": {"x": 25, "y": 55}},
        {"id": "C2", "position": {"x": 15, "y": 65}}
    ],
    "cone_gates": [],
    "balls": [{"position": {"x": 25, "y": 55}}],
    "actions": [
        {"type": "PASS", "from_player": "A1", "to_player": "A2"},
        {"type": "RUN", "player": "A1", "to_position": {"x": 12, "y": 88}},
        {"type": "DRIBBLE", "player": "A2", "to_position": {"x": 22, "y": 75}},
        {"type": "RUN", "player": "A3", "to_position": {"x": 50, "y": 88}},
        {"type": "PASS", "from_player": "A2", "to_player": "A1"},
        {"type": "PASS", "from_player": "A1", "to_player": "A3"},
        {"type": "SHOT", "player": "A3", "target": "GOAL"}
    ],
    "coaching_points": [
        "Timing of the overlap run",
        "Winger must draw defender before releasing ball",
        "Striker attacks near post, midfielder covers far post"
    ],
    "variations": [
        "Add a second defender",
        "Require one-touch finish",
        "Alternate sides"
    ]
}

# Create and render the drill
drill = Drill.model_validate(OVERLAP_AND_CROSS)
render(drill, "/home/claude/drill_system/test_output/overlap_and_cross.svg")
print("Rendered: overlap_and_cross.svg")
