# Soccer Drill Generator - Backend API

A FastAPI backend that generates soccer training drills using Claude AI. Returns both SVG diagrams and coaching descriptions.

## Architecture

```
┌─────────────────────────────────────────┐
│         LOVABLE FRONTEND                │
│   - User inputs drill request           │
│   - Displays SVG + description          │
└─────────────────────────────────────────┘
                    │
                    ▼ HTTP POST
┌─────────────────────────────────────────┐
│         THIS BACKEND (FastAPI)          │
│   - Calls Claude API                    │
│   - Validates drill JSON                │
│   - Renders SVG                         │
└─────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────┐
│         CLAUDE API (Anthropic)          │
│   - Generates drill structure           │
│   - Writes coach description            │
└─────────────────────────────────────────┘
```

## Quick Start (Local Development)

### 1. Clone and setup

```bash
cd drill_backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Set environment variable

```bash
export ANTHROPIC_API_KEY=sk-ant-your-key-here
```

### 3. Run the server

```bash
python main.py
# or
uvicorn main:app --reload --port 8000
```

### 4. Test the API

```bash
curl -X POST http://localhost:8000/api/generate-drill \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Create a 2v1 finishing drill", "num_players": 4}'
```

---

## Deploy to Render.com (Recommended)

Render.com offers free tier hosting perfect for this API.

### Step 1: Push to GitHub

```bash
# Create a new GitHub repository, then:
git init
git add .
git commit -m "Initial commit"
git remote add origin https://github.com/YOUR_USERNAME/soccer-drill-api.git
git push -u origin main
```

### Step 2: Deploy on Render

1. Go to [render.com](https://render.com) and sign up/login
2. Click **"New +"** → **"Web Service"**
3. Connect your GitHub repository
4. Configure:
   - **Name**: `soccer-drill-api`
   - **Environment**: `Python 3`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `uvicorn main:app --host 0.0.0.0 --port $PORT`
5. Add Environment Variable:
   - Key: `ANTHROPIC_API_KEY`
   - Value: Your Anthropic API key
6. Click **"Create Web Service"**

Your API will be live at: `https://soccer-drill-api.onrender.com`

---

## API Endpoints

### `POST /api/generate-drill`

Generate a new drill from natural language.

**Request:**
```json
{
  "prompt": "Create a passing drill focused on quick one-touch combinations",
  "num_players": 6,
  "include_goalkeeper": true,
  "field_type": "HALF",
  "skill_level": "intermediate"
}
```

**Response:**
```json
{
  "success": true,
  "drill_name": "One-Touch Passing Diamond",
  "svg": "base64-encoded-svg-string...",
  "description": "# One-Touch Passing Diamond\n\n## Overview\n...",
  "drill_json": { ... }
}
```

### `POST /api/render-drill`

Re-render an existing drill JSON (for editing/saving).

**Request:** Raw drill JSON object

**Response:** Same as above (without description)

### `GET /health`

Health check endpoint.

---

## Connecting to Lovable

### Step 1: Create Lovable Project

1. Go to [lovable.dev](https://lovable.dev)
2. Create a new project
3. Describe your app: *"A soccer drill generator app where users can describe a drill and get a diagram and coaching instructions"*

### Step 2: Tell Lovable About Your API

In the Lovable chat, paste this prompt:

```
I have a backend API deployed at [YOUR_RENDER_URL]. Please create a frontend that:

1. Has an input form with:
   - Text input for drill description (required)
   - Number input for player count (2-22, default 6)
   - Checkbox for "Include Goalkeeper" (default true)
   - Select for field type: "Half Field" or "Full Field"
   - Select for skill level: "Beginner", "Intermediate", "Advanced" (optional)
   - A "Generate Drill" button

2. When the form is submitted, call my API:
   POST [YOUR_RENDER_URL]/api/generate-drill
   Content-Type: application/json
   Body: {
     "prompt": "<user's description>",
     "num_players": <player count>,
     "include_goalkeeper": <boolean>,
     "field_type": "HALF" or "FULL",
     "skill_level": "beginner" | "intermediate" | "advanced" | null
   }

3. Display the results:
   - Show loading state while waiting
   - Display the SVG diagram (decode from base64)
   - Render the markdown description below
   - Add download buttons for SVG and description

4. The API response format is:
   {
     "success": boolean,
     "drill_name": string,
     "svg": string (base64 encoded),
     "description": string (markdown),
     "drill_json": object
   }

5. Handle errors gracefully - show error messages from the API.
```

### Step 3: Example Lovable Component Code

If Lovable needs help, share this React component pattern:

```jsx
import { useState } from 'react';
import ReactMarkdown from 'react-markdown';

const API_URL = 'https://your-api.onrender.com';

export default function DrillGenerator() {
  const [prompt, setPrompt] = useState('');
  const [numPlayers, setNumPlayers] = useState(6);
  const [includeGK, setIncludeGK] = useState(true);
  const [fieldType, setFieldType] = useState('HALF');
  const [skillLevel, setSkillLevel] = useState('');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);

  const generateDrill = async () => {
    setLoading(true);
    setError(null);
    
    try {
      const response = await fetch(`${API_URL}/api/generate-drill`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          prompt,
          num_players: numPlayers,
          include_goalkeeper: includeGK,
          field_type: fieldType,
          skill_level: skillLevel || null
        })
      });
      
      const data = await response.json();
      
      if (!response.ok) {
        throw new Error(data.detail || 'Failed to generate drill');
      }
      
      setResult(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const downloadSVG = () => {
    const svgContent = atob(result.svg);
    const blob = new Blob([svgContent], { type: 'image/svg+xml' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${result.drill_name.replace(/\s+/g, '_')}.svg`;
    a.click();
  };

  return (
    <div className="max-w-4xl mx-auto p-6">
      <h1 className="text-3xl font-bold mb-6">Soccer Drill Generator</h1>
      
      {/* Input Form */}
      <div className="space-y-4 mb-8">
        <div>
          <label className="block text-sm font-medium mb-1">
            Describe your drill
          </label>
          <textarea
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            placeholder="e.g., Create a 2v1 finishing drill with overlapping runs"
            className="w-full p-3 border rounded-lg"
            rows={3}
          />
        </div>
        
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium mb-1">
              Number of Players
            </label>
            <input
              type="number"
              min={2}
              max={22}
              value={numPlayers}
              onChange={(e) => setNumPlayers(parseInt(e.target.value))}
              className="w-full p-2 border rounded"
            />
          </div>
          
          <div>
            <label className="block text-sm font-medium mb-1">
              Field Type
            </label>
            <select
              value={fieldType}
              onChange={(e) => setFieldType(e.target.value)}
              className="w-full p-2 border rounded"
            >
              <option value="HALF">Half Field</option>
              <option value="FULL">Full Field</option>
            </select>
          </div>
        </div>
        
        <div className="flex items-center gap-4">
          <label className="flex items-center gap-2">
            <input
              type="checkbox"
              checked={includeGK}
              onChange={(e) => setIncludeGK(e.target.checked)}
            />
            Include Goalkeeper
          </label>
          
          <select
            value={skillLevel}
            onChange={(e) => setSkillLevel(e.target.value)}
            className="p-2 border rounded"
          >
            <option value="">Any Skill Level</option>
            <option value="beginner">Beginner</option>
            <option value="intermediate">Intermediate</option>
            <option value="advanced">Advanced</option>
          </select>
        </div>
        
        <button
          onClick={generateDrill}
          disabled={loading || !prompt.trim()}
          className="w-full py-3 bg-blue-600 text-white rounded-lg font-medium
                     disabled:bg-gray-400 hover:bg-blue-700"
        >
          {loading ? 'Generating...' : 'Generate Drill'}
        </button>
      </div>
      
      {/* Error Display */}
      {error && (
        <div className="p-4 bg-red-100 text-red-700 rounded-lg mb-6">
          {error}
        </div>
      )}
      
      {/* Results */}
      {result && (
        <div className="space-y-6">
          <div className="flex items-center justify-between">
            <h2 className="text-2xl font-bold">{result.drill_name}</h2>
            <button
              onClick={downloadSVG}
              className="px-4 py-2 bg-green-600 text-white rounded hover:bg-green-700"
            >
              Download SVG
            </button>
          </div>
          
          {/* SVG Diagram */}
          <div className="border rounded-lg p-4 bg-gray-50">
            <img
              src={`data:image/svg+xml;base64,${result.svg}`}
              alt={result.drill_name}
              className="max-w-full mx-auto"
            />
          </div>
          
          {/* Description */}
          <div className="prose max-w-none">
            <ReactMarkdown>{result.description}</ReactMarkdown>
          </div>
        </div>
      )}
    </div>
  );
}
```

### Step 4: Environment Variables in Lovable

If you need to store the API URL as an environment variable in Lovable:

1. Go to your Lovable project settings
2. Add environment variable:
   - `VITE_API_URL` = `https://your-api.onrender.com`
3. Access it in code as `import.meta.env.VITE_API_URL`

---

## Troubleshooting

### CORS Errors

The backend is configured to allow Lovable domains. If you see CORS errors:
1. Check the `allow_origins` list in `main.py`
2. Add your specific Lovable domain if needed

### API Key Errors

- Ensure `ANTHROPIC_API_KEY` is set in Render dashboard
- Key should start with `sk-ant-`
- Check Anthropic console for usage/billing

### Render Cold Starts

Free tier Render instances sleep after inactivity. First request may take 30-60 seconds.

Solutions:
- Upgrade to paid tier ($7/month)
- Use a health check service to ping your API every 10 minutes
- Show loading state in frontend

---

## File Structure

```
drill_backend/
├── main.py              # FastAPI application
├── requirements.txt     # Python dependencies
├── Dockerfile          # For container deployment
├── render.yaml         # Render.com configuration
├── .env.example        # Environment variable template
├── README.md           # This file
└── drill_system/       # Drill rendering package
    ├── __init__.py
    ├── schema.py       # Pydantic models
    ├── renderer.py     # SVG generation
    ├── validator.py    # Drill validation
    ├── generator.py    # (unused in API - Claude handles generation)
    └── fixtures.py     # Example drills
```

---

## Cost Estimates

### Anthropic API
- ~$0.003 per drill (Claude Sonnet, ~1500 tokens in/out)
- 1000 drills ≈ $3

### Render.com
- Free tier: Works, but has cold starts
- Starter ($7/mo): Always on, faster

### Lovable
- Check lovable.dev for current pricing

---

## License

MIT License - feel free to use and modify.
