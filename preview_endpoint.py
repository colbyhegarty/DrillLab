# ============================================================
# ADD THIS TO YOUR main.py FILE
# ============================================================

# Add these imports at the top of main.py:
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, Response
from pydantic import BaseModel
from typing import Optional
import io

# Add this import for the renderer:
from renderer import render
from schema import Drill

# Add this Pydantic model for the request body:
class PreviewRequest(BaseModel):
    diagram_json: dict
    name: Optional[str] = "Preview Drill"
    padding: Optional[float] = 4.0

# Add this endpoint:
@app.post("/api/preview-diagram")
async def preview_diagram(request: PreviewRequest):
    """Generate a preview SVG with custom padding"""
    try:
        # Build full drill data
        full_drill_data = {
            'name': request.name,
            **request.diagram_json
        }
        
        # Create Drill object
        drill = Drill(**full_drill_data)
        
        # Render to a temporary file
        import tempfile
        with tempfile.NamedTemporaryFile(suffix='.svg', delete=False) as tmp:
            tmp_path = tmp.name
        
        # Render with custom padding
        render(drill, tmp_path, padding=request.padding)
        
        # Read the SVG content
        with open(tmp_path, 'r') as f:
            svg_content = f.read()
        
        # Clean up temp file
        import os
        os.unlink(tmp_path)
        
        # Return SVG
        return Response(content=svg_content, media_type="image/svg+xml")
        
    except Exception as e:
        raise HTTPException(500, f"Failed to generate preview: {str(e)}")
