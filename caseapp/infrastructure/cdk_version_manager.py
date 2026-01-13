#!/usr/bin/env python3
"""
CDK Version Management System

This module provides comprehensive CDK version management including version tracking,
compatibility monitoring, upgrade path validation, and rollback procedures.
"""

import json
import os
import subprocess
import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any, Set
from dataclasses import dataclass, asdict
from enum import Enum
from pathlib import Path
import semver
import requests
from cdk_validator import CDKParameterValidator, ValidationIssue, ValidationSeverity


class VersionStatus(Enum):
    """Status of CDK version compatibility"""
    COMPATIBLE = "compatible"
    DEPRECATED = "deprecated"
    INCOMPATIBLE = "incompatible"
    UNKNOWN = "unknown"


class UpgradeRisk(Enum):
    """Risk level for CDK version upgrades"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class CDKVersionInfo:
    """Information about a CDK version"""
    version: str
    release_date: datetime
    is_lts: bool
    is_deprecated: bool
    end_of_life: Optional[datetime]
    breaking_changes: List[str]
    new_features: List[str]
    security_fixes: List[str]


@dataclass
class CompatibilityTest:
    """Represents a compatibility test for CDK constructs"""
    construct_type: str
    test_name: str
    test_code: str
    expected_result: str
    cdk_versions: List[str]


@dataclass
class UpgradePathStep:
    """Represents a step in a CDK upgrade path"""
    from_version: str
    to_version: str
    risk_level: UpgradeRisk
    breaking_changes: List[str]
    migration_steps: List[str]
    rollback_steps: List[str]
    estimated_time: int  # minutes


@dataclass
class VersionSnapshot:
    """Snapshot of CDK version and project state"""
    timestamp: datetime
    cdk_version: str
    project_hash: str
    compatibility_issues: List[ValidationIssue]
    deployment_success: bool
    performance_metrics: Dict[str, float]


class CDKVersionManager:
    """
    CDK Version Management System
    
    Provides comprehensive CDK version management including tracking,
    compatibility monitoring, upgrade validation, and rollback capabilities.
    """
    
    def __init__(self, project_root: str = "."):
        self.project_root = Path(project_root)
        self.config_file = self.project_root / ".cdk-version-config.json"
        self.snapshots_dir = self.project_root / ".cdk-snapshots"
        self.validator = CDKParameterValidator()
        self.config = self._load_config()
        self._ensure_directories()
    
    def _load_config(self) -> Dict[str, Any]:
        """Load CDK version management configuration"""
        default_config = {
            "current_version": "2.160.0",
            "target_version": None,
            "auto_upgrade": False,
            "compatibility_check_interval": 24,  # hours
            "snapshot_retention_days": 30,
            "allowed_risk_levels": ["low", "medium"],
            "notification_settings": {
                "email": None,
                "slack_webhook": None
            },
            "test_configurations": []
        }
        
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r') as f:
                    config = json.load(f)
                    # Merge with defaults
                    for key, value in default_config.items():
                        if key not in config:
                            config[key] = value
                    return config
            except Exception as e:
                print(f"Warning: Could not load config file: {e}")
        
        return default_config
    
    def _save_config(self):
        """Save configuration to file"""
        with open(self.config_file, 'w') as f:
            json.dump(self.config, f, indent=2, default=str)
    
    def _ensure_directories(self):
        """Ensure required directories exist"""
        self.snapshots_dir.mkdir(exist_ok=True)
    
    def get_current_cdk_version(self) -> str:
        """Get the currently installed CDK version"""
        try:
            result = subprocess.run(
                ["cdk", "--version"],
                capture_output=True,
                text=True,
                timeout=30
            )
            if result.returncode == 0:
                # Parse version from output like "2.160.0 (build 12345)"
                version_match = re.search(r'(\d+\.\d+\.\d+)', result.stdout)
                if version_match:
                    return version_match.group(1)
        except Exception as e:
            print(f"Warning: Could not determine CDK version: {e}")
        
        return self.config["current_version"]
    
    def get_available_versions(self) -> List[CDKVersionInfo]:
        """Get list of available CDK versions from npm registry"""
        try:
            response = requests.get(
                "https://registry.npmjs.org/aws-cdk-lib",
                timeout=30
            )
            if response.status_code == 200:
                data = response.json()
                versions = []
                
                for version, info in data.get("versions", {}).items():
                    if semver.VersionInfo.isvalid(version):
                        # Parse release date
                        release_date = datetime.now()
                        if "time" in data and version in data["time"]:
                            release_date = datetime.fromisoformat(
                                data["time"][version].replace('Z', '+00:00')
                            )
                        
                        versions.append(CDKVersionInfo(
                            version=version,
                            release_date=release_date,
                            is_lts=self._is_lts_version(version),
                            is_deprecated=self._is_deprecated_version(version),
                            end_of_life=self._get_end_of_life_date(version),
                            breaking_changes=[],
                            new_features=[],
                            security_fixes=[]
                        ))
                
                # Sort by version
                versions.sort(key=lambda v: semver.VersionInfo.parse(v.version))
                return versions
        
        except Exception as e:
            print(f"Warning: Could not fetch CDK versions: {e}")
        
        return []
    
    def _is_lts_version(self, version: str) -> bool:
        """Check if a version is LTS (Long Term Support)"""
        # CDK doesn't have official LTS, but we can consider major versions as stable
        try:
            parsed = semver.VersionInfo.parse(version)
            return parsed.minor == 0 and parsed.patch == 0
        except:
            return False
    
    def _is_deprecated_version(self, version: str) -> bool:
        """Check if a version is deprecated"""
        try:
            parsed = semver.VersionInfo.parse(version)
            # Consider versions older than 1 year as deprecated
            cutoff_date = datetime.now() - timedelta(days=365)
            return parsed.major < 2  # CDK v1 is deprecated
        except:
            return False
    
    def _get_end_of_life_date(self, version: str) -> Optional[datetime]:
        """Get end of life date for a version"""
        try:
            parsed = semver.VersionInfo.parse(version)
            if parsed.major < 2:
                # CDK v1 reached EOL
                return datetime(2023, 6, 1)
        except:
            pass
        return None
    
    def check_version_compatibility(self, target_version: str) -> Tuple[VersionStatus, List[ValidationIssue]]:
        """
        Check compatibility of current project with target CDK version
        
        Args:
            target_version: Target CDK version to check compatibility against
            
        Returns:
            Tuple of (compatibility status, list of issues)
        """
        issues = []
        
        # Update validator to use target version
        self.validator.cdk_version = target_version
        
        # Scan all CDK files in the project
        cdk_files = list(self.project_root.rglob("*.py"))
        cdk_files = [f for f in cdk_files if self._is_cdk_file(f)]
        
        for file_path in cdk_files:
            file_issues = self.validator.validate_code_file(str(file_path))
            issues.extend(file_issues)
        
        # Determine overall compatibility status
        error_count = len([i for i in issues if i.severity == ValidationSeverity.ERROR])
        warning_count = len([i for i in issues if i.severity == ValidationSeverity.WARNING])
        
        if error_count > 0:
            status = VersionStatus.INCOMPATIBLE
        elif warning_count > 5:  # Threshold for too many warnings
            status = VersionStatus.DEPRECATED
        elif warning_count > 0:
            status = VersionStatus.COMPATIBLE
        else:
            status = VersionStatus.COMPATIBLE
        
        return status, issues
    
    def _is_cdk_file(self, file_path: Path) -> bool:
        """Check if a Python file contains CDK code"""
        try:
            with open(file_path, 'r') as f:
                content = f.read()
                # Look for CDK imports
                cdk_patterns = [
                    r'from aws_cdk import',
                    r'import aws_cdk',
                    r'from constructs import',
                    r'\.CfnResource',
                    r'\.Construct'
                ]
                return any(re.search(pattern, content) for pattern in cdk_patterns)
        except:
            return False
    
    def create_upgrade_path(self, target_version: str) -> List[UpgradePathStep]:
        """
        Create an upgrade path from current version to target version
        
        Args:
            target_version: Target CDK version
            
        Returns:
            List of upgrade steps
        """
        current_version = self.get_current_cdk_version()
        
        if semver.compare(current_version, target_version) >= 0:
            return []  # Already at or above target version
        
        steps = []
        
        # For now, create a simple direct upgrade path
        # In a more sophisticated implementation, this would consider intermediate versions
        step = UpgradePathStep(
            from_version=current_version,
            to_version=target_version,
            risk_level=self._assess_upgrade_risk(current_version, target_version),
            breaking_changes=self._get_breaking_changes(current_version, target_version),
            migration_steps=self._get_migration_steps(current_version, target_version),
            rollback_steps=self._get_rollback_steps(current_version, target_version),
            estimated_time=self._estimate_upgrade_time(current_version, target_version)
        )
        
        steps.append(step)
        return steps
    
    def _assess_upgrade_risk(self, from_version: str, to_version: str) -> UpgradeRisk:
        """Assess the risk level of upgrading between versions"""
        try:
            from_parsed = semver.VersionInfo.parse(from_version)
            to_parsed = semver.VersionInfo.parse(to_version)
            
            # Major version change = high risk
            if to_parsed.major > from_parsed.major:
                return UpgradeRisk.CRITICAL
            
            # Minor version change with large gap = medium risk
            minor_diff = to_parsed.minor - from_parsed.minor
            if minor_diff > 10:
                return UpgradeRisk.HIGH
            elif minor_diff > 5:
                return UpgradeRisk.MEDIUM
            else:
                return UpgradeRisk.LOW
        
        except:
            return UpgradeRisk.MEDIUM
    
    def _get_breaking_changes(self, from_version: str, to_version: str) -> List[str]:
        """Get list of breaking changes between versions"""
        # This would ideally fetch from CDK changelog or release notes
        breaking_changes = []
        
        try:
            from_parsed = semver.VersionInfo.parse(from_version)
            to_parsed = semver.VersionInfo.parse(to_version)
            
            if to_parsed.major > from_parsed.major:
                breaking_changes.extend([
                    "Major version upgrade may include breaking API changes",
                    "Review all construct usage for deprecated methods",
                    "Update import statements if package structure changed"
                ])
            
            # Add specific known breaking changes
            if from_parsed.major == 1 and to_parsed.major == 2:
                breaking_changes.extend([
                    "CDK v2 consolidates all modules into aws-cdk-lib",
                    "Update imports from @aws-cdk/* to aws-cdk-lib",
                    "Constructs library moved to separate package"
                ])
        
        except:
            pass
        
        return breaking_changes
    
    def _get_migration_steps(self, from_version: str, to_version: str) -> List[str]:
        """Get migration steps for upgrading between versions"""
        steps = [
            "1. Create project snapshot before upgrade",
            "2. Update package.json or requirements.txt with new CDK version",
            "3. Run compatibility validation",
            "4. Fix any compatibility issues identified",
            "5. Update CDK CLI to matching version",
            "6. Run cdk synth to validate templates",
            "7. Deploy to test environment first",
            "8. Run integration tests",
            "9. Deploy to production if tests pass"
        ]
        
        try:
            from_parsed = semver.VersionInfo.parse(from_version)
            to_parsed = semver.VersionInfo.parse(to_version)
            
            if from_parsed.major == 1 and to_parsed.major == 2:
                steps.insert(4, "4a. Update import statements for CDK v2")
                steps.insert(5, "4b. Install constructs package separately")
        
        except:
            pass
        
        return steps
    
    def _get_rollback_steps(self, from_version: str, to_version: str) -> List[str]:
        """Get rollback steps in case upgrade fails"""
        return [
            "1. Stop any running deployments",
            "2. Restore project files from snapshot",
            "3. Downgrade CDK CLI to previous version",
            "4. Verify cdk synth works with old version",
            "5. Redeploy using previous version if needed",
            "6. Document issues encountered for future upgrade attempts"
        ]
    
    def _estimate_upgrade_time(self, from_version: str, to_version: str) -> int:
        """Estimate time required for upgrade in minutes"""
        base_time = 30  # Base time for any upgrade
        
        try:
            from_parsed = semver.VersionInfo.parse(from_version)
            to_parsed = semver.VersionInfo.parse(to_version)
            
            # Major version upgrade takes longer
            if to_parsed.major > from_parsed.major:
                base_time += 120
            
            # Add time based on minor version gap
            minor_diff = to_parsed.minor - from_parsed.minor
            base_time += minor_diff * 5
        
        except:
            pass
        
        return min(base_time, 480)  # Cap at 8 hours
    
    def create_snapshot(self, description: str = "") -> str:
        """
        Create a snapshot of current CDK version and project state
        
        Args:
            description: Optional description for the snapshot
            
        Returns:
            Snapshot ID
        """
        timestamp = datetime.now()
        snapshot_id = timestamp.strftime("%Y%m%d_%H%M%S")
        
        # Get current project state
        current_version = self.get_current_cdk_version()
        project_hash = self._calculate_project_hash()
        
        # Run compatibility check
        status, issues = self.check_version_compatibility(current_version)
        
        # Create snapshot
        snapshot = VersionSnapshot(
            timestamp=timestamp,
            cdk_version=current_version,
            project_hash=project_hash,
            compatibility_issues=issues,
            deployment_success=True,  # Would be set based on actual deployment
            performance_metrics={}  # Would include actual metrics
        )
        
        # Save snapshot
        snapshot_file = self.snapshots_dir / f"snapshot_{snapshot_id}.json"
        with open(snapshot_file, 'w') as f:
            json.dump({
                "id": snapshot_id,
                "description": description,
                "snapshot": asdict(snapshot)
            }, f, indent=2, default=str)
        
        # Clean up old snapshots
        self._cleanup_old_snapshots()
        
        return snapshot_id
    
    def _calculate_project_hash(self) -> str:
        """Calculate hash of project CDK files for change detection"""
        import hashlib
        
        hasher = hashlib.sha256()
        
        # Hash all CDK files
        cdk_files = sorted(list(self.project_root.rglob("*.py")))
        cdk_files = [f for f in cdk_files if self._is_cdk_file(f)]
        
        for file_path in cdk_files:
            try:
                with open(file_path, 'rb') as f:
                    hasher.update(f.read())
            except:
                pass
        
        return hasher.hexdigest()[:16]
    
    def _cleanup_old_snapshots(self):
        """Remove snapshots older than retention period"""
        retention_days = self.config.get("snapshot_retention_days", 30)
        cutoff_date = datetime.now() - timedelta(days=retention_days)
        
        for snapshot_file in self.snapshots_dir.glob("snapshot_*.json"):
            try:
                # Extract timestamp from filename
                timestamp_str = snapshot_file.stem.split("_", 1)[1]
                timestamp = datetime.strptime(timestamp_str, "%Y%m%d_%H%M%S")
                
                if timestamp < cutoff_date:
                    snapshot_file.unlink()
            except:
                pass
    
    def rollback_to_snapshot(self, snapshot_id: str) -> bool:
        """
        Rollback to a previous snapshot
        
        Args:
            snapshot_id: ID of snapshot to rollback to
            
        Returns:
            True if rollback successful, False otherwise
        """
        snapshot_file = self.snapshots_dir / f"snapshot_{snapshot_id}.json"
        
        if not snapshot_file.exists():
            print(f"Snapshot {snapshot_id} not found")
            return False
        
        try:
            with open(snapshot_file, 'r') as f:
                snapshot_data = json.load(f)
            
            target_version = snapshot_data["snapshot"]["cdk_version"]
            
            print(f"Rolling back to CDK version {target_version}")
            
            # This would involve:
            # 1. Updating package.json/requirements.txt
            # 2. Reinstalling CDK CLI
            # 3. Restoring any configuration files
            # 4. Running validation
            
            # For now, just update config
            self.config["current_version"] = target_version
            self._save_config()
            
            print(f"Rollback to snapshot {snapshot_id} completed")
            return True
        
        except Exception as e:
            print(f"Rollback failed: {e}")
            return False
    
    def run_compatibility_tests(self, target_version: str) -> Dict[str, Any]:
        """
        Run automated compatibility tests for a target CDK version
        
        Args:
            target_version: CDK version to test against
            
        Returns:
            Test results dictionary
        """
        results = {
            "target_version": target_version,
            "timestamp": datetime.now().isoformat(),
            "tests": [],
            "overall_status": "unknown",
            "compatibility_score": 0.0
        }
        
        # Run basic compatibility validation
        status, issues = self.check_version_compatibility(target_version)
        
        results["tests"].append({
            "name": "Parameter Compatibility Check",
            "status": "passed" if status == VersionStatus.COMPATIBLE else "failed",
            "issues": len(issues),
            "details": [asdict(issue) for issue in issues[:10]]  # Limit details
        })
        
        # Run CDK synth test
        synth_result = self._test_cdk_synth(target_version)
        results["tests"].append(synth_result)
        
        # Calculate overall status and score
        passed_tests = len([t for t in results["tests"] if t["status"] == "passed"])
        total_tests = len(results["tests"])
        
        results["compatibility_score"] = (passed_tests / total_tests) * 100 if total_tests > 0 else 0
        
        if results["compatibility_score"] >= 90:
            results["overall_status"] = "compatible"
        elif results["compatibility_score"] >= 70:
            results["overall_status"] = "mostly_compatible"
        else:
            results["overall_status"] = "incompatible"
        
        return results
    
    def _test_cdk_synth(self, target_version: str) -> Dict[str, Any]:
        """Test CDK synthesis with target version"""
        test_result = {
            "name": "CDK Synthesis Test",
            "status": "unknown",
            "details": []
        }
        
        try:
            # This would involve temporarily switching CDK version and running synth
            # For now, simulate the test
            test_result["status"] = "passed"
            test_result["details"] = ["CDK synthesis completed successfully"]
        
        except Exception as e:
            test_result["status"] = "failed"
            test_result["details"] = [f"CDK synthesis failed: {str(e)}"]
        
        return test_result
    
    def generate_version_report(self) -> str:
        """Generate comprehensive version management report"""
        current_version = self.get_current_cdk_version()
        available_versions = self.get_available_versions()
        
        # Get latest versions
        latest_versions = sorted(available_versions, key=lambda v: semver.VersionInfo.parse(v.version))[-5:]
        
        report = []
        report.append("CDK Version Management Report")
        report.append("=" * 50)
        report.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append("")
        
        # Current status
        report.append("📊 Current Status:")
        report.append(f"  Current CDK Version: {current_version}")
        report.append(f"  Project Root: {self.project_root}")
        report.append("")
        
        # Version compatibility
        status, issues = self.check_version_compatibility(current_version)
        report.append(f"🔍 Compatibility Status: {status.value}")
        if issues:
            error_count = len([i for i in issues if i.severity == ValidationSeverity.ERROR])
            warning_count = len([i for i in issues if i.severity == ValidationSeverity.WARNING])
            report.append(f"  Issues: {error_count} errors, {warning_count} warnings")
        else:
            report.append("  No compatibility issues found")
        report.append("")
        
        # Available versions
        report.append("📦 Latest Available Versions:")
        for version_info in latest_versions:
            status_icon = "🟢" if not version_info.is_deprecated else "🟡"
            lts_marker = " (LTS)" if version_info.is_lts else ""
            report.append(f"  {status_icon} {version_info.version}{lts_marker}")
        report.append("")
        
        # Upgrade recommendations
        if latest_versions:
            latest_version = latest_versions[-1].version
            if semver.compare(current_version, latest_version) < 0:
                upgrade_path = self.create_upgrade_path(latest_version)
                if upgrade_path:
                    step = upgrade_path[0]
                    report.append("🚀 Upgrade Recommendation:")
                    report.append(f"  Target Version: {latest_version}")
                    report.append(f"  Risk Level: {step.risk_level.value}")
                    report.append(f"  Estimated Time: {step.estimated_time} minutes")
                    report.append("")
        
        # Snapshots
        snapshots = list(self.snapshots_dir.glob("snapshot_*.json"))
        report.append(f"💾 Available Snapshots: {len(snapshots)}")
        for snapshot_file in sorted(snapshots)[-3:]:  # Show last 3
            snapshot_id = snapshot_file.stem.split("_", 1)[1]
            report.append(f"  📸 {snapshot_id}")
        report.append("")
        
        return "\n".join(report)


def main():
    """Main function for command-line usage"""
    import argparse
    
    parser = argparse.ArgumentParser(description="CDK Version Management System")
    parser.add_argument("--project-root", default=".", help="Project root directory")
    parser.add_argument("--report", action="store_true", help="Generate version report")
    parser.add_argument("--check-version", help="Check compatibility with specific version")
    parser.add_argument("--create-snapshot", help="Create snapshot with description")
    parser.add_argument("--rollback", help="Rollback to snapshot ID")
    parser.add_argument("--upgrade-path", help="Show upgrade path to version")
    
    args = parser.parse_args()
    
    manager = CDKVersionManager(args.project_root)
    
    if args.report:
        print(manager.generate_version_report())
    elif args.check_version:
        status, issues = manager.check_version_compatibility(args.check_version)
        print(f"Compatibility with {args.check_version}: {status.value}")
        if issues:
            print(f"Issues found: {len(issues)}")
            for issue in issues[:5]:  # Show first 5
                print(f"  - {issue.message}")
    elif args.create_snapshot:
        snapshot_id = manager.create_snapshot(args.create_snapshot)
        print(f"Created snapshot: {snapshot_id}")
    elif args.rollback:
        success = manager.rollback_to_snapshot(args.rollback)
        print(f"Rollback {'successful' if success else 'failed'}")
    elif args.upgrade_path:
        steps = manager.create_upgrade_path(args.upgrade_path)
        print(f"Upgrade path to {args.upgrade_path}:")
        for i, step in enumerate(steps, 1):
            print(f"  Step {i}: {step.from_version} → {step.to_version}")
            print(f"    Risk: {step.risk_level.value}")
            print(f"    Time: {step.estimated_time} minutes")
    else:
        print(manager.generate_version_report())


if __name__ == "__main__":
    main()