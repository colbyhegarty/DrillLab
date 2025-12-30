"""
Soccer Drill Generator API

FastAPI backend that:
1. Receives drill requests from frontend
2. Calls Claude API to generate drill JSON + description
3. Renders the drill to SVG
4. Returns SVG + description to frontend
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional, List
import anthropic
import tempfile
import base64
import json
import os
import sys

# Add drill_system to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'drill_system'))

from drill_system.schema import Drill
from drill_system.renderer import render

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
# CLAUDE API INTEGRATION
# ============================================================

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
                "description": "COMPREHENSIVE markdown coaching document (1000+ words) that coaches can use directly on the field. Must include: Overview with duration/intensity/focus, detailed Setup with field configuration and starting positions explained in natural language, step-by-step 'How to Run the Drill' section matching the actions array exactly, 5+ detailed Coaching Points with technique explanations, Progressions table with 3-4 levels, Common Mistakes table with observable behaviors and corrections, and practical Coaching Tips. Write in a warm professional coaching voice, not bullet points. This should read like a document from a professional academy."
            }
        },
        "required": ["drill", "coach_description"]
    }
}

SYSTEM_PROMPT = """You are an expert soccer coach and drill designer with decades of experience at professional academies. When asked to create a drill, you MUST use the create_drill tool to return a structured response.

Your drills should be practical, well-organized, and match what a real coach would design. The diagram and description must match perfectly.

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

The coach_description field must be a comprehensive, professional coaching document written in natural coaching language. This is what coaches will read and use on the field.

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
[Describe the field setup in natural sentences - field size, where goals are, any zones marked out]

### Starting Positions
Describe where each player starts in natural language:
- **[Player ID]** starts [location description with context]
- Continue for all players...

### Equipment Needed
- [X] balls
- [X] cones (describe placement)
- [Any other equipment]
- Bibs to distinguish teams

---

## How to Run the Drill

### Sequence of Play
Walk through the drill step by step, exactly matching the actions in the diagram:

1. **The drill begins with [Player] [action]** — [Explain WHY and WHAT to look for]
2. **[Player] then [action]** — [Coaching context and timing cues]
3. **[Continue for each action...]**
4. **The sequence ends when [final action]**

### Reset
[Explain how players reset to starting positions and how quickly the drill should flow]

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

### Sequence of Play
Walk through the drill step by step:

1. **A1 starts by dribbling toward the defender** — The ball carrier must drive at D1 with purpose. Look for A1 to attack the defender's front foot, forcing them to commit.

2. **A2 makes a curved run into space** — As A1 engages the defender, A2 should arc their run to stay onside while finding the pocket of space. The timing is crucial - too early and D1 can recover, too late and the chance is gone.

3. **A1 releases the pass to A2** — The pass should be played into A2's path, weighted so they can take a touch toward goal or finish first-time. A1 must wait until D1 commits before releasing.

4. **A2 finishes on goal** — A2 should aim for the far corner, striking across the goalkeeper. Emphasize composure - placement over power.

### Reset
After each rep, A1 and A2 jog back to starting positions while the next pair prepares. Keep rest to 30-45 seconds to maintain intensity. Rotate the defender every 4-5 reps to keep them fresh.

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
    
    # Player configuration
    prompt_parts.append(f"\n\nPlayer Configuration:")
    prompt_parts.append(f"- Total players: {request.num_players}")
    
    if request.num_goalkeepers > 0:
        prompt_parts.append(f"- Goalkeepers: {request.num_goalkeepers}")
    elif request.include_goalkeeper:
        prompt_parts.append(f"- Include 1 goalkeeper")
    
    # Equipment
    prompt_parts.append(f"\n\nEquipment:")
    prompt_parts.append(f"- Goals: {request.num_goals}")
    
    if request.has_cones:
        prompt_parts.append(f"- Cones/markers: Available")
    
    if request.has_mannequins:
        prompt_parts.append(f"- Mannequins/dummies: Available - USE THEM in the drill")
    
    if request.num_balls:
        prompt_parts.append(f"- Balls: {request.num_balls}")
    
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
