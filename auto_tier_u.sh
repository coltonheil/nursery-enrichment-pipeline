#!/bin/bash
# Auto-start Tier U re-enrichment when current batch completes

echo "Waiting for current batch to complete..."
echo "Monitoring: full_pipeline_output.log"
echo ""

# Wait for pipeline to complete (checks every 60 seconds)
while true; do
    # Check if process is still running
    if ! pgrep -f "full_pipeline_with_progress.py" > /dev/null; then
        echo "✅ Current batch completed!"
        break
    fi
    
    # Show current progress
    tail -3 full_pipeline_output.log | grep -E "\[.*/.* \]" | tail -1
    sleep 60
done

echo ""
echo "Starting Tier U re-enrichment in 10 seconds..."
sleep 10

# Activate venv and run
source venv/bin/activate
nohup python reenrich_tier_u.py > tier_u_output.log 2>&1 &
PID=$!

echo "✅ Tier U re-enrichment started (PID: $PID)"
echo "Monitor: tail -f tier_u_output.log"
echo ""
echo "Expected:"
echo "  - ~978 failed Tier U leads to re-enrich"
echo "  - ~1.5-2 hours runtime"
echo "  - 100-200 leads upgraded to A/B/C"
