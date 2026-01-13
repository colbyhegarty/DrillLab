"""
Soccer Drill Library API
========================
Serves drill library data and renders SVG diagrams on-demand.

Endpoints:
- GET /api/library - List all drills (metadata only)
- GET /api/library/{id} - Get single drill with SVG
- GET /api/library/categories - List all categories
- GET /api/library/filter - Filter drills by criteria
- GET /health - Health check
"""

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import json
import os
import sys
from pathlib import Path

# Add drill_system to path for renderer
sys.path.insert(0, str(Path(__file__).parent / "drill_system"))

app = FastAPI(
    title="Soccer Drill Library API",
    description="API for soccer drill library with SVG diagram rendering",
    version="2.0.0"
)

# CORS - allow all origins for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================
# LOAD DRILL LIBRARY
# ============================================================

LIBRARY_PATH = Path(__file__).parent / "library_drills.json"

def load_library() -> List[Dict]:
    """Load drills from library JSON file"""
    if not LIBRARY_PATH.exists():
        print(f"Warning: {LIBRARY_PATH} not found, using empty library")
        return []
    
    try:
        with open(LIBRARY_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
            # Handle both array and object with 'drills' key
            if isinstance(data, list):
                return data
            elif isinstance(data, dict) and 'drills' in data:
                return data['drills']
            elif isinstance(data, dict):
                return list(data.values())
            return []
    except Exception as e:
        print(f"Error loading library: {e}")
        return []

# ============================================================
# RESPONSE MODELS
# ============================================================

class HealthResponse(BaseModel):
    status: str
    version: str
    drill_count: int

class DrillSummary(BaseModel):
    id: str
    name: str
    category: Optional[str] = None
    age_group: Optional[str] = None
    player_count: Optional[str] = None
    duration: Optional[str] = None
    difficulty: Optional[str] = None
    description: Optional[str] = None
    svg: Optional[str] = None  # Base64 encoded SVG thumbnail

class DrillFull(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    category: Optional[str] = None
    age_group: Optional[str] = None
    player_count: Optional[str] = None
    duration: Optional[str] = None
    difficulty: Optional[str] = None
    setup_text: Optional[str] = None
    instructions_text: Optional[str] = None
    variations_text: Optional[str] = None
    coaching_points_text: Optional[str] = None
    source: Optional[str] = None
    source_url: Optional[str] = None
    drill_json: Optional[Dict] = None

class LibraryListResponse(BaseModel):
    success: bool
    count: int
    drills: List[DrillSummary]

class DrillDetailResponse(BaseModel):
    success: bool
    drill: DrillFull
    svg: Optional[str] = None  # Base64 encoded SVG

class CategoriesResponse(BaseModel):
    success: bool
    categories: List[Dict[str, Any]]

class FilterResponse(BaseModel):
    success: bool
    count: int
    filters_applied: Dict[str, Any]
    drills: List[DrillSummary]

# ============================================================
# SVG RENDERING
# ============================================================

def get_drill_json(drill: Dict) -> Optional[Dict]:
    """
    Extract drill_json from a drill object.
    Handles two formats:
    1. drill_json is nested: {"name": "...", "drill_json": {"field": ..., "players": ...}}
    2. drill_json is at root: {"name": "...", "field": ..., "players": ...}
    """
    # Check if drill_json is nested
    if drill.get('drill_json'):
        return drill['drill_json']
    
    # Check if diagram data is at root level
    if drill.get('field') and drill.get('players'):
        return {
            "name": drill.get('name', 'Untitled'),
            "description": drill.get('description', ''),
            "field": drill.get('field'),
            "players": drill.get('players', []),
            "cones": drill.get('cones', []),
            "cone_gates": drill.get('cone_gates', []),
            "balls": drill.get('balls', []),
            "goals": drill.get('goals', []),
            "mini_goals": drill.get('mini_goals', []),
            "mannequins": drill.get('mannequins', []),
            "actions": drill.get('actions', []),
            "coaching_points": drill.get('coaching_points', []),
            "variations": drill.get('variations', [])
        }
    
    return None


def render_drill_svg(drill_json: Dict) -> Optional[str]:
    """Render drill JSON to SVG and return as base64 string"""
    try:
        import tempfile
        import base64
        from schema import Drill
        from renderer import render
        
        # Convert dict to Drill object
        drill = Drill(**drill_json)
        
        # Render to temp file
        with tempfile.NamedTemporaryFile(suffix='.svg', delete=False) as f:
            temp_path = f.name
        
        render(drill, temp_path)
        
        # Read and encode
        with open(temp_path, 'r') as f:
            svg_content = f.read()
        
        # Clean up
        os.unlink(temp_path)
        
        # Return base64 encoded
        return base64.b64encode(svg_content.encode()).decode()
    
    except Exception as e:
        print(f"Error rendering SVG: {e}")
        return None

# ============================================================
# HELPER FUNCTIONS
# ============================================================

def get_drill_id(drill: Dict, index: int) -> str:
    """Get or generate a drill ID"""
    return drill.get('id') or drill.get('name', f'drill-{index}').lower().replace(' ', '-')

def drill_to_summary(drill: Dict, index: int, include_svg: bool = False) -> DrillSummary:
    """Convert drill dict to summary"""
    svg = None
    if include_svg:
        drill_json = get_drill_json(drill)
        if drill_json:
            svg = render_drill_svg(drill_json)
    
    return DrillSummary(
        id=get_drill_id(drill, index),
        name=drill.get('name', 'Unnamed Drill'),
        category=drill.get('category'),
        age_group=drill.get('age_group'),
        player_count=drill.get('player_count'),
        duration=drill.get('duration'),
        difficulty=drill.get('difficulty'),
        description=drill.get('description', '')[:200] if drill.get('description') else None,
        svg=svg
    )

def drill_to_full(drill: Dict, index: int) -> DrillFull:
    """Convert drill dict to full detail object"""
    return DrillFull(
        id=get_drill_id(drill, index),
        name=drill.get('name', 'Unnamed Drill'),
        description=drill.get('description'),
        category=drill.get('category'),
        age_group=drill.get('age_group'),
        player_count=drill.get('player_count'),
        duration=drill.get('duration'),
        difficulty=drill.get('difficulty'),
        setup_text=drill.get('setup_text'),
        instructions_text=drill.get('instructions_text'),
        variations_text=drill.get('variations_text'),
        coaching_points_text=drill.get('coaching_points_text'),
        source=drill.get('source'),
        source_url=drill.get('source_url'),
        drill_json=get_drill_json(drill)
    )

def matches_filter(drill: Dict, filters: Dict) -> bool:
    """Check if a drill matches the given filters"""
    # Category filter
    if filters.get('category'):
        drill_cat = (drill.get('category') or '').lower()
        filter_cat = filters['category'].lower()
        if filter_cat not in drill_cat:
            return False
    
    # Age group filter
    if filters.get('age_group'):
        drill_age = drill.get('age_group', '')
        filter_age = filters['age_group']
        # Extract numbers for comparison
        try:
            drill_min_age = int(''.join(c for c in drill_age if c.isdigit())[:2] or '0')
            filter_min_age = int(''.join(c for c in filter_age if c.isdigit())[:2] or '0')
            if drill_min_age > filter_min_age:
                return False
        except:
            pass
    
    # Player count filter
    if filters.get('min_players'):
        drill_players = drill.get('player_count', '')
        try:
            drill_min = int(''.join(c for c in drill_players if c.isdigit())[:2] or '99')
            if drill_min > int(filters['min_players']):
                return False
        except:
            pass
    
    if filters.get('max_players'):
        drill_players = drill.get('player_count', '')
        try:
            # Get first number from player count
            drill_min = int(''.join(c for c in drill_players if c.isdigit())[:2] or '0')
            if drill_min > int(filters['max_players']):
                return False
        except:
            pass
    
    # Difficulty filter
    if filters.get('difficulty'):
        drill_diff = (drill.get('difficulty') or '').upper()
        filter_diff = filters['difficulty'].upper()
        if drill_diff and drill_diff != filter_diff:
            return False
    
    # Search query (searches name and description)
    if filters.get('search'):
        search = filters['search'].lower()
        name = (drill.get('name') or '').lower()
        desc = (drill.get('description') or '').lower()
        if search not in name and search not in desc:
            return False
    
    return True

# ============================================================
# API ENDPOINTS
# ============================================================

@app.get("/", response_model=HealthResponse)
@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""
    library = load_library()
    return HealthResponse(
        status="healthy",
        version="2.0.0",
        drill_count=len(library)
    )

@app.get("/api/library", response_model=LibraryListResponse)
async def list_drills(include_svg: bool = Query(True, description="Include SVG diagrams in response")):
    """Get all drills with optional SVG diagrams"""
    library = load_library()
    summaries = [drill_to_summary(drill, i, include_svg=include_svg) for i, drill in enumerate(library)]
    
    return LibraryListResponse(
        success=True,
        count=len(summaries),
        drills=summaries
    )

@app.get("/api/library/categories", response_model=CategoriesResponse)
async def list_categories():
    """Get all unique categories with drill counts"""
    library = load_library()
    
    category_counts = {}
    for drill in library:
        cat = drill.get('category', 'Uncategorized') or 'Uncategorized'
        category_counts[cat] = category_counts.get(cat, 0) + 1
    
    categories = [
        {"name": name, "count": count}
        for name, count in sorted(category_counts.items())
    ]
    
    return CategoriesResponse(
        success=True,
        categories=categories
    )

@app.get("/api/library/filter", response_model=FilterResponse)
async def filter_drills(
    category: Optional[str] = Query(None, description="Filter by category"),
    age_group: Optional[str] = Query(None, description="Filter by age group (e.g., '10+')"),
    min_players: Optional[int] = Query(None, description="Minimum number of players"),
    max_players: Optional[int] = Query(None, description="Maximum number of players"),
    difficulty: Optional[str] = Query(None, description="Filter by difficulty (EASY, MEDIUM, HARD)"),
    search: Optional[str] = Query(None, description="Search in name and description"),
    include_svg: bool = Query(True, description="Include SVG diagrams in response")
):
    """Filter drills by various criteria"""
    library = load_library()
    
    filters = {
        'category': category,
        'age_group': age_group,
        'min_players': min_players,
        'max_players': max_players,
        'difficulty': difficulty,
        'search': search
    }
    
    # Remove None values
    active_filters = {k: v for k, v in filters.items() if v is not None}
    
    # Apply filters
    filtered = [
        drill for drill in library
        if matches_filter(drill, active_filters)
    ]
    
    summaries = [drill_to_summary(drill, i, include_svg=include_svg) for i, drill in enumerate(filtered)]
    
    return FilterResponse(
        success=True,
        count=len(summaries),
        filters_applied=active_filters,
        drills=summaries
    )

@app.get("/api/library/{drill_id}", response_model=DrillDetailResponse)
async def get_drill(drill_id: str):
    """Get a single drill with full details and rendered SVG"""
    library = load_library()
    
    # Find drill by ID or name
    for i, drill in enumerate(library):
        did = get_drill_id(drill, i)
        if did == drill_id or drill.get('name', '').lower().replace(' ', '-') == drill_id.lower():
            full_drill = drill_to_full(drill, i)
            
            # Render SVG if drill data exists
            svg = None
            drill_json = get_drill_json(drill)
            if drill_json:
                svg = render_drill_svg(drill_json)
            
            return DrillDetailResponse(
                success=True,
                drill=full_drill,
                svg=svg
            )
    
    raise HTTPException(status_code=404, detail=f"Drill '{drill_id}' not found")

# ============================================================
# RUN SERVER
# ============================================================

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
