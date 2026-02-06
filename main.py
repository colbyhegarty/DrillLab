"""
Soccer Drill Library API
========================
Serves drill library data and renders SVG diagrams on-demand.

NEW: Added /api/library/{id}/animation endpoint that returns a complete HTML animation player.
This ensures the animation looks exactly the same regardless of frontend implementation.
Lovable just needs to embed it in an iframe.

Endpoints:
- GET /api/library - List all drills (metadata only)
- GET /api/library/{id} - Get single drill with SVG
- GET /api/library/{id}/animation - Get HTML animation player for a drill
- GET /api/library/categories - List all categories
- GET /api/library/filter - Filter drills by criteria
- GET /health - Health check
"""

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "drill_system"))

app = FastAPI(
    title="Soccer Drill Library API",
    description="API for soccer drill library with SVG diagram rendering",
    version="2.2.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

LIBRARY_PATH = Path(__file__).parent / "library_drills.json"

def load_library() -> List[Dict]:
    if not LIBRARY_PATH.exists():
        return []
    try:
        with open(LIBRARY_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
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

# Response Models
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
    has_animation: bool = False
    svg: Optional[str] = None

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
    has_animation: bool = False
    animation_url: Optional[str] = None
    drill_json: Optional[Dict] = None

class LibraryListResponse(BaseModel):
    success: bool
    count: int
    drills: List[DrillSummary]

class DrillDetailResponse(BaseModel):
    success: bool
    drill: DrillFull
    svg: Optional[str] = None

class CategoriesResponse(BaseModel):
    success: bool
    categories: List[Dict[str, Any]]

class CategoriesSimpleResponse(BaseModel):
    success: bool
    categories: List[str]

class FilterResponse(BaseModel):
    success: bool
    count: int
    filters_applied: Dict[str, Any]
    drills: List[DrillSummary]

# Helper Functions
def get_drill_json(drill: Dict) -> Optional[Dict]:
    if drill.get('drill_json'):
        return drill['drill_json']
    if drill.get('field') and drill.get('players'):
        return {
            "name": drill.get('name', 'Untitled'),
            "description": drill.get('description', ''),
            "field": drill.get('field'),
            "players": drill.get('players', []),
            "cones": drill.get('cones', []),
            "cone_gates": drill.get('cone_gates', []),
            "cone_lines": drill.get('cone_lines', []),
            "balls": drill.get('balls', []),
            "goals": drill.get('goals', []),
            "mini_goals": drill.get('mini_goals', []),
            "mannequins": drill.get('mannequins', []),
            "actions": drill.get('actions', []),
            "animation": drill.get('animation'),
            "coaching_points": drill.get('coaching_points', []),
            "variations": drill.get('variations', [])
        }
    return None

def has_animation_data(drill: Dict) -> bool:
    animation = drill.get('animation')
    if animation and isinstance(animation, dict):
        keyframes = animation.get('keyframes', [])
        if keyframes and len(keyframes) > 0:
            return True
    drill_json = drill.get('drill_json')
    if drill_json:
        animation = drill_json.get('animation')
        if animation and isinstance(animation, dict):
            keyframes = animation.get('keyframes', [])
            if keyframes and len(keyframes) > 0:
                return True
    return False

def render_drill_svg(drill_json: Dict) -> Optional[str]:
    try:
        import tempfile
        import base64
        from schema import Drill
        from renderer import render
        drill = Drill(**drill_json)
        with tempfile.NamedTemporaryFile(suffix='.svg', delete=False) as f:
            temp_path = f.name
        render(drill, temp_path)
        with open(temp_path, 'r') as f:
            svg_content = f.read()
        os.unlink(temp_path)
        return base64.b64encode(svg_content.encode()).decode()
    except Exception as e:
        print(f"Error rendering SVG: {e}")
        return None

def get_drill_id(drill: Dict, index: int) -> str:
    return drill.get('id') or drill.get('name', f'drill-{index}').lower().replace(' ', '-')

def clean_coaching_points(text: str) -> str:
    if not text:
        return text
    stop_keywords = ['drill equipment', 'drill ages', 'drill topic', 'soccer drill titled',
        'created by', 'soccerxpert', 'subscribe', 'privacy policy', 'user agreement', 
        'copyright', 'quick links', 'soccer drills', 'soccer tips', 'email address']
    lines = text.split('\n')
    clean_lines = []
    for line in lines:
        line_lower = line.strip().lower()
        if any(keyword in line_lower for keyword in stop_keywords):
            break
        if line.strip():
            cleaned = line.strip()
            if cleaned.startswith('*'):
                cleaned = cleaned[1:].strip()
            if not cleaned.startswith('•'):
                cleaned = '• ' + cleaned
            clean_lines.append(cleaned)
    return '\n'.join(clean_lines)

def clean_instructions(text: str) -> str:
    if not text:
        return text
    lines = text.split('\n')
    clean_lines = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        line_lower = line.lower()
        if any(kw in line_lower for kw in ['drill equipment', 'drill ages', 'soccerxpert']):
            break
        clean_lines.append(line)
    return '\n'.join(clean_lines)

def drill_to_summary(drill: Dict, index: int, include_svg: bool = False) -> DrillSummary:
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
        has_animation=has_animation_data(drill),
        svg=svg
    )

def drill_to_full(drill: Dict, index: int) -> DrillFull:
    drill_id = get_drill_id(drill, index)
    has_anim = has_animation_data(drill)
    return DrillFull(
        id=drill_id,
        name=drill.get('name', 'Unnamed Drill'),
        description=drill.get('description'),
        category=drill.get('category'),
        age_group=drill.get('age_group'),
        player_count=drill.get('player_count'),
        duration=drill.get('duration'),
        difficulty=drill.get('difficulty'),
        setup_text=drill.get('setup_text'),
        instructions_text=clean_instructions(drill.get('instructions_text')),
        variations_text=drill.get('variations_text'),
        coaching_points_text=clean_coaching_points(drill.get('coaching_points_text')),
        source=drill.get('source'),
        source_url=drill.get('source_url'),
        has_animation=has_anim,
        animation_url=f"/api/library/{drill_id}/animation" if has_anim else None,
        drill_json=get_drill_json(drill)
    )

def matches_filter(drill: Dict, filters: Dict) -> bool:
    if filters.get('category'):
        drill_cat = (drill.get('category') or '').lower()
        if filters['category'].lower() not in drill_cat:
            return False
    if filters.get('difficulty'):
        drill_diff = (drill.get('difficulty') or '').upper()
        if drill_diff and drill_diff != filters['difficulty'].upper():
            return False
    if filters.get('search'):
        search = filters['search'].lower()
        name = (drill.get('name') or '').lower()
        desc = (drill.get('description') or '').lower()
        if search not in name and search not in desc:
            return False
    if filters.get('has_animation') is not None:
        if filters['has_animation'] and not has_animation_data(drill):
            return False
        if not filters['has_animation'] and has_animation_data(drill):
            return False
    return True

# Animation HTML Generator
def generate_animation_html(drill_json: Dict, drill_name: str) -> str:
    drill_data_json = json.dumps(drill_json)
    
    return f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{drill_name}</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #f5f5f0; }}
        .container {{ max-width: 900px; margin: 0 auto; padding: 10px; }}
        .canvas-wrapper {{ background: #2d4a2d; border-radius: 12px; padding: 15px; margin-bottom: 15px; }}
        #field-canvas {{ display: block; margin: 0 auto; border-radius: 8px; max-width: 100%; height: auto; }}
        .controls {{ background: #fff; border-radius: 12px; padding: 15px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }}
        .playback-row {{ display: flex; align-items: center; gap: 10px; margin-bottom: 12px; flex-wrap: wrap; }}
        .playback-btn {{ width: 40px; height: 40px; border: 2px solid #3d5a3d; border-radius: 8px; background: #fff; color: #3d5a3d; cursor: pointer; font-size: 16px; display: flex; align-items: center; justify-content: center; }}
        .playback-btn:hover {{ background: #f0f4f0; }}
        .playback-btn.play-btn {{ width: 50px; height: 50px; background: #3d5a3d; color: #fff; border-radius: 50%; }}
        .progress-container {{ flex: 1; min-width: 150px; display: flex; align-items: center; gap: 10px; }}
        .progress-bar {{ flex: 1; height: 8px; background: #e0e0e0; border-radius: 4px; cursor: pointer; }}
        .progress-fill {{ height: 100%; background: #3d5a3d; border-radius: 4px; width: 0%; }}
        .time-display {{ font-size: 14px; color: #666; min-width: 80px; text-align: right; }}
        .options-row {{ display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px; flex-wrap: wrap; gap: 10px; }}
        .speed-select {{ padding: 8px 12px; border: 2px solid #3d5a3d; border-radius: 8px; background: #fff; color: #3d5a3d; font-size: 14px; }}
        .loop-btn {{ padding: 8px 16px; border: 2px solid #3d5a3d; border-radius: 8px; background: #fff; color: #3d5a3d; cursor: pointer; font-size: 14px; }}
        .loop-btn.active {{ background: #3d5a3d; color: #fff; }}
        .keyframe-row {{ display: flex; gap: 8px; flex-wrap: wrap; }}
        .keyframe-btn {{ padding: 8px 16px; border: 2px solid #3d5a3d; border-radius: 20px; background: #fff; color: #3d5a3d; cursor: pointer; font-size: 13px; }}
        .keyframe-btn.active {{ background: #3d5a3d; color: #fff; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="canvas-wrapper">
            <canvas id="field-canvas" width="800" height="600"></canvas>
        </div>
        <div class="controls">
            <div class="playback-row">
                <button class="playback-btn" onclick="goToStart()">⏮</button>
                <button class="playback-btn" onclick="prevKeyframe()">⏪</button>
                <button class="playback-btn play-btn" id="play-btn" onclick="togglePlay()">▶</button>
                <button class="playback-btn" onclick="nextKeyframe()">⏩</button>
                <button class="playback-btn" onclick="goToEnd()">⏭</button>
                <div class="progress-container">
                    <div class="progress-bar" id="progress-bar" onclick="seekProgress(event)">
                        <div class="progress-fill" id="progress-fill"></div>
                    </div>
                    <div class="time-display" id="time-display">0:00 / 0:00</div>
                </div>
            </div>
            <div class="options-row">
                <select class="speed-select" id="speed-select" onchange="updateSpeed()">
                    <option value="0.5">0.5x</option>
                    <option value="1" selected>1x</option>
                    <option value="1.5">1.5x</option>
                    <option value="2">2x</option>
                </select>
                <button class="loop-btn active" id="loop-btn" onclick="toggleLoop()">🔄 Loop On</button>
            </div>
            <div class="keyframe-row" id="keyframe-row"></div>
        </div>
    </div>
    <script>
        const drill = {drill_data_json};
        const state = {{
            keyframes: drill.animation?.keyframes || [],
            isPlaying: false, playbackSpeed: 1, currentTime: 0, totalDuration: 0,
            lastTimestamp: null, animationFrameId: null, selectedKeyframeIndex: 0, looping: true
        }};
        const canvas = document.getElementById('field-canvas');
        const ctx = canvas.getContext('2d');
        const FIELD_PADDING = 50, FIELD_WIDTH = canvas.width - 100, FIELD_HEIGHT = canvas.height - 100;
        
        for (let i = 1; i < state.keyframes.length; i++) state.totalDuration += state.keyframes[i].duration || 1000;
        
        function toCanvas(x, y) {{ return {{ x: FIELD_PADDING + (x / 100) * FIELD_WIDTH, y: FIELD_PADDING + ((100 - y) / 100) * FIELD_HEIGHT }}; }}
        
        function getStartingPositions() {{
            const pos = {{}};
            drill.players?.forEach(p => pos[p.id] = {{ x: p.position.x, y: p.position.y }});
            drill.balls?.forEach((b, i) => pos['ball_' + i] = {{ x: b.position.x, y: b.position.y }});
            return pos;
        }}
        
        function getPositionsAtKeyframe(idx) {{
            let pos = getStartingPositions();
            for (let i = 0; i <= idx && i < state.keyframes.length; i++) {{
                const kf = state.keyframes[i];
                if (kf.positions) Object.entries(kf.positions).forEach(([id, p]) => pos[id] = {{ ...p }});
            }}
            return pos;
        }}
        
        function getPositionsAtTime(time) {{
            if (state.keyframes.length === 0) return getStartingPositions();
            const times = []; let cum = 0;
            for (let i = 0; i < state.keyframes.length; i++) {{ times.push(cum); if (i < state.keyframes.length - 1) cum += state.keyframes[i + 1].duration || 1000; }}
            let from = 0;
            for (let i = 0; i < times.length; i++) if (time >= times[i]) from = i;
            let to = Math.min(from + 1, state.keyframes.length - 1);
            if (from >= state.keyframes.length - 1 || from === to) return getPositionsAtKeyframe(state.keyframes.length - 1);
            const segDur = times[to] - times[from];
            if (segDur <= 0) return getPositionsAtKeyframe(from);
            const prog = Math.min(1, Math.max(0, (time - times[from]) / segDur));
            const fromPos = getPositionsAtKeyframe(from), toPos = getPositionsAtKeyframe(to);
            const ease = state.keyframes[to]?.easing || 'linear';
            const e = ease === 'ease-in' ? prog*prog : ease === 'ease-out' ? 1-(1-prog)*(1-prog) : ease === 'ease-in-out' ? (prog < 0.5 ? 2*prog*prog : 1-Math.pow(-2*prog+2,2)/2) : prog;
            const interp = {{}};
            Object.keys(fromPos).forEach(id => {{ const f = fromPos[id], t = toPos[id] || f; interp[id] = {{ x: f.x + (t.x - f.x) * e, y: f.y + (t.y - f.y) * e }}; }});
            return interp;
        }}
        
        function draw(positions = null) {{
            ctx.clearRect(0, 0, canvas.width, canvas.height);
            if (!positions) positions = state.isPlaying ? getPositionsAtTime(state.currentTime) : getPositionsAtKeyframe(state.selectedKeyframeIndex);
            drawField(); drawConeLines(); drawCones(); drawGoals(); drawMiniGoals(); drawPlayers(positions); drawBalls(positions);
        }}
        
        function drawField() {{
            const p = FIELD_PADDING, w = FIELD_WIDTH, h = FIELD_HEIGHT;
            ctx.fillStyle = '#63b043'; ctx.fillRect(p, p, w, h);
            for (let i = 0; i < 10; i++) {{ ctx.fillStyle = i % 2 === 0 ? '#6fbf4a' : '#63b043'; ctx.fillRect(p + i * (w/10), p, w/10, h); }}
            ctx.strokeStyle = 'rgba(255,255,255,0.5)'; ctx.lineWidth = 1.5; ctx.strokeRect(p, p, w, h);
            if (drill.field?.markings !== false) {{
                ctx.strokeStyle = 'white'; ctx.lineWidth = 1.5;
                const cy = toCanvas(50, 50).y; ctx.beginPath(); ctx.moveTo(p, cy); ctx.lineTo(p + w, cy); ctx.stroke();
                const c = toCanvas(50, 50); ctx.beginPath(); ctx.arc(c.x, c.y, (10/100) * w, 0, Math.PI * 2); ctx.stroke();
                ctx.fillStyle = 'white'; ctx.beginPath(); ctx.arc(c.x, c.y, 3, 0, Math.PI * 2); ctx.fill();
                const fg = drill.field?.goals || 0;
                drawGoalArea(100, fg >= 1); if (drill.field?.type === 'FULL') drawGoalArea(0, fg >= 2);
            }}
        }}
        
        function drawGoalArea(goalY, dg) {{
            const into = goalY === 100 ? -1 : 1;
            ctx.strokeStyle = 'white'; ctx.lineWidth = 1.5;
            const bt = toCanvas(30, goalY + into * 18), bb = toCanvas(70, goalY);
            ctx.strokeRect(bt.x, Math.min(bt.y, bb.y), toCanvas(70, 0).x - toCanvas(30, 0).x, Math.abs(bt.y - bb.y));
            const st = toCanvas(42, goalY + into * 6), sb = toCanvas(58, goalY);
            ctx.strokeRect(st.x, Math.min(st.y, sb.y), toCanvas(58, 0).x - toCanvas(42, 0).x, Math.abs(st.y - sb.y));
            const ps = toCanvas(50, goalY + into * 12); ctx.fillStyle = 'white'; ctx.beginPath(); ctx.arc(ps.x, ps.y, 3, 0, Math.PI * 2); ctx.fill();
            if (dg) {{
                const pos = toCanvas(50, goalY), gw = (8/100) * FIELD_WIDTH, gd = (3/100) * FIELD_HEIGHT;
                ctx.strokeStyle = '#fff'; ctx.lineWidth = 3; ctx.lineCap = 'round';
                if (goalY === 100) {{
                    ctx.beginPath(); ctx.moveTo(pos.x - gw/2, pos.y); ctx.lineTo(pos.x - gw/2, pos.y - gd); ctx.stroke();
                    ctx.beginPath(); ctx.moveTo(pos.x + gw/2, pos.y); ctx.lineTo(pos.x + gw/2, pos.y - gd); ctx.stroke();
                    ctx.beginPath(); ctx.moveTo(pos.x - gw/2, pos.y - gd); ctx.lineTo(pos.x + gw/2, pos.y - gd); ctx.stroke();
                }} else {{
                    ctx.beginPath(); ctx.moveTo(pos.x - gw/2, pos.y); ctx.lineTo(pos.x - gw/2, pos.y + gd); ctx.stroke();
                    ctx.beginPath(); ctx.moveTo(pos.x + gw/2, pos.y); ctx.lineTo(pos.x + gw/2, pos.y + gd); ctx.stroke();
                    ctx.beginPath(); ctx.moveTo(pos.x - gw/2, pos.y + gd); ctx.lineTo(pos.x + gw/2, pos.y + gd); ctx.stroke();
                }}
            }}
        }}
        
        function drawConeLines() {{
            if (!drill.cone_lines) return;
            const cones = drill.cones || [];
            drill.cone_lines.forEach(l => {{
                if (l.from_cone < cones.length && l.to_cone < cones.length) {{
                    const f = toCanvas(cones[l.from_cone].position.x, cones[l.from_cone].position.y);
                    const t = toCanvas(cones[l.to_cone].position.x, cones[l.to_cone].position.y);
                    ctx.strokeStyle = '#f4a261'; ctx.lineWidth = 2; ctx.beginPath(); ctx.moveTo(f.x, f.y); ctx.lineTo(t.x, t.y); ctx.stroke();
                }}
            }});
        }}
        
        function drawCones() {{
            if (!drill.cones) return;
            drill.cones.forEach(c => {{
                const pos = toCanvas(c.position.x, c.position.y);
                ctx.fillStyle = '#f4a261'; ctx.beginPath(); ctx.moveTo(pos.x, pos.y - 8); ctx.lineTo(pos.x - 6, pos.y + 5); ctx.lineTo(pos.x + 6, pos.y + 5); ctx.closePath(); ctx.fill();
                ctx.strokeStyle = '#000'; ctx.lineWidth = 0.8; ctx.stroke();
            }});
        }}
        
        function drawGoals() {{
            if (!drill.goals) return;
            drill.goals.forEach(g => {{
                const pos = toCanvas(g.position.x, g.position.y), rot = g.rotation || 0;
                const gw = (8/100) * FIELD_WIDTH, gd = (3/100) * FIELD_HEIGHT;
                ctx.save(); ctx.translate(pos.x, pos.y); ctx.rotate((rot * Math.PI) / 180);
                ctx.strokeStyle = '#fff'; ctx.lineWidth = 3;
                ctx.beginPath(); ctx.moveTo(-gw/2, gd/2); ctx.lineTo(-gw/2, -gd/2); ctx.stroke();
                ctx.beginPath(); ctx.moveTo(gw/2, gd/2); ctx.lineTo(gw/2, -gd/2); ctx.stroke();
                ctx.beginPath(); ctx.moveTo(-gw/2, -gd/2); ctx.lineTo(gw/2, -gd/2); ctx.stroke();
                ctx.restore();
            }});
        }}
        
        function drawMiniGoals() {{
            if (!drill.mini_goals) return;
            drill.mini_goals.forEach(g => {{
                const pos = toCanvas(g.position.x, g.position.y), rot = ((g.rotation || 0) + 180) % 360;
                const gw = (4/100) * FIELD_WIDTH, gd = (2/100) * FIELD_HEIGHT;
                ctx.save(); ctx.translate(pos.x, pos.y); ctx.rotate((rot * Math.PI) / 180);
                ctx.strokeStyle = '#fff'; ctx.lineWidth = 2;
                ctx.beginPath(); ctx.moveTo(-gw/2, gd/2); ctx.lineTo(-gw/2, -gd/2); ctx.lineTo(gw/2, -gd/2); ctx.lineTo(gw/2, gd/2); ctx.stroke();
                ctx.restore();
            }});
        }}
        
        function drawPlayers(positions) {{
            if (!drill.players) return;
            const colors = {{ 'ATTACKER': '#e63946', 'DEFENDER': '#457b9d', 'GOALKEEPER': '#f1fa3c', 'NEUTRAL': '#f4a261' }};
            drill.players.forEach(p => {{
                const pd = positions[p.id] || p.position, pos = toCanvas(pd.x, pd.y);
                ctx.fillStyle = colors[p.role] || '#888'; ctx.strokeStyle = '#fff'; ctx.lineWidth = 1.5;
                ctx.beginPath(); ctx.arc(pos.x, pos.y, 12, 0, Math.PI * 2); ctx.fill(); ctx.stroke();
                ctx.fillStyle = '#fff'; ctx.font = 'bold 9px sans-serif'; ctx.textAlign = 'center'; ctx.textBaseline = 'top';
                ctx.fillText(p.id, pos.x, pos.y + 16);
            }});
        }}
        
        function drawBalls(positions) {{
            if (!drill.balls) return;
            drill.balls.forEach((b, i) => {{
                const pd = positions['ball_' + i] || b.position, pos = toCanvas(pd.x, pd.y);
                ctx.fillStyle = '#fff'; ctx.strokeStyle = '#000'; ctx.lineWidth = 1.5;
                ctx.beginPath(); ctx.arc(pos.x, pos.y, 10, 0, Math.PI * 2); ctx.fill(); ctx.stroke();
                ctx.fillStyle = '#000'; ctx.beginPath();
                for (let j = 0; j < 5; j++) {{ const a = (j * 72 - 90) * Math.PI / 180, px = pos.x + 5 * Math.cos(a), py = pos.y + 5 * Math.sin(a); if (j === 0) ctx.moveTo(px, py); else ctx.lineTo(px, py); }}
                ctx.closePath(); ctx.fill();
            }});
        }}
        
        function togglePlay() {{ if (state.isPlaying) stopPlayback(); else startPlayback(); }}
        function startPlayback() {{
            if (state.keyframes.length < 2) return;
            if (state.currentTime >= state.totalDuration) state.currentTime = 0;
            state.isPlaying = true; state.lastTimestamp = null;
            document.getElementById('play-btn').textContent = '⏸';
            state.animationFrameId = requestAnimationFrame(animationLoop);
            updateKeyframeButtons();
        }}
        function stopPlayback() {{
            state.isPlaying = false;
            if (state.animationFrameId) cancelAnimationFrame(state.animationFrameId);
            document.getElementById('play-btn').textContent = '▶';
        }}
        function animationLoop(ts) {{
            if (!state.isPlaying) return;
            if (state.lastTimestamp === null) state.lastTimestamp = ts;
            state.currentTime += (ts - state.lastTimestamp) * state.playbackSpeed;
            state.lastTimestamp = ts;
            if (state.currentTime >= state.totalDuration) {{
                if (state.looping) state.currentTime = 0;
                else {{ state.currentTime = state.totalDuration; stopPlayback(); return; }}
            }}
            draw(getPositionsAtTime(state.currentTime));
            updateProgressBar();
            state.animationFrameId = requestAnimationFrame(animationLoop);
        }}
        function goToStart() {{ stopPlayback(); state.currentTime = 0; state.selectedKeyframeIndex = 0; updateUI(); draw(); }}
        function goToEnd() {{ stopPlayback(); state.currentTime = state.totalDuration; state.selectedKeyframeIndex = state.keyframes.length - 1; updateUI(); draw(); }}
        function prevKeyframe() {{ stopPlayback(); if (state.selectedKeyframeIndex > 0) state.selectedKeyframeIndex--; jumpToKeyframeIndex(state.selectedKeyframeIndex); }}
        function nextKeyframe() {{ stopPlayback(); if (state.selectedKeyframeIndex < state.keyframes.length - 1) state.selectedKeyframeIndex++; jumpToKeyframeIndex(state.selectedKeyframeIndex); }}
        function jumpToKeyframeIndex(idx) {{
            stopPlayback(); state.selectedKeyframeIndex = idx;
            let t = 0; for (let i = 1; i <= idx; i++) t += state.keyframes[i].duration || 1000;
            state.currentTime = t; updateUI(); draw();
        }}
        function seekProgress(e) {{
            stopPlayback();
            const rect = e.currentTarget.getBoundingClientRect();
            state.currentTime = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width)) * state.totalDuration;
            updateProgressBar(); draw(getPositionsAtTime(state.currentTime));
        }}
        function updateSpeed() {{ state.playbackSpeed = parseFloat(document.getElementById('speed-select').value); }}
        function toggleLoop() {{
            state.looping = !state.looping;
            const btn = document.getElementById('loop-btn');
            btn.classList.toggle('active', state.looping);
            btn.textContent = state.looping ? '🔄 Loop On' : '🔄 Loop Off';
        }}
        function updateProgressBar() {{
            const prog = state.totalDuration > 0 ? (state.currentTime / state.totalDuration) * 100 : 0;
            document.getElementById('progress-fill').style.width = prog + '%';
            const cs = Math.floor(state.currentTime / 1000), ts = Math.floor(state.totalDuration / 1000);
            document.getElementById('time-display').textContent = Math.floor(cs/60) + ':' + (cs%60).toString().padStart(2,'0') + ' / ' + Math.floor(ts/60) + ':' + (ts%60).toString().padStart(2,'0');
        }}
        function updateKeyframeButtons() {{
            document.getElementById('keyframe-row').innerHTML = state.keyframes.map((kf, i) =>
                '<button class="keyframe-btn ' + (state.selectedKeyframeIndex === i && !state.isPlaying ? 'active' : '') + '" onclick="jumpToKeyframeIndex(' + i + ')">' + (kf.label || 'Step ' + i) + '</button>'
            ).join('');
        }}
        function updateUI() {{ updateProgressBar(); updateKeyframeButtons(); }}
        updateUI(); draw();
    </script>
</body>
</html>'''

# API Endpoints
@app.get("/", response_model=HealthResponse)
@app.get("/health", response_model=HealthResponse)
async def health_check():
    library = load_library()
    return HealthResponse(status="healthy", version="2.2.0", drill_count=len(library))

@app.get("/api/library", response_model=LibraryListResponse)
async def list_drills(include_svg: bool = Query(True)):
    library = load_library()
    summaries = [drill_to_summary(drill, i, include_svg=include_svg) for i, drill in enumerate(library)]
    return LibraryListResponse(success=True, count=len(summaries), drills=summaries)

@app.get("/api/library/categories", response_model=CategoriesResponse)
async def list_categories():
    library = load_library()
    category_counts = {}
    for drill in library:
        cat = drill.get('category', '') or ''
        if cat.strip():
            category_counts[cat] = category_counts.get(cat, 0) + 1
    categories = [{"name": name, "count": count} for name, count in sorted(category_counts.items()) if name.strip()]
    return CategoriesResponse(success=True, categories=categories)

@app.get("/api/library/categories/simple", response_model=CategoriesSimpleResponse)
async def list_categories_simple():
    library = load_library()
    categories = set()
    for drill in library:
        cat = drill.get('category', '') or ''
        if cat.strip():
            categories.add(cat.strip())
    return CategoriesSimpleResponse(success=True, categories=sorted(list(categories)))

@app.get("/api/library/filter", response_model=FilterResponse)
async def filter_drills(
    category: Optional[str] = Query(None),
    difficulty: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    has_animation: Optional[bool] = Query(None),
    include_svg: bool = Query(True)
):
    library = load_library()
    filters = {k: v for k, v in {'category': category, 'difficulty': difficulty, 'search': search, 'has_animation': has_animation}.items() if v is not None}
    filtered = [drill for drill in library if matches_filter(drill, filters)]
    summaries = [drill_to_summary(drill, i, include_svg=include_svg) for i, drill in enumerate(filtered)]
    return FilterResponse(success=True, count=len(summaries), filters_applied=filters, drills=summaries)

@app.get("/api/library/{drill_id}/animation", response_class=HTMLResponse)
async def get_drill_animation(drill_id: str):
    library = load_library()
    for i, drill in enumerate(library):
        did = get_drill_id(drill, i)
        if did == drill_id or drill.get('name', '').lower().replace(' ', '-') == drill_id.lower():
            drill_json = get_drill_json(drill)
            if not drill_json:
                raise HTTPException(status_code=404, detail=f"Drill '{drill_id}' has no diagram data")
            if not has_animation_data(drill):
                raise HTTPException(status_code=404, detail=f"Drill '{drill_id}' has no animation data")
            return HTMLResponse(content=generate_animation_html(drill_json, drill.get('name', 'Drill Animation')))
    raise HTTPException(status_code=404, detail=f"Drill '{drill_id}' not found")

@app.get("/api/library/{drill_id}", response_model=DrillDetailResponse)
async def get_drill(drill_id: str):
    library = load_library()
    for i, drill in enumerate(library):
        did = get_drill_id(drill, i)
        if did == drill_id or drill.get('name', '').lower().replace(' ', '-') == drill_id.lower():
            full_drill = drill_to_full(drill, i)
            svg = None
            drill_json = get_drill_json(drill)
            if drill_json:
                svg = render_drill_svg(drill_json)
            return DrillDetailResponse(success=True, drill=full_drill, svg=svg)
    raise HTTPException(status_code=404, detail=f"Drill '{drill_id}' not found")

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
