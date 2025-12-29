"""
Test Fixtures - Predefined drill definitions for testing.

These drills can be used to:
1. Test the rendering pipeline without API calls
2. Validate the schema
3. Serve as examples for the LLM prompt
"""

# ============================================================
# EXAMPLE DRILLS
# ============================================================

PASSING_TRIANGLE = {
    "name": "Passing Triangle",
    "description": "Basic 3-player passing drill to develop quick, accurate passing",
    "field": {
        "type": "HALF",
        "attacking_direction": "NORTH",
        "markings": True,
        "goals": 0
    },
    "players": [
        {"id": "A1", "role": "ATTACKER", "position": {"x": 30, "y": 60}},
        {"id": "A2", "role": "ATTACKER", "position": {"x": 70, "y": 60}},
        {"id": "A3", "role": "ATTACKER", "position": {"x": 50, "y": 40}}
    ],
    "cones": [],
    "cone_gates": [],
    "balls": [{"position": {"x": 30, "y": 60}}],
    "actions": [
        {"type": "PASS", "from_player": "A1", "to_player": "A2"},
        {"type": "PASS", "from_player": "A2", "to_player": "A3"},
        {"type": "PASS", "from_player": "A3", "to_player": "A1"}
    ],
    "coaching_points": [
        "Open body position to receive",
        "First touch away from pressure",
        "Weight of pass - firm but controllable"
    ],
    "variations": [
        "One touch only",
        "Add a defender in the middle"
    ]
}


FINISHING_2V1 = {
    "name": "2v1 Finishing",
    "description": "Two attackers against one defender, focusing on quick combination play and finishing",
    "field": {
        "type": "HALF",
        "attacking_direction": "NORTH",
        "markings": True,
        "goals": 1
    },
    "players": [
        {"id": "GK", "role": "GOALKEEPER", "position": {"x": 50, "y": 98}},
        {"id": "A1", "role": "ATTACKER", "position": {"x": 35, "y": 65}},
        {"id": "A2", "role": "ATTACKER", "position": {"x": 65, "y": 65}},
        {"id": "D1", "role": "DEFENDER", "position": {"x": 50, "y": 78}}
    ],
    "cones": [],
    "cone_gates": [],
    "balls": [{"position": {"x": 35, "y": 65}}],
    "actions": [
        {"type": "DRIBBLE", "player": "A1", "to_position": {"x": 42, "y": 75}},
        {"type": "RUN", "player": "A2", "to_position": {"x": 58, "y": 85}},
        {"type": "PASS", "from_player": "A1", "to_player": "A2"},
        {"type": "SHOT", "player": "A2", "target": "GOAL"}
    ],
    "coaching_points": [
        "Commit the defender before passing",
        "Timing of the run - stay onside",
        "Finish across the goalkeeper"
    ],
    "variations": [
        "Start from wider positions",
        "Add second defender"
    ]
}


DRIBBLE_THROUGH_GATES = {
    "name": "Dribble Through Gates",
    "description": "Individual dribbling drill through cone gates to improve close control",
    "field": {
        "type": "HALF",
        "attacking_direction": "NORTH",
        "markings": True,
        "goals": 0
    },
    "players": [
        {"id": "A1", "role": "ATTACKER", "position": {"x": 50, "y": 30}}
    ],
    "cones": [],
    "cone_gates": [
        {"id": "G1", "center": {"x": 50, "y": 45}, "width": 8, "orientation": "HORIZONTAL"},
        {"id": "G2", "center": {"x": 50, "y": 60}, "width": 8, "orientation": "HORIZONTAL"},
        {"id": "G3", "center": {"x": 50, "y": 75}, "width": 8, "orientation": "HORIZONTAL"}
    ],
    "balls": [{"position": {"x": 50, "y": 30}}],
    "actions": [
        {"type": "DRIBBLE", "player": "A1", "to_position": {"x": 50, "y": 45}, "through_gate": "G1"},
        {"type": "DRIBBLE", "player": "A1", "to_position": {"x": 50, "y": 60}, "through_gate": "G2"},
        {"type": "DRIBBLE", "player": "A1", "to_position": {"x": 50, "y": 75}, "through_gate": "G3"}
    ],
    "coaching_points": [
        "Head up while dribbling",
        "Use both feet",
        "Accelerate through the gate"
    ],
    "variations": [
        "Add a time challenge",
        "Use outside foot only"
    ]
}


CROSSING_AND_FINISHING = {
    "name": "Crossing and Finishing",
    "description": "Wide player crosses for two strikers to attack",
    "field": {
        "type": "HALF",
        "attacking_direction": "NORTH",
        "markings": True,
        "goals": 1
    },
    "players": [
        {"id": "GK", "role": "GOALKEEPER", "position": {"x": 50, "y": 98}},
        {"id": "A1", "role": "ATTACKER", "position": {"x": 85, "y": 70}},  # Wide player
        {"id": "A2", "role": "ATTACKER", "position": {"x": 45, "y": 75}},  # Near post
        {"id": "A3", "role": "ATTACKER", "position": {"x": 55, "y": 72}},  # Far post
        {"id": "D1", "role": "DEFENDER", "position": {"x": 50, "y": 85}}
    ],
    "cones": [],
    "cone_gates": [],
    "balls": [{"position": {"x": 85, "y": 70}}],
    "actions": [
        {"type": "DRIBBLE", "player": "A1", "to_position": {"x": 90, "y": 85}},
        {"type": "RUN", "player": "A2", "to_position": {"x": 48, "y": 92}},
        {"type": "RUN", "player": "A3", "to_position": {"x": 58, "y": 88}},
        {"type": "PASS", "from_player": "A1", "to_player": "A2"},
        {"type": "SHOT", "player": "A2", "target": "GOAL"}
    ],
    "coaching_points": [
        "Get to the byline before crossing",
        "Attack the near post with conviction",
        "Far post runner arrives late"
    ],
    "variations": [
        "Cross from opposite side",
        "Cutback instead of cross"
    ]
}


RONDO_4V2 = {
    "name": "4v2 Rondo",
    "description": "Possession drill with 4 attackers keeping the ball from 2 defenders",
    "field": {
        "type": "HALF",
        "attacking_direction": "NORTH",
        "markings": False,
        "goals": 0
    },
    "players": [
        {"id": "A1", "role": "ATTACKER", "position": {"x": 35, "y": 50}},
        {"id": "A2", "role": "ATTACKER", "position": {"x": 65, "y": 50}},
        {"id": "A3", "role": "ATTACKER", "position": {"x": 50, "y": 35}},
        {"id": "A4", "role": "ATTACKER", "position": {"x": 50, "y": 65}},
        {"id": "D1", "role": "DEFENDER", "position": {"x": 45, "y": 52}},
        {"id": "D2", "role": "DEFENDER", "position": {"x": 55, "y": 48}}
    ],
    "cones": [
        {"position": {"x": 30, "y": 30}},
        {"position": {"x": 70, "y": 30}},
        {"position": {"x": 70, "y": 70}},
        {"position": {"x": 30, "y": 70}}
    ],
    "cone_gates": [],
    "balls": [{"position": {"x": 35, "y": 50}}],
    "actions": [
        {"type": "PASS", "from_player": "A1", "to_player": "A4"},
        {"type": "PASS", "from_player": "A4", "to_player": "A2"},
        {"type": "PASS", "from_player": "A2", "to_player": "A3"},
        {"type": "PASS", "from_player": "A3", "to_player": "A1"}
    ],
    "coaching_points": [
        "Play with head up - scan before receiving",
        "Move after passing to create angles",
        "Defenders work together, not separately"
    ],
    "variations": [
        "Two touch maximum",
        "Add a third defender"
    ]
}


BUILD_FROM_BACK = {
    "name": "Build From Back",
    "description": "Playing out from the goalkeeper through the defense",
    "field": {
        "type": "HALF",
        "attacking_direction": "NORTH",
        "markings": True,
        "goals": 1
    },
    "players": [
        {"id": "GK", "role": "GOALKEEPER", "position": {"x": 50, "y": 95}},
        {"id": "D1", "role": "DEFENDER", "position": {"x": 30, "y": 85}},
        {"id": "D2", "role": "DEFENDER", "position": {"x": 70, "y": 85}},
        {"id": "A1", "role": "ATTACKER", "position": {"x": 50, "y": 70}},
        {"id": "A2", "role": "ATTACKER", "position": {"x": 35, "y": 55}},
        {"id": "A3", "role": "ATTACKER", "position": {"x": 65, "y": 55}}
    ],
    "cones": [],
    "cone_gates": [
        {"id": "G1", "center": {"x": 50, "y": 50}, "width": 20, "orientation": "HORIZONTAL"}
    ],
    "balls": [{"position": {"x": 50, "y": 95}}],
    "actions": [
        {"type": "PASS", "from_player": "GK", "to_player": "D1"},
        {"type": "PASS", "from_player": "D1", "to_player": "A1"},
        {"type": "PASS", "from_player": "A1", "to_player": "A2"},
        {"type": "DRIBBLE", "player": "A2", "to_position": {"x": 40, "y": 45}, "through_gate": "G1"}
    ],
    "coaching_points": [
        "Goalkeeper commands the build-up",
        "Center backs split wide",
        "Midfielder shows for the ball between lines"
    ],
    "variations": [
        "Add pressing attacker",
        "Play to opposite side"
    ]
}


CHAINED_ACTIONS_DEMO = {
    "name": "Chained Actions Demo",
    "description": "Demonstrates how actions chain together - pass starts from dribble end, not player start",
    "field": {
        "type": "HALF",
        "attacking_direction": "NORTH",
        "markings": True,
        "goals": 1
    },
    "players": [
        {"id": "A1", "role": "ATTACKER", "position": {"x": 30, "y": 50}},
        {"id": "A2", "role": "ATTACKER", "position": {"x": 70, "y": 50}},
    ],
    "cones": [],
    "cone_gates": [],
    "balls": [{"position": {"x": 30, "y": 50}}],
    "actions": [
        # A1 dribbles forward from (30,50) to (35,70)
        {"type": "DRIBBLE", "player": "A1", "to_position": {"x": 35, "y": 70}},
        # A2 runs into the box from (70,50) to (55,88)
        {"type": "RUN", "player": "A2", "to_position": {"x": 55, "y": 88}},
        # A1 passes to A2 - should go from (35,70) to (55,88), NOT from (30,50) to (70,50)
        {"type": "PASS", "from_player": "A1", "to_player": "A2"},
        # A2 shoots - should start from (55,88), NOT from (70,50)
        {"type": "SHOT", "player": "A2", "target": "GOAL"}
    ],
    "coaching_points": [
        "This drill demonstrates action chaining",
        "Notice how pass starts from end of dribble",
        "Notice how shot starts from end of run"
    ],
    "variations": []
}


GIVE_AND_GO = {
    "name": "Give and Go (Wall Pass)",
    "description": "Classic wall pass combination with proper action chaining",
    "field": {
        "type": "HALF",
        "attacking_direction": "NORTH",
        "markings": True,
        "goals": 1
    },
    "players": [
        {"id": "GK", "role": "GOALKEEPER", "position": {"x": 50, "y": 98}},
        {"id": "A1", "role": "ATTACKER", "position": {"x": 40, "y": 55}},
        {"id": "A2", "role": "ATTACKER", "position": {"x": 55, "y": 70}},
        {"id": "D1", "role": "DEFENDER", "position": {"x": 48, "y": 65}},
    ],
    "cones": [],
    "cone_gates": [],
    "balls": [{"position": {"x": 40, "y": 55}}],
    "actions": [
        # A1 dribbles toward defender
        {"type": "DRIBBLE", "player": "A1", "to_position": {"x": 45, "y": 62}},
        # A1 passes to A2 (wall player) - starts from dribble end
        {"type": "PASS", "from_player": "A1", "to_player": "A2"},
        # A1 runs behind defender into space
        {"type": "RUN", "player": "A1", "to_position": {"x": 52, "y": 82}},
        # A2 one-touch passes back to A1's new position
        {"type": "PASS", "from_player": "A2", "to_player": "A1"},
        # A1 shoots from new position
        {"type": "SHOT", "player": "A1", "target": "GOAL"}
    ],
    "coaching_points": [
        "Disguise the initial pass",
        "Accelerate into space after passing",
        "Wall player: one-touch pass into runner's path"
    ],
    "variations": [
        "Add second defender",
        "Vary starting positions"
    ]
}


# All fixtures in a dict for easy access
ALL_FIXTURES = {
    "passing_triangle": PASSING_TRIANGLE,
    "finishing_2v1": FINISHING_2V1,
    "dribble_through_gates": DRIBBLE_THROUGH_GATES,
    "crossing_and_finishing": CROSSING_AND_FINISHING,
    "rondo_4v2": RONDO_4V2,
    "build_from_back": BUILD_FROM_BACK,
    "chained_actions_demo": CHAINED_ACTIONS_DEMO,
    "give_and_go": GIVE_AND_GO,
}
