"""
SVG Pre-Rendering Script
=========================
This script pre-renders all drill SVGs and uploads them to Supabase Storage.

Usage:
1. Make sure your drills are already in Supabase (run migrate_to_supabase.py first)
2. Run: python prerender_svgs.py

The script will:
- Fetch all drills from Supabase
- Render SVG for each drill using your renderer
- Upload SVG to Supabase Storage
- Update the drill record with the SVG URL
"""

import os
import sys
import tempfile
from pathlib import Path
from typing import Dict, Optional
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add your drill_system to path (adjust path as needed)
sys.path.insert(0, str(Path(__file__).parent / "drill_system"))

# Supabase credentials
SUPABASE_URL = "https://dgvaiejyixwxallybbcl.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImRndmFpZWp5aXh3eGFsbHliYmNsIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3MDQzMjE2NywiZXhwIjoyMDg2MDA4MTY3fQ.Up0unYsv9iUmyoG22MHGLZRI9y8KyRYcPXCU3h0PDC0"

# Storage bucket name
SVG_BUCKET = "drill-svgs"
ANIMATION_BUCKET = "drill-animations"

# ============================================================
# RENDERING FUNCTIONS
# ============================================================

def reconstruct_drill_json(drill: Dict) -> Dict:
    """Reconstruct full drill JSON from database record"""
    diagram = drill.get('diagram_json', {})
    animation = drill.get('animation_json')
    
    full_drill = {
        "name": drill['name'],
        "description": drill.get('description', ''),
        "field": diagram.get('field', {}),
        "players": diagram.get('players', []),
        "cones": diagram.get('cones', []),
        "cone_gates": diagram.get('cone_gates', []),
        "cone_lines": diagram.get('cone_lines', []),
        "balls": diagram.get('balls', []),
        "goals": diagram.get('goals', []),
        "mini_goals": diagram.get('mini_goals', []),
        "mannequins": diagram.get('mannequins', []),
        "actions": diagram.get('actions', []),
        "coaching_points": diagram.get('coaching_points', []),
        "variations": diagram.get('variations', [])
    }
    
    if animation:
        full_drill['animation'] = animation
    
    return full_drill


def render_svg(drill_json: Dict) -> Optional[str]:
    """Render drill to SVG and return the SVG content"""
    try:
        from schema import Drill
        from renderer import render
        
        drill = Drill(**drill_json)
        
        with tempfile.NamedTemporaryFile(suffix='.svg', delete=False) as f:
            temp_path = f.name
        
        render(drill, temp_path)
        
        with open(temp_path, 'r') as f:
            svg_content = f.read()
        
        os.unlink(temp_path)
        return svg_content
    
    except Exception as e:
        print(f"    Error rendering SVG: {e}")
        return None


def generate_animation_html(drill_json: Dict, drill_name: str) -> Optional[str]:
    """Generate animation HTML player for a drill"""
    import json
    
    animation = drill_json.get('animation')
    if not animation or not animation.get('keyframes'):
        return None
    
    drill_data_json = json.dumps(drill_json)
    
    # This is the same HTML template from main.py
    html = f'''<!DOCTYPE html>
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
    
    return html


# ============================================================
# UPLOAD FUNCTIONS
# ============================================================

def upload_to_storage(supabase, bucket: str, filename: str, content: str, content_type: str) -> Optional[str]:
    """Upload content to Supabase Storage and return the public URL"""
    try:
        # Upload file
        result = supabase.storage.from_(bucket).upload(
            filename,
            content.encode('utf-8'),
            {"content-type": content_type}
        )
        
        # Get public URL
        public_url = supabase.storage.from_(bucket).get_public_url(filename)
        return public_url
    
    except Exception as e:
        # If file exists, try to update it
        if "already exists" in str(e).lower() or "duplicate" in str(e).lower():
            try:
                supabase.storage.from_(bucket).update(
                    filename,
                    content.encode('utf-8'),
                    {"content-type": content_type}
                )
                return supabase.storage.from_(bucket).get_public_url(filename)
            except:
                pass
        print(f"    Error uploading to storage: {e}")
        return None


def prerender_all_svgs():
    """Main function to pre-render all SVGs"""
    from supabase import create_client
    
    if not SUPABASE_URL or not SUPABASE_KEY:
        print("ERROR: Missing Supabase credentials!")
        return
    
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    
    # Fetch all drills
    print("Fetching drills from Supabase...")
    result = supabase.table('drills').select('*').execute()
    drills = result.data
    print(f"Found {len(drills)} drills")
    
    # Process each drill
    success_count = 0
    error_count = 0
    
    for i, drill in enumerate(drills):
        drill_id = drill['id']
        drill_name = drill['name']
        print(f"\n[{i+1}/{len(drills)}] Processing: {drill_name}")
        
        # Reconstruct full drill JSON
        drill_json = reconstruct_drill_json(drill)
        
        # Render SVG
        print("  Rendering SVG...")
        svg_content = render_svg(drill_json)
        
        if svg_content:
            # Upload SVG
            print("  Uploading SVG...")
            svg_url = upload_to_storage(
                supabase, 
                SVG_BUCKET, 
                f"{drill_id}.svg", 
                svg_content, 
                "image/svg+xml"
            )
            
            if svg_url:
                # Update drill record with SVG URL
                supabase.table('drills').update({
                    'svg_url': svg_url
                }).eq('id', drill_id).execute()
                print(f"  ✓ SVG uploaded: {svg_url[:50]}...")
            else:
                error_count += 1
                continue
        else:
            error_count += 1
            continue
        
        # Generate and upload animation HTML if applicable
        if drill.get('animation_json'):
            print("  Generating animation HTML...")
            animation_html = generate_animation_html(drill_json, drill_name)
            
            if animation_html:
                print("  Uploading animation HTML...")
                animation_url = upload_to_storage(
                    supabase,
                    ANIMATION_BUCKET,
                    f"{drill_id}.html",
                    animation_html,
                    "text/html"
                )
                
                if animation_url:
                    supabase.table('drills').update({
                        'animation_html_url': animation_url
                    }).eq('id', drill_id).execute()
                    print(f"  ✓ Animation uploaded: {animation_url[:50]}...")
        
        success_count += 1
    
    print(f"\n{'='*50}")
    print(f"Pre-rendering complete!")
    print(f"  Success: {success_count}")
    print(f"  Errors: {error_count}")


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Pre-render drill SVGs and upload to Supabase')
    parser.add_argument('--drill-id', help='Only process a specific drill by ID')
    
    args = parser.parse_args()
    
    if args.drill_id:
        # Process single drill (for testing)
        print(f"Processing single drill: {args.drill_id}")
        # TODO: Implement single drill processing
    else:
        prerender_all_svgs()
