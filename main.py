"""
Soccer Drill Generator API

FastAPI backend that:
1. Receives drill requests from frontend
2. Calls Claude API to generate drill JSON + description
3. Renders the drill to SVG
4. Returns SVG + description to frontend
5. Serves drill library (pre-approved drills)
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
import anthropic
import tempfile
import base64
import json
import os
import sys
import random
from pathlib import Path

# Add drill_system to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'drill_system'))

from drill_system.schema import Drill
from drill_system.renderer import render

# Library file path (in same directory as main.py)
LIBRARY_FILE = Path(__file__).parent / "library_drills.json"

# ============================================================
# FASTAPI APP SETUP
# ============================================================

app = FastAPI(
    title="Soccer Drill Generator API",
    description="Generate soccer training drills with AI",
    version="1.0.0"
)

# CORS - Allow Lovable frontend to connect
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://*.lovable.app",
        "https://*.lovableproject.com",
        "http://localhost:3000",
        "http://localhost:5173",
        "*"  # For development - restrict in production
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================
# REQUEST/RESPONSE MODELS
# ============================================================

class DrillRequest(BaseModel):
    """Request from frontend to generate a drill"""
    # Core requirement
    prompt: str = Field(..., description="Natural language drill request", min_length=5)
    
    # Player configuration
    num_players: int = Field(default=6, ge=2, le=30, description="Total number of players")
    num_goalkeepers: int = Field(default=0, ge=0, le=4, description="Number of goalkeepers")
    include_goalkeeper: bool = Field(default=True)  # Legacy support
    
    # Equipment
    num_goals: int = Field(default=1, ge=0, le=2, description="Number of goals to use")
    has_cones: bool = Field(default=True)
    has_mannequins: bool = Field(default=False)
    num_balls: Optional[int] = Field(default=None, ge=1, description="Number of balls")
    
    # Field configuration
    field_type: str = Field(default="HALF", pattern="^(HALF|FULL)$")
    field_size: Optional[str] = Field(default=None, description="Descriptive field size")
    
    # Player details
    age_group: Optional[str] = Field(default=None, description="e.g., U12, College, Professional")
    skill_level: Optional[str] = Field(default=None, pattern="^(beginner|intermediate|advanced)$")
    
    # Session details  
    intensity: Optional[str] = Field(default=None, description="Low, Medium, High, Variable")
    duration_minutes: Optional[int] = Field(default=None, ge=5, le=120, description="Drill duration")
    
    # Drill categorization
    drill_type: Optional[str] = Field(default=None, description="e.g., Finishing, Passing, Defensive")
    
    # Additional context
    additional_notes: Optional[str] = Field(default=None, description="Any extra requirements")


class DrillResponse(BaseModel):
    """Response containing generated drill"""
    success: bool
    drill_name: str
    svg: str  # Base64 encoded SVG
    description: str  # Markdown coach description
    drill_json: dict  # Raw drill JSON for debugging/storage
    error: Optional[str] = None


class HealthResponse(BaseModel):
    """Health check response"""
    status: str
    version: str


# ============================================================
# DRILL LIBRARY - Models and Helpers
# ============================================================

class LibraryDrill(BaseModel):
    """A drill in the library"""
    id: str
    name: str
    description: str
    category: Optional[str] = None
    setup: Optional[str] = None
    instructions: Optional[str] = None
    variations: Optional[str] = None
    coaching_points: Optional[str] = None
    age_group: Optional[str] = None
    player_count: Optional[str] = None
    duration: Optional[str] = None
    difficulty: Optional[str] = None
    drill_json: Dict[str, Any]  # The diagram data
    source_url: Optional[str] = None
    source_site: Optional[str] = None


class LibraryDrillResponse(BaseModel):
    """Single drill with rendered SVG"""
    success: bool
    drill: LibraryDrill
    svg: str  # Base64 encoded SVG (rendered on-demand)


class LibraryListResponse(BaseModel):
    """List of drills in library"""
    success: bool
    count: int
    drills: List[Dict[str, Any]]  # Drill metadata without SVG


def load_library() -> List[Dict]:
    """Load drill library from JSON file"""
    if not LIBRARY_FILE.exists():
        return []
    try:
        with open(LIBRARY_FILE, 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"[LIBRARY] Error loading library: {e}")
        return []


def render_drill_to_svg(drill_json: Dict) -> str:
    """Render drill JSON to base64 SVG"""
    # Ensure required fields
    drill_json.setdefault("cones", [])
    drill_json.setdefault("cone_gates", [])
    drill_json.setdefault("mannequins", [])
    drill_json.setdefault("coaching_points", [])
    drill_json.setdefault("variations", [])
    
    drill = Drill.model_validate(drill_json)
    
    with tempfile.NamedTemporaryFile(suffix=".svg", delete=False) as f:
        svg_path = f.name
    
    render(drill, svg_path)
    
    with open(svg_path, 'r') as f:
        svg_content = f.read()
    
    os.unlink(svg_path)
    
    return base64.b64encode(svg_content.encode()).decode()


# ============================================================
# LIBRARY API ENDPOINTS
# ============================================================

@app.get("/api/library", response_model=LibraryListResponse)
async def get_library(
    category: Optional[str] = None,
    limit: int = 100
):
    """
    Get list of all drills in the library.
    
    Returns metadata only (no SVG) for fast loading.
    Use /api/library/{id} to get full drill with rendered SVG.
    """
    drills = load_library()
    
    # Filter by category if specified
    if category:
        drills = [d for d in drills if d.get('category', '').lower() == category.lower()]
    
    # Limit results
    drills = drills[:limit]
    
    # Return metadata only (exclude drill_json to keep response light)
    drill_summaries = []
    for d in drills:
        summary = {
            "id": d.get("id"),
            "name": d.get("name"),
            "description": d.get("description", ""),
            "category": d.get("category"),
            "age_group": d.get("age_group"),
            "player_count": d.get("player_count"),
            "duration": d.get("duration"),
            "difficulty": d.get("difficulty"),
        }
        drill_summaries.append(summary)
    
    return LibraryListResponse(
        success=True,
        count=len(drill_summaries),
        drills=drill_summaries
    )


@app.get("/api/library/{drill_id}")
async def get_library_drill(drill_id: str):
    """
    Get a specific drill from the library with freshly rendered SVG.
    
    SVG is rendered on-demand using the current renderer.py,
    so changes to the renderer are reflected immediately.
    """
    drills = load_library()
    
    # Find the drill
    drill_data = None
    for d in drills:
        if d.get("id") == drill_id:
            drill_data = d
            break
    
    if not drill_data:
        raise HTTPException(status_code=404, detail=f"Drill {drill_id} not found")
    
    # Check if it has diagram data
    drill_json = drill_data.get("drill_json")
    if not drill_json:
        raise HTTPException(status_code=400, detail=f"Drill {drill_id} has no diagram data")
    
    try:
        # Render SVG on-demand
        svg_base64 = render_drill_to_svg(drill_json)
        
        return {
            "success": True,
            "drill": drill_data,
            "svg": svg_base64
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error rendering drill: {str(e)}")


@app.get("/api/library/categories/list")
async def get_library_categories():
    """Get list of all categories in the library"""
    drills = load_library()
    
    categories = set()
    for d in drills:
        cat = d.get("category")
        if cat:
            categories.add(cat)
    
    return {
        "success": True,
        "categories": sorted(list(categories))
    }




# Tool definition for structured output
DRILL_TOOL = {
    "name": "create_drill",
    "description": "Create a complete soccer drill with diagram data and coaching description",
    "input_schema": {
        "type": "object",
        "properties": {
            "drill": {
                "type": "object",
                "description": "The drill definition for rendering the diagram",
                "properties": {
                    "name": {"type": "string", "description": "Name of the drill"},
                    "description": {"type": "string", "description": "Brief description"},
                    "field": {
                        "type": "object",
                        "properties": {
                            "type": {"type": "string", "enum": ["HALF", "FULL"]},
                            "attacking_direction": {"type": "string", "enum": ["NORTH", "SOUTH"]},
                            "markings": {"type": "boolean"},
                            "goals": {"type": "integer", "enum": [0, 1, 2]}
                        },
                        "required": ["type", "attacking_direction", "markings", "goals"]
                    },
                    "players": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "id": {"type": "string", "pattern": "^[A-Z]+[0-9]*$"},
                                "role": {"type": "string", "enum": ["ATTACKER", "DEFENDER", "GOALKEEPER", "NEUTRAL"]},
                                "position": {
                                    "type": "object",
                                    "properties": {
                                        "x": {"type": "number", "minimum": 0, "maximum": 100},
                                        "y": {"type": "number", "minimum": 0, "maximum": 100}
                                    },
                                    "required": ["x", "y"]
                                }
                            },
                            "required": ["id", "role", "position"]
                        }
                    },
                    "cones": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "position": {
                                    "type": "object",
                                    "properties": {
                                        "x": {"type": "number"},
                                        "y": {"type": "number"}
                                    },
                                    "required": ["x", "y"]
                                }
                            }
                        }
                    },
                    "cone_gates": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "id": {"type": "string"},
                                "center": {
                                    "type": "object",
                                    "properties": {
                                        "x": {"type": "number"},
                                        "y": {"type": "number"}
                                    }
                                },
                                "width": {"type": "number"},
                                "orientation": {"type": "string", "enum": ["HORIZONTAL", "VERTICAL"]}
                            }
                        }
                    },
                    "mannequins": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "id": {"type": "string"},
                                "position": {
                                    "type": "object",
                                    "properties": {
                                        "x": {"type": "number"},
                                        "y": {"type": "number"}
                                    }
                                }
                            }
                        }
                    },
                    "balls": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "position": {
                                    "type": "object",
                                    "properties": {
                                        "x": {"type": "number"},
                                        "y": {"type": "number"}
                                    }
                                }
                            }
                        }
                    },
                    "actions": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "type": {"type": "string", "enum": ["PASS", "RUN", "DRIBBLE", "SHOT"]},
                                "player": {"type": "string"},
                                "from_player": {"type": "string"},
                                "to_player": {"type": "string"},
                                "to_position": {
                                    "type": "object",
                                    "properties": {
                                        "x": {"type": "number"},
                                        "y": {"type": "number"}
                                    }
                                },
                                "target": {"type": "string"}
                            },
                            "required": ["type"]
                        }
                    },
                    "coaching_points": {"type": "array", "items": {"type": "string"}},
                    "variations": {"type": "array", "items": {"type": "string"}}
                },
                "required": ["name", "description", "field", "players", "balls", "actions"]
            },
            "coach_description": {
                "type": "string",
                "description": "COMPREHENSIVE markdown coaching document (1000+ words) that a coach can use to run the drill WITHOUT the diagram. MUST include: Overview, detailed Setup (field configuration with specific dimensions, ALL player starting positions with exact locations, ALL equipment with placement), 'How to Run the Drill' section with NUMBERED STEPS matching EACH action in the actions array (if 5 actions, 5 numbered steps), Reset & Rotation instructions, 5+ Coaching Points, Progressions table, Common Mistakes table. The step-by-step instructions are CRITICAL - each step must name the player ID and describe exactly what they do (e.g., 'A1 passes to A2 at the top of the box')."
            }
        },
        "required": ["drill", "coach_description"]
    }
}

SYSTEM_PROMPT = """You are an expert soccer coach and drill designer with decades of experience at professional academies. When asked to create a drill, you MUST use the create_drill tool to return a structured response.

Your drills should be practical, well-organized, and match what a real coach would design. The diagram and description must match perfectly.

## RESOURCE USAGE (IMPORTANT)

The coach will specify AVAILABLE resources (players, goals, cones, etc.). These are MAXIMUM limits, not requirements:
- You do NOT need to use all available players - use what makes sense for the drill
- Many drills work better with fewer active players and a queue/line (e.g., 3-4 active, rest waiting)
- However, you CANNOT use resources that aren't available
- If goals = 0, do NOT include any goals or SHOT actions
- If cones are not available, do NOT include cones
- If mannequins are not available, do NOT include mannequins

Design the BEST drill for the training goal, not the drill that uses the most resources.

## COORDINATE SYSTEM (CRITICAL - READ CAREFULLY)

The field uses a 0-100 coordinate system for BOTH x and y:
- x-axis: 0 = left touchline, 50 = center, 100 = right touchline
- y-axis: 0 = bottom of diagram, 100 = top of diagram

### When attacking NORTH (default, goal at top):
| Location | Coordinates |
|----------|-------------|
| Attacking goal center | (50, 100) |
| Goalkeeper position | (50, 97) |
| Penalty spot | (50, 88) |
| Top of 18-yard box | y = 82 |
| Top of 6-yard box | y = 94 |
| Left post | (44, 100) |
| Right post | (56, 100) |
| 18-yard box left edge | x = 30 |
| 18-yard box right edge | x = 70 |
| Center circle | (50, 50) |
| Halfway line | y = 50 |

### HALF FIELD IMPORTANT:
When field.type = "HALF" and goals = 1:
- ONLY the attacking half is shown (y = 50 to y = 100 when attacking NORTH)
- ALL players must be positioned with y >= 50
- Place players between y=55 and y=95 for good visibility
- DO NOT place any player below y=50 - they will be cut off!

### FULL FIELD:
When field.type = "FULL":
- The entire field is shown (y = 0 to y = 100)
- You can place players anywhere

## PLAYER CONFIGURATION

### Roles and Colors:
- ATTACKER: Red circles - offensive players
- DEFENDER: Blue circles - defensive players  
- GOALKEEPER: Yellow circle - always position near goal line
- NEUTRAL: Orange circles - servers, support players, resting players

### ID Conventions:
- Attackers: A1, A2, A3, A4...
- Defenders: D1, D2, D3...
- Goalkeeper: GK
- Neutral/Servers: N1, N2...

## ACTIONS - HOW THEY WORK

### PASS (white solid arrow)
Ball travels from one player to another.
```json
{"type": "PASS", "from_player": "A1", "to_player": "A2"}
```

### RUN (yellow dashed arrow)
Player moves WITHOUT the ball - off-ball movement, making runs.
```json
{"type": "RUN", "player": "A2", "to_position": {"x": 55, "y": 85}}
```

### DRIBBLE (white wavy line)
Player moves WITH the ball.
```json
{"type": "DRIBBLE", "player": "A1", "to_position": {"x": 45, "y": 75}}
```

### SHOT (red arrow toward goal)
Shot on goal from current position.
```json
{"type": "SHOT", "player": "A2", "target": "GOAL"}
```

## CRITICAL: ACTION CHAINING

Actions execute in sequence. Each action starts from where the player CURRENTLY is, not their starting position.

Example sequence:
1. A1 starts at (30, 60)
2. A1 DRIBBLES to (40, 75) → A1 is now at (40, 75)
3. A2 RUNS from (60, 60) to (55, 85) → A2 is now at (55, 85)
4. A1 PASSES to A2 → Arrow goes from (40, 75) to (55, 85)
5. A2 SHOOTS → Arrow goes from (55, 85) toward goal

The renderer tracks positions automatically - just put actions in the right order.

## FIELD CONFIGURATION

```json
"field": {
    "type": "HALF",           // "HALF" or "FULL"
    "attacking_direction": "NORTH",  // Always use "NORTH"
    "markings": true,         // Show field lines
    "goals": 1                // 0, 1, or 2
}
```

**Rules:**
- goals = 0: No goal markings (rondos, possession drills)
- goals = 1: Attacking goal only (finishing, shooting drills)
- goals = 2: Both goals (full scrimmages, transition drills)
- When HALF field with goals=1, only attacking half (y >= 50) is visible

## EQUIPMENT

### Cones (orange triangles):
```json
"cones": [
    {"position": {"x": 30, "y": 60}},
    {"position": {"x": 50, "y": 60}}
]
```

### Cone Gates (pairs of cones):
```json
"cone_gates": [
    {"id": "G1", "center": {"x": 50, "y": 70}, "width": 8, "orientation": "HORIZONTAL"}
]
```
- HORIZONTAL: cones side by side (for dribbling through)
- VERTICAL: cones top/bottom (for passing through)

### Mannequins (dark gray dummies):
```json
"mannequins": [
    {"id": "M1", "position": {"x": 45, "y": 70}},
    {"id": "M2", "position": {"x": 55, "y": 78}}
]
```

### Balls:
Place at the starting player's position:
```json
"balls": [{"position": {"x": 35, "y": 65}}]
```

---

## COMPLETE EXAMPLE 1: 2v1 Finishing Drill

**Request:** "2v1 finishing with combination play"

```json
{
    "name": "2v1 Combination Finish",
    "description": "Two attackers combine against one defender to create a shooting opportunity",
    "field": {
        "type": "HALF",
        "attacking_direction": "NORTH",
        "markings": true,
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
    "coaching_points": [
        "A1 must commit the defender before releasing the pass",
        "A2 times the run to stay onside while finding space",
        "Pass should be weighted to arrive ahead of A2's run",
        "Finish low and across the goalkeeper to the far corner"
    ],
    "variations": [
        "Require one-touch finish",
        "Add second defender",
        "Start from different angles"
    ]
}
```

---

## COMPLETE EXAMPLE 2: Passing Rondo (No Goals)

**Request:** "4v2 possession rondo"

```json
{
    "name": "4v2 Possession Rondo",
    "description": "Four attackers keep possession against two defenders in a tight space",
    "field": {
        "type": "HALF",
        "attacking_direction": "NORTH",
        "markings": false,
        "goals": 0
    },
    "players": [
        {"id": "A1", "role": "ATTACKER", "position": {"x": 35, "y": 35}},
        {"id": "A2", "role": "ATTACKER", "position": {"x": 65, "y": 35}},
        {"id": "A3", "role": "ATTACKER", "position": {"x": 35, "y": 65}},
        {"id": "A4", "role": "ATTACKER", "position": {"x": 65, "y": 65}},
        {"id": "D1", "role": "DEFENDER", "position": {"x": 45, "y": 50}},
        {"id": "D2", "role": "DEFENDER", "position": {"x": 55, "y": 50}}
    ],
    "cones": [
        {"position": {"x": 30, "y": 30}},
        {"position": {"x": 70, "y": 30}},
        {"position": {"x": 30, "y": 70}},
        {"position": {"x": 70, "y": 70}}
    ],
    "cone_gates": [],
    "mannequins": [],
    "balls": [{"position": {"x": 35, "y": 35}}],
    "actions": [
        {"type": "PASS", "from_player": "A1", "to_player": "A2"},
        {"type": "PASS", "from_player": "A2", "to_player": "A4"},
        {"type": "PASS", "from_player": "A4", "to_player": "A3"},
        {"type": "PASS", "from_player": "A3", "to_player": "A1"}
    ],
    "coaching_points": [
        "Receive across your body to open up passing angles",
        "Keep the ball moving - don't hold it too long",
        "Body position open to see all teammates",
        "Communicate with teammates"
    ],
    "variations": [
        "Two-touch maximum",
        "One-touch only",
        "Add a third defender",
        "Score by splitting the defenders with a pass"
    ]
}
```

---

## COMPLETE EXAMPLE 3: Overlap and Cross

**Request:** "Wing play with overlapping fullback"

```json
{
    "name": "Overlap and Cross",
    "description": "Winger and fullback combine with an overlapping run to deliver a cross",
    "field": {
        "type": "HALF",
        "attacking_direction": "NORTH",
        "markings": true,
        "goals": 1
    },
    "players": [
        {"id": "GK", "role": "GOALKEEPER", "position": {"x": 50, "y": 97}},
        {"id": "A1", "role": "ATTACKER", "position": {"x": 25, "y": 58}},
        {"id": "A2", "role": "ATTACKER", "position": {"x": 18, "y": 65}},
        {"id": "A3", "role": "ATTACKER", "position": {"x": 50, "y": 70}},
        {"id": "D1", "role": "DEFENDER", "position": {"x": 28, "y": 78}}
    ],
    "cones": [],
    "cone_gates": [],
    "mannequins": [],
    "balls": [{"position": {"x": 25, "y": 58}}],
    "actions": [
        {"type": "PASS", "from_player": "A1", "to_player": "A2"},
        {"type": "RUN", "player": "A1", "to_position": {"x": 15, "y": 90}},
        {"type": "DRIBBLE", "player": "A2", "to_position": {"x": 25, "y": 76}},
        {"type": "RUN", "player": "A3", "to_position": {"x": 50, "y": 88}},
        {"type": "PASS", "from_player": "A2", "to_player": "A1"},
        {"type": "PASS", "from_player": "A1", "to_player": "A3"},
        {"type": "SHOT", "player": "A3", "target": "GOAL"}
    ],
    "coaching_points": [
        "A1 must time the overlap - not too early or defender recovers",
        "A2 drives inside to draw the defender before releasing",
        "A3 attacks the near post area with a late run",
        "Cross should be driven low between GK and defenders"
    ],
    "variations": [
        "Add a far post runner",
        "Cutback option instead of cross",
        "Add a second defender",
        "Run the drill from the right side"
    ]
}
```

---

## COACH DESCRIPTION FORMAT (CRITICAL - FOLLOW EXACTLY)

The coach_description field must be a comprehensive, professional coaching document that a coach can use to run the drill WITHOUT looking at the diagram. This is essential - the description must be complete and standalone.

Write in a warm, professional tone as if you're an experienced coach explaining to another coach. Be specific, practical, and actionable.

### REQUIRED STRUCTURE:

```markdown
# [Drill Name]

## Overview
[2-3 sentences describing the drill purpose, what it develops, and why it's effective. Write naturally, not in bullet points.]

**Players:** [X] (including [Y] goalkeeper(s))  
**Duration:** [X-Y] minutes  
**Intensity:** [Low/Medium/High]  
**Focus:** [Main skills being developed]

---

## Setup

### Field Configuration
[Describe the field setup completely - field size (half/full), where goals are positioned, any zones or areas marked with cones. A coach reading this should be able to set up the field without the diagram.]

### Starting Positions
Describe where EVERY player starts with specific locations:
- **[Player ID]** starts [specific location - e.g., "on the left side of the field, 10 yards outside the 18-yard box"]
- **[Player ID]** starts [specific location]
- Continue for ALL players in the drill...

### Equipment Needed
- [X] balls (specify where they're placed)
- [X] cones (describe exactly where each cone goes)
- [X] goals (specify full-size, mini-goals, etc.)
- [Any other equipment]
- Bibs: [specify colors for different roles]

---

## How to Run the Drill (CRITICAL SECTION)

### Step-by-Step Instructions
THIS SECTION MUST MATCH THE ACTIONS IN THE DIAGRAM EXACTLY. Walk through every single action:

1. **[Player ID] [specific action with detail]** — [Player] starts with the ball and [passes to/dribbles toward/runs to] [destination/target player]. [Add coaching context: what to look for, timing cues, technique focus]

2. **[Player ID] [specific action with detail]** — After receiving, [Player] [next action]. [Coaching context]

3. **[Continue numbering EVERY action in the diagram...]**

4. **The drill ends when [final action - usually a shot or final pass]**

IMPORTANT: Each numbered step must correspond to one action arrow in the diagram. If there are 5 action arrows, there should be 5 numbered steps. Use player IDs (A1, A2, D1, GK, etc.) consistently.

### Reset & Rotation
[Explain exactly how players reset to starting positions, who rotates where, and how quickly the drill should restart. Include rest periods if applicable.]

---

## Coaching Points

Focus on these key teaching points during the drill:

1. **[Technical Point]:** [Detailed explanation of the technique - what good execution looks like, common errors, and corrections]

2. **[Tactical Point]:** [Explain the game understanding aspect - when/why players make certain decisions]

3. **[Movement Point]:** [Timing, angles, body position details]

4. **[Communication Point]:** [What players should be calling out]

5. **[Intensity Point]:** [Expectations for effort, tempo, competitiveness]

---

## Progressions

Start simple and add complexity as players master each level:

| Level | Progression | When to Advance |
|-------|-------------|-----------------|
| 1 | [Base drill as described] | When players complete 5 successful reps |
| 2 | [First progression - add constraint or defender] | When success rate hits 70% |
| 3 | [Second progression - increase difficulty] | When players are comfortable |
| 4 | [Game-realistic version] | To finish the session |

---

## Common Mistakes & Corrections

Watch for these issues and use these corrections:

| Mistake | What You'll See | Correction |
|---------|----------------|------------|
| [Mistake 1] | [Observable behavior] | [Specific coaching intervention] |
| [Mistake 2] | [Observable behavior] | [Specific coaching intervention] |
| [Mistake 3] | [Observable behavior] | [Specific coaching intervention] |

---

## Coaching Tips

- [Practical tip for running this drill effectively]
- [How to keep energy high]
- [What to watch for as the coach]
```

### EXAMPLE OF GOOD COACH DESCRIPTION:

Here's an example of the quality and detail expected:

```markdown
# 2v1 Finishing with Overlap

## Overview
This drill develops combination play and finishing in 2v1 situations. Players learn to commit defenders, time supporting runs, and finish under pressure. It's a high-tempo drill that simulates real game attacking scenarios in the final third.

**Players:** 4 (including 1 goalkeeper)  
**Duration:** 12-15 minutes  
**Intensity:** High  
**Focus:** Combination play, finishing, decision-making, movement off the ball

---

## Setup

### Field Configuration
Use half a field with a full-size goal. The drill takes place in and around the penalty area, giving players realistic distances and angles for finishing.

### Starting Positions
- **GK** starts on the goal line, ready to face shots from various angles
- **A1** (attacker with ball) starts on the left side, about 10 yards outside the 18-yard box with the ball at their feet
- **A2** (supporting attacker) starts centrally, level with A1, ready to make a run
- **D1** (defender) starts between the attackers and goal, positioned to delay the attack

### Equipment Needed
- 6-8 balls (placed behind A1's starting position for quick restarts)
- 4 cones to mark starting positions
- Bibs: red for attackers, blue for defender

---

## How to Run the Drill

### Step-by-Step Instructions

1. **A1 dribbles toward D1** — A1 starts with the ball at their feet and drives directly at the defender. The goal is to force D1 to commit - A1 should attack D1's front shoulder at pace, not slowly approach. Look for A1 keeping the ball on their back foot, ready to release the pass.

2. **A2 makes a curved run behind D1** — As A1 engages the defender, A2 times their run to arc around and behind D1 into the space between the defender and goal. A2 should start the run when A1 is about 5 yards from D1. The run should curve from central to wide-to-central, staying onside.

3. **A1 passes to A2** — Once D1 commits (shows their hips toward A1), A1 plays a firm pass into A2's path. The pass should lead A2 toward goal, not to their feet. Use the inside of the foot for accuracy.

4. **A2 shoots on goal** — A2 takes a touch to set the ball, then finishes into the far corner. Emphasize composure - A2 should pick their spot before shooting, aiming low and across the goalkeeper.

### Reset & Rotation
After each rep:
- A1 and A2 jog back to their starting positions
- The next pair (if using multiple groups) steps up immediately
- Keep rest to 30-45 seconds maximum to maintain intensity
- Rotate D1 every 4-5 reps to prevent fatigue
- Balls should be staged behind A1's starting position for quick restarts

---

## Coaching Points

Focus on these key teaching points:

1. **Commit the Defender:** A1 must drive at D1 with enough conviction to force a decision. If A1 is passive, D1 can cover both attacker and passing lane. Look for A1 attacking D1's front shoulder.

2. **Timing of the Run:** A2's run is everything. Watch for players who run too early (offside or easily tracked) or too late (chance gone). The trigger is when A1 drops their shoulder to engage the defender.

3. **Pass Weight:** The pass should arrive in A2's stride, not behind them or too far ahead. A1 should play the ball with the inside of the foot for accuracy, not power.

4. **Finishing Composure:** Under pressure, players often snatch at shots. Remind A2 to take a breath, pick a corner, and stroke the ball. Accuracy beats power.

5. **Body Shape on Finish:** A2 should open their body to see the goal before receiving. This allows a first-time finish or a clean touch into shooting position.

---

## Progressions

| Level | Progression | When to Advance |
|-------|-------------|-----------------|
| 1 | Passive defender (50% pressure) | After 3-4 successful combinations |
| 2 | Active defender at full speed | When attackers are timing runs well |
| 3 | Add a second defender who starts deeper | When success rate is above 60% |
| 4 | Require one-touch finish only | To increase urgency and tempo |

---

## Common Mistakes & Corrections

| Mistake | What You'll See | Correction |
|---------|----------------|------------|
| Pass too early | A1 passes before D1 commits, defender intercepts | "Wait for the defender to show you their hips, then play" |
| Run too flat | A2 runs straight, stays in D1's cover shadow | "Curve your run - start wide, finish central" |
| Shooting high | A2 leans back, ball flies over bar | "Get over the ball, land on your shooting foot" |
| Poor first touch | A2's touch goes under feet or too wide | "Touch into space toward the goal, not sideways" |

---

## Coaching Tips

- Stand where you can see both the combination and the finish - usually near the corner of the 18-yard box
- Give immediate feedback after each rep - one coaching point only
- Celebrate good combinations even when the finish misses - reinforce the process
- If energy drops, add competition: "Next goal wins" or "Attackers vs defenders - who gets more?"
```

IMPORTANT: Your coach_description must be this detailed and professional. Do not write short, generic descriptions. Coaches need specific, actionable guidance they can use immediately on the field.

CRITICAL REQUIREMENT: The "How to Run the Drill" section must have one numbered step for EACH action in your actions array. If you have 6 actions (e.g., dribble, pass, run, pass, dribble, shot), you must have 6 numbered steps explaining each one. A coach should be able to run this drill using ONLY the text description, without ever seeing the diagram.

---

## FINAL CHECKLIST BEFORE RESPONDING

Before returning your response, verify:

1. ☐ All players have y >= 50 if using HALF field with goals
2. ☐ Ball position matches the starting player's position
3. ☐ Actions are in logical sequence (pass after player has ball, etc.)
4. ☐ Player IDs in actions match player IDs in players array
5. ☐ GK is positioned near y=97 if included
6. ☐ Players are spread out reasonably (not on top of each other)
7. ☐ The description sequence matches the actions array exactly
8. ☐ Coaching points are specific and actionable, not generic

Remember: The diagram and description will be shown side by side. They MUST match perfectly.
"""


def get_reference_drills(category: Optional[str], num_examples: int = 2) -> List[Dict]:
    """
    Get reference drills - first try curated gold standards, then fall back to library.
    
    Args:
        category: Drill category (e.g., "Finishing", "Possession")
        num_examples: Number of examples to return (1-3)
    
    Returns:
        List of drill dictionaries with setup, instructions, and drill_json
    """
    # First, check if we have curated examples for this category
    curated = CURATED_EXAMPLES.get(category.lower() if category else '', [])
    
    if curated:
        # Use curated examples (they're already high quality)
        return curated[:num_examples]
    
    # Fall back to library
    library = load_library()
    
    if not library:
        return []
    
    # Filter by category if specified
    if category:
        category_lower = category.lower().strip()
        matching = [
            d for d in library 
            if d.get('category', '').lower().strip() == category_lower
            or category_lower in d.get('category', '').lower()
        ]
    else:
        matching = library
    
    if not matching:
        matching = library
    
    # Randomly select
    num_to_select = min(num_examples, len(matching))
    selected = random.sample(matching, num_to_select) if matching else []
    
    return selected


def format_reference_drills_for_prompt(drills: List[Dict]) -> str:
    """Format reference drills for inclusion in the Claude prompt - FULL details"""
    if not drills:
        return ""
    
    sections = ["\n\n## REFERENCE DRILLS - STUDY THESE CAREFULLY"]
    sections.append("These are high-quality example drills. Your drill MUST match this level of quality.")
    sections.append("CRITICAL: Study how the drill_json EXACTLY matches the setup and instructions.\n")
    
    for i, drill in enumerate(drills, 1):
        sections.append(f"### Example {i}: {drill.get('name', 'Unnamed')}")
        sections.append(f"**Category:** {drill.get('category', 'General')}")
        
        # Include FULL setup - don't truncate
        setup = drill.get('setup') or drill.get('setup_text', '')
        if setup:
            sections.append(f"\n**Setup:**\n{setup}")
        
        # Include FULL instructions
        instructions = drill.get('instructions') or drill.get('instructions_text', '')
        if instructions:
            sections.append(f"\n**Instructions:**\n{instructions}")
        
        # Include coaching points - these explain WHY
        coaching = drill.get('coaching_points') or drill.get('coaching_points_text', '')
        if coaching:
            sections.append(f"\n**Coaching Points:**\n{coaching}")
        
        # Include FULL drill_json - this is the most important part
        if drill.get('drill_json'):
            sections.append(f"\n**DIAGRAM JSON (your output must follow this structure exactly):**")
            sections.append("```json")
            sections.append(json.dumps(drill['drill_json'], indent=2))
            sections.append("```")
        
        sections.append("\n---\n")
    
    sections.append("## YOUR TASK")
    sections.append("Create a NEW, ORIGINAL drill that:")
    sections.append("1. Matches the user's requirements (players, equipment, etc.)")
    sections.append("2. Has the same quality level as the examples above")
    sections.append("3. Has a drill_json where EVERY action matches the written instructions")
    sections.append("4. Uses realistic player positions and movements")
    sections.append("")
    
    return "\n".join(sections)


# ============================================================
# CURATED GOLD STANDARD EXAMPLES
# ============================================================
# These are manually selected high-quality drills that serve as
# the primary reference for AI generation. Add more as you approve them.

CURATED_EXAMPLES = {
    "possession": [
        {
            "name": "5v3v1 Rondo Possession Drill",
            "category": "Possession",
            "setup": """• Mark out a 20x20 yard grid with cones
• Divide players into one team of five and one team of three, each wearing different colored jerseys
• From the team of five, position four players around the outside of the grid and one player inside
• Place all three players from the team of three inside the grid
• Have extra balls nearby to keep the drill moving
• For teams with 16 or more players, set up two separate grids running simultaneously""",
            "instructions": """1. Start with the team of three keeping possession against the single defender in a 3v1 rondo inside the grid
2. The three attackers pass and move to maintain possession while the lone defender pressures
3. When the single defender wins the ball, they immediately pass to any outside player
4. Once the ball reaches an outside player, the game becomes a 5v3 rondo with four outside players and one inside player keeping possession
5. The team of three now defends and tries to win the ball back
6. As the single player passes to the outside, they switch roles with one of the three defenders who becomes the new single attacker
7. The four outside players stay outside and work the ball around the perimeter while using the inside player
8. If the team of three wins possession back, play immediately switches to a 3v1 rondo again inside the grid
9. Continue this back and forth pattern as possession changes hands
10. Keep score by awarding points for completing a set number of consecutive passes""",
            "coaching_points": """• The transition moment is critical - players must switch their mindset from attack to defense instantly
• Inside attackers should constantly move to create passing angles and triangles of support
• The single defender needs to be smart about pressure - cut off one passing lane to force a predictable pass
• Outside players must stay alert and ready to receive even though they're not currently in the action
• Body shape matters when receiving - open up to see multiple passing options
• Quick one or two touch passing keeps the ball moving and makes defending harder
• Defenders should work together to press and cover passing lanes as a unit
• Communication is huge - call for the ball and let teammates know when pressure is coming
• Players switching roles need to move quickly into their new position
• The pace should stay high - this isn't a walking drill""",
            "drill_json": {
                "name": "5v3v1 Rondo Possession Drill",
                "description": "Dynamic possession drill alternating between 3v1 and 5v3 scenarios based on ball possession changes",
                "field": {"type": "FULL", "attacking_direction": "NORTH", "markings": False, "goals": 0},
                "players": [
                    {"id": "A1", "role": "ATTACKER", "position": {"x": 38, "y": 49}},
                    {"id": "A2", "role": "ATTACKER", "position": {"x": 48, "y": 38}},
                    {"id": "A3", "role": "ATTACKER", "position": {"x": 49, "y": 62}},
                    {"id": "A4", "role": "ATTACKER", "position": {"x": 62, "y": 50}},
                    {"id": "A5", "role": "ATTACKER", "position": {"x": 50, "y": 50}},
                    {"id": "D1", "role": "DEFENDER", "position": {"x": 46, "y": 45}},
                    {"id": "D2", "role": "DEFENDER", "position": {"x": 53, "y": 53}},
                    {"id": "D3", "role": "DEFENDER", "position": {"x": 45, "y": 55}}
                ],
                "cones": [
                    {"position": {"x": 40, "y": 40}},
                    {"position": {"x": 60, "y": 40}},
                    {"position": {"x": 40, "y": 60}},
                    {"position": {"x": 60, "y": 60}}
                ],
                "cone_gates": [],
                "balls": [{"position": {"x": 45, "y": 55}}],
                "mannequins": [],
                "actions": [
                    {"type": "PASS", "from_player": "D3", "to_player": "D2"},
                    {"type": "PASS", "from_player": "D2", "to_player": "D1"},
                    {"type": "PASS", "from_player": "D1", "to_player": "A2"}
                ],
                "coaching_points": [],
                "variations": []
            }
        },
        {
            "name": "5v3 Switching Rondo",
            "category": "Possession",
            "setup": """• Set up two 12x12 yard grids using cones with about 5 yards of space between them
• Divide players into two teams of five, each wearing different colored jerseys
• In the first grid, place five players from one team and three players from the opposing team
• Position the remaining two players from the defending team in the second grid
• Keep extra balls near the coach to maintain flow when balls go out of play""",
            "instructions": """1. Start play with a 5v3 rondo in the first grid where five attackers work to maintain possession
2. The three defenders press and try to win the ball
3. When the three defenders win possession, they immediately switch play by passing to their two teammates waiting in the other grid
4. As the ball travels to the second grid, three players from the original attacking team sprint to the second grid to defend
5. The two players who were waiting now have three teammates join them to create a new 5v3 situation
6. The two remaining players from the original attacking team stay in the first grid and wait
7. Play continues with possession switching between grids each time the defending team wins the ball
8. Rotate which three players transition to the other grid so everyone experiences different roles
9. Keep the pace high and competitive throughout the drill""",
            "coaching_points": """• The switch pass must be accurate and weighted properly to reach teammates in the other grid
• Three players need to decide quickly who transitions to defend in the other grid
• Players waiting in the empty grid should position themselves to receive the switch pass at good angles
• Attackers in possession need constant movement to create passing options in tight space
• First touch is critical in the small grid to keep the ball away from defenders
• Defenders should press together and cut off passing lanes rather than chasing individually
• Communication is huge during transitions so players know who's going and who's staying
• Players transitioning to defend must sprint to apply pressure immediately in the new grid
• The two waiting players should scan and anticipate when the switch might happen
• Body shape when receiving matters to see multiple passing options and avoid pressure
• Players staying behind should be ready in case the switch pass gets intercepted""",
            "drill_json": {
                "name": "5v3 Switching Rondo",
                "description": "Two-grid possession drill where teams switch between grids when possession is lost, creating continuous 5v3 scenarios with rapid transitions",
                "field": {"type": "FULL", "attacking_direction": "NORTH", "markings": False, "goals": 0},
                "players": [
                    {"id": "A1", "role": "ATTACKER", "position": {"x": 30, "y": 44}},
                    {"id": "A2", "role": "ATTACKER", "position": {"x": 38, "y": 36}},
                    {"id": "A3", "role": "ATTACKER", "position": {"x": 47, "y": 45}},
                    {"id": "A4", "role": "ATTACKER", "position": {"x": 37, "y": 51}},
                    {"id": "A5", "role": "ATTACKER", "position": {"x": 31, "y": 37}},
                    {"id": "D1", "role": "DEFENDER", "position": {"x": 38, "y": 44}},
                    {"id": "D2", "role": "DEFENDER", "position": {"x": 44, "y": 38}},
                    {"id": "D3", "role": "DEFENDER", "position": {"x": 44, "y": 50}},
                    {"id": "D4", "role": "DEFENDER", "position": {"x": 65, "y": 46}},
                    {"id": "D5", "role": "DEFENDER", "position": {"x": 68, "y": 38}}
                ],
                "cones": [
                    {"position": {"x": 26, "y": 32}},
                    {"position": {"x": 38, "y": 32}},
                    {"position": {"x": 50, "y": 32}},
                    {"position": {"x": 26, "y": 44}},
                    {"position": {"x": 50, "y": 44}},
                    {"position": {"x": 26, "y": 56}},
                    {"position": {"x": 38, "y": 56}},
                    {"position": {"x": 50, "y": 56}},
                    {"position": {"x": 56, "y": 32}},
                    {"position": {"x": 68, "y": 32}},
                    {"position": {"x": 80, "y": 32}},
                    {"position": {"x": 56, "y": 44}},
                    {"position": {"x": 80, "y": 44}},
                    {"position": {"x": 56, "y": 56}},
                    {"position": {"x": 68, "y": 56}},
                    {"position": {"x": 80, "y": 56}}
                ],
                "cone_gates": [],
                "balls": [{"position": {"x": 38, "y": 44}}],
                "mannequins": [],
                "actions": [
                    {"type": "PASS", "from_player": "A1", "to_player": "A2"},
                    {"type": "PASS", "from_player": "A2", "to_player": "A3"},
                    {"type": "PASS", "from_player": "A3", "to_player": "D4"}
                ],
                "coaching_points": [],
                "variations": []
            }
        },
        {
            "name": "6v1 Overload Add Defenders Drill",
            "category": "Possession",
            "setup": """• Create a square or rectangular grid using cones, sized 20x20 yards for younger players or 30x30 yards for older players
• Place one defender in the grid to start
• Position six attackers inside the grid with one player starting with the ball
• Keep the remaining players outside the area ready to enter as additional defenders
• Have extra balls nearby to restart play quickly when needed""",
            "instructions": """1. The attacking team begins play by passing and moving to keep possession away from the single defender
2. Attackers try to complete as many consecutive passes as possible
3. Add a new defender when the attackers reach a set number of passes, such as 5 or 10 consecutive completions
4. When possession changes, the attacking team starts their pass count from zero
5. Continue adding defenders each time the pass target is reached
6. The drill progresses from 6v1 to 6v2, then 6v3, and continues until a set time limit or number of defenders is reached
7. Reset the drill or rotate players after reaching the predetermined endpoint""",
            "coaching_points": """• Attackers need to scan constantly to find open teammates and identify where space exists
• Communication is essential as pressure builds. Simple calls help teammates know support is available
• First touch must move the ball away from pressure and into space where the next pass opens up
• Players without the ball should make sharp runs at angles to create clear passing lanes
• As more defenders enter, attackers must spread wider to stretch the defense
• The closest defender to the ball should apply immediate pressure to limit time and space
• Defenders must stay patient and avoid diving in, which creates gaps for attackers to exploit
• Defensive players should work together to cut off passing options and force mistakes
• Watch for the transition moment when the ball turns over. Instant pressure or instant support makes the difference
• Players switching from attack to defense need to recover quickly with their head up looking for the ball""",
            "drill_json": {
                "name": "6v1 Overload Add Defenders Drill",
                "description": "Progressive possession drill starting with 6 attackers vs 1 defender. Additional defenders are added each time attackers reach target consecutive passes (5-10). Develops possession under increasing pressure.",
                "field": {"type": "FULL", "attacking_direction": "NORTH", "markings": False, "goals": 0},
                "players": [
                    {"id": "A1", "role": "ATTACKER", "position": {"x": 45, "y": 45}},
                    {"id": "A2", "role": "ATTACKER", "position": {"x": 55, "y": 47}},
                    {"id": "A3", "role": "ATTACKER", "position": {"x": 42, "y": 52}},
                    {"id": "A4", "role": "ATTACKER", "position": {"x": 58, "y": 53}},
                    {"id": "A5", "role": "ATTACKER", "position": {"x": 47, "y": 57}},
                    {"id": "A6", "role": "ATTACKER", "position": {"x": 53, "y": 55}},
                    {"id": "D1", "role": "DEFENDER", "position": {"x": 50, "y": 50}},
                    {"id": "D2", "role": "DEFENDER", "position": {"x": 65, "y": 45}},
                    {"id": "D3", "role": "DEFENDER", "position": {"x": 65, "y": 50}},
                    {"id": "D4", "role": "DEFENDER", "position": {"x": 65, "y": 55}},
                    {"id": "D5", "role": "DEFENDER", "position": {"x": 70, "y": 47}},
                    {"id": "D6", "role": "DEFENDER", "position": {"x": 70, "y": 53}}
                ],
                "cones": [
                    {"position": {"x": 40, "y": 40}},
                    {"position": {"x": 60, "y": 40}},
                    {"position": {"x": 40, "y": 60}},
                    {"position": {"x": 60, "y": 60}}
                ],
                "cone_gates": [],
                "balls": [{"position": {"x": 45, "y": 45}}],
                "mannequins": [],
                "actions": [
                    {"type": "PASS", "from_player": "A1", "to_player": "A2"},
                    {"type": "PASS", "from_player": "A2", "to_player": "A6"},
                    {"type": "RUN", "player": "D2", "to_position": {"x": 58, "y": 48}}
                ],
                "coaching_points": [],
                "variations": []
            }
        },
        {
            "name": "4v4+2 Endzone Possession Game",
            "category": "Possession",
            "setup": """• Create a 12x20 yard grid using cones
• Mark two endzones that are 3x12 yards on each end of the grid
• Divide your team into two groups of six players each, plus select two neutral players
• Place four players from each team in the central playing area
• Position one player from each team in each endzone
• Station the two neutral players outside the long sides of the grid
• Keep a supply of balls near the coach to restart play quickly""",
            "instructions": """1. Start the game with one team in possession in the center grid
2. The team with the ball plays 4v4 in the middle, using the two neutral outside players as passing options
3. Players can pass to their teammate in the endzone to help maintain possession
4. The endzone player must move to find open space and good angles to receive
5. When an endzone player receives the ball, they can dribble out of the zone to join the game
6. If the endzone player dribbles out, they switch positions with the player who passed them the ball
7. Exception: if a neutral player passes to the endzone, no position switch happens and the ball must be passed back out
8. When the other team wins the ball, they immediately try to keep possession and use their endzone player
9. Start as a simple rondo with no scoring to let players learn the pattern
10. Progress to scoring one point for completing a set number of consecutive passes
11. Next progression: score one point for passing to the endzone and keeping possession
12. Final progression: score one point for passing to one endzone, keeping the ball, then passing to the opposite endzone""",
            "coaching_points": """• Players need to scan before receiving the ball to know where pressure is coming from and where space exists
• First touch should move the ball into space away from defenders, not just stop it
• The endzone player can't stand still - they must move side to side to create passing angles
• Players in the middle should constantly check their shoulders to stay aware of all options
• Speed of play matters - one or two touch passing breaks down the defense faster than holding the ball
• Body shape when receiving is key - open up to see the whole field
• Players off the ball need to move into passing lanes and create triangles of support
• Communication helps - call for the ball when you're open but keep it simple and clear
• When defending, work together to press as a unit and cut off passing lanes
• The neutral players should move up and down their line to stay available at the right angle""",
            "drill_json": {
                "name": "4v4+2 Endzone Possession Game",
                "description": "A possession drill with two teams of 4 playing in the center, supported by 2 neutral players and endzone teammates. Teams maintain possession and can switch positions when passing to endzones.",
                "field": {"type": "FULL", "attacking_direction": "NORTH", "markings": False, "goals": 0},
                "players": [
                    {"id": "A1", "role": "ATTACKER", "position": {"x": 45, "y": 52}},
                    {"id": "A2", "role": "ATTACKER", "position": {"x": 51, "y": 60}},
                    {"id": "A3", "role": "ATTACKER", "position": {"x": 52, "y": 54}},
                    {"id": "A4", "role": "ATTACKER", "position": {"x": 55, "y": 48}},
                    {"id": "A5", "role": "ATTACKER", "position": {"x": 53, "y": 41}},
                    {"id": "A6", "role": "ATTACKER", "position": {"x": 47, "y": 68}},
                    {"id": "D1", "role": "DEFENDER", "position": {"x": 47, "y": 50}},
                    {"id": "D2", "role": "DEFENDER", "position": {"x": 53, "y": 56}},
                    {"id": "D3", "role": "DEFENDER", "position": {"x": 51, "y": 52}},
                    {"id": "D4", "role": "DEFENDER", "position": {"x": 49, "y": 46}},
                    {"id": "D5", "role": "DEFENDER", "position": {"x": 53, "y": 69}},
                    {"id": "D6", "role": "DEFENDER", "position": {"x": 48, "y": 41}},
                    {"id": "N1", "role": "NEUTRAL", "position": {"x": 42, "y": 55}},
                    {"id": "N2", "role": "NEUTRAL", "position": {"x": 58, "y": 55}}
                ],
                "cones": [
                    {"position": {"x": 44, "y": 40}},
                    {"position": {"x": 56, "y": 40}},
                    {"position": {"x": 44, "y": 70}},
                    {"position": {"x": 56, "y": 70}},
                    {"position": {"x": 44, "y": 43}},
                    {"position": {"x": 56, "y": 43}},
                    {"position": {"x": 44, "y": 67}},
                    {"position": {"x": 56, "y": 67}}
                ],
                "cone_gates": [],
                "balls": [{"position": {"x": 45, "y": 52}}],
                "mannequins": [],
                "actions": [
                    {"type": "PASS", "from_player": "A1", "to_player": "A2"},
                    {"type": "PASS", "from_player": "A2", "to_player": "A6"},
                    {"type": "DRIBBLE", "player": "A6", "to_position": {"x": 47, "y": 60}},
                    {"type": "RUN", "player": "A2", "to_position": {"x": 50, "y": 68}}
                ],
                "coaching_points": [],
                "variations": []
            }
        }
    ]
}


def call_claude_api(request: DrillRequest) -> dict:
    """Call Claude API to generate drill"""
    
    client = anthropic.Anthropic()  # Uses ANTHROPIC_API_KEY env var
    
    # Build comprehensive prompt from all request fields
    prompt_parts = []
    
    # Drill type and main description
    if request.drill_type:
        prompt_parts.append(f"Create a {request.drill_type} drill")
    else:
        prompt_parts.append("Create a soccer drill")
    
    prompt_parts.append(f"based on this request: {request.prompt}")
    
    # Get reference drills from library based on drill type/category
    reference_category = request.drill_type  # Use drill_type as category
    if not reference_category:
        # Try to infer category from prompt
        prompt_lower = request.prompt.lower()
        if any(word in prompt_lower for word in ['finish', 'shoot', 'shot', 'goal', 'score']):
            reference_category = 'Finishing'
        elif any(word in prompt_lower for word in ['possess', 'rondo', 'keep']):
            reference_category = 'Possession'
        elif any(word in prompt_lower for word in ['pass', 'combination', 'one-two']):
            reference_category = 'Passing'
        elif any(word in prompt_lower for word in ['dribbl', '1v1', 'skill']):
            reference_category = 'Dribbling'
        elif any(word in prompt_lower for word in ['defend', 'press', 'tackle']):
            reference_category = 'Defending'
    
    # Get 1-3 reference drills
    reference_drills = get_reference_drills(reference_category, num_examples=2)
    reference_prompt = format_reference_drills_for_prompt(reference_drills)
    
    if reference_drills:
        print(f"[GENERATE] Using {len(reference_drills)} reference drills from category: {reference_category}")
        for rd in reference_drills:
            print(f"[GENERATE]   - {rd.get('name', 'Unnamed')}")
    
    # IMPORTANT: Resources are AVAILABLE, not required
    prompt_parts.append(f"\n\n## AVAILABLE RESOURCES (Maximum - use what makes sense for the drill)")
    prompt_parts.append(f"\nIMPORTANT: These are the MAXIMUM resources available. You do NOT need to use all of them.")
    prompt_parts.append(f"Design the best drill for the training goal - some drills work better with fewer players (e.g., lines/queues).")
    prompt_parts.append(f"However, you CANNOT use resources that aren't available (e.g., no goals if goals=0).")
    
    # Player configuration
    prompt_parts.append(f"\n\nPlayers Available:")
    prompt_parts.append(f"- Up to {request.num_players} players available (use fewer if appropriate for the drill)")
    
    if request.num_goalkeepers > 0:
        prompt_parts.append(f"- Goalkeepers available: {request.num_goalkeepers}")
    elif request.include_goalkeeper:
        prompt_parts.append(f"- 1 goalkeeper available if needed")
    
    # Equipment
    prompt_parts.append(f"\n\nEquipment Available:")
    if request.num_goals > 0:
        prompt_parts.append(f"- Goals: {request.num_goals} (MUST use at least 1 if this is a finishing drill)")
    else:
        prompt_parts.append(f"- Goals: NONE AVAILABLE - do NOT include any goals or shots on goal")
    
    if request.has_cones:
        prompt_parts.append(f"- Cones/markers: Available (use as needed)")
    else:
        prompt_parts.append(f"- Cones/markers: NOT available")
    
    if request.has_mannequins:
        prompt_parts.append(f"- Mannequins/dummies: Available - consider using them for passive defenders")
    else:
        prompt_parts.append(f"- Mannequins/dummies: NOT available")
    
    if request.num_balls:
        prompt_parts.append(f"- Balls: {request.num_balls} available")
    
    # Field setup
    prompt_parts.append(f"\n\nField Setup:")
    prompt_parts.append(f"- Field type: {request.field_type}")
    
    if request.field_size:
        prompt_parts.append(f"- Field size description: {request.field_size}")
    
    # Player details
    if request.age_group or request.skill_level:
        prompt_parts.append(f"\n\nPlayer Details:")
        if request.age_group:
            prompt_parts.append(f"- Age group: {request.age_group}")
        if request.skill_level:
            prompt_parts.append(f"- Skill level: {request.skill_level}")
    
    # Session details
    if request.intensity or request.duration_minutes:
        prompt_parts.append(f"\n\nSession Details:")
        if request.intensity:
            prompt_parts.append(f"- Intensity: {request.intensity}")
        if request.duration_minutes:
            prompt_parts.append(f"- Duration: {request.duration_minutes} minutes")
    
    # Additional notes
    if request.additional_notes:
        prompt_parts.append(f"\n\nAdditional Notes: {request.additional_notes}")
    
    # Add reference drills to the prompt
    prompt_parts.append(reference_prompt)
    
    prompt_parts.append("\n\nUse the create_drill tool to return both the drill JSON and a detailed coach description.")
    
    user_message = "".join(prompt_parts)

    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=4096,
        system=SYSTEM_PROMPT,
        tools=[DRILL_TOOL],
        tool_choice={"type": "tool", "name": "create_drill"},
        messages=[
            {"role": "user", "content": user_message}
        ]
    )
    
    # Extract tool use response
    for block in response.content:
        if block.type == "tool_use" and block.name == "create_drill":
            return block.input
    
    raise ValueError("Claude did not return expected tool response")


# ============================================================
# API ENDPOINTS
# ============================================================

@app.get("/", response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""
    return HealthResponse(status="healthy", version="1.0.0")


@app.get("/health", response_model=HealthResponse)
async def health():
    """Health check endpoint"""
    return HealthResponse(status="healthy", version="1.0.0")


# Test drill with known-good data for debugging
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
    "coaching_points": ["Commit the defender before passing", "Time the run to stay onside"],
    "variations": ["One-touch finish", "Add second defender"]
}

TEST_DESCRIPTION = """# Test 2v1 Finishing

## Overview
Two attackers combine against one defender to create a shooting opportunity. This drill focuses on combination play, timing of runs, and clinical finishing.

**Players:** 4 (including 1 goalkeeper)  
**Duration:** 10-15 minutes  
**Intensity:** Medium-High  
**Focus:** Finishing, combination play, movement off the ball

---

## Setup

### Field
- Half field with one full-size goal
- Goalkeeper in goal

### Starting Positions
- **GK (Goalkeeper):** In goal, central position
- **A1 (Attacker):** Left side, just above halfway line with the ball
- **A2 (Attacker):** Right side, level with A1
- **D1 (Defender):** Central, between attackers and goal

### Equipment
- 1 ball
- Bibs to differentiate attackers and defender

---

## Sequence of Play

1. **A1 dribbles forward** — A1 drives toward the defender to commit them and create space
2. **A2 makes a diagonal run** — As A1 engages the defender, A2 runs into the space behind
3. **A1 passes to A2** — Once the defender commits, A1 releases the ball to A2
4. **A2 shoots on goal** — A2 finishes first time or with a touch

---

## Coaching Points

- **Commit the defender:** A1 must drive at D1 to force a decision
- **Timing of the run:** A2 waits until A1 has engaged the defender before moving
- **Weight of pass:** Ball should arrive in A2's stride
- **Finishing technique:** Strike across the goalkeeper to the far corner

---

## Variations

| Variation | Description |
|-----------|-------------|
| One-touch finish | A2 must finish first time |
| Add defender | Include D2 to increase difficulty |
"""


@app.get("/api/test-drill", response_model=DrillResponse)
async def test_drill():
    """
    Test endpoint that renders a known-good drill.
    Use this to verify the rendering pipeline works.
    Hit this endpoint to check if SVG generation is working.
    """
    try:
        drill = Drill.model_validate(TEST_DRILL)
        
        print(f"[TEST] Rendering test drill with {len(drill.actions)} actions")
        for i, action in enumerate(drill.actions):
            print(f"[TEST]   Action {i+1}: {action}")
        
        with tempfile.NamedTemporaryFile(suffix=".svg", delete=False) as f:
            svg_path = f.name
        
        render(drill, svg_path)
        
        with open(svg_path, 'r') as f:
            svg_content = f.read()
        
        os.unlink(svg_path)
        
        print(f"[TEST] SVG generated: {len(svg_content)} bytes")
        
        return DrillResponse(
            success=True,
            drill_name=drill.name,
            svg=base64.b64encode(svg_content.encode()).decode(),
            description=TEST_DESCRIPTION,
            drill_json=TEST_DRILL
        )
        
    except Exception as e:
        print(f"[TEST] Error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Test render error: {str(e)}")


@app.post("/api/generate-drill", response_model=DrillResponse)
async def generate_drill(request: DrillRequest):
    """
    Generate a soccer drill from natural language description.
    
    Returns SVG diagram and coaching description.
    """
    try:
        # 1. Call Claude API
        print(f"[GENERATE] Received request: {request.prompt[:100]}...")
        result = call_claude_api(request)
        
        if not result or "drill" not in result:
            print(f"[GENERATE] ERROR: Invalid response - result keys: {result.keys() if result else 'None'}")
            raise ValueError("Invalid response from Claude API")
        
        # 2. Log what Claude returned
        drill_data = result["drill"]
        print(f"[GENERATE] Claude returned drill: {drill_data.get('name', 'NO NAME')}")
        print(f"[GENERATE] Players: {len(drill_data.get('players', []))}")
        print(f"[GENERATE] Actions: {len(drill_data.get('actions', []))}")
        
        # Log each action
        for i, action in enumerate(drill_data.get('actions', [])):
            print(f"[GENERATE]   Action {i+1}: {action}")
        
        # Ensure required fields have defaults
        drill_data.setdefault("cones", [])
        drill_data.setdefault("cone_gates", [])
        drill_data.setdefault("mannequins", [])
        drill_data.setdefault("coaching_points", [])
        drill_data.setdefault("variations", [])
        
        drill = Drill.model_validate(drill_data)
        print(f"[GENERATE] Validated - rendering {len(drill.actions)} actions")
        
        # 3. Render to SVG
        with tempfile.NamedTemporaryFile(suffix=".svg", delete=False) as f:
            svg_path = f.name
        
        render(drill, svg_path)
        
        with open(svg_path, 'r') as f:
            svg_content = f.read()
        
        print(f"[GENERATE] SVG generated: {len(svg_content)} bytes")
        
        # Clean up temp file
        os.unlink(svg_path)
        
        # 4. Return response
        return DrillResponse(
            success=True,
            drill_name=drill.name,
            svg=base64.b64encode(svg_content.encode()).decode(),
            description=result.get("coach_description", ""),
            drill_json=drill_data
        )
        
    except anthropic.APIError as e:
        raise HTTPException(
            status_code=502,
            detail=f"Claude API error: {str(e)}"
        )
    except ValueError as e:
        raise HTTPException(
            status_code=422,
            detail=f"Validation error: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Internal error: {str(e)}"
        )


@app.post("/api/render-drill", response_model=DrillResponse)
async def render_existing_drill(drill_json: dict):
    """
    Render an existing drill JSON to SVG.
    
    Useful for re-rendering saved drills or editing.
    """
    try:
        # Ensure required fields have defaults
        drill_json.setdefault("cones", [])
        drill_json.setdefault("cone_gates", [])
        drill_json.setdefault("mannequins", [])
        drill_json.setdefault("coaching_points", [])
        drill_json.setdefault("variations", [])
        
        drill = Drill.model_validate(drill_json)
        
        with tempfile.NamedTemporaryFile(suffix=".svg", delete=False) as f:
            svg_path = f.name
        
        render(drill, svg_path)
        
        with open(svg_path, 'r') as f:
            svg_content = f.read()
        
        os.unlink(svg_path)
        
        return DrillResponse(
            success=True,
            drill_name=drill.name,
            svg=base64.b64encode(svg_content.encode()).decode(),
            description="",  # No description for re-renders
            drill_json=drill_json
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Render error: {str(e)}"
        )


# ============================================================
# RUN SERVER
# ============================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
