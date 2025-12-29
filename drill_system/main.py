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
                "description": "Detailed markdown description for coaches including: Overview, Setup (field, starting positions, equipment), Sequence of Play (numbered steps), Coaching Points, and Variations"
            }
        },
        "required": ["drill", "coach_description"]
    }
}

SYSTEM_PROMPT = """You are an expert soccer coach and drill designer. When asked to create a drill, you MUST use the create_drill tool to return a structured response.

## COORDINATE SYSTEM (CRITICAL)
- Field coordinates are 0-100 for both x and y
- x: 0 = left sideline, 100 = right sideline, 50 = center
- y: 0 = bottom of diagram, 100 = top of diagram
- Attacking NORTH (default): goal at y=100, penalty spot at y=88, top of 18-yard box at y=82
- Attacking SOUTH: goal at y=0, penalty spot at y=12, top of 18-yard box at y=18

## REFERENCE POSITIONS (when attacking NORTH)
- Goal line center: (50, 100)
- Penalty spot: (50, 88)
- Top of 18-yard box: (50, 82)
- Left edge of 18-yard box: (30, 82)
- Right edge of 18-yard box: (70, 82)
- Center circle: (50, 50)
- Goalkeeper position: (50, 98)

## PLAYER ROLES
- ATTACKER: Offensive players (red)
- DEFENDER: Defensive players (blue)
- GOALKEEPER: Keeper (yellow)
- NEUTRAL: Support players, servers, etc. (orange)

## PLAYER ID CONVENTIONS
- Attackers: A1, A2, A3...
- Defenders: D1, D2, D3...
- Goalkeeper: GK
- Neutral: N1, N2...

## ACTION TYPES
1. PASS: Ball movement from one player to another
   - Requires: from_player, to_player
   
2. RUN: Player movement WITHOUT the ball (off-ball movement)
   - Requires: player, to_position
   
3. DRIBBLE: Player movement WITH the ball
   - Requires: player, to_position
   
4. SHOT: Shot on goal
   - Requires: player, target: "GOAL"

## CRITICAL: ACTION CHAINING
Actions are rendered in sequence and CHAIN TOGETHER:
- If A1 starts at (30, 50) and dribbles to (40, 70)
- Then A1 passes to A2
- The pass arrow starts from (40, 70), NOT from (30, 50)

Always think about where players END UP after each action.

## EQUIPMENT
- cones: Individual cone markers for positions
- cone_gates: Pairs of cones forming gates (specify center, width, orientation)
- mannequins: Training dummies to simulate defenders (specify id, position)
- balls: Starting ball position(s)

## FIELD CONFIGURATION
- type: "HALF" (default) or "FULL"
- goals: 0 (no goal), 1 (attacking goal only), 2 (both goals)
- If goals=0, no goal markings shown (good for possession drills)
- Half field with goals shows only the attacking half

## COACH DESCRIPTION FORMAT
Write a detailed markdown document including:
1. **Overview** - Brief summary, players needed, duration, intensity, focus areas
2. **Setup** - Field setup, starting positions, equipment needed
3. **Sequence of Play** - Numbered steps matching the actions exactly
4. **Coaching Points** - Key teaching points
5. **Variations** - Ways to progress or modify the drill

The description MUST match the diagram exactly - every action in the JSON should be described in the sequence.
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


@app.post("/api/generate-drill", response_model=DrillResponse)
async def generate_drill(request: DrillRequest):
    """
    Generate a soccer drill from natural language description.
    
    Returns SVG diagram and coaching description.
    """
    try:
        # 1. Call Claude API
        result = call_claude_api(request)
        
        if not result or "drill" not in result:
            raise ValueError("Invalid response from Claude API")
        
        # 2. Validate drill against schema
        drill_data = result["drill"]
        
        # Ensure required fields have defaults
        drill_data.setdefault("cones", [])
        drill_data.setdefault("cone_gates", [])
        drill_data.setdefault("mannequins", [])
        drill_data.setdefault("coaching_points", [])
        drill_data.setdefault("variations", [])
        
        drill = Drill.model_validate(drill_data)
        
        # 3. Render to SVG
        with tempfile.NamedTemporaryFile(suffix=".svg", delete=False) as f:
            svg_path = f.name
        
        render(drill, svg_path)
        
        with open(svg_path, 'r') as f:
            svg_content = f.read()
        
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
