# Soccer Drill Generation System

A production-ready system for generating soccer training drills with AI-powered content and perfectly aligned diagram rendering.

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Set your OpenAI API key
export OPENAI_API_KEY='your-key-here'

# Generate a drill
python pipeline.py "Finishing under pressure" -p 6 -o drill.svg
```

## Features

- **AI-Powered Generation**: Uses OpenAI's structured output for reliable drill creation
- **Schema Validation**: Pydantic ensures all drills are structurally correct
- **Semantic Validation**: Verifies drills match their stated goals
- **SVG/PNG Rendering**: Clean, professional diagrams
- **Retry Logic**: Automatic retry on validation failures

## File Structure

```
drill_system/
├── __init__.py      # Clean exports for library usage
├── schema.py        # Pydantic models (Drill, Player, Action, etc.)
├── generator.py     # LLM integration with OpenAI
├── validator.py     # Structural and semantic validation
├── renderer.py      # SVG/PNG diagram generation
├── pipeline.py      # Complete end-to-end workflow + CLI
├── fixtures.py      # Example drills for testing
├── tests.py         # Test suite
└── requirements.txt
```

## Usage

### CLI Usage

```bash
# Basic drill
python pipeline.py "Passing combinations" -p 6 -o passing.svg

# With constraints
python pipeline.py "2v1 finishing" -p 4 --attackers 2 --defenders 1 --gk -o finishing.svg

# Full field drill
python pipeline.py "Possession game" -p 10 --full-field -o possession.svg

# Save JSON for later
python pipeline.py "Crossing drill" -p 6 -o cross.svg --json cross.json

# Render from existing JSON
python pipeline.py --from-json cross.json -o cross_v2.svg
```

### Library Usage

```python
from drill_system import DrillPipeline

# Initialize pipeline
pipeline = DrillPipeline()

# Generate a drill
result = pipeline.generate(
    goal="Finishing under pressure",
    num_players=6,
    has_goalkeeper=True,
    output_svg="drill.svg",
    output_json="drill.json"
)

# Access the drill
print(result.drill.name)
print(result.drill.description)

for point in result.drill.coaching_points:
    print(f"- {point}")

# Check validation
if not result.is_valid:
    print("Errors:", result.errors)
print("Warnings:", result.warnings)
```

### Manual Drill Creation

```python
from drill_system import (
    Drill, Player, Position, Ball, PassAction, 
    PlayerRole, render
)

drill = Drill(
    name="Simple Passing",
    description="Two players passing back and forth",
    players=[
        Player(id="A1", role=PlayerRole.ATTACKER, position=Position(x=30, y=50)),
        Player(id="A2", role=PlayerRole.ATTACKER, position=Position(x=70, y=50)),
    ],
    balls=[Ball(position=Position(x=30, y=50))],
    actions=[
        PassAction(from_player="A1", to_player="A2"),
        PassAction(from_player="A2", to_player="A1"),
    ],
    coaching_points=["Weight of pass", "Open body position"]
)

render(drill, "simple_passing.svg")
```

## Coordinate System

The field uses normalized 0-100 coordinates:

```
        0   10   20   30   40   50   60   70   80   90  100  (X)
  100  ┌────────────────────────────────────────────────────┐
       │                    ┌──GOAL──┐                      │  
   90  │              ┌─────┴────────┴─────┐                │  
       │              │     6-YARD BOX     │                │  
   80  │        ┌─────┴────────────────────┴─────┐          │  
       │        │         18-YARD BOX            │          │
   70  │        │                                │          │
       │        └────────────────────────────────┘          │
   50  ├────────────────── HALFWAY LINE ────────────────────┤
       │                                                    │
   30  │                                                    │
       │                                                    │
   10  │                                                    │
    0  └────────────────────────────────────────────────────┘
  (Y)
```

**Attacking NORTH** (default): Goal at y=100, penalty spot at y=88
**Attacking SOUTH**: Goal at y=0, penalty spot at y=12

## JSON Schema

Drills are defined in JSON matching this structure:

```json
{
  "name": "Drill Name",
  "description": "What this drill practices",
  "field": {
    "type": "HALF",
    "attacking_direction": "NORTH",
    "markings": true,
    "goals": 1
  },
  "players": [
    {
      "id": "A1",
      "role": "ATTACKER",
      "position": {"x": 50, "y": 60}
    }
  ],
  "balls": [
    {"position": {"x": 50, "y": 60}}
  ],
  "cone_gates": [
    {
      "id": "G1",
      "center": {"x": 50, "y": 50},
      "width": 8,
      "orientation": "HORIZONTAL"
    }
  ],
  "actions": [
    {"type": "PASS", "from_player": "A1", "to_player": "A2"},
    {"type": "RUN", "player": "A3", "to_position": {"x": 60, "y": 85}},
    {"type": "DRIBBLE", "player": "A1", "to_position": {"x": 50, "y": 80}},
    {"type": "SHOT", "player": "A2", "target": "GOAL"}
  ],
  "coaching_points": [
    "Point 1",
    "Point 2"
  ],
  "variations": [
    "Add a defender"
  ]
}
```

## Validation

The system performs multiple levels of validation:

### Structural Validation
- All positions within bounds (0-100)
- Player spacing (minimum 3 units apart)
- Goalkeeper positioned near goal
- Ball placed with a player

### Reference Validation
- All player IDs in actions exist
- All cone gate IDs in dribbles exist

### Semantic Validation
- Finishing drills have SHOT actions
- Passing drills have multiple PASS actions
- Dribbling drills have DRIBBLE actions
- Crossing drills have wide players

### Ball Tracking
- Verifies correct player has ball before passing
- Tracks possession through action sequence

## Testing

Run the test suite without API calls:

```bash
python tests.py
```

This validates:
- Schema parsing
- Structural validation
- Semantic validation
- SVG rendering
- JSON round-trip

## API Reference

### DrillPipeline

```python
DrillPipeline(api_key=None, model="gpt-4o-mini")
```

**Methods:**
- `generate(goal, num_players, ...) -> PipelineResult`
- `generate_from_json(json_path, output_svg) -> PipelineResult`

### PipelineResult

**Properties:**
- `drill: Drill` - The generated drill
- `validation: ValidationResult` - Validation results
- `is_valid: bool` - True if no errors
- `errors: List[str]` - Error messages
- `warnings: List[str]` - Warning messages
- `svg_path: Optional[str]` - Path to SVG if generated
- `json_path: Optional[str]` - Path to JSON if saved

### Drill

**Fields:**
- `name: str`
- `description: str`
- `field: FieldConfig`
- `players: List[Player]`
- `cones: List[Cone]`
- `cone_gates: List[ConeGate]`
- `balls: List[Ball]`
- `actions: List[Action]`
- `coaching_points: List[str]`
- `variations: List[str]`

## Integration with Your App

For your coaching app, you'll want to:

1. **Create a form** for coach input (player count, goal, constraints)
2. **Call the pipeline** to generate the drill
3. **Display both** the text description and SVG diagram
4. **Allow edits** by modifying the JSON and re-rendering

```python
# Example integration
from drill_system import DrillPipeline

def create_drill_for_coach(form_data):
    pipeline = DrillPipeline()
    
    result = pipeline.generate(
        goal=form_data["goal"],
        num_players=form_data["player_count"],
        has_goalkeeper=form_data.get("has_gk", False),
        has_cones=form_data.get("has_cones", True),
        age_group=form_data.get("age_group"),
        skill_level=form_data.get("skill_level"),
        output_svg=f"drills/{uuid4()}.svg",
        output_json=f"drills/{uuid4()}.json"
    )
    
    return {
        "name": result.drill.name,
        "description": result.drill.description,
        "coaching_points": result.drill.coaching_points,
        "variations": result.drill.variations,
        "svg_url": result.svg_path,
        "is_valid": result.is_valid,
        "warnings": result.warnings
    }
```

## License

MIT
