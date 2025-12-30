"""
Test script to verify the rendering pipeline works.
Run this directly: python test_render.py
Or hit the /api/test-drill endpoint
"""

# Test drill with known-good data
TEST_DRILL = {
    "name": "Test 2v1 Finishing",
    "description": "Two attackers combine against one defender",
    "field": {
        "type": "HALF",
        "attacking_direction": "NORTH",
        "markings": True,
        "goals": 1
    },
    "players": [
        {"id": "GK", "role": "GOALKEEPER", "position": {"x": 50, "y": 97}},
        {"id": "A1", "role": "ATTACKER", "position": {"x": 35, "y": 62}},
        {"id": "A2", "role": "ATTACKER", "position": {"x": 65, "y": 62}},
        {"id": "D1", "role": "DEFENDER", "position": {"x": 50, "y": 76}}
    ],
    "cones": [],
    "cone_gates": [],
    "mannequins": [],
    "balls": [{"position": {"x": 35, "y": 62}}],
    "actions": [
        {"type": "DRIBBLE", "player": "A1", "to_position": {"x": 42, "y": 74}},
        {"type": "RUN", "player": "A2", "to_position": {"x": 58, "y": 84}},
        {"type": "PASS", "from_player": "A1", "to_player": "A2"},
        {"type": "SHOT", "player": "A2", "target": "GOAL"}
    ],
    "coaching_points": ["Commit the defender", "Time the run"],
    "variations": ["One-touch finish"]
}

if __name__ == "__main__":
    import sys
    import os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'drill_system'))
    
    from drill_system.schema import Drill
    from drill_system.renderer import render
    
    print("Testing drill rendering...")
    print(f"Actions in test drill: {len(TEST_DRILL['actions'])}")
    
    # Validate
    drill = Drill.model_validate(TEST_DRILL)
    print(f"Validated drill: {drill.name}")
    print(f"Players: {[p.id for p in drill.players]}")
    print(f"Actions: {len(drill.actions)}")
    
    for i, action in enumerate(drill.actions):
        print(f"  Action {i+1}: {action}")
    
    # Render
    output_path = "/tmp/test_drill.svg"
    render(drill, output_path)
    
    # Check output
    with open(output_path, 'r') as f:
        svg_content = f.read()
    
    print(f"\nSVG generated: {len(svg_content)} bytes")
    print(f"Contains 'line': {'<line' in svg_content or 'path' in svg_content}")
    print(f"Contains 'polygon' (arrows): {'polygon' in svg_content}")
    
    print("\n✓ Test complete! Check /tmp/test_drill.svg")
