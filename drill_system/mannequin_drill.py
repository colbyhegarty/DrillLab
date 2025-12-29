"""
Slalom Dribble and Finish Drill - uses mannequins
"""
import sys
sys.path.insert(0, '/home/claude/drill_system')

from schema import Drill
from renderer import render

SLALOM_FINISH = {
    "name": "Slalom Dribble and Finish",
    "description": "Dribbling through mannequins simulating defenders, then finishing on goal",
    "field": {
        "type": "HALF",
        "attacking_direction": "NORTH",
        "markings": True,
        "goals": 1
    },
    "players": [
        {"id": "GK", "role": "GOALKEEPER", "position": {"x": 50, "y": 98}},
        {"id": "A1", "role": "ATTACKER", "position": {"x": 50, "y": 55}}
    ],
    "cones": [
        {"position": {"x": 50, "y": 55}}
    ],
    "cone_gates": [],
    "mannequins": [
        {"id": "M1", "position": {"x": 45, "y": 65}},
        {"id": "M2", "position": {"x": 55, "y": 72}},
        {"id": "M3", "position": {"x": 45, "y": 79}}
    ],
    "balls": [{"position": {"x": 50, "y": 55}}],
    "actions": [
        {"type": "DRIBBLE", "player": "A1", "to_position": {"x": 52, "y": 85}},
        {"type": "SHOT", "player": "A1", "target": "GOAL"}
    ],
    "coaching_points": [
        "Keep the ball close when dribbling past mannequins",
        "Use both feet to change direction",
        "Head up to see the goal before shooting",
        "Shoot across the goalkeeper"
    ],
    "variations": [
        "Timed runs - compete for fastest completion",
        "Specify which foot to finish with",
        "Add a passive defender at the end"
    ]
}

# Create and render the drill
drill = Drill.model_validate(SLALOM_FINISH)
render(drill, "/home/claude/drill_system/test_output/slalom_finish.svg")
print("Rendered: slalom_finish.svg")
