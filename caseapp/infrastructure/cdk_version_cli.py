#!/usr/bin/env python3
"""
CDK Version Management CLI

Command-line interface for comprehensive CDK version management including
version tracking, compatibility monitoring, upgrade validation, and rollback procedures.
"""

import argparse
import sys
import json
from pathlib import Path
from datetime import datetime
from typing import Optional

from cdk_version_manager import CDKVersionManager, UpgradeRisk
from cdk_compatibility_tests import CDKCompatibilityTester


class CDKVersionCLI:
    """Command-line interface for CDK version management"""
    
    def __init__(self, project_root: str = "."):
        self.project_root = project_root
        self.manager = CDKVersionManager(project_root)
        self.tester = CDKCompatibilityTester()
    
    def cmd_status(self, args) -> int:
        """Show current CDK version status"""
        print("🔍 CDK Version Status")
        print("=" * 30)
        
        current_version = self.manager.get_current_cdk_version()
        print(f"Current Version: {current_version}")
        
        # Check compatibility
        status, issues = self.manager.check_version_compatibility(current_version)
        print(f"Compatibility: {status.value}")
        
        if issues:
            error_count = len([i for i in issues if i.severity.value == "error"])
            warning_count = len([i for i in issues if i.severity.value == "warning"])
            print(f"Issues: {error_count} errors, {warning_count} warnings")
            
            if args.verbose:
                print("\nIssues:")
                for issue in issues[:5]:  # Show first 5
                    print(f"  {issue.severity.value.upper()}: {issue.message}")
                if len(issues) > 5:
                    print(f"  ... and {len(issues) - 5} more")
        else:
            print("✅ No compatibility issues found")
        
        return 0
    
    def cmd_check(self, args) -> int:
        """Check compatibility with a specific CDK version"""
        target_version = args.version
        print(f"🔍 Checking compatibility with CDK {target_version}")
        print("=" * 50)
        
        status, issues = self.manager.check_version_compatibility(target_version)
        print(f"Compatibility Status: {status.value}")
        
        if issues:
            error_count = len([i for i in issues if i.severity.value == "error"])
            warning_count = len([i for i in issues if i.severity.value == "warning"])
            print(f"Issues Found: {error_count} errors, {warning_count} warnings")
            
            if args.show_issues or args.verbose:
                print("\nDetailed Issues:")
                for issue in issues:
                    severity_icon = "🔴" if issue.severity.value == "error" else "🟡"
                    print(f"{severity_icon} {issue.construct_type}.{issue.parameter}")
                    print(f"   {issue.message}")
                    if issue.suggestion:
                        print(f"   💡 {issue.suggestion}")
                    print()
        else:
            print("✅ No compatibility issues found")
        
        # Run compatibility tests if requested
        if args.run_tests:
            print("\n🧪 Running compatibility tests...")
            results = self.tester.run_all_tests(target_version)
            
            total = results['total_tests']
            passed = results['passed_tests']
            success_rate = (passed / total * 100) if total > 0 else 0
            
            print(f"Test Results: {passed}/{total} passed ({success_rate:.1f}%)")
            
            if args.verbose:
                for test_result in results['test_results']:
                    status_icon = "✅" if test_result['success'] else "❌"
                    print(f"  {status_icon} {test_result['test_name']}")
        
        return 0 if status.value in ["compatible", "deprecated"] else 1
    
    def cmd_upgrade(self, args) -> int:
        """Show upgrade path to a target version"""
        target_version = args.version
        print(f"🚀 Upgrade Path to CDK {target_version}")
        print("=" * 40)
        
        current_version = self.manager.get_current_cdk_version()
        print(f"Current Version: {current_version}")
        print(f"Target Version: {target_version}")
        print()
        
        # Check if upgrade is needed
        import semver
        if semver.compare(current_version, target_version) >= 0:
            print("✅ Already at or above target version")
            return 0
        
        # Get upgrade path
        steps = self.manager.create_upgrade_path(target_version)
        
        if not steps:
            print("❌ No upgrade path available")
            return 1
        
        for i, step in enumerate(steps, 1):
            risk_icon = {
                UpgradeRisk.LOW: "🟢",
                UpgradeRisk.MEDIUM: "🟡", 
                UpgradeRisk.HIGH: "🟠",
                UpgradeRisk.CRITICAL: "🔴"
            }.get(step.risk_level, "❓")
            
            print(f"Step {i}: {step.from_version} → {step.to_version}")
            print(f"  Risk Level: {risk_icon} {step.risk_level.value}")
            print(f"  Estimated Time: {step.estimated_time} minutes")
            print()
            
            if step.breaking_changes and args.verbose:
                print("  Breaking Changes:")
                for change in step.breaking_changes:
                    print(f"    • {change}")
                print()
            
            if args.show_steps or args.verbose:
                print("  Migration Steps:")
                for j, migration_step in enumerate(step.migration_steps, 1):
                    print(f"    {j}. {migration_step}")
                print()
        
        # Check if upgrade is safe based on risk tolerance
        max_risk = max(step.risk_level for step in steps)
        allowed_risks = [UpgradeRisk[r.upper()] for r in self.manager.config.get("allowed_risk_levels", ["low", "medium"])]
        
        if max_risk not in allowed_risks:
            print(f"⚠️  Warning: Upgrade risk ({max_risk.value}) exceeds configured tolerance")
            print("   Consider reviewing breaking changes and testing thoroughly")
        
        return 0
    
    def cmd_snapshot(self, args) -> int:
        """Create a snapshot of current state"""
        description = args.description or f"Manual snapshot created at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        
        print("📸 Creating snapshot...")
        snapshot_id = self.manager.create_snapshot(description)
        print(f"✅ Snapshot created: {snapshot_id}")
        print(f"   Description: {description}")
        
        return 0
    
    def cmd_rollback(self, args) -> int:
        """Rollback to a previous snapshot"""
        snapshot_id = args.snapshot_id
        
        print(f"⏪ Rolling back to snapshot {snapshot_id}...")
        
        if args.dry_run:
            print("🔍 Dry run mode - no changes will be made")
            # Show what would be done
            snapshot_file = self.manager.snapshots_dir / f"snapshot_{snapshot_id}.json"
            if snapshot_file.exists():
                with open(snapshot_file, 'r') as f:
                    snapshot_data = json.load(f)
                target_version = snapshot_data["snapshot"]["cdk_version"]
                print(f"   Would rollback to CDK version: {target_version}")
                print(f"   Snapshot description: {snapshot_data.get('description', 'No description')}")
            else:
                print(f"❌ Snapshot {snapshot_id} not found")
                return 1
        else:
            success = self.manager.rollback_to_snapshot(snapshot_id)
            if success:
                print("✅ Rollback completed successfully")
            else:
                print("❌ Rollback failed")
                return 1
        
        return 0
    
    def cmd_test(self, args) -> int:
        """Run compatibility tests"""
        cdk_version = args.version or self.manager.get_current_cdk_version()
        
        print(f"🧪 Running CDK compatibility tests for version {cdk_version}")
        print("=" * 60)
        
        results = self.tester.run_all_tests(cdk_version)
        
        # Generate and display report
        report = self.tester.generate_test_report(results)
        print(report)
        
        # Save results if requested
        if args.save_results:
            results_file = Path(f"cdk_compatibility_results_{cdk_version.replace('.', '_')}.json")
            with open(results_file, 'w') as f:
                json.dump(results, f, indent=2)
            print(f"\n💾 Results saved to {results_file}")
        
        # Return non-zero if tests failed
        return 0 if results['failed_tests'] == 0 else 1
    
    def cmd_report(self, args) -> int:
        """Generate comprehensive version management report"""
        print("📊 Generating CDK Version Management Report...")
        print()
        
        report = self.manager.generate_version_report()
        print(report)
        
        # Save report if requested
        if args.save:
            report_file = Path(f"cdk_version_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt")
            with open(report_file, 'w') as f:
                f.write(report)
            print(f"\n💾 Report saved to {report_file}")
        
        return 0
    
    def cmd_config(self, args) -> int:
        """Manage configuration"""
        if args.show:
            print("⚙️  Current Configuration:")
            print(json.dumps(self.manager.config, indent=2, default=str))
        
        if args.set:
            key, value = args.set.split('=', 1)
            # Try to parse value as JSON, fallback to string
            try:
                parsed_value = json.loads(value)
            except:
                parsed_value = value
            
            self.manager.config[key] = parsed_value
            self.manager._save_config()
            print(f"✅ Set {key} = {parsed_value}")
        
        return 0
    
    def cmd_snapshots(self, args) -> int:
        """List available snapshots"""
        snapshots = list(self.manager.snapshots_dir.glob("snapshot_*.json"))
        
        if not snapshots:
            print("📸 No snapshots found")
            return 0
        
        print(f"📸 Available Snapshots ({len(snapshots)} total):")
        print("=" * 50)
        
        # Sort by timestamp (newest first)
        snapshots.sort(reverse=True)
        
        for snapshot_file in snapshots:
            try:
                with open(snapshot_file, 'r') as f:
                    snapshot_data = json.load(f)
                
                snapshot_id = snapshot_file.stem.split("_", 1)[1]
                cdk_version = snapshot_data["snapshot"]["cdk_version"]
                description = snapshot_data.get("description", "No description")
                timestamp = snapshot_data["snapshot"]["timestamp"]
                
                print(f"📸 {snapshot_id}")
                print(f"   CDK Version: {cdk_version}")
                print(f"   Created: {timestamp}")
                print(f"   Description: {description}")
                print()
            
            except Exception as e:
                print(f"❌ Error reading snapshot {snapshot_file.name}: {e}")
        
        return 0


def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(
        description="CDK Version Management CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s status                          # Show current status
  %(prog)s check 2.160.0                   # Check compatibility with version
  %(prog)s upgrade 2.160.0 --show-steps   # Show upgrade path
  %(prog)s snapshot "Before upgrade"       # Create snapshot
  %(prog)s test --save-results             # Run compatibility tests
  %(prog)s rollback 20240112_143022        # Rollback to snapshot
  %(prog)s report --save                   # Generate full report
        """
    )
    
    parser.add_argument("--project-root", default=".", help="Project root directory")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # Status command
    status_parser = subparsers.add_parser("status", help="Show current CDK version status")
    status_parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    
    # Check command
    check_parser = subparsers.add_parser("check", help="Check compatibility with CDK version")
    check_parser.add_argument("version", help="CDK version to check")
    check_parser.add_argument("--show-issues", action="store_true", help="Show detailed issues")
    check_parser.add_argument("--run-tests", action="store_true", help="Run compatibility tests")
    
    # Upgrade command
    upgrade_parser = subparsers.add_parser("upgrade", help="Show upgrade path to version")
    upgrade_parser.add_argument("version", help="Target CDK version")
    upgrade_parser.add_argument("--show-steps", action="store_true", help="Show detailed migration steps")
    
    # Snapshot command
    snapshot_parser = subparsers.add_parser("snapshot", help="Create snapshot of current state")
    snapshot_parser.add_argument("description", nargs="?", help="Snapshot description")
    
    # Rollback command
    rollback_parser = subparsers.add_parser("rollback", help="Rollback to snapshot")
    rollback_parser.add_argument("snapshot_id", help="Snapshot ID to rollback to")
    rollback_parser.add_argument("--dry-run", action="store_true", help="Show what would be done")
    
    # Test command
    test_parser = subparsers.add_parser("test", help="Run compatibility tests")
    test_parser.add_argument("--version", help="CDK version to test (default: current)")
    test_parser.add_argument("--save-results", action="store_true", help="Save test results to file")
    
    # Report command
    report_parser = subparsers.add_parser("report", help="Generate comprehensive report")
    report_parser.add_argument("--save", action="store_true", help="Save report to file")
    
    # Config command
    config_parser = subparsers.add_parser("config", help="Manage configuration")
    config_parser.add_argument("--show", action="store_true", help="Show current configuration")
    config_parser.add_argument("--set", help="Set configuration value (key=value)")
    
    # Snapshots command
    snapshots_parser = subparsers.add_parser("snapshots", help="List available snapshots")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 1
    
    # Create CLI instance
    cli = CDKVersionCLI(args.project_root)
    
    # Execute command
    try:
        command_method = getattr(cli, f"cmd_{args.command}")
        return command_method(args)
    except AttributeError:
        print(f"❌ Unknown command: {args.command}")
        return 1
    except KeyboardInterrupt:
        print("\n⚠️  Operation cancelled by user")
        return 130
    except Exception as e:
        print(f"❌ Error: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())