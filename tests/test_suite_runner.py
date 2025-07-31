#!/usr/bin/env python3
"""
Comprehensive test suite runner for the Local Orchestrator Tray project.

This script runs all test suites in a coordinated manner and provides
comprehensive reporting on test coverage, performance, and quality metrics.

Test Suite Components:
1. Config Validation Tests - Tests the refactored config validation methods
2. Channel Support Tests - Tests Telegram channel message handling
3. Integration Tests - Tests complete message processing pipeline
4. Property-Based Tests - Tests edge cases with generated data
5. Helper Method Tests - Tests extracted helper methods (TDD-driven)
6. Concurrent Processing Tests - Tests thread safety and concurrency
7. Security Tests - Tests token validation and sanitization
8. Error Recovery Tests - Tests fault tolerance and recovery
9. Performance Tests - Tests performance characteristics and scalability

Usage:
    python test_suite_runner.py [options]
    
Options:
    --fast          Run only fast tests (skip performance/load tests)
    --integration   Run only integration tests
    --security      Run only security tests
    --performance   Run only performance tests
    --coverage      Generate coverage report
    --benchmark     Run performance benchmarks
    --verbose       Verbose output
    --parallel      Run tests in parallel where possible
"""

import sys
import argparse
import subprocess
import time
import json
from pathlib import Path
from typing import Dict, List, Optional
import concurrent.futures
from dataclasses import dataclass

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


@dataclass
class TestSuiteResult:
    """Results from running a test suite."""
    __test__ = False  # Tell pytest this is not a test class
    name: str
    passed: int
    failed: int
    skipped: int
    errors: int
    duration: float
    coverage: Optional[float] = None
    memory_peak: Optional[float] = None
    

class TestSuiteRunner:
    """Coordinates execution of all test suites."""
    __test__ = False  # Tell pytest this is not a test class
    
    TEST_SUITES = {
        'config_validation': {
            'file': 'test_config_validation_refactoring.py',
            'description': 'Config validation method refactoring tests',
            'category': 'unit',
            'priority': 'high',
            'estimated_time': 30
        },
        'channel_support': {
            'file': 'test_telegram_channel_support.py',
            'description': 'Telegram channel support tests',
            'category': 'integration',
            'priority': 'high',
            'estimated_time': 45
        },
        'message_pipeline': {
            'file': 'test_integration_message_pipeline.py',
            'description': 'Complete message processing pipeline tests',
            'category': 'integration',
            'priority': 'high',
            'estimated_time': 60
        },
        'property_based': {
            'file': 'test_property_based_config_validation.py',
            'description': 'Property-based config validation tests',
            'category': 'property',
            'priority': 'medium',
            'estimated_time': 90
        },
        'helper_methods': {
            'file': 'test_helper_method_extraction.py',
            'description': 'Helper method extraction tests (TDD)',
            'category': 'unit',
            'priority': 'high',
            'estimated_time': 40
        },
        'concurrent_processing': {
            'file': 'test_concurrent_message_processing.py',
            'description': 'Concurrent message processing tests',
            'category': 'concurrent',
            'priority': 'medium',
            'estimated_time': 120
        },
        'security': {
            'file': 'test_security_token_validation.py',
            'description': 'Security and token validation tests',
            'category': 'security',
            'priority': 'high',
            'estimated_time': 30
        },
        'error_recovery': {
            'file': 'test_error_recovery_scenarios.py',
            'description': 'Error recovery and fault tolerance tests',
            'category': 'resilience',
            'priority': 'medium',
            'estimated_time': 75
        },
        'performance': {
            'file': 'test_performance_and_load.py',
            'description': 'Performance and load tests',
            'category': 'performance',
            'priority': 'low',
            'estimated_time': 180
        }
    }
    
    def __init__(self, args):
        self.args = args
        self.results: List[TestSuiteResult] = []
        self.start_time = time.time()
        
    def run_test_suite(self, suite_name: str, suite_config: Dict) -> TestSuiteResult:
        """Run a single test suite and return results."""
        test_file = Path(__file__).parent / suite_config['file']
        
        if not test_file.exists():
            print(f"⚠️  Test file not found: {suite_config['file']}")
            return TestSuiteResult(
                name=suite_name,
                passed=0, failed=1, skipped=0, errors=1,
                duration=0.0
            )
        
        print(f"🧪 Running {suite_name}: {suite_config['description']}")
        
        # Build pytest command
        cmd = ['python', '-m', 'pytest', str(test_file)]
        
        if self.args.verbose:
            cmd.extend(['-v', '-s'])
        else:
            cmd.append('--tb=short')
            
        if self.args.coverage:
            cmd.extend(['--cov=local_orchestrator_tray', f'--cov-report=term-missing'])
            
        # Add performance monitoring for performance tests
        if suite_name == 'performance':
            cmd.extend(['--benchmark-only', '--benchmark-sort=mean'])
        
        # Run the test suite
        start_time = time.time()
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=suite_config.get('estimated_time', 60) * 2  # Double the estimated time for timeout
            )
            duration = time.time() - start_time
            
            # Parse pytest output to extract metrics
            passed, failed, skipped, errors = self._parse_pytest_output(result.stdout)
            
            if result.returncode == 0:
                status = "✅ PASSED"
            else:
                status = "❌ FAILED"
                if self.args.verbose:
                    print(f"STDOUT:\n{result.stdout}")
                    print(f"STDERR:\n{result.stderr}")
            
            print(f"{status} {suite_name} in {duration:.1f}s ({passed} passed, {failed} failed, {skipped} skipped)")
            
            return TestSuiteResult(
                name=suite_name,
                passed=passed,
                failed=failed,
                skipped=skipped,
                errors=errors,
                duration=duration
            )
            
        except subprocess.TimeoutExpired:
            print(f"⏰ TIMEOUT {suite_name} (exceeded {suite_config.get('estimated_time', 60) * 2}s)")
            return TestSuiteResult(
                name=suite_name,
                passed=0, failed=0, skipped=0, errors=1,
                duration=suite_config.get('estimated_time', 60) * 2
            )
        except Exception as e:
            print(f"💥 ERROR running {suite_name}: {e}")
            return TestSuiteResult(
                name=suite_name,
                passed=0, failed=1, skipped=0, errors=1,
                duration=time.time() - start_time
            )
    
    def _parse_pytest_output(self, output: str) -> tuple:
        """Parse pytest output to extract test counts."""
        # Look for pytest summary line
        lines = output.split('\n')
        
        for line in reversed(lines):
            if 'passed' in line or 'failed' in line or 'error' in line:
                # Try to extract numbers
                import re
                
                passed = len(re.findall(r'(\d+) passed', line))
                failed = len(re.findall(r'(\d+) failed', line))
                skipped = len(re.findall(r'(\d+) skipped', line))
                errors = len(re.findall(r'(\d+) error', line))
                
                # Extract actual numbers
                passed_match = re.search(r'(\d+) passed', line)
                failed_match = re.search(r'(\d+) failed', line)
                skipped_match = re.search(r'(\d+) skipped', line)
                error_match = re.search(r'(\d+) error', line)
                
                passed = int(passed_match.group(1)) if passed_match else 0
                failed = int(failed_match.group(1)) if failed_match else 0
                skipped = int(skipped_match.group(1)) if skipped_match else 0
                errors = int(error_match.group(1)) if error_match else 0
                
                return passed, failed, skipped, errors
        
        # Fallback: count test functions in output
        test_lines = [line for line in lines if '::test_' in line]
        total_tests = len(test_lines)
        
        if 'FAILED' in output:
            return 0, total_tests, 0, 0
        else:
            return total_tests, 0, 0, 0
    
    def get_test_suites_to_run(self) -> List[str]:
        """Determine which test suites to run based on arguments."""
        if self.args.fast:
            # Skip slow tests
            return [name for name, config in self.TEST_SUITES.items() 
                   if config['category'] not in ['performance', 'property']]
        
        if self.args.integration:
            return [name for name, config in self.TEST_SUITES.items() 
                   if config['category'] == 'integration']
        
        if self.args.security:
            return [name for name, config in self.TEST_SUITES.items() 
                   if config['category'] == 'security']
        
        if self.args.performance:
            return [name for name, config in self.TEST_SUITES.items() 
                   if config['category'] == 'performance']
        
        # Run all tests by default
        return list(self.TEST_SUITES.keys())
    
    def run_sequential(self, suite_names: List[str]):
        """Run test suites sequentially."""
        for suite_name in suite_names:
            suite_config = self.TEST_SUITES[suite_name]
            result = self.run_test_suite(suite_name, suite_config)
            self.results.append(result)
    
    def run_parallel(self, suite_names: List[str]):
        """Run test suites in parallel where possible."""
        # Group by category for parallel execution
        categories = {}
        for suite_name in suite_names:
            category = self.TEST_SUITES[suite_name]['category']
            if category not in categories:
                categories[category] = []
            categories[category].append(suite_name)
        
        # Run categories in parallel, but suites within category sequentially
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            futures = []
            
            for category, suites_in_category in categories.items():
                if category in ['performance', 'concurrent']:
                    # Run performance tests sequentially to avoid resource conflicts
                    for suite_name in suites_in_category:
                        suite_config = self.TEST_SUITES[suite_name]
                        future = executor.submit(self.run_test_suite, suite_name, suite_config)
                        futures.append(future)
                else:
                    # Run other categories in parallel
                    for suite_name in suites_in_category:
                        suite_config = self.TEST_SUITES[suite_name]
                        future = executor.submit(self.run_test_suite, suite_name, suite_config)
                        futures.append(future)
            
            # Collect results
            for future in concurrent.futures.as_completed(futures):
                try:
                    result = future.result()
                    self.results.append(result)
                except Exception as e:
                    print(f"💥 Parallel execution error: {e}")
    
    def generate_report(self):
        """Generate comprehensive test report."""
        total_duration = time.time() - self.start_time
        
        print("\n" + "="*80)
        print("🎯 TEST SUITE SUMMARY")
        print("="*80)
        
        total_passed = sum(r.passed for r in self.results)
        total_failed = sum(r.failed for r in self.results)
        total_skipped = sum(r.skipped for r in self.results)
        total_errors = sum(r.errors for r in self.results)
        total_tests = total_passed + total_failed + total_skipped + total_errors
        
        print(f"📊 Overall Results:")
        print(f"   Total Tests: {total_tests}")
        print(f"   ✅ Passed: {total_passed}")
        print(f"   ❌ Failed: {total_failed}")
        print(f"   ⏭️  Skipped: {total_skipped}")
        print(f"   💥 Errors: {total_errors}")
        print(f"   ⏱️  Total Time: {total_duration:.1f}s")
        
        if total_tests > 0:
            success_rate = (total_passed / total_tests) * 100
            print(f"   📈 Success Rate: {success_rate:.1f}%")
        
        print(f"\n📋 Individual Suite Results:")
        for result in sorted(self.results, key=lambda x: x.duration, reverse=True):
            suite_config = self.TEST_SUITES.get(result.name, {})
            status = "✅" if result.failed == 0 and result.errors == 0 else "❌"
            priority = suite_config.get('priority', 'unknown')
            category = suite_config.get('category', 'unknown')
            
            print(f"   {status} {result.name:<20} [{priority:>6}] [{category:>12}] "
                  f"{result.duration:>6.1f}s  "
                  f"({result.passed}✅ {result.failed}❌ {result.skipped}⏭️ {result.errors}💥)")
        
        # Generate recommendations
        print(f"\n💡 Recommendations:")
        
        failed_high_priority = [r for r in self.results 
                              if r.failed > 0 and self.TEST_SUITES.get(r.name, {}).get('priority') == 'high']
        if failed_high_priority:
            print(f"   🚨 HIGH PRIORITY: Fix failing tests in {[r.name for r in failed_high_priority]}")
        
        slow_tests = [r for r in self.results if r.duration > 60]
        if slow_tests:
            print(f"   🐌 PERFORMANCE: Consider optimizing slow tests: {[r.name for r in slow_tests]}")
        
        skipped_tests = [r for r in self.results if r.skipped > 5]
        if skipped_tests:
            print(f"   ⏭️  COVERAGE: Many skipped tests in: {[r.name for r in skipped_tests]}")
        
        # Overall assessment
        print(f"\n🎯 Overall Assessment:")
        if total_failed == 0 and total_errors == 0:
            print("   🎉 EXCELLENT: All tests passing! Ready for production.")
        elif total_failed <= 2 and total_errors == 0:
            print("   👍 GOOD: Minor test failures. Review and fix before merge.")
        elif success_rate > 80:
            print("   ⚠️  FAIR: Some test failures. Needs attention before deployment.")
        else:
            print("   🚨 POOR: Many test failures. Significant work needed.")
        
        # Save detailed report
        if self.args.benchmark:
            self.save_benchmark_report()
    
    def save_benchmark_report(self):
        """Save detailed benchmark report."""
        report_file = Path(__file__).parent / 'test_benchmark_report.json'
        
        report_data = {
            'timestamp': time.time(),
            'total_duration': time.time() - self.start_time,
            'suites': [
                {
                    'name': r.name,
                    'passed': r.passed,
                    'failed': r.failed,
                    'skipped': r.skipped,
                    'errors': r.errors,
                    'duration': r.duration,
                    'category': self.TEST_SUITES.get(r.name, {}).get('category'),
                    'priority': self.TEST_SUITES.get(r.name, {}).get('priority')
                }
                for r in self.results
            ]
        }
        
        with open(report_file, 'w') as f:
            json.dump(report_data, f, indent=2)
        
        print(f"📊 Detailed benchmark report saved to: {report_file}")
    
    def run(self):
        """Run the complete test suite."""
        print("🚀 Local Orchestrator Tray - Comprehensive Test Suite")
        print("=" * 60)
        
        suite_names = self.get_test_suites_to_run()
        estimated_time = sum(self.TEST_SUITES[name]['estimated_time'] for name in suite_names)
        
        print(f"📋 Running {len(suite_names)} test suites (estimated {estimated_time//60}m {estimated_time%60}s)")
        print(f"🎯 Test categories: {set(self.TEST_SUITES[name]['category'] for name in suite_names)}")
        print()
        
        # Run tests
        if self.args.parallel and len(suite_names) > 1:
            print("🔄 Running test suites in parallel...")
            self.run_parallel(suite_names)
        else:
            print("⏭️  Running test suites sequentially...")
            self.run_sequential(suite_names)
        
        # Generate report
        self.generate_report()
        
        # Return exit code based on results
        total_failed = sum(r.failed for r in self.results)
        total_errors = sum(r.errors for r in self.results)
        
        if total_failed > 0 or total_errors > 0:
            print(f"\n💥 Test suite FAILED with {total_failed} failures and {total_errors} errors")
            return 1
        else:
            print(f"\n🎉 Test suite PASSED - All tests successful!")
            return 0


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Local Orchestrator Tray Comprehensive Test Suite",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    
    parser.add_argument('--fast', action='store_true',
                       help='Run only fast tests (skip performance/load tests)')
    parser.add_argument('--integration', action='store_true',
                       help='Run only integration tests')
    parser.add_argument('--security', action='store_true',
                       help='Run only security tests')
    parser.add_argument('--performance', action='store_true',
                       help='Run only performance tests')
    parser.add_argument('--coverage', action='store_true',
                       help='Generate coverage report')
    parser.add_argument('--benchmark', action='store_true',
                       help='Run performance benchmarks and save results')
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='Verbose output')
    parser.add_argument('--parallel', action='store_true',
                       help='Run tests in parallel where possible')
    
    args = parser.parse_args()
    
    # Create and run test suite
    runner = TestSuiteRunner(args)
    exit_code = runner.run()
    
    sys.exit(exit_code)


if __name__ == '__main__':
    main()