"""
Test Runner - Validates the drill system with predefined fixtures.

Run this to verify the system works without needing API calls.

Usage:
    python tests.py
"""

import json
import sys
from pathlib import Path

from schema import Drill
from validator import validate_drill, StructuralValidator, SemanticValidator
from renderer import render
from fixtures import ALL_FIXTURES


def test_schema_validation():
    """Test that all fixtures pass schema validation"""
    print("=" * 50)
    print("SCHEMA VALIDATION")
    print("=" * 50)
    
    passed = 0
    failed = 0
    
    for name, data in ALL_FIXTURES.items():
        try:
            drill = Drill.model_validate(data)
            print(f"  ✓ {name}")
            passed += 1
        except Exception as e:
            print(f"  ✗ {name}: {e}")
            failed += 1
    
    print(f"\nPassed: {passed}/{passed + failed}")
    return failed == 0


def test_structural_validation():
    """Test structural validation on all fixtures"""
    print("\n" + "=" * 50)
    print("STRUCTURAL VALIDATION")
    print("=" * 50)
    
    all_passed = True
    
    for name, data in ALL_FIXTURES.items():
        drill = Drill.model_validate(data)
        result = StructuralValidator(drill).validate()
        
        errors = [i for i in result.issues if i.severity == "error"]
        warnings = [i for i in result.issues if i.severity == "warning"]
        
        if errors:
            print(f"  ✗ {name}")
            for e in errors:
                print(f"      Error: {e.message}")
            all_passed = False
        else:
            print(f"  ✓ {name}")
            if warnings:
                for w in warnings:
                    print(f"      Warning: {w.message}")
    
    return all_passed


def test_semantic_validation():
    """Test semantic validation matches drill goals"""
    print("\n" + "=" * 50)
    print("SEMANTIC VALIDATION")
    print("=" * 50)
    
    test_cases = [
        ("finishing_2v1", "finishing"),
        ("passing_triangle", "passing"),
        ("dribble_through_gates", "dribbling"),
        ("crossing_and_finishing", "crossing"),
    ]
    
    all_passed = True
    
    for fixture_name, goal_keyword in test_cases:
        data = ALL_FIXTURES[fixture_name]
        drill = Drill.model_validate(data)
        result = SemanticValidator(drill).validate_goal(goal_keyword)
        
        errors = [i for i in result.issues if i.severity == "error"]
        
        if errors:
            print(f"  ✗ {fixture_name} vs '{goal_keyword}'")
            for e in errors:
                print(f"      {e.message}")
            all_passed = False
        else:
            print(f"  ✓ {fixture_name} matches '{goal_keyword}'")
    
    return all_passed


def test_rendering():
    """Test rendering all fixtures to SVG"""
    print("\n" + "=" * 50)
    print("RENDERING")
    print("=" * 50)
    
    output_dir = Path("test_output")
    output_dir.mkdir(exist_ok=True)
    
    all_passed = True
    
    for name, data in ALL_FIXTURES.items():
        try:
            drill = Drill.model_validate(data)
            output_path = output_dir / f"{name}.svg"
            render(drill, str(output_path))
            print(f"  ✓ {name} -> {output_path}")
        except Exception as e:
            print(f"  ✗ {name}: {e}")
            all_passed = False
    
    return all_passed


def test_json_roundtrip():
    """Test that drills can be serialized and deserialized"""
    print("\n" + "=" * 50)
    print("JSON ROUND-TRIP")
    print("=" * 50)
    
    all_passed = True
    
    for name, data in ALL_FIXTURES.items():
        try:
            # Parse
            drill = Drill.model_validate(data)
            
            # Serialize
            json_str = json.dumps(drill.model_dump())
            
            # Deserialize
            loaded = json.loads(json_str)
            drill2 = Drill.model_validate(loaded)
            
            # Compare
            assert drill.name == drill2.name
            assert len(drill.players) == len(drill2.players)
            assert len(drill.actions) == len(drill2.actions)
            
            print(f"  ✓ {name}")
        except Exception as e:
            print(f"  ✗ {name}: {e}")
            all_passed = False
    
    return all_passed


def run_all_tests():
    """Run all tests"""
    print("\n" + "=" * 50)
    print("DRILL SYSTEM TEST SUITE")
    print("=" * 50)
    
    results = {
        "Schema Validation": test_schema_validation(),
        "Structural Validation": test_structural_validation(),
        "Semantic Validation": test_semantic_validation(),
        "Rendering": test_rendering(),
        "JSON Round-trip": test_json_roundtrip(),
    }
    
    print("\n" + "=" * 50)
    print("SUMMARY")
    print("=" * 50)
    
    all_passed = True
    for test_name, passed in results.items():
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"  {status}: {test_name}")
        if not passed:
            all_passed = False
    
    print()
    if all_passed:
        print("All tests passed! ✓")
        return 0
    else:
        print("Some tests failed. ✗")
        return 1


if __name__ == "__main__":
    sys.exit(run_all_tests())
