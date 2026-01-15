#!/bin/bash
#
# Slack Notification Retry Queue
# Queues failed Slack notifications and retries with exponential backoff
#
# Usage: bash slack-retry-queue.sh <action> [args...]
# Actions: queue, process, status
#

set -euo pipefail

# Configuration
QUEUE_DIR=".slack-retry-queue"
MAX_RETRIES=5
INITIAL_BACKOFF=5  # seconds
MAX_BACKOFF=300    # 5 minutes

# Ensure queue directory exists
mkdir -p "$QUEUE_DIR"

# Function to generate unique message ID
generate_message_id() {
    echo "msg_$(date +%s)_$$_$RANDOM"
}

# Function to queue a failed notification
queue_notification() {
    local notification_type="$1"
    shift
    local args=("$@")
    
    local message_id=$(generate_message_id)
    local queue_file="$QUEUE_DIR/$message_id.json"
    
    # Create queue entry
    cat > "$queue_file" << EOF
{
  "message_id": "$message_id",
  "notification_type": "$notification_type",
  "args": $(printf '%s\n' "${args[@]}" | jq -R . | jq -s .),
  "retry_count": 0,
  "queued_at": "$(date -u +"%Y-%m-%dT%H:%M:%SZ")",
  "next_retry_at": "$(date -u -d "+${INITIAL_BACKOFF} seconds" +"%Y-%m-%dT%H:%M:%SZ" 2>/dev/null || date -u -v+${INITIAL_BACKOFF}S +"%Y-%m-%dT%H:%M:%SZ")"
}
EOF
    
    echo "[$(date -u +"%Y-%m-%d %H:%M:%S UTC")] Queued notification: $message_id (type: $notification_type)"
    echo "$message_id"
}

# Function to calculate next retry time with exponential backoff
calculate_backoff() {
    local retry_count=$1
    local backoff=$((INITIAL_BACKOFF * (2 ** retry_count)))
    
    # Cap at max backoff
    if [ $backoff -gt $MAX_BACKOFF ]; then
        backoff=$MAX_BACKOFF
    fi
    
    echo $backoff
}

# Function to process retry queue
process_queue() {
    local processed=0
    local failed=0
    local skipped=0
    
    echo "[$(date -u +"%Y-%m-%d %H:%M:%S UTC")] Processing Slack retry queue..."
    
    # Process each queued message
    for queue_file in "$QUEUE_DIR"/*.json 2>/dev/null; do
        [ -f "$queue_file" ] || continue
        
        # Read queue entry
        local message_id=$(jq -r '.message_id' "$queue_file")
        local notification_type=$(jq -r '.notification_type' "$queue_file")
        local retry_count=$(jq -r '.retry_count' "$queue_file")
        local next_retry_at=$(jq -r '.next_retry_at' "$queue_file")
        
        # Check if it's time to retry
        local current_time=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
        if [[ "$current_time" < "$next_retry_at" ]]; then
            skipped=$((skipped + 1))
            continue
        fi
        
        # Check if max retries exceeded
        if [ $retry_count -ge $MAX_RETRIES ]; then
            echo "[$(date -u +"%Y-%m-%d %H:%M:%S UTC")] Max retries exceeded for $message_id. Moving to dead letter queue."
            mv "$queue_file" "$QUEUE_DIR/dead_letter_$message_id.json"
            failed=$((failed + 1))
            continue
        fi
        
        # Extract args
        local args=()
        while IFS= read -r arg; do
            args+=("$arg")
        done < <(jq -r '.args[]' "$queue_file")
        
        # Attempt to send notification
        echo "[$(date -u +"%Y-%m-%d %H:%M:%S UTC")] Retrying $message_id (attempt $((retry_count + 1))/$MAX_RETRIES)..."
        
        if bash "$(dirname "$0")/slack-notifier.sh" "$notification_type" "${args[@]}" 2>/dev/null; then
            echo "[$(date -u +"%Y-%m-%d %H:%M:%S UTC")] Successfully sent $message_id"
            rm "$queue_file"
            processed=$((processed + 1))
        else
            # Update retry count and next retry time
            local new_retry_count=$((retry_count + 1))
            local backoff=$(calculate_backoff $new_retry_count)
            local new_next_retry=$(date -u -d "+${backoff} seconds" +"%Y-%m-%dT%H:%M:%SZ" 2>/dev/null || date -u -v+${backoff}S +"%Y-%m-%dT%H:%M:%SZ")
            
            jq --arg retry "$new_retry_count" \
               --arg next "$new_next_retry" \
               '.retry_count = ($retry | tonumber) | .next_retry_at = $next' \
               "$queue_file" > "$queue_file.tmp" && mv "$queue_file.tmp" "$queue_file"
            
            echo "[$(date -u +"%Y-%m-%d %H:%M:%S UTC")] Retry failed for $message_id. Next retry in ${backoff}s"
            failed=$((failed + 1))
        fi
    done
    
    echo "[$(date -u +"%Y-%m-%d %H:%M:%S UTC")] Queue processing complete: $processed sent, $failed failed, $skipped skipped"
    
    # Send summary if there were failures
    if [ $failed -gt 0 ] && [ $processed -gt 0 ]; then
        bash "$(dirname "$0")/slack-notifier.sh" custom \
            "📊 Slack notification queue processed: $processed sent, $failed pending retry" \
            2>/dev/null || true
    fi
}

# Function to show queue status
show_status() {
    local queued=$(find "$QUEUE_DIR" -name "*.json" ! -name "dead_letter_*" 2>/dev/null | wc -l)
    local dead_letter=$(find "$QUEUE_DIR" -name "dead_letter_*.json" 2>/dev/null | wc -l)
    
    echo "Slack Retry Queue Status"
    echo "========================"
    echo "Queued messages: $queued"
    echo "Dead letter queue: $dead_letter"
    echo ""
    
    if [ $queued -gt 0 ]; then
        echo "Pending Messages:"
        for queue_file in "$QUEUE_DIR"/*.json 2>/dev/null; do
            [ -f "$queue_file" ] || continue
            [[ "$(basename "$queue_file")" == dead_letter_* ]] && continue
            
            local message_id=$(jq -r '.message_id' "$queue_file")
            local notification_type=$(jq -r '.notification_type' "$queue_file")
            local retry_count=$(jq -r '.retry_count' "$queue_file")
            local next_retry_at=$(jq -r '.next_retry_at' "$queue_file")
            
            echo "  - $message_id: $notification_type (retry $retry_count/$MAX_RETRIES, next: $next_retry_at)"
        done
    fi
}

# Main script
ACTION="${1:-}"

case "$ACTION" in
    queue)
        shift
        queue_notification "$@"
        ;;
    process)
        process_queue
        ;;
    status)
        show_status
        ;;
    *)
        echo "Usage: $0 <action> [args...]"
        echo "Actions:"
        echo "  queue <notification_type> <args...>  - Queue a failed notification"
        echo "  process                               - Process retry queue"
        echo "  status                                - Show queue status"
        exit 1
        ;;
esac
