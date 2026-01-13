#!/usr/bin/env python3
"""
CDK Parameter Validation Service

This module provides validation for CDK parameters to ensure compatibility
with the target CDK version and prevent deployment failures due to
unsupported parameters.
"""

import json
import re
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from enum import Enum


class ValidationSeverity(Enum):
    """Severity levels for validation issues"""
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


@dataclass
class ValidationIssue:
    """Represents a validation issue found in CDK code"""
    severity: ValidationSeverity
    construct_type: str
    parameter: str
    message: str
    suggestion: Optional[str] = None
    line_number: Optional[int] = None


@dataclass
class CompatibilityRule:
    """Represents a compatibility rule for CDK constructs"""
    construct_type: str
    unsupported_parameters: List[str]
    deprecated_parameters: List[str]
    parameter_mappings: Dict[str, str]  # old_param -> new_param
    min_cdk_version: Optional[str] = None
    max_cdk_version: Optional[str] = None


class CDKParameterValidator:
    """
    CDK Parameter Validation Service
    
    Validates CDK parameters for compatibility with target CDK versions
    and provides suggestions for fixing incompatible parameters.
    """
    
    def __init__(self, cdk_version: str = "2.160.0"):
        self.cdk_version = cdk_version
        self.compatibility_rules = self._load_compatibility_rules()
        
    def _load_compatibility_rules(self) -> Dict[str, CompatibilityRule]:
        """Load compatibility rules for different CDK constructs"""
        rules = {
            "CfnCacheCluster": CompatibilityRule(
                construct_type="CfnCacheCluster",
                unsupported_parameters=[
                    "at_rest_encryption_enabled",  # Not supported in CfnCacheCluster
                    "auth_token",  # Not supported in CfnCacheCluster, use CfnReplicationGroup
                    "transit_encryption_enabled",  # Not supported with t3.micro instances
                ],
                deprecated_parameters=[],
                parameter_mappings={},
                min_cdk_version="2.0.0"
            ),
            "ApplicationLoadBalancedFargateService": CompatibilityRule(
                construct_type="ApplicationLoadBalancedFargateService",
                unsupported_parameters=[
                    "deployment_configuration",  # Use min_healthy_percent and max_healthy_percent
                ],
                deprecated_parameters=[],
                parameter_mappings={
                    "deployment_configuration": "min_healthy_percent, max_healthy_percent"
                },
                min_cdk_version="2.0.0"
            ),
            "LogQueryWidget": CompatibilityRule(
                construct_type="LogQueryWidget",
                unsupported_parameters=[
                    "log_groups",  # Use log_group_names instead
                ],
                deprecated_parameters=[],
                parameter_mappings={
                    "log_groups": "log_group_names"
                },
                min_cdk_version="2.0.0"
            ),
            "SnsAction": CompatibilityRule(
                construct_type="SnsAction",
                unsupported_parameters=[],
                deprecated_parameters=[],
                parameter_mappings={},
                min_cdk_version="2.0.0"
            )
        }
        return rules
    
    def validate_parameters(self, construct_type: str, parameters: Dict[str, Any]) -> List[ValidationIssue]:
        """
        Validate parameters for a specific CDK construct type
        
        Args:
            construct_type: The CDK construct type (e.g., 'CfnCacheCluster')
            parameters: Dictionary of parameters to validate
            
        Returns:
            List of validation issues found
        """
        issues = []
        
        if construct_type not in self.compatibility_rules:
            issues.append(ValidationIssue(
                severity=ValidationSeverity.INFO,
                construct_type=construct_type,
                parameter="",
                message=f"No compatibility rules defined for {construct_type}",
                suggestion="Consider adding compatibility rules for this construct type"
            ))
            return issues
        
        rule = self.compatibility_rules[construct_type]
        
        # Check for unsupported parameters
        for param in parameters.keys():
            if param in rule.unsupported_parameters:
                suggestion = None
                if param in rule.parameter_mappings:
                    suggestion = f"Use '{rule.parameter_mappings[param]}' instead"
                
                issues.append(ValidationIssue(
                    severity=ValidationSeverity.ERROR,
                    construct_type=construct_type,
                    parameter=param,
                    message=f"Parameter '{param}' is not supported in {construct_type}",
                    suggestion=suggestion
                ))
            
            elif param in rule.deprecated_parameters:
                suggestion = None
                if param in rule.parameter_mappings:
                    suggestion = f"Use '{rule.parameter_mappings[param]}' instead"
                
                issues.append(ValidationIssue(
                    severity=ValidationSeverity.WARNING,
                    construct_type=construct_type,
                    parameter=param,
                    message=f"Parameter '{param}' is deprecated in {construct_type}",
                    suggestion=suggestion
                ))
        
        return issues
    
    def validate_code_file(self, file_path: str) -> List[ValidationIssue]:
        """
        Validate a Python CDK code file for compatibility issues
        
        Args:
            file_path: Path to the Python file to validate
            
        Returns:
            List of validation issues found
        """
        issues = []
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                lines = content.split('\n')
            
            # Parse CDK construct usage patterns
            construct_patterns = {
                r'elasticache\.CfnCacheCluster\s*\(': 'CfnCacheCluster',
                r'ecs_patterns\.ApplicationLoadBalancedFargateService\s*\(': 'ApplicationLoadBalancedFargateService',
                r'cloudwatch\.LogQueryWidget\s*\(': 'LogQueryWidget',
                r'cloudwatch\.SnsAction\s*\(': 'SnsAction',
            }
            
            for line_num, line in enumerate(lines, 1):
                for pattern, construct_type in construct_patterns.items():
                    if re.search(pattern, line):
                        # Extract parameters from the construct call
                        params = self._extract_parameters_from_line(line, lines, line_num - 1)
                        validation_issues = self.validate_parameters(construct_type, params)
                        
                        # Add line numbers to issues
                        for issue in validation_issues:
                            issue.line_number = line_num
                            issues.append(issue)
        
        except Exception as e:
            issues.append(ValidationIssue(
                severity=ValidationSeverity.ERROR,
                construct_type="FileValidation",
                parameter="",
                message=f"Error reading file {file_path}: {str(e)}",
                suggestion="Check file permissions and encoding"
            ))
        
        return issues
    
    def _extract_parameters_from_line(self, line: str, all_lines: List[str], start_line: int) -> Dict[str, Any]:
        """
        Extract parameters from a CDK construct call
        
        This is a simplified parameter extraction that looks for common patterns.
        A more sophisticated implementation would use AST parsing.
        """
        params = {}
        
        # Look for parameter patterns in the current line and following lines
        param_patterns = [
            r'at_rest_encryption_enabled\s*=\s*True',
            r'auth_token\s*=\s*["\'][^"\']*["\']',
            r'transit_encryption_enabled\s*=\s*True',
            r'deployment_configuration\s*=\s*ecs\.DeploymentConfiguration',
            r'log_groups\s*=\s*\[',
            r'cloudwatch\.SnsAction',
        ]
        
        # Check current line and next few lines for parameters
        for i in range(start_line, min(start_line + 20, len(all_lines))):
            if i >= len(all_lines):
                break
                
            check_line = all_lines[i]
            
            for pattern in param_patterns:
                if re.search(pattern, check_line):
                    # Extract parameter name
                    if 'at_rest_encryption_enabled' in check_line:
                        params['at_rest_encryption_enabled'] = True
                    elif 'auth_token' in check_line:
                        params['auth_token'] = "token_value"
                    elif 'transit_encryption_enabled' in check_line:
                        params['transit_encryption_enabled'] = True
                    elif 'deployment_configuration' in check_line:
                        params['deployment_configuration'] = "DeploymentConfiguration"
                    elif 'log_groups' in check_line:
                        params['log_groups'] = []
                    elif 'cloudwatch.SnsAction' in check_line:
                        # This indicates incorrect import usage
                        params['_incorrect_sns_import'] = True
        
        return params
    
    def generate_fix_suggestions(self, issues: List[ValidationIssue]) -> Dict[str, str]:
        """
        Generate specific fix suggestions for validation issues
        
        Args:
            issues: List of validation issues
            
        Returns:
            Dictionary mapping issue descriptions to fix suggestions
        """
        fixes = {}
        
        for issue in issues:
            key = f"{issue.construct_type}.{issue.parameter}"
            
            if issue.construct_type == "CfnCacheCluster":
                if issue.parameter == "at_rest_encryption_enabled":
                    fixes[key] = (
                        "Remove the 'at_rest_encryption_enabled' parameter. "
                        "For encryption at rest, consider using CfnReplicationGroup instead of CfnCacheCluster."
                    )
                elif issue.parameter == "auth_token":
                    fixes[key] = (
                        "Remove the 'auth_token' parameter. "
                        "For authentication, use CfnReplicationGroup which supports auth tokens."
                    )
                elif issue.parameter == "transit_encryption_enabled":
                    fixes[key] = (
                        "Remove the 'transit_encryption_enabled' parameter. "
                        "Transit encryption is not supported with t3.micro instances in CfnCacheCluster. "
                        "Use CfnReplicationGroup or higher instance types for encryption features."
                    )
            
            elif issue.construct_type == "ApplicationLoadBalancedFargateService":
                if issue.parameter == "deployment_configuration":
                    fixes[key] = (
                        "Replace 'deployment_configuration=ecs.DeploymentConfiguration(...)' with "
                        "'min_healthy_percent=50, max_healthy_percent=200' (adjust values as needed)."
                    )
            
            elif issue.construct_type == "LogQueryWidget":
                if issue.parameter == "log_groups":
                    fixes[key] = (
                        "Replace 'log_groups=[LogGroup.from_log_group_name(...)]' with "
                        "'log_group_names=[\"/log/group/name\"]' using string names instead of LogGroup objects."
                    )
            
            elif issue.construct_type == "SnsAction":
                if issue.parameter == "_incorrect_sns_import":
                    fixes[key] = (
                        "Change 'cloudwatch.SnsAction' to 'cw_actions.SnsAction' and add "
                        "'aws_cloudwatch_actions as cw_actions' to your imports."
                    )
        
        return fixes
    
    def create_compatibility_report(self, file_path: str) -> str:
        """
        Create a comprehensive compatibility report for a CDK file
        
        Args:
            file_path: Path to the CDK file to analyze
            
        Returns:
            Formatted compatibility report as string
        """
        issues = self.validate_code_file(file_path)
        fixes = self.generate_fix_suggestions(issues)
        
        report = []
        report.append(f"CDK Compatibility Report for {file_path}")
        report.append("=" * 60)
        report.append(f"CDK Version: {self.cdk_version}")
        report.append("")
        
        if not issues:
            report.append("✅ No compatibility issues found!")
            return "\n".join(report)
        
        # Group issues by severity
        errors = [i for i in issues if i.severity == ValidationSeverity.ERROR]
        warnings = [i for i in issues if i.severity == ValidationSeverity.WARNING]
        info = [i for i in issues if i.severity == ValidationSeverity.INFO]
        
        report.append(f"Summary: {len(errors)} errors, {len(warnings)} warnings, {len(info)} info")
        report.append("")
        
        # Report errors
        if errors:
            report.append("🔴 ERRORS (must fix):")
            for issue in errors:
                report.append(f"  Line {issue.line_number or '?'}: {issue.construct_type}.{issue.parameter}")
                report.append(f"    {issue.message}")
                if issue.suggestion:
                    report.append(f"    💡 {issue.suggestion}")
                
                fix_key = f"{issue.construct_type}.{issue.parameter}"
                if fix_key in fixes:
                    report.append(f"    🔧 Fix: {fixes[fix_key]}")
                report.append("")
        
        # Report warnings
        if warnings:
            report.append("🟡 WARNINGS (should fix):")
            for issue in warnings:
                report.append(f"  Line {issue.line_number or '?'}: {issue.construct_type}.{issue.parameter}")
                report.append(f"    {issue.message}")
                if issue.suggestion:
                    report.append(f"    💡 {issue.suggestion}")
                report.append("")
        
        # Report info
        if info:
            report.append("ℹ️  INFO:")
            for issue in info:
                report.append(f"  {issue.construct_type}: {issue.message}")
                if issue.suggestion:
                    report.append(f"    💡 {issue.suggestion}")
                report.append("")
        
        return "\n".join(report)


def main():
    """Main function for command-line usage"""
    import sys
    
    if len(sys.argv) != 2:
        print("Usage: python cdk_validator.py <path_to_cdk_file>")
        sys.exit(1)
    
    file_path = sys.argv[1]
    validator = CDKParameterValidator()
    report = validator.create_compatibility_report(file_path)
    print(report)


if __name__ == "__main__":
    main()