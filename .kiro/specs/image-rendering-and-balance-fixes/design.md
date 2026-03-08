# Image Rendering and Balance Fixes Bugfix Design

## Overview

This bugfix addresses multiple systemic issues in the Discord fishing game plugin:

1. **Image Rendering Height Calculation Errors**: All image rendering commands (backpack, shop, equipment, fishing zones, etc.) generate images with insufficient height when content is extensive, causing bottom content to be truncated.

2. **Game Balance Issues**: Potential imbalances in numerical values for rods, accessories, baits, and items that may affect gameplay fairness.

3. **Command System Redundancy**: Excessive independent commands with overlapping functionality that increase player learning curve.

4. **Help Documentation Synchronization**: The fishing help command displays content that may not reflect current functionality.

The primary focus is on the image rendering bug, which directly impacts player experience by preventing them from viewing complete item information. The balance and command system issues require investigation to determine specific problems before implementing fixes.

## Glossary

- **Bug_Condition (C)**: The condition that triggers image truncation - when rendered content exceeds calculated image height
- **Property (P)**: The desired behavior - all content should be fully visible within the generated image
- **Preservation**: Existing visual styling, layout patterns, and functionality that must remain unchanged
- **draw_*_image functions**: Functions in the `draw/` directory that generate PIL images for Discord display
- **height calculation**: The process of computing total image height by summing header, content sections, gaps, and footer
- **card_h**: Height of individual item cards in the rendering layout
- **section_gap**: Vertical spacing between different content sections

## Bug Details

### Bug Condition

The bug manifests when image rendering functions calculate insufficient height for the total content to be displayed. The functions in `draw/backpack.py`, `draw/equipment.py`, `draw/shop.py`, `draw/fishing_zone.py`, `draw/state.py`, and `draw/market.py` either miscalculate the required height or fail to account for all content regions, resulting in bottom content being clipped.

**Formal Specification:**
```
FUNCTION isBugCondition(input)
  INPUT: input of type RenderRequest containing items/content to display
  OUTPUT: boolean
  
  RETURN (calculatedHeight < actualContentHeight)
         AND (numberOfItems > minimalTestCase)
         AND (generatedImage.height < requiredHeight)
END FUNCTION
```

**Specific Manifestations:**

1. **Backpack Rendering** (`draw/backpack.py`):
   - When user has many rods (>4), accessories (>4), baits (>6), or items (>6)
   - Height calculation uses fixed row heights but may not account for actual card spacing
   - Current calculation: `header_h + rod_h + acc_h + bait_h + item_h + section_gap * 5 + footer_h + 40`
   - Issue: The calculation increments `y` coordinate correctly in loops but initial height may be underestimated

2. **Equipment Rendering** (`draw/equipment.py`):
   - When displaying many rods or accessories in list view
   - Height calculation: `header_h + max(1, len(entries)) * card_h + footer_h + bottom_pad`
   - Issue: `card_h` is dynamically calculated but may not match actual rendered card height

3. **Shop Rendering** (`draw/shop.py`):
   - Shop list: `header_h + max(1, len(shops)) * row_h + footer_h + bottom_pad`
   - Shop detail: `header_h + max(1, len(items)) * card_h + footer_h + bottom_pad`
   - Issue: Similar to equipment, dynamic card height may not match calculation

4. **Fishing Zone Rendering** (`draw/fishing_zone.py`):
   - Height: `header_h + 24 + (len(zones) * (card_h + section_gap)) + footer_h + 24`
   - Issue: Fixed `card_h = 154` may not accommodate all zone information

5. **State Rendering** (`draw/state.py`):
   - Height calculated by incrementing `y` coordinate through sections
   - Issue: Pre-calculation of height before rendering may not match actual layout

6. **Market Rendering** (`draw/market.py`):
   - Height: `header_h + total_rows * row_h + total_sections * sec_head_h + footer_h + bottom_pad`
   - Issue: Dynamic row height calculation may not match actual text rendering


### Examples

**Example 1: Backpack with Many Items**
- Input: User has 10 rods, 8 accessories, 12 baits, 15 items
- Expected: All items visible in generated image
- Actual: Bottom items (last few items in the items section) are clipped
- Root Cause: Height calculation doesn't account for actual rendered card positions

**Example 2: Equipment List with 20+ Rods**
- Input: Display list of 25 rods
- Expected: All 25 rods visible with scrollable image
- Actual: Last 3-5 rods are cut off at bottom
- Root Cause: `card_h` calculation may be smaller than actual rendered card height

**Example 3: Shop Detail with Many Products**
- Input: Shop with 15 products
- Expected: All products visible
- Actual: Last 2-3 products truncated
- Root Cause: Similar height miscalculation

**Edge Case: Minimal Content**
- Input: User has only 1 rod, 1 accessory
- Expected: Image renders correctly without excessive whitespace
- Actual: Works correctly (bug only manifests with larger content)

## Expected Behavior

### Preservation Requirements

**Unchanged Behaviors:**
- Visual styling (colors, fonts, gradients, card designs) must remain identical
- Layout patterns (card positioning, spacing between elements) must be preserved
- All existing functionality (filtering, truncation logic, display codes) must continue to work
- Performance characteristics should not degrade significantly

**Scope:**
All inputs that result in correctly-sized images (minimal content cases) should continue to work exactly as before. This includes:
- Single-item displays
- Empty category displays
- All visual styling elements (rounded corners, shadows, borders, gradients)
- Text formatting and truncation logic
- Icon and emoji displays


## Hypothesized Root Cause

Based on the bug description and code analysis, the most likely issues are:

1. **Inconsistent Height Calculation Methods**: Different files use different approaches to calculate image height:
   - Some pre-calculate height before rendering (backpack.py, equipment.py, shop.py)
   - Some calculate height by tracking `y` coordinate during layout (state.py)
   - Mismatch between calculation method and actual rendering logic

2. **Dynamic Text Height Not Accounted For**: 
   - Functions use `textbbox` to measure text height for card sizing
   - However, the measured height may not include padding, line spacing, or multi-line text
   - Example in equipment.py: `card_h = max(card_h, body_h + small_h * 2 + 44)` may underestimate actual space needed

3. **Section Gap and Padding Inconsistencies**:
   - Fixed section gaps (e.g., `section_gap = 20`) may not match actual spacing in rendering
   - Bottom padding calculations vary across files
   - Some files add extra padding (e.g., `+ 40`, `+ 24`) without clear justification

4. **Loop-Based Height Accumulation Errors**:
   - In backpack.py, height is pre-calculated but `y` coordinate is incremented in loops
   - If loop increments don't match pre-calculation, truncation occurs
   - Example: `y += rod_section_height + section_gap` after rod loop, but initial calculation may differ

5. **Card Overlap and Text Overflow**:
   - When cards are positioned too close together, text may overflow into adjacent cards
   - This doesn't increase calculated height but makes content unreadable
   - Particularly affects long item names or descriptions

## Correctness Properties

Property 1: Bug Condition - Complete Content Visibility

_For any_ rendering request where content items are provided (rods, accessories, baits, items, shops, zones, etc.), the fixed rendering functions SHALL generate an image with sufficient height such that all content is fully visible without truncation, and the bottom-most content element is at least `footer_h + bottom_padding` pixels from the image bottom edge.

**Validates: Requirements 2.1, 2.2, 2.3, 2.4, 2.5**

Property 2: Preservation - Visual Styling and Layout

_For any_ rendering request, the fixed functions SHALL produce images with identical visual styling (colors, fonts, gradients, card designs, borders, shadows) and layout patterns (card positioning, spacing ratios, alignment) as the original functions, preserving the existing aesthetic and user experience.

**Validates: Requirements 3.1, 3.2, 3.3, 3.4**


## Fix Implementation

### Changes Required

Assuming our root cause analysis is correct, the fix should standardize height calculation across all rendering functions and ensure accurate accounting of all content regions.

**Approach: Two-Pass Rendering**

Instead of pre-calculating height, use a two-pass approach:
1. **First Pass**: Render to a temporary image while tracking actual `y` coordinates
2. **Second Pass**: Create final image with correct height and render again

Alternatively, use a **Single-Pass with Accurate Calculation**:
1. Calculate height by simulating the exact rendering logic
2. Ensure all padding, gaps, and text heights are accurately measured
3. Add safety margin (e.g., +50 pixels) to prevent edge cases

**File**: `draw/backpack.py`

**Function**: `draw_backpack_image`

**Specific Changes**:
1. **Verify Height Calculation Logic**: Ensure `rod_h`, `acc_h`, `bait_h`, `item_h` match actual rendered heights
   - Current: `rod_h = rod_rows * 170 if rods else 60`
   - Verify: Does each rod actually take 170 pixels including gaps?
   - Fix: Measure actual card height + gap in rendering loop

2. **Add Safety Margin**: Add extra padding to prevent edge case truncation
   - Add `+ 50` or `+ 100` to final height calculation
   - This ensures even with slight miscalculations, content is visible

3. **Standardize Section Height Calculation**: Use consistent method across all sections
   - For each section: `section_height = (num_rows * (card_height + row_gap)) + section_header_height`
   - Ensure this matches actual rendering loop logic

4. **Debug Logging**: Add optional logging to compare calculated vs actual heights
   - Log: `calculated_height`, `final_y_coordinate`, `difference`
   - This helps identify remaining issues

**File**: `draw/equipment.py`

**Function**: `draw_equipment_image`

**Specific Changes**:
1. **Fix Card Height Calculation**: Ensure `card_h` accounts for all text lines and padding
   - Current: `card_h = max(card_h, body_h + small_h * 2 + 44)`
   - Issue: May not account for description text line
   - Fix: Add `+ small_h` for description line, increase padding to 60

2. **Verify Bottom Padding**: Ensure `bottom_pad = 24` is sufficient
   - Test with maximum content and verify no truncation
   - Increase if needed

**File**: `draw/shop.py`

**Function**: `draw_shop_list_image` and `draw_shop_detail_image`

**Specific Changes**:
1. **Standardize Row Height**: Ensure `row_h` and `card_h` match actual rendering
   - Use same calculation method as equipment.py
   - Add safety margin

2. **Account for Long Text**: Ensure description text doesn't overflow
   - Current truncation: `desc[:45]`, `desc[:55]`
   - Verify this fits within card boundaries


**File**: `draw/fishing_zone.py`

**Function**: `draw_fishing_zones_image`

**Specific Changes**:
1. **Verify Card Height**: Ensure `card_h = 154` accommodates all zone information
   - Check if all text lines fit within 154 pixels
   - Increase if needed based on actual content

2. **Add Safety Margin**: Current calculation seems straightforward, but add margin
   - Change: `height = max(height, 320)` to `height = max(height + 50, 320)`

**File**: `draw/state.py`

**Function**: `draw_state_image`

**Specific Changes**:
1. **Fix Pre-calculation Method**: Current method pre-calculates `y` coordinate
   - This is error-prone as it duplicates rendering logic
   - Better: Calculate height after rendering or use consistent formula

2. **Verify Conditional Sections**: Title section is conditional
   - Ensure height calculation matches actual rendering
   - Current logic seems correct but verify with testing

**File**: `draw/market.py`

**Function**: `draw_market_list_image`

**Specific Changes**:
1. **Verify Row Height Calculation**: Dynamic calculation may be inaccurate
   - Current: `row_h = max(row_h, body_h + 14)`
   - Verify this matches actual card rendering
   - Add extra padding if needed

2. **Account for Section Headers**: Ensure `sec_head_h` is accurate
   - Current: `sec_head_h = max(sec_head_h, head_h + 14)`
   - Verify and add margin

### General Fix Strategy

**For All Files**:
1. Add a `SAFETY_MARGIN = 50` constant at the top of each file
2. Add this margin to final height calculation: `height = calculated_height + SAFETY_MARGIN`
3. Standardize height calculation method across all files
4. Add assertions or logging to verify calculated height matches actual content

**Testing Strategy**:
1. Create test cases with maximum content (50+ items per category)
2. Generate images and verify no truncation
3. Verify visual styling is preserved
4. Check performance impact (should be minimal)


## Testing Strategy

### Validation Approach

The testing strategy follows a two-phase approach: first, surface counterexamples that demonstrate the bug on unfixed code, then verify the fix works correctly and preserves existing behavior.

### Exploratory Bug Condition Checking

**Goal**: Surface counterexamples that demonstrate the bug BEFORE implementing the fix. Confirm or refute the root cause analysis. If we refute, we will need to re-hypothesize.

**Test Plan**: Create test data with large numbers of items in each category, generate images using the UNFIXED code, and measure whether bottom content is truncated. Compare calculated image height with actual content height requirements.

**Test Cases**:
1. **Backpack Overflow Test**: Create user with 15 rods, 12 accessories, 18 baits, 20 items (will fail on unfixed code)
   - Generate backpack image
   - Measure: Does last item in items section appear fully?
   - Expected failure: Last 2-3 items truncated

2. **Equipment List Overflow Test**: Create list of 30 rods with varying attributes (will fail on unfixed code)
   - Generate equipment image
   - Measure: Are all 30 rods visible?
   - Expected failure: Last 4-5 rods cut off

3. **Shop Detail Overflow Test**: Create shop with 20 products (will fail on unfixed code)
   - Generate shop detail image
   - Measure: Are all products visible?
   - Expected failure: Last 2-3 products truncated

4. **Fishing Zone Overflow Test**: Create 15 fishing zones with full information (may fail on unfixed code)
   - Generate fishing zones image
   - Measure: Are all zones fully visible?
   - Expected failure: Last zone may be partially cut off

5. **State Panel with All Features Test**: Create user with all equipment, buffs, and features active (may fail on unfixed code)
   - Generate state image
   - Measure: Is footer visible?
   - Expected failure: Footer may be cut off

**Expected Counterexamples**:
- Images where `calculated_height < actual_content_height`
- Bottom content (last items, footer) not visible in generated PNG
- Possible causes: height calculation underestimates actual rendering, missing padding/gaps, text overflow

### Fix Checking

**Goal**: Verify that for all inputs where the bug condition holds (large content), the fixed function produces images with complete visibility.

**Pseudocode:**
```
FOR ALL input WHERE isBugCondition(input) DO
  image := draw_function_fixed(input)
  ASSERT image.height >= calculate_actual_content_height(input)
  ASSERT all_content_visible(image)
  ASSERT footer_visible(image)
END FOR
```

**Test Cases**:
1. **Maximum Content Test**: Test with maximum realistic content (50 items per category)
2. **Varied Content Test**: Test with different combinations (many rods, few accessories, etc.)
3. **Long Text Test**: Test with items having maximum-length names and descriptions
4. **Edge Case Test**: Test with exactly the threshold where bug manifests (e.g., 8 rods)


### Preservation Checking

**Goal**: Verify that for all inputs where the bug condition does NOT hold (minimal content), the fixed function produces the same result as the original function.

**Pseudocode:**
```
FOR ALL input WHERE NOT isBugCondition(input) DO
  image_original := draw_function_original(input)
  image_fixed := draw_function_fixed(input)
  ASSERT images_visually_identical(image_original, image_fixed)
  ASSERT same_dimensions(image_original, image_fixed) OR image_fixed.height >= image_original.height
END FOR
```

**Testing Approach**: Property-based testing is recommended for preservation checking because:
- It generates many test cases automatically across the input domain
- It catches edge cases that manual unit tests might miss
- It provides strong guarantees that behavior is unchanged for all non-buggy inputs

**Test Plan**: Observe behavior on UNFIXED code first for minimal content cases, then write property-based tests capturing that behavior.

**Test Cases**:
1. **Single Item Preservation**: Observe that single-item displays work correctly on unfixed code, then verify this continues after fix
   - Test: User with 1 rod, 1 accessory, 1 bait, 1 item
   - Assert: Image dimensions and visual appearance identical (or height slightly larger with safety margin)

2. **Empty Category Preservation**: Observe that empty categories display correctly on unfixed code
   - Test: User with no rods, no accessories, etc.
   - Assert: "暫無魚竿" messages display correctly

3. **Visual Styling Preservation**: Verify all visual elements remain unchanged
   - Test: Compare color values, font sizes, border radii, shadow effects
   - Assert: All styling constants unchanged

4. **Layout Pattern Preservation**: Verify card positioning and spacing ratios
   - Test: Measure card positions for 2-item and 4-item cases
   - Assert: Relative positions and spacing ratios identical

### Unit Tests

- Test height calculation functions in isolation with various input sizes
- Test edge cases: 0 items, 1 item, 2 items (boundary of row calculations)
- Test text measurement functions with various font sizes and text lengths
- Test that safety margin is applied correctly
- Test that all sections (header, content, footer) are accounted for in height calculation

### Property-Based Tests

- Generate random item counts (0-50 per category) and verify no truncation
- Generate random text lengths for names/descriptions and verify no overflow
- Generate random combinations of equipped/unequipped items and verify correct display
- Test that image height is monotonically increasing with content size (more items = taller image)
- Test that visual styling properties remain constant across all generated test cases

### Integration Tests

- Test full workflow: create user data → generate image → verify in Discord
- Test with real database data from production (anonymized)
- Test performance: ensure image generation time remains acceptable (<2 seconds)
- Test memory usage: ensure large images don't cause memory issues
- Test with different Discord client versions to ensure compatibility

### Manual Visual Inspection

- Generate images with various content sizes and manually inspect for:
  - Complete visibility of all content
  - No overlapping cards or text
  - Consistent spacing and alignment
  - Proper color rendering and gradients
  - Readable text at all sizes
  - Proper emoji and icon display


## Additional Issues Requiring Investigation

The following issues are documented in the requirements but require investigation before implementation:

### Game Balance Issues

**Status**: Requires data analysis and gameplay testing

**Investigation Plan**:
1. **Rod Balance Analysis**:
   - Extract all rod data from `core/initial_data.py` or database
   - Analyze attribute progression across rarity levels
   - Check for outliers (rods with unusually high/low bonuses)
   - Verify refine level scaling is balanced

2. **Accessory Balance Analysis**:
   - Extract all accessory data
   - Check for duplicate effects or overlapping functionality
   - Verify bonus values scale appropriately with rarity
   - Ensure no accessory is strictly superior to all others at same rarity

3. **Bait Balance Analysis**:
   - Compare consumable vs permanent baits
   - Verify cost-to-benefit ratio is reasonable
   - Check duration values are appropriate
   - Ensure no bait is mandatory for progression

4. **Item Balance Analysis**:
   - Verify item effects match descriptions
   - Check for overpowered or underpowered items
   - Ensure item costs are appropriate for effects
   - Verify no items break game economy

**Deliverable**: Separate analysis document with specific balance recommendations

### Command System Redundancy

**Status**: Requires command usage analysis and UX review

**Investigation Plan**:
1. **Command Inventory**:
   - List all commands from `handlers/` directory
   - Categorize by functionality (fishing, inventory, social, admin, etc.)
   - Identify overlapping or redundant commands

2. **Usage Analysis**:
   - Analyze command usage logs (if available)
   - Identify rarely-used commands
   - Identify commands that could be merged

3. **UX Review**:
   - Evaluate command naming consistency
   - Check for confusing command structures
   - Identify opportunities for subcommands or command groups

**Deliverable**: Command restructuring proposal with migration plan

### Help Documentation Synchronization

**Status**: Requires documentation audit

**Investigation Plan**:
1. **Documentation Audit**:
   - Review current help command output
   - Compare with actual implemented features
   - Identify outdated or incorrect information

2. **Synchronization Strategy**:
   - Determine how to keep help docs in sync with code
   - Consider auto-generating help from command definitions
   - Establish documentation update process

**Deliverable**: Updated help documentation and synchronization process

**Note**: These issues are lower priority than the image rendering bug and should be addressed in separate bugfix cycles after the primary issue is resolved.
