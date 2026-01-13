#!/usr/bin/env python3
"""
CDK Compatibility Tests

Automated tests for validating CDK construct compatibility across different versions.
These tests help ensure that CDK code works correctly when upgrading between versions.
"""

import json
import tempfile
import subprocess
import os
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from pathlib import Path
import pytest


@dataclass
class CompatibilityTestCase:
    """Represents a compatibility test case"""
    name: str
    description: str
    cdk_code: str
    expected_constructs: List[str]
    min_cdk_version: str
    max_cdk_version: Optional[str] = None
    should_synthesize: bool = True
    expected_errors: List[str] = None


class CDKCompatibilityTester:
    """
    CDK Compatibility Testing Framework
    
    Provides automated testing of CDK constructs across different versions
    to validate compatibility and catch breaking changes.
    """
    
    def __init__(self, test_project_dir: Optional[str] = None):
        self.test_project_dir = Path(test_project_dir) if test_project_dir else None
        self.test_cases = self._load_test_cases()
    
    def _load_test_cases(self) -> List[CompatibilityTestCase]:
        """Load predefined compatibility test cases"""
        return [
            # ElastiCache CfnCacheCluster tests
            CompatibilityTestCase(
                name="elasticache_cfn_cache_cluster_basic",
                description="Basic ElastiCache CfnCacheCluster without encryption",
                cdk_code="""
from aws_cdk import Stack, aws_elasticache as elasticache
from constructs import Construct

class TestStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs):
        super().__init__(scope, construct_id, **kwargs)
        
        elasticache.CfnCacheCluster(
            self, "TestCluster",
            cache_node_type="cache.t3.micro",
            engine="redis",
            num_cache_nodes=1
        )
""",
                expected_constructs=["AWS::ElastiCache::CacheCluster"],
                min_cdk_version="2.0.0",
                should_synthesize=True
            ),
            
            CompatibilityTestCase(
                name="elasticache_cfn_cache_cluster_invalid_encryption",
                description="ElastiCache CfnCacheCluster with invalid encryption parameter",
                cdk_code="""
from aws_cdk import Stack, aws_elasticache as elasticache
from constructs import Construct

class TestStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs):
        super().__init__(scope, construct_id, **kwargs)
        
        elasticache.CfnCacheCluster(
            self, "TestCluster",
            cache_node_type="cache.t3.micro",
            engine="redis",
            num_cache_nodes=1,
            at_rest_encryption_enabled=True  # This should fail
        )
""",
                expected_constructs=[],
                min_cdk_version="2.0.0",
                should_synthesize=False,
                expected_errors=["at_rest_encryption_enabled"]
            ),
            
            # ECS ApplicationLoadBalancedFargateService tests
            CompatibilityTestCase(
                name="ecs_alb_fargate_service_basic",
                description="Basic ECS ApplicationLoadBalancedFargateService",
                cdk_code="""
from aws_cdk import Stack, aws_ecs_patterns as ecs_patterns, aws_ec2 as ec2
from constructs import Construct

class TestStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs):
        super().__init__(scope, construct_id, **kwargs)
        
        vpc = ec2.Vpc(self, "TestVpc", max_azs=2)
        
        ecs_patterns.ApplicationLoadBalancedFargateService(
            self, "TestService",
            vpc=vpc,
            memory_limit_mib=512,
            cpu=256,
            task_image_options=ecs_patterns.ApplicationLoadBalancedTaskImageOptions(
                image=ecs_patterns.ContainerImage.from_registry("nginx")
            )
        )
""",
                expected_constructs=[
                    "AWS::ECS::Cluster",
                    "AWS::ECS::Service",
                    "AWS::ElasticLoadBalancingV2::LoadBalancer"
                ],
                min_cdk_version="2.0.0",
                should_synthesize=True
            ),
            
            # CloudWatch LogQueryWidget tests
            CompatibilityTestCase(
                name="cloudwatch_log_query_widget_valid",
                description="CloudWatch LogQueryWidget with log group names",
                cdk_code="""
from aws_cdk import Stack, aws_cloudwatch as cloudwatch
from constructs import Construct

class TestStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs):
        super().__init__(scope, construct_id, **kwargs)
        
        cloudwatch.LogQueryWidget(
            title="Test Query",
            log_group_names=["/aws/lambda/test-function"],
            query_lines=[
                "fields @timestamp, @message",
                "sort @timestamp desc",
                "limit 100"
            ]
        )
""",
                expected_constructs=[],  # Widgets don't create CloudFormation resources
                min_cdk_version="2.0.0",
                should_synthesize=True
            ),
            
            # CDK v1 to v2 migration test
            CompatibilityTestCase(
                name="cdk_v1_import_style",
                description="CDK v1 style imports (should fail in v2)",
                cdk_code="""
from aws_cdk import core
from aws_cdk.aws_s3 import Bucket

class TestStack(core.Stack):
    def __init__(self, scope: core.Construct, construct_id: str, **kwargs):
        super().__init__(scope, construct_id, **kwargs)
        
        Bucket(self, "TestBucket")
""",
                expected_constructs=[],
                min_cdk_version="1.0.0",
                max_cdk_version="1.999.999",
                should_synthesize=False,
                expected_errors=["import"]
            ),
            
            # Security Group test
            CompatibilityTestCase(
                name="ec2_security_group_basic",
                description="Basic EC2 Security Group",
                cdk_code="""
from aws_cdk import Stack, aws_ec2 as ec2
from constructs import Construct

class TestStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs):
        super().__init__(scope, construct_id, **kwargs)
        
        vpc = ec2.Vpc(self, "TestVpc", max_azs=2)
        
        security_group = ec2.SecurityGroup(
            self, "TestSecurityGroup",
            vpc=vpc,
            description="Test security group",
            allow_all_outbound=True
        )
        
        security_group.add_ingress_rule(
            peer=ec2.Peer.any_ipv4(),
            connection=ec2.Port.tcp(80),
            description="Allow HTTP"
        )
""",
                expected_constructs=["AWS::EC2::SecurityGroup"],
                min_cdk_version="2.0.0",
                should_synthesize=True
            )
        ]
    
    def create_test_project(self, test_case: CompatibilityTestCase) -> Path:
        """Create a temporary CDK project for testing"""
        if self.test_project_dir:
            project_dir = self.test_project_dir / f"test_{test_case.name}"
        else:
            project_dir = Path(tempfile.mkdtemp(prefix=f"cdk_test_{test_case.name}_"))
        
        project_dir.mkdir(exist_ok=True)
        
        # Create app.py
        app_code = f"""#!/usr/bin/env python3
import aws_cdk as cdk
{test_case.cdk_code}

app = cdk.App()
TestStack(app, "TestStack")
app.synth()
"""
        
        with open(project_dir / "app.py", 'w') as f:
            f.write(app_code)
        
        # Create cdk.json
        cdk_json = {
            "app": "python3 app.py",
            "watch": {
                "include": ["**"],
                "exclude": [
                    "README.md",
                    "cdk*.json",
                    "requirements*.txt",
                    "source.bat",
                    "**/__pycache__",
                    "**/*.pyc"
                ]
            },
            "context": {
                "@aws-cdk/aws-lambda:recognizeLayerVersion": True,
                "@aws-cdk/core:checkSecretUsage": True,
                "@aws-cdk/core:target-partitions": ["aws", "aws-cn"]
            }
        }
        
        with open(project_dir / "cdk.json", 'w') as f:
            json.dump(cdk_json, f, indent=2)
        
        # Create requirements.txt
        requirements = [
            f"aws-cdk-lib>={test_case.min_cdk_version}",
            "constructs>=10.0.0"
        ]
        
        if test_case.max_cdk_version:
            requirements[0] = f"aws-cdk-lib>={test_case.min_cdk_version},<{test_case.max_cdk_version}"
        
        with open(project_dir / "requirements.txt", 'w') as f:
            f.write('\n'.join(requirements))
        
        return project_dir
    
    def run_synthesis_test(self, test_case: CompatibilityTestCase) -> Dict[str, Any]:
        """Run CDK synthesis test for a test case"""
        result = {
            "test_name": test_case.name,
            "success": False,
            "synthesis_successful": False,
            "expected_constructs_found": [],
            "unexpected_errors": [],
            "expected_errors_found": [],
            "output": "",
            "error_output": ""
        }
        
        project_dir = None
        try:
            # Create test project
            project_dir = self.create_test_project(test_case)
            
            # Run CDK synth
            process = subprocess.run(
                ["cdk", "synth", "--no-staging"],
                cwd=project_dir,
                capture_output=True,
                text=True,
                timeout=120
            )
            
            result["output"] = process.stdout
            result["error_output"] = process.stderr
            result["synthesis_successful"] = process.returncode == 0
            
            # Check if synthesis result matches expectations
            if test_case.should_synthesize:
                if process.returncode == 0:
                    # Check for expected constructs in CloudFormation template
                    template_content = process.stdout
                    for construct in test_case.expected_constructs:
                        if construct in template_content:
                            result["expected_constructs_found"].append(construct)
                    
                    # Success if all expected constructs found
                    result["success"] = (
                        len(result["expected_constructs_found"]) == len(test_case.expected_constructs)
                    )
                else:
                    result["unexpected_errors"].append(f"Synthesis failed: {process.stderr}")
            else:
                # Test expects synthesis to fail
                if process.returncode != 0:
                    # Check if expected errors are present
                    if test_case.expected_errors:
                        for expected_error in test_case.expected_errors:
                            if expected_error.lower() in process.stderr.lower():
                                result["expected_errors_found"].append(expected_error)
                        
                        result["success"] = (
                            len(result["expected_errors_found"]) == len(test_case.expected_errors)
                        )
                    else:
                        result["success"] = True  # Any failure is expected
                else:
                    result["unexpected_errors"].append("Synthesis succeeded but was expected to fail")
        
        except subprocess.TimeoutExpired:
            result["error_output"] = "CDK synthesis timed out"
        except Exception as e:
            result["error_output"] = f"Test execution failed: {str(e)}"
        finally:
            # Cleanup test project
            if project_dir and not self.test_project_dir:
                import shutil
                try:
                    shutil.rmtree(project_dir)
                except:
                    pass
        
        return result
    
    def run_all_tests(self, cdk_version_filter: Optional[str] = None) -> Dict[str, Any]:
        """
        Run all compatibility tests
        
        Args:
            cdk_version_filter: Only run tests compatible with this CDK version
            
        Returns:
            Test results summary
        """
        results = {
            "timestamp": "2024-01-12T00:00:00Z",
            "cdk_version_filter": cdk_version_filter,
            "total_tests": 0,
            "passed_tests": 0,
            "failed_tests": 0,
            "test_results": []
        }
        
        for test_case in self.test_cases:
            # Skip tests that don't match version filter
            if cdk_version_filter:
                try:
                    import semver
                    if semver.compare(cdk_version_filter, test_case.min_cdk_version) < 0:
                        continue
                    if test_case.max_cdk_version and semver.compare(cdk_version_filter, test_case.max_cdk_version) > 0:
                        continue
                except:
                    pass
            
            print(f"Running test: {test_case.name}")
            test_result = self.run_synthesis_test(test_case)
            results["test_results"].append(test_result)
            results["total_tests"] += 1
            
            if test_result["success"]:
                results["passed_tests"] += 1
                print(f"  ✅ PASSED")
            else:
                results["failed_tests"] += 1
                print(f"  ❌ FAILED: {test_result.get('error_output', 'Unknown error')}")
        
        return results
    
    def generate_test_report(self, results: Dict[str, Any]) -> str:
        """Generate a formatted test report"""
        report = []
        report.append("CDK Compatibility Test Report")
        report.append("=" * 40)
        report.append(f"Timestamp: {results['timestamp']}")
        if results['cdk_version_filter']:
            report.append(f"CDK Version Filter: {results['cdk_version_filter']}")
        report.append("")
        
        # Summary
        total = results['total_tests']
        passed = results['passed_tests']
        failed = results['failed_tests']
        success_rate = (passed / total * 100) if total > 0 else 0
        
        report.append(f"📊 Summary:")
        report.append(f"  Total Tests: {total}")
        report.append(f"  Passed: {passed}")
        report.append(f"  Failed: {failed}")
        report.append(f"  Success Rate: {success_rate:.1f}%")
        report.append("")
        
        # Test details
        if results['test_results']:
            report.append("📋 Test Details:")
            for test_result in results['test_results']:
                status = "✅ PASS" if test_result['success'] else "❌ FAIL"
                report.append(f"  {status} {test_result['test_name']}")
                
                if not test_result['success']:
                    if test_result['unexpected_errors']:
                        for error in test_result['unexpected_errors']:
                            report.append(f"    Error: {error}")
                    if test_result['error_output']:
                        # Show first line of error output
                        first_error_line = test_result['error_output'].split('\n')[0]
                        report.append(f"    Output: {first_error_line}")
                
                report.append("")
        
        return "\n".join(report)


# Pytest integration for running tests in CI/CD
class TestCDKCompatibility:
    """Pytest test class for CDK compatibility tests"""
    
    @pytest.fixture(scope="class")
    def tester(self):
        return CDKCompatibilityTester()
    
    def test_elasticache_basic(self, tester):
        """Test basic ElastiCache configuration"""
        test_case = next(tc for tc in tester.test_cases if tc.name == "elasticache_cfn_cache_cluster_basic")
        result = tester.run_synthesis_test(test_case)
        assert result["success"], f"Test failed: {result.get('error_output', 'Unknown error')}"
    
    def test_elasticache_invalid_encryption(self, tester):
        """Test ElastiCache with invalid encryption parameter"""
        test_case = next(tc for tc in tester.test_cases if tc.name == "elasticache_cfn_cache_cluster_invalid_encryption")
        result = tester.run_synthesis_test(test_case)
        assert result["success"], f"Test should have failed but didn't: {result.get('output', '')}"
    
    def test_ecs_alb_fargate_service(self, tester):
        """Test ECS ApplicationLoadBalancedFargateService"""
        test_case = next(tc for tc in tester.test_cases if tc.name == "ecs_alb_fargate_service_basic")
        result = tester.run_synthesis_test(test_case)
        assert result["success"], f"Test failed: {result.get('error_output', 'Unknown error')}"
    
    def test_cloudwatch_log_query_widget(self, tester):
        """Test CloudWatch LogQueryWidget"""
        test_case = next(tc for tc in tester.test_cases if tc.name == "cloudwatch_log_query_widget_valid")
        result = tester.run_synthesis_test(test_case)
        assert result["success"], f"Test failed: {result.get('error_output', 'Unknown error')}"
    
    def test_security_group_basic(self, tester):
        """Test basic Security Group configuration"""
        test_case = next(tc for tc in tester.test_cases if tc.name == "ec2_security_group_basic")
        result = tester.run_synthesis_test(test_case)
        assert result["success"], f"Test failed: {result.get('error_output', 'Unknown error')}"


def main():
    """Main function for command-line usage"""
    import argparse
    
    parser = argparse.ArgumentParser(description="CDK Compatibility Testing")
    parser.add_argument("--cdk-version", help="Filter tests for specific CDK version")
    parser.add_argument("--test-dir", help="Directory to create test projects in")
    parser.add_argument("--report-only", action="store_true", help="Generate report from previous results")
    
    args = parser.parse_args()
    
    tester = CDKCompatibilityTester(args.test_dir)
    
    if not args.report_only:
        print("Running CDK compatibility tests...")
        results = tester.run_all_tests(args.cdk_version)
        
        # Save results
        results_file = Path("cdk_compatibility_results.json")
        with open(results_file, 'w') as f:
            json.dump(results, f, indent=2)
        
        print(f"\nResults saved to {results_file}")
    else:
        # Load previous results
        results_file = Path("cdk_compatibility_results.json")
        if results_file.exists():
            with open(results_file, 'r') as f:
                results = json.load(f)
        else:
            print("No previous results found")
            return
    
    # Generate and display report
    report = tester.generate_test_report(results)
    print("\n" + report)


if __name__ == "__main__":
    main()