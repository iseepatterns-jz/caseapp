# CDK Version Management System

A comprehensive system for managing AWS CDK versions, ensuring compatibility, and providing safe upgrade paths with automated testing and rollback capabilities.

## Overview

The CDK Version Management System addresses the challenges of maintaining CDK infrastructure code across different CDK versions by providing:

- **Version Tracking**: Monitor current and available CDK versions
- **Compatibility Monitoring**: Automated validation of CDK parameters and constructs
- **Upgrade Path Validation**: Safe upgrade planning with risk assessment
- **Automated Testing**: Comprehensive compatibility tests across CDK versions
- **Rollback Procedures**: Snapshot-based rollback for failed upgrades
- **CLI Interface**: Easy-to-use command-line tools for all operations

## Components

### 1. CDK Parameter Validator (`cdk_validator.py`)

Validates CDK parameters for compatibility with target CDK versions and provides suggestions for fixing incompatible parameters.

**Key Features:**

- Parameter compatibility checking for common CDK constructs
- Automated code scanning for compatibility issues
- Fix suggestions with specific remediation steps
- Support for ElastiCache, ECS, CloudWatch, and other AWS services

### 2. CDK Version Manager (`cdk_version_manager.py`)

Comprehensive version management including tracking, upgrade planning, and snapshot management.

**Key Features:**

- Current and available version detection
- Upgrade path creation with risk assessment
- Project state snapshots for rollback
- Configuration management
- Integration with npm registry for version information

### 3. CDK Compatibility Tests (`cdk_compatibility_tests.py`)

Automated testing framework for validating CDK construct compatibility across different versions.

**Key Features:**

- Predefined test cases for common CDK patterns
- Automated CDK synthesis testing
- Pytest integration for CI/CD pipelines
- Comprehensive test reporting

### 4. CLI Interface (`cdk_version_cli.py`)

Command-line interface providing easy access to all version management functionality.

**Key Features:**

- Status checking and compatibility validation
- Upgrade path planning and execution guidance
- Snapshot creation and rollback operations
- Test execution and reporting
- Configuration management

## Installation

1. **Install Dependencies:**

   ```bash
   pip install -r requirements-cdk-version.txt
   ```

2. **Verify CDK CLI Installation:**

   ```bash
   cdk --version
   ```

3. **Make CLI Executable:**
   ```bash
   chmod +x cdk_version_cli.py
   ```

## Quick Start

### 1. Check Current Status

```bash
python cdk_version_cli.py status
```

Output:

```
🔍 CDK Version Status
==============================
Current Version: 2.160.0
Compatibility: compatible
✅ No compatibility issues found
```

### 2. Check Compatibility with Target Version

```bash
python cdk_version_cli.py check 2.170.0 --show-issues
```

### 3. Plan an Upgrade

```bash
python cdk_version_cli.py upgrade 2.170.0 --show-steps
```

### 4. Create a Snapshot Before Upgrade

```bash
python cdk_version_cli.py snapshot "Before upgrading to 2.170.0"
```

### 5. Run Compatibility Tests

```bash
python cdk_version_cli.py test --save-results
```

### 6. Generate Comprehensive Report

```bash
python cdk_version_cli.py report --save
```

## Detailed Usage

### Version Status and Compatibility

**Check current status:**

```bash
python cdk_version_cli.py status --verbose
```

**Check compatibility with specific version:**

```bash
python cdk_version_cli.py check 2.160.0 --run-tests
```

**Show detailed compatibility issues:**

```bash
python cdk_version_cli.py check 2.160.0 --show-issues --verbose
```

### Upgrade Planning

**Show upgrade path:**

```bash
python cdk_version_cli.py upgrade 2.170.0
```

**Show detailed migration steps:**

```bash
python cdk_version_cli.py upgrade 2.170.0 --show-steps --verbose
```

### Snapshot Management

**Create snapshot:**

```bash
python cdk_version_cli.py snapshot "Pre-production deployment"
```

**List available snapshots:**

```bash
python cdk_version_cli.py snapshots
```

**Rollback to snapshot (dry run):**

```bash
python cdk_version_cli.py rollback 20240112_143022 --dry-run
```

**Perform actual rollback:**

```bash
python cdk_version_cli.py rollback 20240112_143022
```

### Testing

**Run all compatibility tests:**

```bash
python cdk_version_cli.py test
```

**Test specific CDK version:**

```bash
python cdk_version_cli.py test --version 2.160.0 --save-results
```

**Run tests with pytest:**

```bash
pytest cdk_compatibility_tests.py -v
```

### Configuration Management

**Show current configuration:**

```bash
python cdk_version_cli.py config --show
```

**Update configuration:**

```bash
python cdk_version_cli.py config --set "auto_upgrade=false"
python cdk_version_cli.py config --set "allowed_risk_levels=[\"low\",\"medium\"]"
```

## Configuration

The system uses a `.cdk-version-config.json` file for configuration:

```json
{
  "current_version": "2.160.0",
  "target_version": null,
  "auto_upgrade": false,
  "compatibility_check_interval": 24,
  "snapshot_retention_days": 30,
  "allowed_risk_levels": ["low", "medium"],
  "notification_settings": {
    "email": null,
    "slack_webhook": null
  },
  "test_configurations": []
}
```

### Configuration Options

- **current_version**: Currently installed CDK version
- **target_version**: Target version for upgrades (optional)
- **auto_upgrade**: Enable automatic upgrades (default: false)
- **compatibility_check_interval**: Hours between compatibility checks
- **snapshot_retention_days**: Days to keep snapshots
- **allowed_risk_levels**: Acceptable risk levels for upgrades
- **notification_settings**: Email/Slack notifications (future feature)

## Compatibility Rules

The system includes built-in compatibility rules for common CDK constructs:

### ElastiCache CfnCacheCluster

**Unsupported Parameters:**

- `at_rest_encryption_enabled` - Not supported in CfnCacheCluster
- `auth_token` - Use CfnReplicationGroup instead
- `transit_encryption_enabled` - Not supported with t3.micro instances

**Fix Suggestions:**

- Use `CfnReplicationGroup` for encryption features
- Use higher instance types for encryption support

### ECS ApplicationLoadBalancedFargateService

**Parameter Changes:**

- `deployment_configuration` → Use `min_healthy_percent` and `max_healthy_percent`

### CloudWatch LogQueryWidget

**Parameter Changes:**

- `log_groups` → Use `log_group_names` with string names

## Testing Framework

### Predefined Test Cases

The system includes comprehensive test cases for:

1. **ElastiCache Configurations**

   - Basic CfnCacheCluster setup
   - Invalid encryption parameters
   - Instance type compatibility

2. **ECS Service Patterns**

   - ApplicationLoadBalancedFargateService
   - Task definition configurations
   - Health check setups

3. **CloudWatch Components**

   - LogQueryWidget configurations
   - Dashboard widgets
   - Alarm configurations

4. **Security Groups**
   - Basic security group creation
   - Ingress/egress rule configurations
   - VPC integration

### Custom Test Cases

Add custom test cases by extending the `CompatibilityTestCase` class:

```python
from cdk_compatibility_tests import CompatibilityTestCase

custom_test = CompatibilityTestCase(
    name="my_custom_test",
    description="Test my custom CDK pattern",
    cdk_code="""
# Your CDK code here
""",
    expected_constructs=["AWS::S3::Bucket"],
    min_cdk_version="2.0.0",
    should_synthesize=True
)
```

## Integration with CI/CD

### GitHub Actions Integration

```yaml
name: CDK Version Management
on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  cdk-compatibility:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Setup Python
        uses: actions/setup-python@v4
        with:
          python-version: "3.9"

      - name: Install dependencies
        run: |
          pip install -r caseapp/infrastructure/requirements-cdk-version.txt

      - name: Run CDK compatibility tests
        run: |
          cd caseapp/infrastructure
          python cdk_version_cli.py test --save-results

      - name: Check compatibility with latest CDK
        run: |
          cd caseapp/infrastructure
          python cdk_version_cli.py check $(npm view aws-cdk-lib version) --run-tests
```

### Pre-commit Hooks

```yaml
# .pre-commit-config.yaml
repos:
  - repo: local
    hooks:
      - id: cdk-compatibility-check
        name: CDK Compatibility Check
        entry: python caseapp/infrastructure/cdk_version_cli.py
        args: [status]
        language: system
        pass_filenames: false
```

## Troubleshooting

### Common Issues

**1. CDK CLI Not Found**

```bash
# Install CDK CLI
npm install -g aws-cdk

# Verify installation
cdk --version
```

**2. Permission Errors**

```bash
# Make scripts executable
chmod +x cdk_version_cli.py
```

**3. Missing Dependencies**

```bash
# Install all dependencies
pip install -r requirements-cdk-version.txt
```

**4. Synthesis Failures**

```bash
# Check CDK project structure
cdk ls

# Validate CDK app
cdk synth --no-staging
```

### Debug Mode

Enable verbose output for debugging:

```bash
python cdk_version_cli.py status --verbose
python cdk_version_cli.py check 2.160.0 --verbose
```

### Log Files

The system creates log files in the project directory:

- `.cdk-version-config.json` - Configuration
- `.cdk-snapshots/` - Snapshot storage
- `cdk_compatibility_results_*.json` - Test results

## Best Practices

### 1. Regular Compatibility Checks

Run compatibility checks regularly:

```bash
# Weekly compatibility check
python cdk_version_cli.py status
python cdk_version_cli.py test
```

### 2. Snapshot Before Changes

Always create snapshots before major changes:

```bash
python cdk_version_cli.py snapshot "Before CDK upgrade to 2.170.0"
```

### 3. Test in Staging First

Test upgrades in staging environment:

```bash
# Check compatibility
python cdk_version_cli.py check 2.170.0 --run-tests

# Plan upgrade
python cdk_version_cli.py upgrade 2.170.0 --show-steps
```

### 4. Monitor Risk Levels

Configure appropriate risk tolerance:

```bash
python cdk_version_cli.py config --set "allowed_risk_levels=[\"low\"]"
```

### 5. Automate Testing

Integrate with CI/CD pipelines for automated testing.

## Advanced Features

### Custom Compatibility Rules

Extend the validator with custom rules:

```python
from cdk_validator import CompatibilityRule, CDKParameterValidator

# Add custom rule
custom_rule = CompatibilityRule(
    construct_type="MyCustomConstruct",
    unsupported_parameters=["old_parameter"],
    deprecated_parameters=["deprecated_parameter"],
    parameter_mappings={"old_parameter": "new_parameter"}
)

validator = CDKParameterValidator()
validator.compatibility_rules["MyCustomConstruct"] = custom_rule
```

### Automated Notifications

Configure notifications for compatibility issues:

```python
# In configuration
{
  "notification_settings": {
    "email": "devops@company.com",
    "slack_webhook": "https://hooks.slack.com/..."
  }
}
```

### Performance Monitoring

Track upgrade performance:

```python
# Monitor upgrade metrics
snapshot = manager.create_snapshot("Performance baseline")
# ... perform upgrade ...
new_snapshot = manager.create_snapshot("Post-upgrade metrics")
```

## Contributing

### Adding New Test Cases

1. Create test case in `cdk_compatibility_tests.py`
2. Add to the `_load_test_cases()` method
3. Test with `python cdk_version_cli.py test`

### Adding Compatibility Rules

1. Add rule to `cdk_validator.py`
2. Update `_load_compatibility_rules()` method
3. Test with sample CDK code

### Extending CLI Commands

1. Add command method to `CDKVersionCLI` class
2. Add argument parser in `main()` function
3. Test with `python cdk_version_cli.py <command>`

## Support

For issues and questions:

1. Check the troubleshooting section
2. Run with `--verbose` flag for detailed output
3. Review log files and error messages
4. Create GitHub issue with reproduction steps

## License

This CDK Version Management System is part of the Deployment Infrastructure Reliability project and follows the same licensing terms as the main project.
