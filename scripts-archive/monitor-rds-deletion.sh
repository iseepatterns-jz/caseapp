#!/bin/bash
DB_ID="courtcasemanagementstack-courtcasedatabasef7bbe8d0-jkknae8z8dgv"
START_TIME=$(date +%s)

echo "=== RDS Deletion Monitor Started at $(date) ==="
echo "DB Instance: $DB_ID"
echo ""

# Check every 2 minutes for up to 20 minutes
for i in {1..10}; do
    CURRENT_TIME=$(date +%s)
    ELAPSED=$((CURRENT_TIME - START_TIME))
    ELAPSED_MIN=$((ELAPSED / 60))
    
    echo "[Check $i at ${ELAPSED_MIN}m] Checking RDS status..."
    
    STATUS=$(AWS_PAGER="" aws rds describe-db-instances --db-instance-identifier "$DB_ID" --query 'DBInstances[0].DBInstanceStatus' 2>/dev/null || echo "deleted")
    
    if [ "$STATUS" = "deleted" ]; then
        echo ""
        echo "=== RDS Instance deleted at ${ELAPSED_MIN}m ==="
        exit 0
    fi
    
    echo "  Status: $STATUS"
    
    if [ $i -lt 10 ]; then
        echo "  Waiting 2 minutes..."
        sleep 120
    fi
done

echo ""
echo "=== RDS deletion timeout after 20 minutes ==="
exit 1
