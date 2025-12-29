"""
Drill Pipeline - Complete end-to-end drill generation.

This is the main entry point for generating drills. It orchestrates:
1. LLM generation with structured output
2. Validation (structural + semantic)
3. Rendering to SVG/PNG

Usage:
    from pipeline import DrillPipeline
    
    pipeline = DrillPipeline()
    result = pipeline.generate(
        goal="Finishing under pressure",
        num_players=6,
        output_svg="drill.svg"
    )
"""

import json
import os
from pathlib import Path
from typing import Optional, List
from dataclasses import dataclass

from schema import Drill, CoachRequest, CoachConstraints, FieldType
from generator import DrillGenerator
from validator import validate_drill, ValidationResult
from renderer import render, render_to_png


@dataclass
class PipelineResult:
    """Result of drill generation pipeline"""
    drill: Drill
    validation: ValidationResult
    svg_path: Optional[str] = None
    png_path: Optional[str] = None
    json_path: Optional[str] = None
    
    @property
    def is_valid(self) -> bool:
        return self.validation.is_valid
    
    @property
    def errors(self) -> List[str]:
        return [e.message for e in self.validation.errors]
    
    @property
    def warnings(self) -> List[str]:
        return [w.message for w in self.validation.warnings]


class DrillPipeline:
    """
    Complete pipeline for generating soccer drills.
    
    Example:
        pipeline = DrillPipeline()
        
        # Simple usage
        result = pipeline.generate(
            goal="Finishing under pressure",
            num_players=6,
            output_svg="drill.svg"
        )
        
        # Access the drill
        print(result.drill.name)
        print(result.drill.coaching_points)
        
        # Check validation
        if not result.is_valid:
            print("Errors:", result.errors)
    """
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "gpt-4o-mini"
    ):
        self.generator = DrillGenerator(api_key=api_key, model=model)
    
    def generate(
        self,
        goal: str,
        num_players: int = 6,
        num_attackers: Optional[int] = None,
        num_defenders: Optional[int] = None,
        has_goalkeeper: bool = False,
        has_cones: bool = True,
        num_cones: Optional[int] = None,
        field_size: FieldType = FieldType.HALF,
        age_group: Optional[str] = None,
        skill_level: Optional[str] = None,
        additional_notes: Optional[str] = None,
        output_svg: Optional[str] = None,
        output_png: Optional[str] = None,
        output_json: Optional[str] = None,
        max_retries: int = 3
    ) -> PipelineResult:
        """
        Generate a complete drill with validation and rendering.
        
        Args:
            goal: Primary training goal (e.g., "finishing under pressure")
            num_players: Total number of players
            num_attackers: Number of attackers (optional)
            num_defenders: Number of defenders (optional)
            has_goalkeeper: Include goalkeeper
            has_cones: Cones available
            num_cones: Number of cones (optional)
            field_size: HALF or FULL field
            age_group: e.g., "U14"
            skill_level: "beginner", "intermediate", "advanced"
            additional_notes: Extra instructions
            output_svg: Path to save SVG (optional)
            output_png: Path to save PNG (optional)
            output_json: Path to save JSON (optional)
            max_retries: LLM retry attempts
        
        Returns:
            PipelineResult with drill, validation, and file paths
        """
        # Generate drill
        drill = self.generator.generate(
            goal=goal,
            num_players=num_players,
            num_attackers=num_attackers,
            num_defenders=num_defenders,
            has_goalkeeper=has_goalkeeper,
            has_cones=has_cones,
            num_cones=num_cones,
            field_size=field_size,
            age_group=age_group,
            skill_level=skill_level,
            additional_notes=additional_notes,
            max_retries=max_retries
        )
        
        # Validate
        validation = validate_drill(drill, goal=goal)
        
        # Create result
        result = PipelineResult(drill=drill, validation=validation)
        
        # Render outputs
        if output_svg:
            result.svg_path = render(drill, output_svg)
        
        if output_png:
            result.png_path = render_to_png(drill, output_png)
        
        if output_json:
            with open(output_json, 'w') as f:
                json.dump(drill.model_dump(), f, indent=2)
            result.json_path = output_json
        
        return result
    
    def generate_from_json(
        self,
        json_path: str,
        output_svg: Optional[str] = None,
        output_png: Optional[str] = None
    ) -> PipelineResult:
        """
        Load a drill from JSON and validate/render it.
        
        Useful for testing or re-rendering saved drills.
        """
        with open(json_path) as f:
            data = json.load(f)
        
        drill = Drill.model_validate(data)
        validation = validate_drill(drill)
        
        result = PipelineResult(drill=drill, validation=validation)
        
        if output_svg:
            result.svg_path = render(drill, output_svg)
        
        if output_png:
            result.png_path = render_to_png(drill, output_png)
        
        return result


# ============================================================
# CLI
# ============================================================

def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Generate soccer drill diagrams",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Generate a finishing drill
  python pipeline.py "Finishing under pressure" -p 6 -o drill.svg
  
  # Generate with specific constraints
  python pipeline.py "Passing combinations" -p 8 --attackers 5 --defenders 3 --gk
  
  # Render from existing JSON
  python pipeline.py --from-json drill.json -o drill.svg
        """
    )
    
    parser.add_argument(
        "goal",
        nargs="?",
        help="Drill goal (e.g., 'Finishing under pressure')"
    )
    parser.add_argument(
        "-p", "--players",
        type=int,
        default=6,
        help="Number of players (default: 6)"
    )
    parser.add_argument(
        "--attackers",
        type=int,
        help="Number of attackers"
    )
    parser.add_argument(
        "--defenders",
        type=int,
        help="Number of defenders"
    )
    parser.add_argument(
        "--gk", "--goalkeeper",
        action="store_true",
        help="Include goalkeeper"
    )
    parser.add_argument(
        "--no-cones",
        action="store_true",
        help="No cones available"
    )
    parser.add_argument(
        "--full-field",
        action="store_true",
        help="Use full field instead of half"
    )
    parser.add_argument(
        "--age",
        type=str,
        help="Age group (e.g., U14)"
    )
    parser.add_argument(
        "--skill",
        choices=["beginner", "intermediate", "advanced"],
        help="Skill level"
    )
    parser.add_argument(
        "-o", "--output",
        type=str,
        default="drill.svg",
        help="Output SVG path (default: drill.svg)"
    )
    parser.add_argument(
        "--png",
        type=str,
        help="Also output PNG to this path"
    )
    parser.add_argument(
        "--json",
        type=str,
        help="Also save JSON to this path"
    )
    parser.add_argument(
        "--from-json",
        type=str,
        help="Load drill from JSON instead of generating"
    )
    parser.add_argument(
        "--model",
        type=str,
        default="gpt-4o-mini",
        help="OpenAI model to use (default: gpt-4o-mini)"
    )
    
    args = parser.parse_args()
    
    # Check API key
    if not args.from_json and not os.environ.get("OPENAI_API_KEY"):
        print("Error: OPENAI_API_KEY environment variable not set")
        print("Set it with: export OPENAI_API_KEY='your-key'")
        return 1
    
    pipeline = DrillPipeline(model=args.model)
    
    if args.from_json:
        # Render from existing JSON
        result = pipeline.generate_from_json(
            args.from_json,
            output_svg=args.output,
            output_png=args.png
        )
        print(f"Loaded: {result.drill.name}")
    else:
        if not args.goal:
            parser.print_help()
            print("\nError: goal is required")
            return 1
        
        # Generate new drill
        result = pipeline.generate(
            goal=args.goal,
            num_players=args.players,
            num_attackers=args.attackers,
            num_defenders=args.defenders,
            has_goalkeeper=args.gk,
            has_cones=not args.no_cones,
            field_size=FieldType.FULL if args.full_field else FieldType.HALF,
            age_group=args.age,
            skill_level=args.skill,
            output_svg=args.output,
            output_png=args.png,
            output_json=args.json
        )
    
    # Print summary
    print("\n" + "=" * 50)
    print(f"DRILL: {result.drill.name}")
    print("=" * 50)
    print(f"\n{result.drill.description}")
    
    print(f"\nPlayers: {len(result.drill.players)}")
    print(f"Actions: {len(result.drill.actions)}")
    
    if result.drill.coaching_points:
        print("\nCoaching Points:")
        for point in result.drill.coaching_points:
            print(f"  • {point}")
    
    if result.drill.variations:
        print("\nVariations:")
        for var in result.drill.variations:
            print(f"  • {var}")
    
    # Validation results
    if result.errors:
        print("\n⚠ Validation Errors:")
        for error in result.errors:
            print(f"  ✗ {error}")
    
    if result.warnings:
        print("\nWarnings:")
        for warning in result.warnings:
            print(f"  ⚡ {warning}")
    
    # Output files
    print("\nGenerated Files:")
    if result.svg_path:
        print(f"  SVG: {result.svg_path}")
    if result.png_path:
        print(f"  PNG: {result.png_path}")
    if result.json_path:
        print(f"  JSON: {result.json_path}")
    
    return 0


if __name__ == "__main__":
    exit(main())
