#!/usr/bin/env python3
"""
Integration tests for CDK Version Management System

Simple tests to verify the core functionality works correctly.
"""

import os
import tempfile
import shutil
from pathlib import Path
import json

from cdk_version_manager import CDKVersionManager
from cdk_validator import CDKParameterValidator


def test_cdk_parameter_validator():
    """Test CDK parameter validation functionality"""
    print("🧪 Testing CDK Parameter Validator...")
    
    validator = CDKParameterValidator()
    
    # Test ElastiCache validation
    params = {
        "at_rest_encryption_enabled": True,
        "cache_node_type": "cache.t3.micro"
    }
    
    issues = validator.validate_parameters("CfnCacheCluster", params)
    assert len(issues) > 0, "Should detect at_rest_encryption_enabled issue"
    assert any("at_rest_encryption_enabled" in issue.parameter for issue in issues)
    
    print("  ✅ Parameter validation working correctly")


def test_cdk_version_manager():
    """Test CDK version manager functionality"""
    print("🧪 Testing CDK Version Manager...")
    
    # Create temporary project directory
    with tempfile.TemporaryDirectory() as temp_dir:
        manager = CDKVersionManager(temp_dir)
        
        # Test current version detection
        current_version = manager.get_current_cdk_version()
        assert current_version is not None, "Should detect CDK version"
        print(f"  ✅ Current version detected: {current_version}")
        
        # Test compatibility check
        status, issues = manager.check_version_compatibility(current_version)
        print(f"  ✅ Compatibility check completed: {status.value}")
        
        # Test snapshot creation
        snapshot_id = manager.create_snapshot("Test snapshot")
        assert snapshot_id is not None, "Should create snapshot"
        print(f"  ✅ Snapshot created: {snapshot_id}")
        
        # Test upgrade path creation
        upgrade_steps = manager.create_upgrade_path("3.0.0")
        print(f"  ✅ Upgrade path created with {len(upgrade_steps)} steps")


def test_project_file_scanning():
    """Test scanning of actual project files"""
    print("🧪 Testing Project File Scanning...")
    
    validator = CDKParameterValidator()
    
    # Look for CDK files in the current project
    project_root = Path(".")
    cdk_files = []
    
    for file_path in project_root.rglob("*.py"):
        if file_path.name.startswith("cdk_") or "infrastructure" in str(file_path):
            try:
                with open(file_path, 'r') as f:
                    content = f.read()
                    if "aws_cdk" in content or "CfnCacheCluster" in content:
                        cdk_files.append(file_path)
            except:
                pass
    
    print(f"  ✅ Found {len(cdk_files)} CDK-related files")
    
    # Test validation on actual files
    total_issues = 0
    for file_path in cdk_files[:3]:  # Test first 3 files
        try:
            issues = validator.validate_code_file(str(file_path))
            total_issues += len(issues)
            print(f"  📄 {file_path.name}: {len(issues)} issues")
        except Exception as e:
            print(f"  ⚠️  Could not validate {file_path.name}: {e}")
    
    print(f"  ✅ Total issues found: {total_issues}")


def test_configuration_management():
    """Test configuration management"""
    print("🧪 Testing Configuration Management...")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        manager = CDKVersionManager(temp_dir)
        
        # Test default configuration
        assert "current_version" in manager.config
        assert "allowed_risk_levels" in manager.config
        print("  ✅ Default configuration loaded")
        
        # Test configuration update
        original_version = manager.config["current_version"]
        manager.config["current_version"] = "2.160.0"
        manager._save_config()
        
        # Create new manager to test persistence
        manager2 = CDKVersionManager(temp_dir)
        assert manager2.config["current_version"] == "2.160.0"
        print("  ✅ Configuration persistence working")


def test_report_generation():
    """Test report generation"""
    print("🧪 Testing Report Generation...")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        manager = CDKVersionManager(temp_dir)
        
        # Generate report
        report = manager.generate_version_report()
        
        assert "CDK Version Management Report" in report
        assert "Current Status" in report
        assert "Current CDK Version" in report
        print("  ✅ Report generation working")


def main():
    """Run all integration tests"""
    print("🚀 Running CDK Version Management System Integration Tests")
    print("=" * 60)
    
    try:
        test_cdk_parameter_validator()
        test_cdk_version_manager()
        test_project_file_scanning()
        test_configuration_management()
        test_report_generation()
        
        print("\n🎉 All tests passed successfully!")
        print("✅ CDK Version Management System is working correctly")
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main())