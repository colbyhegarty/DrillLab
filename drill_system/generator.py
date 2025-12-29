"""
Drill Generator - LLM-powered drill creation with structured output.

Uses OpenAI's JSON mode to guarantee valid output that conforms to the schema.
"""

import json
import os
from typing import Optional

from openai import OpenAI

from schema import (
    Drill, CoachRequest, CoachConstraints,
    FieldType, AttackingDirection,
    get_reference_positions
)


SYSTEM_PROMPT = """You are an expert soccer/football coach creating training drills.

You will receive a coach's request describing what they want to practice. Generate a complete drill as valid JSON matching the schema provided.

## COORDINATE SYSTEM (CRITICAL)

The field uses normalized 0-100 coordinates:
- X axis: 0 = left sideline, 100 = right sideline, 50 = center
- Y axis: 0 = bottom of diagram, 100 = top of diagram

### ATTACKING NORTH (default - attacking toward top):
- Attacking goal at y=100
- Penalty spot at y=88
- Top of 18-yard box at y=82
- Halfway line at y=50
- Own goal at y=0

### ATTACKING SOUTH (attacking toward bottom):
- Attacking goal at y=0
- Penalty spot at y=12
- Top of 18-yard box at y=18
- Halfway line at y=50
- Own goal at y=100

## PLAYER ID CONVENTIONS
- Attackers: A1, A2, A3...
- Defenders: D1, D2, D3...
- Goalkeeper: GK
- Neutral: N1, N2...

## SPACING GUIDELINES
- Minimum 5-8 units between players for visibility
- Short pass: 10-20 units
- Medium pass: 20-35 units
- Long pass: 35-50 units
- Cone gates: typically 6-10 units wide

## ACTION TYPES
- PASS: Ball movement between players (requires from_player, to_player)
- RUN: Player movement without ball (requires player, to_position)
- DRIBBLE: Player movement with ball (requires player, to_position)
- SHOT: Strike on goal (requires player, target="GOAL")

## RULES
1. All positions must use absolute x,y coordinates (0-100)
2. Every player referenced in actions must exist in the players list
3. Actions should flow logically (ball holder makes passes/dribbles)
4. Place the ball with the player who acts first
5. Include 2-4 specific coaching points
6. Suggest 1-2 variations when appropriate

Generate ONLY valid JSON. No markdown, no explanation, just the JSON object."""


def build_prompt(request: CoachRequest) -> str:
    """Build the user prompt from a coach request"""
    
    refs = get_reference_positions(AttackingDirection.NORTH)
    
    prompt = f"""Create a soccer drill:

GOAL: {request.goal}
"""
    
    if request.secondary_goals:
        prompt += f"SECONDARY GOALS: {', '.join(request.secondary_goals)}\n"
    
    prompt += f"""
CONSTRAINTS:
- Players: {request.constraints.num_players}"""
    
    if request.constraints.num_attackers is not None:
        prompt += f"\n- Attackers: {request.constraints.num_attackers}"
    if request.constraints.num_defenders is not None:
        prompt += f"\n- Defenders: {request.constraints.num_defenders}"
    if request.constraints.has_goalkeeper:
        prompt += "\n- Include goalkeeper: Yes"
    
    prompt += f"\n- Cones available: {'Yes' if request.constraints.has_cones else 'No'}"
    if request.constraints.num_cones:
        prompt += f" ({request.constraints.num_cones} cones)"
    
    prompt += f"\n- Field: {request.constraints.field_size.value}"
    
    if request.constraints.age_group:
        prompt += f"\n- Age group: {request.constraints.age_group}"
    if request.constraints.skill_level:
        prompt += f"\n- Skill level: {request.constraints.skill_level}"
    
    if request.additional_notes:
        prompt += f"\n\nNOTES: {request.additional_notes}"
    
    prompt += f"""

REFERENCE POSITIONS (attacking NORTH):
{json.dumps(refs, indent=2)}

Generate the drill as JSON."""
    
    return prompt


class DrillGenerator:
    """
    Generates soccer drills using an LLM with structured output.
    
    Example:
        generator = DrillGenerator()
        drill = generator.generate(
            goal="Finishing under pressure",
            num_players=6
        )
    """
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "gpt-4o-mini"
    ):
        self.client = OpenAI(api_key=api_key or os.environ.get("OPENAI_API_KEY"))
        self.model = model
    
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
        max_retries: int = 3,
        temperature: float = 0.7
    ) -> Drill:
        """
        Generate a drill from simple parameters.
        
        Args:
            goal: Primary training goal (e.g., "finishing under pressure")
            num_players: Total number of players
            num_attackers: Specific number of attackers (optional)
            num_defenders: Specific number of defenders (optional)
            has_goalkeeper: Whether to include a goalkeeper
            has_cones: Whether cones are available
            num_cones: Specific number of cones (optional)
            field_size: HALF or FULL field
            age_group: e.g., "U14", "Adult"
            skill_level: "beginner", "intermediate", or "advanced"
            additional_notes: Extra instructions for the drill
            max_retries: Number of retry attempts on failure
            temperature: LLM temperature (0.0-1.0)
        
        Returns:
            Drill: Validated drill object
        """
        request = CoachRequest(
            goal=goal,
            constraints=CoachConstraints(
                num_players=num_players,
                num_attackers=num_attackers,
                num_defenders=num_defenders,
                has_goalkeeper=has_goalkeeper,
                has_cones=has_cones,
                num_cones=num_cones,
                field_size=field_size,
                age_group=age_group,
                skill_level=skill_level
            ),
            additional_notes=additional_notes
        )
        
        return self.generate_from_request(request, max_retries, temperature)
    
    def generate_from_request(
        self,
        request: CoachRequest,
        max_retries: int = 3,
        temperature: float = 0.7
    ) -> Drill:
        """
        Generate a drill from a full CoachRequest object.
        """
        user_prompt = build_prompt(request)
        last_error = None
        
        for attempt in range(max_retries):
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": user_prompt}
                    ],
                    response_format={"type": "json_object"},
                    temperature=temperature,
                    max_tokens=4000
                )
                
                content = response.choices[0].message.content
                data = json.loads(content)
                
                # Validate with Pydantic
                drill = Drill.model_validate(data)
                return drill
                
            except json.JSONDecodeError as e:
                last_error = f"JSON decode error: {e}"
                print(f"Attempt {attempt + 1}/{max_retries}: {last_error}")
                
            except Exception as e:
                last_error = str(e)
                print(f"Attempt {attempt + 1}/{max_retries}: {last_error}")
        
        raise RuntimeError(f"Failed to generate valid drill after {max_retries} attempts. Last error: {last_error}")


# Convenience function for simple usage
def generate_drill(goal: str, num_players: int = 6, **kwargs) -> Drill:
    """
    Quick function to generate a drill.
    
    Example:
        drill = generate_drill("Finishing under pressure", num_players=6)
    """
    generator = DrillGenerator()
    return generator.generate(goal=goal, num_players=num_players, **kwargs)
