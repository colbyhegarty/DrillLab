"""
Migration Script: JSON to Supabase
==================================
This script migrates your drill JSON data to Supabase.

Usage:
1. Install dependencies: pip install supabase python-dotenv
2. Create .env file with your Supabase credentials
3. Run: python migrate_to_supabase.py

The script will:
- Read your JSON file
- Transform each drill into the database format
- Insert into Supabase
- Verify the migration
"""

import json
import os
from pathlib import Path
from typing import Dict, List, Optional
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# ============================================================
# CONFIGURATION
# ============================================================

# Your JSON file path
JSON_FILE_PATH = "library_drills.json"  # Update this path

# Supabase credentials (set these in .env file)
SUPABASE_URL = "https://dgvaiejyixwxallybbcl.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImRndmFpZWp5aXh3eGFsbHliYmNsIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3MDQzMjE2NywiZXhwIjoyMDg2MDA4MTY3fQ.Up0unYsv9iUmyoG22MHGLZRI9y8KyRYcPXCU3h0PDC0"

from supabase import create_client
import json

# 👇 NORMALIZERS GO HERE
def normalize_difficulty(value):
    if not value:
        return None

    normalized = value.strip().upper()

    if normalized not in {"EASY", "MEDIUM", "HARD"}:
        print(f'⚠️ Unknown difficulty: "{value}"')
        return None  # or "MEDIUM"

    return normalized


# ============================================================
# TRANSFORMATION FUNCTIONS
# ============================================================

def generate_drill_id(drill: Dict, index: int) -> str:
    """Generate a URL-friendly ID from the drill name"""
    name = drill.get('name', f'drill-{index}')
    # Convert to lowercase, replace spaces with hyphens, remove special chars
    drill_id = name.lower()
    drill_id = drill_id.replace(' ', '-')
    drill_id = ''.join(c for c in drill_id if c.isalnum() or c == '-')
    drill_id = '-'.join(filter(None, drill_id.split('-')))  # Remove double hyphens
    return drill_id


def extract_diagram_json(drill: Dict) -> Dict:
    """Extract only the diagram-related fields into a separate JSON object"""
    return {
        "field": drill.get("field", {}),
        "players": drill.get("players", []),
        "cones": drill.get("cones", []),
        "cone_gates": drill.get("cone_gates", []),
        "cone_lines": drill.get("cone_lines", []),
        "balls": drill.get("balls", []),
        "goals": drill.get("goals", []),
        "mini_goals": drill.get("mini_goals", []),
        "mannequins": drill.get("mannequins", []),
        "actions": drill.get("actions", []),
        "coaching_points": drill.get("coaching_points", []),
        "variations": drill.get("variations", [])
    }


def extract_animation_json(drill: Dict) -> Optional[Dict]:
    """Extract animation data if it exists"""
    animation = drill.get("animation")
    if animation and isinstance(animation, dict):
        keyframes = animation.get("keyframes", [])
        if keyframes and len(keyframes) > 0:
            return animation
    return None


def transform_drill(drill: Dict, index: int) -> Dict:
    """Transform a drill from JSON format to database format"""
    drill_id = generate_drill_id(drill, index)
    
    return {
        "id": drill_id,
        "name": drill.get("name", "Untitled Drill"),
        "description": drill.get("description"),
        "category": drill.get("category"),
        "difficulty": normalize_difficulty(drill.get("difficulty")),
        "age_group": drill.get("age_group"),
        "player_count": drill.get("player_count"),
        "duration": drill.get("duration"),
        "setup_text": drill.get("setup_text"),
        "instructions_text": drill.get("instructions_text"),
        "variations_text": drill.get("variations_text"),
        "coaching_points_text": drill.get("coaching_points_text"),
        "source": drill.get("source"),
        "source_url": drill.get("source_url"),
        "diagram_json": extract_diagram_json(drill),
        "animation_json": extract_animation_json(drill),
        # These will be populated later by the SVG rendering script
        "svg_url": None,
        "animation_html_url": None,
        "thumbnail_url": None
    }


# ============================================================
# MIGRATION FUNCTIONS
# ============================================================

def load_json_data(file_path: str) -> List[Dict]:
    """Load drills from JSON file"""
    print(f"Loading drills from {file_path}...")
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # Handle different JSON structures
    if isinstance(data, list):
        drills = data
    elif isinstance(data, dict) and 'drills' in data:
        drills = data['drills']
    else:
        drills = list(data.values())
    
    print(f"Loaded {len(drills)} drills")
    return drills


def migrate_to_supabase(drills: List[Dict], batch_size: int = 50):
    """Migrate drills to Supabase in batches"""
    from supabase import create_client
    
    if not SUPABASE_URL or not SUPABASE_KEY:
        print("ERROR: Missing Supabase credentials!")
        print("Please set SUPABASE_URL and SUPABASE_SERVICE_KEY in your .env file")
        return False
    
    # Create Supabase client
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    
    print(f"\nMigrating {len(drills)} drills to Supabase...")
    
    # Transform all drills
    transformed = []
    seen_ids = set()
    
    for i, drill in enumerate(drills):
        record = transform_drill(drill, i)
        
        # Handle duplicate IDs
        base_id = record['id']
        counter = 1
        while record['id'] in seen_ids:
            record['id'] = f"{base_id}-{counter}"
            counter += 1
        seen_ids.add(record['id'])
        
        transformed.append(record)
    
    # Insert in batches
    total_inserted = 0
    errors = []
    
    for i in range(0, len(transformed), batch_size):
        batch = transformed[i:i + batch_size]
        try:
            result = supabase.table('drills').upsert(batch).execute()
            total_inserted += len(batch)
            print(f"  Inserted batch {i // batch_size + 1}: {len(batch)} drills")
        except Exception as e:
            error_msg = f"Error in batch {i // batch_size + 1}: {str(e)}"
            print(f"  {error_msg}")
            errors.append(error_msg)
    
    print(f"\nMigration complete!")
    print(f"  Total inserted: {total_inserted}")
    print(f"  Errors: {len(errors)}")
    
    if errors:
        print("\nErrors encountered:")
        for error in errors:
            print(f"  - {error}")
    
    return len(errors) == 0


def verify_migration():
    """Verify the migration by counting records and spot-checking"""
    from supabase import create_client
    
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    
    print("\nVerifying migration...")
    
    # Count total records
    result = supabase.table('drills').select('id', count='exact').execute()
    total_count = result.count
    print(f"  Total drills in database: {total_count}")
    
    # Count by category
    result = supabase.rpc('get_category_counts').execute()
    print(f"  Categories: {result.data}")
    
    # Count with animation
    result = supabase.table('drills').select('id', count='exact').eq('has_animation', True).execute()
    animation_count = result.count
    print(f"  Drills with animation: {animation_count}")
    
    # Spot check first drill
    result = supabase.table('drills').select('*').limit(1).execute()
    if result.data:
        drill = result.data[0]
        print(f"\n  Sample drill:")
        print(f"    ID: {drill['id']}")
        print(f"    Name: {drill['name']}")
        print(f"    Category: {drill['category']}")
        print(f"    Has animation: {drill['has_animation']}")
        print(f"    Diagram JSON keys: {list(drill['diagram_json'].keys())}")


def export_for_backup(drills: List[Dict], output_path: str = "drills_backup.json"):
    """Export transformed drills as JSON backup"""
    transformed = [transform_drill(drill, i) for i, drill in enumerate(drills)]
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(transformed, f, indent=2, ensure_ascii=False)
    
    print(f"Backup saved to {output_path}")


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Migrate drill JSON to Supabase')
    parser.add_argument('--json', default=JSON_FILE_PATH, help='Path to JSON file')
    parser.add_argument('--verify-only', action='store_true', help='Only verify existing migration')
    parser.add_argument('--backup', action='store_true', help='Create JSON backup of transformed data')
    parser.add_argument('--dry-run', action='store_true', help='Transform but do not insert')
    
    args = parser.parse_args()
    
    if args.verify_only:
        verify_migration()
    else:
        # Load data
        drills = load_json_data(args.json)
        
        if args.backup:
            export_for_backup(drills)
        
        if args.dry_run:
            print("\nDry run - showing first transformed drill:")
            transformed = transform_drill(drills[0], 0)
            print(json.dumps(transformed, indent=2, default=str))
        else:
            # Run migration
            success = migrate_to_supabase(drills)
            
            if success:
                verify_migration()
