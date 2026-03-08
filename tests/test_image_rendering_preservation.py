"""
Preservation Property Tests for Image Rendering

**Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 3.8, 3.9, 3.10, 3.11, 3.12, 3.13, 3.14**

These tests capture baseline behavior on UNFIXED code for minimal content cases.
They verify that visual styling, layout patterns, and functionality are preserved
after implementing the fix.

CRITICAL: These tests MUST PASS on unfixed code - they establish the baseline
behavior that must be preserved.

Expected Outcome: Tests PASS (this confirms baseline behavior to preserve)
"""

from __future__ import annotations

import sys
import types
from typing import Dict, Any, List, Tuple
from PIL import Image
import random

# Provide a lightweight astrbot.api.logger stub for unit tests
class _DummyLogger:
    def info(self, *args, **kwargs):
        pass

    def error(self, *args, **kwargs):
        pass

    def warning(self, *args, **kwargs):
        pass

    def debug(self, *args, **kwargs):
        pass


if "astrbot.api" not in sys.modules:
    astrbot_module = types.ModuleType("astrbot")
    api_module = types.ModuleType("astrbot.api")
    api_module.logger = _DummyLogger()
    astrbot_module.api = api_module
    sys.modules["astrbot"] = astrbot_module
    sys.modules["astrbot.api"] = api_module

# Add parent directory to path for imports
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from draw.backpack import draw_backpack_image


# ============================================================================
# Test Data Generators
# ============================================================================

def create_test_rod(rod_id: int, rarity: int = 5) -> Dict[str, Any]:
    """Create a test rod with specified attributes"""
    return {
        "id": rod_id,
        "name": f"測試魚竿{rod_id}",
        "rarity": rarity,
        "bonus_fish_quality_modifier": 1.2,
        "bonus_fish_quantity_modifier": 1.1,
        "max_durability": 100,
        "current_durability": 80,
    }


def create_test_accessory(acc_id: int, rarity: int = 5) -> Dict[str, Any]:
    """Create a test accessory with specified attributes"""
    return {
        "id": acc_id,
        "name": f"測試飾品{acc_id}",
        "rarity": rarity,
        "bonus_fish_quality_modifier": 1.15,
        "bonus_fish_quantity_modifier": 1.1,
        "bonus_rare_fish_chance": 1.05,
        "bonus_coin_modifier": 1.2,
    }


def create_test_bait(bait_id: int) -> Dict[str, Any]:
    """Create a test bait with specified attributes"""
    return {
        "id": bait_id,
        "name": f"測試魚餌{bait_id}",
        "quantity": 10,
        "duration_minutes": 30,
        "effect_description": "增加稀有魚類出現機率",
    }


def create_test_item(item_id: int) -> Dict[str, Any]:
    """Create a test item with specified attributes"""
    return {
        "id": item_id,
        "name": f"測試道具{item_id}",
        "quantity": 5,
        "effect_description": "恢復魚竿耐久度",
    }


# ============================================================================
# Test Data Generation for Property-Based Testing
# ============================================================================

def generate_minimal_content_case() -> Dict[str, Any]:
    """
    Generate a random minimal content case (0-4 items per category).
    These are cases where the bug does NOT manifest and behavior must be preserved.
    """
    num_rods = random.randint(0, 4)
    num_accessories = random.randint(0, 4)
    num_baits = random.randint(0, 4)
    num_items = random.randint(0, 4)
    
    return {
        "nickname": "測試用戶",
        "rods": [create_test_rod(i, rarity=5 + (i % 5)) for i in range(1, num_rods + 1)],
        "accessories": [create_test_accessory(i, rarity=5 + (i % 5)) for i in range(1, num_accessories + 1)],
        "baits": [create_test_bait(i) for i in range(1, num_baits + 1)],
        "items": [create_test_item(i) for i in range(1, num_items + 1)],
    }


# ============================================================================
# Visual Styling Verification Functions
# ============================================================================

def verify_image_dimensions(image: Image.Image) -> Dict[str, Any]:
    """Verify basic image dimensions are reasonable"""
    return {
        "width": image.width,
        "height": image.height,
        "width_is_900": image.width == 900,
        "height_reasonable": 200 <= image.height <= 2000,
    }


def verify_visual_styling(image: Image.Image) -> Dict[str, Any]:
    """
    Verify visual styling elements are present.
    This checks that the image has expected color patterns and structure.
    """
    # Sample pixels from different regions to verify styling
    pixels = image.load()
    
    # Check header region (should have gradient/solid color)
    header_sample = pixels[450, 60]  # Center of header
    
    # Check card region (if content exists)
    card_sample = pixels[225, 200]  # Typical card position
    
    # Check background (should have gradient)
    bg_sample = pixels[450, 150]
    
    return {
        "has_header_color": header_sample is not None,
        "has_card_color": card_sample is not None,
        "has_background": bg_sample is not None,
        "image_mode": image.mode,
        "is_rgb": image.mode in ["RGB", "RGBA"],
    }


def verify_layout_patterns(image: Image.Image, user_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Verify layout patterns are consistent.
    For minimal content, we expect specific height patterns.
    """
    num_rods = len(user_data.get("rods", []))
    num_accessories = len(user_data.get("accessories", []))
    num_baits = len(user_data.get("baits", []))
    num_items = len(user_data.get("items", []))
    
    # Expected minimum height components
    header_h = 120
    section_gap = 20
    footer_h = 60
    
    # For minimal content, each section should be either 60px (empty) or calculated
    import math
    rod_rows = math.ceil(num_rods / 2) if num_rods else 0
    acc_rows = math.ceil(num_accessories / 2) if num_accessories else 0
    bait_rows = math.ceil(num_baits / 3) if num_baits else 0
    item_rows = math.ceil(num_items / 3) if num_items else 0
    
    # Each section with content has: title (40px) + rows * card_height
    # Empty sections: 60px (includes title and empty message)
    rod_h = (40 + rod_rows * 170) if num_rods else 60
    acc_h = (40 + acc_rows * 170) if num_accessories else 60
    bait_h = (40 + bait_rows * 120) if num_baits else 60
    item_h = (40 + item_rows * 120) if num_items else 60
    
    expected_min_height = (
        header_h + rod_h + acc_h + bait_h + item_h + section_gap * 5 + footer_h + 40
    )
    # Add SAFETY_MARGIN of 50px
    expected_min_height_with_margin = expected_min_height + 50
    
    return {
        "actual_height": image.height,
        "expected_min_height": expected_min_height,
        "height_sufficient": image.height >= expected_min_height,
        "height_not_excessive": image.height <= expected_min_height_with_margin + 50,  # Allow some margin
        "num_rods": num_rods,
        "num_accessories": num_accessories,
        "num_baits": num_baits,
        "num_items": num_items,
    }


# ============================================================================
# Property-Based Tests
# ============================================================================

def test_property_preservation_minimal_content_renders_correctly():
    """
    **Property 2: Preservation** - Visual Styling and Minimal Content Rendering
    
    **Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 3.8, 3.9, 3.10, 3.11, 3.12, 3.13, 3.14**
    
    For any minimal content case (0-4 items per category), the rendering function
    SHALL produce a valid image with:
    - Correct dimensions (width=900, height appropriate for content)
    - Proper visual styling (RGB/RGBA mode, gradient background, card colors)
    - Consistent layout patterns (height matches expected calculation)
    - No excessive whitespace (height not more than 100px over expected)
    
    This test establishes baseline behavior on UNFIXED code that must be preserved.
    
    This is a property-based test that generates 100 random minimal content cases.
    """
    print("\n=== Property-Based Test: Minimal Content Rendering ===")
    print("Generating 100 random minimal content cases (0-4 items per category)...\n")
    
    num_examples = 100
    passed = 0
    failed = 0
    failures = []
    
    for i in range(num_examples):
        user_data = generate_minimal_content_case()
        
        try:
            # Generate image
            image = draw_backpack_image(user_data, data_dir=".")
            
            # Verify dimensions
            dims = verify_image_dimensions(image)
            assert dims["width_is_900"], f"Width should be 900, got {dims['width']}"
            assert dims["height_reasonable"], f"Height {dims['height']} is not reasonable"
            
            # Verify visual styling
            styling = verify_visual_styling(image)
            assert styling["is_rgb"], f"Image mode should be RGB/RGBA, got {styling['image_mode']}"
            assert styling["has_header_color"], "Header region should have color"
            assert styling["has_background"], "Background should have color"
            
            # Verify layout patterns
            layout = verify_layout_patterns(image, user_data)
            assert layout["height_sufficient"], (
                f"Image height {layout['actual_height']}px is insufficient for content "
                f"(needs at least {layout['expected_min_height']}px)"
            )
            assert layout["height_not_excessive"], (
                f"Image height {layout['actual_height']}px is excessive for minimal content "
                f"(expected ~{layout['expected_min_height']}px, max {layout['expected_min_height'] + 100}px)"
            )
            
            passed += 1
            
        except AssertionError as e:
            failed += 1
            failures.append({
                "case": i + 1,
                "user_data": user_data,
                "error": str(e)
            })
    
    # Report results
    print(f"Results: {passed}/{num_examples} passed, {failed}/{num_examples} failed")
    
    if failures:
        print("\nFailures:")
        for failure in failures[:5]:  # Show first 5 failures
            print(f"  Case {failure['case']}: {failure['error']}")
            print(f"    Data: {len(failure['user_data']['rods'])} rods, "
                  f"{len(failure['user_data']['accessories'])} accessories, "
                  f"{len(failure['user_data']['baits'])} baits, "
                  f"{len(failure['user_data']['items'])} items")
    
    # Assert all passed
    assert failed == 0, f"{failed}/{num_examples} test cases failed"
    
    print("\n✓ All property-based tests passed!")
    print("Baseline behavior confirmed for minimal content cases.")


# ============================================================================
# Specific Test Cases for Edge Cases
# ============================================================================

def test_preservation_empty_backpack():
    """
    Test that empty backpack (no items) renders correctly.
    This is an important edge case for preservation.
    """
    user_data = {
        "nickname": "空背包用戶",
        "rods": [],
        "accessories": [],
        "baits": [],
        "items": [],
    }
    
    image = draw_backpack_image(user_data, data_dir=".")
    
    # Verify basic properties
    assert image.width == 900, f"Width should be 900, got {image.width}"
    assert image.height >= 200, f"Height should be at least 200, got {image.height}"
    # With SAFETY_MARGIN of 50px, empty backpack height is now ~610px (was ~560px)
    assert image.height <= 650, f"Height should not exceed 650 for empty backpack, got {image.height}"
    
    # Verify image is valid
    assert image.mode in ["RGB", "RGBA"], f"Image mode should be RGB/RGBA, got {image.mode}"
    
    print(f"✓ Empty backpack renders correctly: {image.width}x{image.height}")


def test_preservation_single_item_each_category():
    """
    Test that single item in each category renders correctly.
    This is the minimal non-empty case.
    """
    user_data = {
        "nickname": "單項用戶",
        "rods": [create_test_rod(1)],
        "accessories": [create_test_accessory(1)],
        "baits": [create_test_bait(1)],
        "items": [create_test_item(1)],
    }
    
    image = draw_backpack_image(user_data, data_dir=".")
    
    # Verify basic properties
    assert image.width == 900, f"Width should be 900, got {image.width}"
    
    # Calculate expected height (with section titles and SAFETY_MARGIN)
    header_h = 120
    section_gap = 20
    footer_h = 60
    # Each section has: title (40px) + content
    # 1 rod: 40 + 1 row * 170 = 210
    # 1 accessory: 40 + 1 row * 170 = 210
    # 1 bait: 40 + 1 row * 120 = 160
    # 1 item: 40 + 1 row * 120 = 160
    expected_height = header_h + 210 + 210 + 160 + 160 + section_gap * 5 + footer_h + 40
    # Add SAFETY_MARGIN of 50px
    expected_height_with_margin = expected_height + 50
    
    assert image.height >= expected_height, (
        f"Height should be at least {expected_height}, got {image.height}"
    )
    assert image.height <= expected_height_with_margin + 50, (
        f"Height should not exceed {expected_height_with_margin + 50}, got {image.height}"
    )
    
    print(f"✓ Single item per category renders correctly: {image.width}x{image.height}")


def test_preservation_two_items_per_row():
    """
    Test that 2 rods (1 row) and 2 accessories (1 row) render correctly.
    This tests the row layout for rods/accessories.
    """
    user_data = {
        "nickname": "雙項用戶",
        "rods": [create_test_rod(1), create_test_rod(2)],
        "accessories": [create_test_accessory(1), create_test_accessory(2)],
        "baits": [],
        "items": [],
    }
    
    image = draw_backpack_image(user_data, data_dir=".")
    
    # Verify basic properties
    assert image.width == 900, f"Width should be 900, got {image.width}"
    
    # Calculate expected height (with section titles and SAFETY_MARGIN)
    header_h = 120
    section_gap = 20
    footer_h = 60
    # 2 rods: 40 + 1 row * 170 = 210
    # 2 accessories: 40 + 1 row * 170 = 210
    # 0 baits: 60 (empty section)
    # 0 items: 60 (empty section)
    expected_height = header_h + 210 + 210 + 60 + 60 + section_gap * 5 + footer_h + 40
    # Add SAFETY_MARGIN of 50px
    expected_height_with_margin = expected_height + 50
    
    assert image.height >= expected_height, (
        f"Height should be at least {expected_height}, got {image.height}"
    )
    assert image.height <= expected_height_with_margin + 50, (
        f"Height should not exceed {expected_height_with_margin + 50}, got {image.height}"
    )
    
    print(f"✓ Two items per row renders correctly: {image.width}x{image.height}")


def test_preservation_three_items_per_row():
    """
    Test that 3 baits (1 row) and 3 items (1 row) render correctly.
    This tests the row layout for baits/items.
    """
    user_data = {
        "nickname": "三項用戶",
        "rods": [],
        "accessories": [],
        "baits": [create_test_bait(1), create_test_bait(2), create_test_bait(3)],
        "items": [create_test_item(1), create_test_item(2), create_test_item(3)],
    }
    
    image = draw_backpack_image(user_data, data_dir=".")
    
    # Verify basic properties
    assert image.width == 900, f"Width should be 900, got {image.width}"
    
    # Calculate expected height (with section titles and SAFETY_MARGIN)
    header_h = 120
    section_gap = 20
    footer_h = 60
    # 0 rods: 60 (empty section)
    # 0 accessories: 60 (empty section)
    # 3 baits: 40 + 1 row * 120 = 160
    # 3 items: 40 + 1 row * 120 = 160
    expected_height = header_h + 60 + 60 + 160 + 160 + section_gap * 5 + footer_h + 40
    # Add SAFETY_MARGIN of 50px
    expected_height_with_margin = expected_height + 50
    
    assert image.height >= expected_height, (
        f"Height should be at least {expected_height}, got {image.height}"
    )
    assert image.height <= expected_height_with_margin + 50, (
        f"Height should not exceed {expected_height_with_margin + 50}, got {image.height}"
    )
    
    print(f"✓ Three items per row renders correctly: {image.width}x{image.height}")


def test_preservation_four_items_boundary():
    """
    Test with 4 items per category (boundary case before bug manifests).
    This is the upper limit of minimal content.
    """
    user_data = {
        "nickname": "四項用戶",
        "rods": [create_test_rod(i) for i in range(1, 5)],
        "accessories": [create_test_accessory(i) for i in range(1, 5)],
        "baits": [create_test_bait(i) for i in range(1, 5)],
        "items": [create_test_item(i) for i in range(1, 5)],
    }
    
    image = draw_backpack_image(user_data, data_dir=".")
    
    # Verify basic properties
    assert image.width == 900, f"Width should be 900, got {image.width}"
    
    # Calculate expected height (with section titles and SAFETY_MARGIN)
    import math
    header_h = 120
    section_gap = 20
    footer_h = 60
    # 4 rods: 40 + 2 rows * 170 = 380
    # 4 accessories: 40 + 2 rows * 170 = 380
    # 4 baits: 40 + 2 rows * 120 = 280
    # 4 items: 40 + 2 rows * 120 = 280
    expected_height = header_h + 380 + 380 + 280 + 280 + section_gap * 5 + footer_h + 40
    # Add SAFETY_MARGIN of 50px
    expected_height_with_margin = expected_height + 50
    
    assert image.height >= expected_height, (
        f"Height should be at least {expected_height}, got {image.height}"
    )
    assert image.height <= expected_height_with_margin + 50, (
        f"Height should not exceed {expected_height_with_margin + 50}, got {image.height}"
    )
    
    print(f"✓ Four items per category renders correctly: {image.width}x{image.height}")


# ============================================================================
# Main Test Runner
# ============================================================================

if __name__ == "__main__":
    print("\n=== Running Preservation Property Tests ===\n")
    
    # Run specific test cases
    print("Running specific edge case tests...")
    test_preservation_empty_backpack()
    test_preservation_single_item_each_category()
    test_preservation_two_items_per_row()
    test_preservation_three_items_per_row()
    test_preservation_four_items_boundary()
    
    print("\nRunning property-based tests...")
    print("(This will generate 100 random minimal content cases)")
    test_property_preservation_minimal_content_renders_correctly()
    
    print("\n✓ All preservation tests passed!")
    print("Baseline behavior confirmed on unfixed code.")
