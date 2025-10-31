#!/usr/bin/env python3
"""
Test runner script for Virginia plugin tests.

Usage:
    python run_tests.py                    # Run all tests
    python run_tests.py --unit            # Run only unit tests
    python run_tests.py --integration     # Run only integration tests
    python run_tests.py --verbose         # Run with verbose output
"""

import sys
import os
import unittest
import argparse

# Add project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def run_tests(test_type='all', verbose=False):
    """Run tests based on type."""
    # Import test modules
    from tests.test_virginia_sync import (
        TestVirginiaFileDiscovery,
        TestVirginiaDataParsing,
        TestVirginiaSyncWorkflow,
        TestVirginiaDataValidation,
        TestVirginiaErrorScenarios,
        TestVirginiaGeocoding
    )
    
    # Create test suite
    suite = unittest.TestSuite()
    
    # Map test types to classes
    test_classes = {
        'unit': [TestVirginiaFileDiscovery, TestVirginiaDataParsing, TestVirginiaGeocoding],
        'integration': [TestVirginiaSyncWorkflow, TestVirginiaDataValidation],
        'error': [TestVirginiaErrorScenarios],
        'all': [
            TestVirginiaFileDiscovery,
            TestVirginiaDataParsing,
            TestVirginiaSyncWorkflow,
            TestVirginiaDataValidation,
            TestVirginiaErrorScenarios,
            TestVirginiaGeocoding
        ]
    }
    
    # Add test classes to suite
    for test_class in test_classes.get(test_type, []):
        tests = unittest.TestLoader().loadTestsFromTestCase(test_class)
        suite.addTests(tests)
    
    # Run tests
    verbosity = 2 if verbose else 1
    runner = unittest.TextTestRunner(verbosity=verbosity, buffer=True)
    result = runner.run(suite)
    
    # Print summary
    print(f"\n{'='*60}")
    print(f"Test Summary ({test_type.upper()} TESTS)")
    print(f"{'='*60}")
    print(f"Tests run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    
    if result.testsRun > 0:
        success_rate = ((result.testsRun - len(result.failures) - len(result.errors)) / result.testsRun * 100)
        print(f"Success rate: {success_rate:.1f}%")
    
    if result.failures:
        print(f"\nFAILURES ({len(result.failures)}):")
        for test, traceback in result.failures:
            print(f"  - {test}")
    
    if result.errors:
        print(f"\nERRORS ({len(result.errors)}):")
        for test, traceback in result.errors:
            print(f"  - {test}")
    
    # Return exit code
    return 0 if result.wasSuccessful() else 1

def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description='Run Virginia plugin tests')
    parser.add_argument('--unit', action='store_true', help='Run only unit tests')
    parser.add_argument('--integration', action='store_true', help='Run only integration tests')
    parser.add_argument('--error', action='store_true', help='Run only error scenario tests')
    parser.add_argument('--verbose', '-v', action='store_true', help='Verbose output')
    
    args = parser.parse_args()
    
    # Determine test type
    if args.unit:
        test_type = 'unit'
    elif args.integration:
        test_type = 'integration'
    elif args.error:
        test_type = 'error'
    else:
        test_type = 'all'
    
    # Run tests
    exit_code = run_tests(test_type, args.verbose)
    sys.exit(exit_code)

if __name__ == '__main__':
    main()