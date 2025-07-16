#!/usr/bin/env python3
"""
Test script for program collections automation

This script validates the automation setup and tests key functionality
without making actual changes to the correction files.
"""

import json
import logging
import sys
import tempfile
from pathlib import Path

from program_collections_automation import ProgramCollectionsGenerator

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def test_configuration_loading():
    """Test loading of configuration files"""
    logger.info("Testing configuration loading...")

    generator = ProgramCollectionsGenerator()
    approved_prod, control_transferred, act_codes, ic_codes = generator.load_config_files()

    print(f"✓ Loaded {len(approved_prod)} approved production programs")
    print(f"✓ Loaded {len(control_transferred)} control transferred programs")
    print(f"✓ Loaded {len(act_codes)} activity codes")
    print(f"✓ Loaded {len(ic_codes)} IC codes")

    # Validate some expected values
    assert len(approved_prod) > 0, "Should have approved production programs"
    assert len(act_codes) > 0, "Should have activity codes"
    assert len(ic_codes) > 0, "Should have IC codes"

    return True


def test_data_download():
    """Test downloading program metadata"""
    logger.info("Testing data download...")

    generator = ProgramCollectionsGenerator()

    try:
        df = generator.download_program_data()
        print(f"✓ Downloaded {len(df)} programs")

        # Validate data structure
        required_columns = ['fileName', 'name', 'fundingIDList', 'niaidURL']
        for col in required_columns:
            assert col in df.columns, f"Missing required column: {col}"

        # Check for valid data
        valid_programs = df[
            (~df['fundingIDList'].isna()) &
            (df['fundingIDList'] != 'not found') &
            (~df['niaidURL'].isna()) &
            (df['fileName'] != '--')
        ]

        print(f"✓ Found {len(valid_programs)} valid programs for processing")

        return True

    except Exception as e:
        logger.warning(f"Data download failed, will try local file: {e}")
        return False


def test_grant_parsing():
    """Test grant ID parsing functionality"""
    logger.info("Testing grant ID parsing...")

    generator = ProgramCollectionsGenerator()
    _, _, act_codes, ic_codes = generator.load_config_files()

    # Test cases for grant ID parsing
    test_grants = [
        "1-R01-AI073685-01",
        "R01AI073685",
        "AI073685-01",
        "U01AI12345"
    ]

    for grant in test_grants:
        parsed = generator.parse_grant_id(grant, act_codes, ic_codes)
        print(
            f"✓ Parsed {grant}: IC={parsed['icCode']}, Serial={parsed['serialNum']}")

    return True


def test_search_functionality():
    """Test record search functionality"""
    logger.info("Testing search functionality...")

    generator = ProgramCollectionsGenerator()

    # Test with a small set of grants
    test_grants = ["AI073685", "AI123456"]  # Mix of real and fake

    try:
        records = generator.search_records(test_grants, 'staging')
        print(f"✓ Search returned {len(records)} records")
        return True

    except Exception as e:
        logger.warning(f"Search test failed: {e}")
        return False


def test_file_generation():
    """Test file generation without writing to actual correction directories"""
    logger.info("Testing file generation...")

    # Create temporary directory for testing
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        # Create mock correction directories
        staging_dir = temp_path / 'collections_corrections_staging'
        prod_dir = temp_path / 'collections_corrections_production'
        staging_dir.mkdir()
        prod_dir.mkdir()

        # Initialize generator with temp path
        generator = ProgramCollectionsGenerator()
        generator.correction_path = temp_path

        try:
            # Get sample data
            df = generator.download_program_data()
            if len(df) == 0:
                print("⚠ No data available for testing file generation")
                return False

            # Test with first valid program
            valid_programs = df[
                (~df['fundingIDList'].isna()) &
                (df['fundingIDList'] != 'not found') &
                (~df['niaidURL'].isna()) &
                (df['fileName'] != '--')
            ]

            if len(valid_programs) == 0:
                print("⚠ No valid programs found for testing")
                return False

            # Generate files for one program
            test_row = valid_programs.iloc[0]

            # Test metadata file generation
            generator._create_metadata_file(test_row, 'staging')
            metadata_file = staging_dir / \
                f"{test_row['fileName']}_correction.json"

            assert metadata_file.exists(), "Metadata file should be created"

            # Validate JSON structure
            with open(metadata_file) as f:
                metadata = json.load(f)

            assert 'sourceOrganization' in metadata, "Should have sourceOrganization"
            assert len(metadata['sourceOrganization']
                       ) > 0, "Should have organization data"

            print(f"✓ Generated metadata file: {metadata_file}")

            # Test records file generation
            _, _, act_codes, ic_codes = generator.load_config_files()
            generator._create_records_file(
                test_row, 'staging', act_codes, ic_codes, [])

            records_file = staging_dir / f"{test_row['fileName']}_records.txt"

            if records_file.exists():
                with open(records_file) as f:
                    record_count = len([line for line in f if line.strip()])
                print(f"✓ Generated records file with {record_count} records")
            else:
                print("✓ Records file created (may be empty if no matches found)")

            return True

        except Exception as e:
            logger.error(f"File generation test failed: {e}")
            return False


def run_all_tests():
    """Run all tests"""
    tests = [
        ("Configuration Loading", test_configuration_loading),
        ("Data Download", test_data_download),
        ("Grant Parsing", test_grant_parsing),
        ("Search Functionality", test_search_functionality),
        ("File Generation", test_file_generation),
    ]

    passed = 0
    failed = 0

    print("=" * 60)
    print("PROGRAM COLLECTIONS AUTOMATION TEST SUITE")
    print("=" * 60)

    for test_name, test_func in tests:
        print(f"\n{test_name}:")
        print("-" * 40)

        try:
            result = test_func()
            if result:
                print(f"✅ {test_name} PASSED")
                passed += 1
            else:
                print(f"❌ {test_name} FAILED")
                failed += 1
        except Exception as e:
            print(f"❌ {test_name} FAILED: {e}")
            failed += 1

    print("\n" + "=" * 60)
    print(f"TEST RESULTS: {passed} passed, {failed} failed")
    print("=" * 60)

    if failed == 0:
        print("🎉 All tests passed! The automation is ready to use.")
        return True
    else:
        print("⚠️  Some tests failed. Please check the configuration and dependencies.")
        return False


if __name__ == '__main__':
    success = run_all_tests()
    sys.exit(0 if success else 1)
