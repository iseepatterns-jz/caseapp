# Design Document: Deployment Infrastructure Reliability

## Overview

This design enhances the deployment infrastructure to provide better concurrent deployment handling, improved visibility, and automated recovery mechanisms. The solution focuses on making the CI/CD pipeline more resilient and user-friendly while maintaining safety guarantees against concurrent deployments.

## Architecture

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     GitHub Actions Workflow                      │
│  ┌────────────┐  ┌──────────────┐  ┌────────────────────────┐  │
│  │   Build    │→ │  Validation  │→ │  Deployment Monitor    │  │
│  │   & Test   │  │   Gateway    │  │  (Background Process)  │  │
│  └────────────┘  └──────────────┘  └────────────────────────┘  │
│                          ↓                      ↓                │
│                  ┌───────────────┐      ┌──────────────┐        │
│                  │  Deployment   │      │    Slack     │        │
│                  │  Coordinator  │      │  Notifier    │        │
│                  └───────────────┘      └──────────────┘        │
└─────────────────────────────────────────────────────────────────┘
                           ↓                      ↓
┌─────────────────────────────────────────────────────────────────┐
│                      AWS Infrastructure                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐  │
│  │ CloudFormation│  │  DynamoDB    │  │   CloudWatch Logs   │  │
│  │     Stack     │  │  Registry    │  │  (Correlation IDs)  │  │
│  └──────────────┘  └──────────────┘  └──────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

### Component Interactions

1. **Validation Gateway**: First line of defense, checks for active deployments
2. **Deployment Coordinator**: Manages deployment state and queuing
3. **Deployment Monitor**: Background process that tracks deployment progress
4. **Slack Notifier**: Sends real-time updates to Slack channels
5. **Deployment Registry**: DynamoDB table tracking active deployments

## Components and Interfaces

### 1. Enhanced Validation Script

**File**: `caseapp/scripts/enhanced-deployment-validation.sh`

**Enhancements**:

- Add detailed deployment status reporting
- Include stack event history in error messages
- Provide estimated completion time for active deployments
- Add AWS Console links for monitoring

**New Functions**:

```bash
# Get detailed deployment status
get_deployment_status() {
    local stack_name="$1"
    local status=$(aws cloudformation describe-stacks ...)
    local events=$(aws cloudformation describe-stack-events ...)
    local start_time=$(...)
    local elapsed=$(...)

    # Return structured status information
    echo "Status: $status"
    echo "Started: $start_time"
    echo "Elapsed: $elapsed"
    echo "Recent Events: $events"
}

# Estimate deployment completion time
estimate_completion_time() {
    local stack_name="$1"
    local current_status="$2"

    # Based on historical data and current progress
    # Return estimated minutes remaining
}

# Generate AWS Console link
get_console_link() {
    local stack_name="$1"
    local region="$2"
    echo "https://console.aws.amazon.com/cloudformation/home?region=$region#/stacks/stackinfo?stackId=$stack_name"
}
```

### 2. Deployment Coordinator

**File**: `caseapp/scripts/deployment-coordinator.sh`

**Purpose**: Manages deployment queuing and coordination

**Functions**:

```bash
# Register a deployment attempt
register_deployment() {
    local correlation_id="$1"
    local workflow_run_id="$2"
    local environment="$3"

    # Store in DynamoDB or local state file
    # Include: timestamp, correlation_id, workflow_run_id, status
}

# Check if deployment can proceed
can_deploy() {
    local environment="$1"

    # Check CloudFormation stack status
    # Check deployment registry
    # Return: true/false with reason
}

# Wait for active deployment to complete
wait_for_deployment() {
    local max_wait_minutes="$1"
    local check_interval_seconds="$2"

    # Poll stack status
    # Send periodic updates
    # Return when deployment completes or timeout
}

# Clean up deployment registration
cleanup_deployment() {
    local correlation_id="$1"
    # Remove from registry
}
```

### 3. Deployment Monitor

**File**: `caseapp/scripts/deployment-monitor.sh`

**Purpose**: Background process that monitors active deployments

**Features**:

- Runs as background process during deployment
- Monitors CloudFormation stack events
- Detects stalled deployments
- Sends Slack notifications
- Logs all events with correlation IDs

**Implementation**:

```bash
#!/bin/bash
# Deployment Monitor - runs in background

CORRELATION_ID="$1"
STACK_NAME="$2"
SLACK_CHANNEL="$3"
LOG_FILE="$4"

monitor_deployment() {
    local last_event_time=""
    local stall_threshold=600  # 10 minutes

    while true; do
        # Get current stack status
        status=$(aws cloudformation describe-stacks ...)

        # Check if deployment is complete
        if [[ "$status" =~ (CREATE_COMPLETE|UPDATE_COMPLETE|ROLLBACK_COMPLETE) ]]; then
            send_slack_notification "✅ Deployment complete: $status"
            break
        fi

        # Check if deployment failed
        if [[ "$status" =~ (CREATE_FAILED|UPDATE_FAILED|ROLLBACK_FAILED) ]]; then
            send_slack_notification "❌ Deployment failed: $status"
            break
        fi

        # Get recent events
        events=$(aws cloudformation describe-stack-events ...)

        # Check for stalled deployment
        if [ -n "$last_event_time" ]; then
            time_since_last_event=$(calculate_elapsed "$last_event_time")
            if [ $time_since_last_event -gt $stall_threshold ]; then
                send_slack_notification "⚠️ Deployment may be stalled - no events for ${time_since_last_event}s"
            fi
        fi

        # Log events
        echo "[$CORRELATION_ID] Status: $status" >> "$LOG_FILE"

        # Wait before next check
        sleep 30
    done
}

monitor_deployment
```

### 4. Slack Notifier

**File**: `caseapp/scripts/slack-notifier.sh`

**Purpose**: Centralized Slack notification handling

**Functions**:

```bash
# Send deployment start notification
notify_deployment_start() {
    local correlation_id="$1"
    local environment="$2"
    local workflow_run_id="$3"

    mcp_slack_conversations_add_message \
      --channel_id="#kiro-updates" \
      --payload="🚀 Deployment Started
Environment: $environment
Correlation ID: $correlation_id
Workflow: https://github.com/owner/repo/actions/runs/$workflow_run_id"
}

# Send concurrent deployment detected notification
notify_concurrent_deployment() {
    local active_correlation_id="$1"
    local active_start_time="$2"
    local estimated_completion="$3"

    mcp_slack_conversations_add_message \
      --channel_id="#kiro-updates" \
      --payload="⏸️ Deployment Queued
An active deployment is in progress:
- Correlation ID: $active_correlation_id
- Started: $active_start_time
- Estimated completion: $estimated_completion minutes
Your deployment will proceed when the active deployment completes."
}

# Send deployment progress update
notify_deployment_progress() {
    local correlation_id="$1"
    local progress_message="$2"

    mcp_slack_conversations_add_message \
      --channel_id="#kiro-updates" \
      --payload="⏳ Deployment Progress [$correlation_id]
$progress_message"
}

# Send deployment complete notification
notify_deployment_complete() {
    local correlation_id="$1"
    local environment="$2"
    local duration="$3"
    local alb_dns="$4"

    mcp_slack_conversations_add_message \
      --channel_id="#kiro-updates" \
      --payload="✅ Deployment Complete
Environment: $environment
Correlation ID: $correlation_id
Duration: $duration minutes
Application URL: http://$alb_dns"
}

# Send deployment failed notification
notify_deployment_failed() {
    local correlation_id="$1"
    local environment="$2"
    local error_message="$3"
    local console_link="$4"

    mcp_slack_conversations_add_message \
      --channel_id="#kiro-updates" \
      --payload="❌ Deployment Failed
Environment: $environment
Correlation ID: $correlation_id
Error: $error_message
AWS Console: $console_link"
}
```

### 5. GitHub Actions Workflow Updates

**File**: `.github/workflows/ci-cd.yml`

**Changes to deploy-production job**:

```yaml
- name: Run comprehensive pre-deployment validation with coordination
  working-directory: caseapp
  run: |
    echo "🔍 Running pre-deployment validation with coordination..."

    # Generate correlation ID
    export CORRELATION_ID="$(date +%Y%m%d-%H%M%S)-$(openssl rand -hex 4)"
    export WORKFLOW_RUN_ID="${{ github.run_id }}"
    export ENVIRONMENT="production"

    # Make scripts executable
    chmod +x scripts/enhanced-deployment-validation.sh
    chmod +x scripts/deployment-coordinator.sh
    chmod +x scripts/slack-notifier.sh

    # Send deployment start notification
    ./scripts/slack-notifier.sh start "$CORRELATION_ID" "$ENVIRONMENT" "$WORKFLOW_RUN_ID"

    # Check if deployment can proceed
    if ./scripts/deployment-coordinator.sh can_deploy "$ENVIRONMENT"; then
      echo "✅ No active deployment detected - proceeding"
      
      # Register this deployment
      ./scripts/deployment-coordinator.sh register "$CORRELATION_ID" "$WORKFLOW_RUN_ID" "$ENVIRONMENT"
      
      # Run validation
      ./scripts/enhanced-deployment-validation.sh
    else
      echo "⏸️ Active deployment detected - checking coordination options"
      
      # Get active deployment details
      active_deployment=$(./scripts/deployment-coordinator.sh get_active "$ENVIRONMENT")
      
      # Send notification about concurrent deployment
      ./scripts/slack-notifier.sh concurrent "$active_deployment"
      
      # Wait for active deployment with timeout
      if ./scripts/deployment-coordinator.sh wait "$ENVIRONMENT" 30; then
        echo "✅ Active deployment completed - proceeding"
        ./scripts/deployment-coordinator.sh register "$CORRELATION_ID" "$WORKFLOW_RUN_ID" "$ENVIRONMENT"
        ./scripts/enhanced-deployment-validation.sh
      else
        echo "❌ Timeout waiting for active deployment"
        ./scripts/slack-notifier.sh timeout "$CORRELATION_ID"
        exit 1
      fi
    fi
  timeout-minutes: 40

- name: Deploy with monitoring
  working-directory: caseapp
  run: |
    echo "🚀 Starting deployment with active monitoring..."

    # Start deployment monitor in background
    ./scripts/deployment-monitor.sh \
      "$CORRELATION_ID" \
      "CourtCaseManagementStack" \
      "#kiro-updates" \
      "deployment-monitor.log" &

    MONITOR_PID=$!

    # Run deployment
    ./scripts/deploy-with-validation.sh

    # Wait for monitor to complete
    wait $MONITOR_PID

    # Cleanup deployment registration
    ./scripts/deployment-coordinator.sh cleanup "$CORRELATION_ID"
  timeout-minutes: 90
```

## Data Models

### Deployment Registry Entry

**Storage**: DynamoDB table or local state file

```json
{
  "correlation_id": "20260114-215432-375a1384",
  "workflow_run_id": "21010944613",
  "environment": "production",
  "stack_name": "CourtCaseManagementStack",
  "status": "IN_PROGRESS",
  "started_at": "2026-01-14T21:54:32Z",
  "updated_at": "2026-01-14T22:04:18Z",
  "github_run_url": "https://github.com/owner/repo/actions/runs/21010944613",
  "aws_console_url": "https://console.aws.amazon.com/cloudformation/...",
  "events": [
    {
      "timestamp": "2026-01-14T21:54:32Z",
      "event": "DEPLOYMENT_STARTED",
      "details": "Validation passed, starting deployment"
    },
    {
      "timestamp": "2026-01-14T21:58:00Z",
      "event": "ECS_SERVICE_CREATED",
      "details": "ECS service created successfully"
    }
  ]
}
```

### Deployment Status Response

```json
{
  "can_deploy": false,
  "reason": "ACTIVE_DEPLOYMENT_IN_PROGRESS",
  "active_deployment": {
    "correlation_id": "20260114-215432-375a1384",
    "started_at": "2026-01-14T21:54:32Z",
    "elapsed_minutes": 10,
    "estimated_remaining_minutes": 15,
    "current_status": "CREATE_IN_PROGRESS",
    "recent_events": [
      "ElastiCache cluster: CREATE_COMPLETE",
      "ECS Service: CREATE_COMPLETE",
      "RDS Instance: CREATE_IN_PROGRESS"
    ]
  }
}
```

## Correctness Properties

_A property is a characteristic or behavior that should hold true across all valid executions of a system—essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees._

### Property 1: Deployment Exclusivity

_For any_ environment (staging or production), at most one deployment can be in an active state (CREATE_IN_PROGRESS, UPDATE_IN_PROGRESS, ROLLBACK_IN_PROGRESS) at any given time.

**Validates: Requirements 1.1, 1.4**

### Property 2: Correlation ID Uniqueness

_For any_ deployment attempt, the generated correlation ID must be unique across all deployments in the system.

**Validates: Requirements 8.1**

### Property 3: Notification Completeness

_For any_ deployment lifecycle (start, progress, complete/fail), all corresponding Slack notifications must be sent to the appropriate channels.

**Validates: Requirements 5.1, 5.3, 5.4**

### Property 4: Deployment State Consistency

_For any_ deployment registration, the recorded state in the deployment registry must match the actual CloudFormation stack status.

**Validates: Requirements 3.1, 8.4**

### Property 5: Monitor Process Lifecycle

_For any_ deployment, the monitoring background process must start when deployment begins and terminate when deployment completes or fails.

**Validates: Requirements 6.1, 6.3**

### Property 6: Validation Ordering

_For any_ deployment validation run, the check for active deployments must execute before all other validation checks.

**Validates: Requirements 1.5, 7.1**

### Property 7: Wait Timeout Bounds

_For any_ deployment wait operation, the actual wait time must not exceed the configured maximum wait timeout.

**Validates: Requirements 3.2**

### Property 8: Cleanup Idempotence

_For any_ deployment cleanup operation, executing cleanup multiple times with the same correlation ID must produce the same result as executing it once.

**Validates: Requirements 4.4**

## Error Handling

### Concurrent Deployment Detected

**Error Code**: EXIT_CODE_2
**Message**: "Deployment already in progress"
**Action**:

1. Get active deployment details
2. Send Slack notification with status
3. Offer to wait for completion
4. If wait timeout, fail gracefully

### Deployment Monitor Failure

**Error**: Monitor process crashes or becomes unresponsive
**Action**:

1. Detect monitor failure via process check
2. Restart monitor process
3. Send Slack alert about monitoring gap
4. Continue deployment (don't fail deployment due to monitor issues)

### Slack Notification Failure

**Error**: Slack API unavailable or rate limited
**Action**:

1. Log notification failure
2. Continue deployment (don't block on Slack)
3. Queue notifications for retry
4. Send summary notification when Slack recovers

### Deployment Registry Unavailable

**Error**: Cannot read/write deployment registry
**Action**:

1. Fall back to CloudFormation stack status only
2. Log registry unavailability
3. Continue with reduced coordination features
4. Warn about potential concurrent deployment risks

## Testing Strategy

### Unit Tests

**Test Concurrent Deployment Detection**:

- Create mock CloudFormation stack in CREATE_IN_PROGRESS
- Run validation script
- Verify exit code 2 and error message

**Test Correlation ID Generation**:

- Generate 1000 correlation IDs
- Verify all are unique
- Verify format matches expected pattern

**Test Slack Notification Formatting**:

- Generate notifications for each deployment state
- Verify message format and content
- Verify correct channel routing

### Integration Tests

**Test Full Deployment Coordination**:

- Start first deployment
- Attempt second deployment while first is active
- Verify second deployment waits
- Verify second deployment proceeds after first completes

**Test Deployment Monitor**:

- Start deployment with monitor
- Verify monitor sends periodic updates
- Verify monitor detects completion
- Verify monitor terminates properly

### Property-Based Tests

**Property Test: Deployment Exclusivity** (Property 1):

- Generate random deployment attempts
- Verify only one can be active at a time
- Verify proper queuing and coordination

**Property Test: Correlation ID Uniqueness** (Property 2):

- Generate large number of correlation IDs
- Verify no collisions
- Verify format consistency

**Property Test: Notification Completeness** (Property 3):

- Simulate various deployment scenarios
- Verify all expected notifications are sent
- Verify notification ordering

**Property Test: Monitor Lifecycle** (Property 5):

- Start deployments with monitors
- Verify monitors start and stop correctly
- Verify no orphaned monitor processes

## Deployment Plan

### Phase 1: Enhanced Validation (Week 1)

- Update enhanced-deployment-validation.sh with detailed status reporting
- Add AWS Console link generation
- Add deployment time estimation
- Test with existing deployments

### Phase 2: Deployment Coordinator (Week 2)

- Implement deployment-coordinator.sh
- Add deployment registry (file-based initially)
- Implement wait and queue logic
- Test coordination between multiple workflow runs

### Phase 3: Deployment Monitor (Week 3)

- Implement deployment-monitor.sh
- Add background process management
- Implement stall detection
- Test monitoring during actual deployments

### Phase 4: Slack Integration (Week 4)

- Implement slack-notifier.sh
- Add all notification types
- Test notification delivery
- Add error handling for Slack failures

### Phase 5: GitHub Actions Integration (Week 5)

- Update CI/CD workflow
- Add coordination steps
- Add monitoring integration
- Test end-to-end workflow

### Phase 6: Testing and Refinement (Week 6)

- Run comprehensive integration tests
- Test failure scenarios
- Refine error messages
- Update documentation
