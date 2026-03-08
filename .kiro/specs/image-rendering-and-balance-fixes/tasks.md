# Implementation Plan

- [x] 1. Write bug condition exploration test
  - **Property 1: Bug Condition** - Image Height Truncation with Large Content
  - **CRITICAL**: This test MUST FAIL on unfixed code - failure confirms the bug exists
  - **DO NOT attempt to fix the test or the code when it fails**
  - **NOTE**: This test encodes the expected behavior - it will validate the fix when it passes after implementation
  - **GOAL**: Surface counterexamples that demonstrate the bug exists
  - **Scoped PBT Approach**: For deterministic bugs, scope the property to the concrete failing case(s) to ensure reproducibility
  - Test implementation details from Bug Condition in design: `isBugCondition(input)` where `calculatedHeight < actualContentHeight` AND `numberOfItems > minimalTestCase`
  - Create test data with large numbers of items: 15 rods, 12 accessories, 18 baits, 20 items for backpack test
  - Generate images using UNFIXED code for all rendering functions (backpack, equipment, shop, fishing zones, state, market)
  - The test assertions should match the Expected Behavior Properties from design: all content fully visible without truncation
  - Run test on UNFIXED code
  - **EXPECTED OUTCOME**: Test FAILS (this is correct - it proves the bug exists)
  - Document counterexamples found: which images show truncation, where content is cut off, measured height vs required height
  - Mark task complete when test is written, run, and failure is documented
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5_

- [x] 2. Write preservation property tests (BEFORE implementing fix)
  - **Property 2: Preservation** - Visual Styling and Minimal Content Rendering
  - **IMPORTANT**: Follow observation-first methodology
  - Observe behavior on UNFIXED code for non-buggy inputs (minimal content cases)
  - Test cases: single item displays (1 rod, 1 accessory), empty categories, 2-4 item cases
  - Write property-based tests capturing observed behavior patterns from Preservation Requirements
  - Verify visual styling preserved: colors, fonts, gradients, card designs, borders, shadows
  - Verify layout patterns preserved: card positioning, spacing ratios, alignment
  - Verify functionality preserved: filtering, truncation logic, display codes
  - Property-based testing generates many test cases for stronger guarantees
  - Run tests on UNFIXED code
  - **EXPECTED OUTCOME**: Tests PASS (this confirms baseline behavior to preserve)
  - Mark task complete when tests are written, run, and passing on unfixed code
  - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 3.8, 3.9, 3.10, 3.11, 3.12, 3.13, 3.14_

- [x] 3. Fix image rendering height calculation errors

  - [x] 3.1 Implement height calculation fixes for all rendering functions
    - Add `SAFETY_MARGIN = 50` constant to each draw file
    - Fix `draw/backpack.py`: Verify section height calculations match actual rendering, add safety margin
    - Fix `draw/equipment.py`: Ensure `card_h` accounts for all text lines and padding, increase padding to 60
    - Fix `draw/shop.py`: Standardize row height calculation, ensure description text fits within cards
    - Fix `draw/fishing_zone.py`: Verify `card_h = 154` accommodates all zone info, add safety margin
    - Fix `draw/state.py`: Fix pre-calculation method to match actual rendering logic
    - Fix `draw/market.py`: Verify row height calculation matches actual card rendering, add padding
    - Standardize height calculation method across all files: `section_height = (num_rows * (card_height + row_gap)) + section_header_height`
    - Add final height calculation: `height = calculated_height + SAFETY_MARGIN`
    - _Bug_Condition: isBugCondition(input) where calculatedHeight < actualContentHeight AND numberOfItems > minimalTestCase_
    - _Expected_Behavior: For any rendering request with content items, generate image with sufficient height such that all content is fully visible without truncation, and bottom-most content element is at least footer_h + bottom_padding pixels from image bottom edge_
    - _Preservation: Visual styling (colors, fonts, gradients, card designs, borders, shadows) and layout patterns (card positioning, spacing ratios, alignment) must remain identical to original functions_
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 2.1, 2.2, 2.3, 2.4, 2.5, 3.1, 3.2, 3.3, 3.4_

  - [x] 3.2 Verify bug condition exploration test now passes
    - **Property 1: Expected Behavior** - Complete Content Visibility
    - **IMPORTANT**: Re-run the SAME test from task 1 - do NOT write a new test
    - The test from task 1 encodes the expected behavior
    - When this test passes, it confirms the expected behavior is satisfied
    - Run bug condition exploration test from step 1
    - **EXPECTED OUTCOME**: Test PASSES (confirms bug is fixed)
    - Verify all images show complete content without truncation
    - Verify bottom-most content is at least footer_h + bottom_padding from image bottom
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5_

  - [x] 3.3 Verify preservation tests still pass
    - **Property 2: Preservation** - Visual Styling and Layout Preservation
    - **IMPORTANT**: Re-run the SAME tests from task 2 - do NOT write new tests
    - Run preservation property tests from step 2
    - **EXPECTED OUTCOME**: Tests PASS (confirms no regressions)
    - Confirm all tests still pass after fix (no regressions)
    - Verify visual styling unchanged for minimal content cases
    - Verify layout patterns preserved
    - Verify functionality preserved

- [x] 4. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.
  - Primary image rendering bug is now fixed
  - Secondary issues (balance, command system, help docs) require investigation before implementation
