"""
Bug Condition Exploration Test for Image Rendering Height Calculation

**Validates: Requirements 1.1, 1.2, 1.3, 1.4, 1.5**

This test is designed to FAIL on unfixed code to confirm the bug exists.
The bug manifests when rendering functions calculate insufficient height for content,
causing bottom content to be truncated.

CRITICAL: This test MUST FAIL on unfixed code - failure confirms the bug exists.
DO NOT attempt to fix the test or the code when it fails.

Expected Outcome: Test FAILS (this is correct - it proves the bug exists)
"""

from __future__ import annotations

import sys
import types
from typing import Dict, Any, List
from PIL import Image

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


def calculate_expected_content_height(user_data: Dict[str, Any]) -> int:
    """
    Calculate the expected minimum height needed to display all content.
    This represents what the height SHOULD be to avoid truncation.
    """
    import math
    
    header_h = 120
    section_gap = 20
    footer_h = 60
    
    rods = user_data.get("rods", [])
    accessories = user_data.get("accessories", [])
    baits = user_data.get("baits", [])
    items = user_data.get("items", [])
    
    # Calculate actual space needed for each section
    # Each rod/accessory card is 170px tall, 2 per row
    rod_rows = math.ceil(len(rods) / 2) if rods else 0
    acc_rows = math.ceil(len(accessories) / 2) if accessories else 0
    
    # Each bait/item card is 120px tall, 3 per row
    bait_rows = math.ceil(len(baits) / 3) if baits else 0
    item_rows = math.ceil(len(items) / 3) if items else 0
    
    # Calculate section heights (including section title which is ~40px)
    rod_h = (rod_rows * 170 + 40) if rods else 60
    acc_h = (acc_rows * 170 + 40) if accessories else 60
    bait_h = (bait_rows * 120 + 40) if baits else 60
    item_h = (item_rows * 120 + 40) if items else 60
    
    # Total height: header + all sections + gaps between sections + footer + bottom padding
    # There are 4 sections (rods, accessories, baits, items) so 5 gaps (including top and bottom)
    expected_height = (
        header_h + rod_h + acc_h + bait_h + item_h + section_gap * 5 + footer_h + 40
    )
    
    return expected_height


def verify_content_visibility(image: Image.Image, user_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Verify that the generated image has sufficient height for all content.
    Returns a dict with verification results.
    """
    expected_height = calculate_expected_content_height(user_data)
    actual_height = image.height
    
    # Check if image height is sufficient
    height_sufficient = actual_height >= expected_height
    
    # Calculate how much content might be truncated
    height_deficit = max(0, expected_height - actual_height)
    
    return {
        "height_sufficient": height_sufficient,
        "expected_height": expected_height,
        "actual_height": actual_height,
        "height_deficit": height_deficit,
        "num_rods": len(user_data.get("rods", [])),
        "num_accessories": len(user_data.get("accessories", [])),
        "num_baits": len(user_data.get("baits", [])),
        "num_items": len(user_data.get("items", [])),
    }


def test_bug_condition_backpack_with_large_content():
    """
    **Property 1: Bug Condition** - Image Height Truncation with Large Content
    
    **Validates: Requirements 1.1, 1.2, 1.3, 1.4, 1.5**
    
    CRITICAL: This test MUST FAIL on unfixed code - failure confirms the bug exists.
    
    Test with large numbers of items as specified in the task:
    - 15 rods
    - 12 accessories
    - 18 baits
    - 20 items
    
    The test verifies that the generated image has sufficient height to display
    all content without truncation. On unfixed code, this test should FAIL,
    demonstrating that the bug exists.
    """
    # Create test data with large numbers of items
    user_data = {
        "nickname": "測試用戶",
        "rods": [create_test_rod(i, rarity=5 + (i % 5)) for i in range(1, 16)],  # 15 rods
        "accessories": [create_test_accessory(i, rarity=5 + (i % 5)) for i in range(1, 13)],  # 12 accessories
        "baits": [create_test_bait(i) for i in range(1, 19)],  # 18 baits
        "items": [create_test_item(i) for i in range(1, 21)],  # 20 items
    }
    
    # Generate image using UNFIXED code
    image = draw_backpack_image(user_data, data_dir=".")
    
    # Verify content visibility
    result = verify_content_visibility(image, user_data)
    
    # Document the counterexample
    print("\n=== Bug Condition Test Results ===")
    print(f"Number of rods: {result['num_rods']}")
    print(f"Number of accessories: {result['num_accessories']}")
    print(f"Number of baits: {result['num_baits']}")
    print(f"Number of items: {result['num_items']}")
    print(f"Expected minimum height: {result['expected_height']}px")
    print(f"Actual image height: {result['actual_height']}px")
    print(f"Height deficit: {result['height_deficit']}px")
    print(f"Content fully visible: {result['height_sufficient']}")
    
    if not result['height_sufficient']:
        print("\n✓ BUG CONFIRMED: Image height is insufficient for content!")
        print(f"  Bottom content is likely truncated by ~{result['height_deficit']}px")
    else:
        print("\n✗ UNEXPECTED: Image height appears sufficient")
        print("  This may indicate the bug doesn't manifest with this test case")
        print("  or the code has already been fixed")
    
    # This assertion should FAIL on unfixed code, confirming the bug exists
    assert result['height_sufficient'], (
        f"Bug condition detected: Image height ({result['actual_height']}px) is insufficient "
        f"for content (needs {result['expected_height']}px). "
        f"Bottom content is truncated by approximately {result['height_deficit']}px. "
        f"This confirms the bug exists as expected."
    )


if __name__ == "__main__":
    # Run the test directly for debugging
    test_bug_condition_backpack_with_large_content()
