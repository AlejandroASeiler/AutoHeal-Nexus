#!/bin/bash
# =====================================================
# notify_build_progress.sh
# Notifies via Telegram and exposes Prometheus metrics
# Monitors build and deploy like Kubernetes controller
# =====================================================

set -euo pipefail

# Load environment variables
if [ -f .env ]; then
    source .env
else
    echo "Error: .env file not found"
    exit 1
fi

TELEGRAM_API="https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage"
CHAT_ID="${TELEGRAM_CHAT_ID}"
LOG_FILE="logs/build.log"
PROM_FILE="monitoring/exporters/pipeline_metrics.prom"
CHECK_INTERVAL=120
FREEZE_THRESHOLD=300

mkdir -p "$(dirname "$LOG_FILE")" "$(dirname "$PROM_FILE")"

# =====================================================
# Functions
# =====================================================

send_msg() {
    local text="$1"
    local parse_mode="${2:-HTML}"
    
    curl -s -X POST "$TELEGRAM_API" \
        -d chat_id="$CHAT_ID" \
        -d parse_mode="$parse_mode" \
        --data-urlencode "text=$(printf '%b' "$text")" >/dev/null || true
}

write_metric() {
    echo "$1 $2" >> "$PROM_FILE"
}

send_traceback_if_exists() {
    if grep -q -E "Traceback|ERROR|Error|Exception|CRITICAL|Failed|failed" "$LOG_FILE"; then
        local lines
        lines=$(awk '/Traceback|ERROR|Error|Exception|CRITICAL|Failed|failed/{found=1} found' "$LOG_FILE" | tail -n 50)
        
        # Format for Telegram
        local msg="🚨 <b>ERROR DETECTED</b> 🚨\n\n"
        msg+="🕐 <b>Time:</b> $(date '+%Y-%m-%d %H:%M:%S')\n"
        msg+="📝 <b>Log File:</b> <code>$LOG_FILE</code>\n\n"
        msg+="📋 <b>Error Details:</b>\n<pre>$(echo "$lines" | head -c 3000)</pre>"
        
        send_msg "$msg" "HTML"
        write_metric "build_status" 0
        write_metric "build_errors_total" 1
    fi
}

health_check() {
    local running stopped unhealthy
    running=$(docker ps --format '{{.Names}}' | wc -l)
    stopped=$(docker ps -a --filter "status=exited" --format '{{.Names}}' | wc -l)
    unhealthy=$(docker ps --filter "health=unhealthy" --format '{{.Names}}' | wc -l)
    
    local msg="🔍 <b>Health Check</b>\n\n"
    msg+="✅ <b>Running:</b> $running containers\n"
    msg+="⏸️ <b>Stopped:</b> $stopped containers\n"
    msg+="⚠️ <b>Unhealthy:</b> $unhealthy containers\n"
    msg+="🕐 <b>Time:</b> $(date '+%Y-%m-%d %H:%M:%S')"
    
    send_msg "$msg" "HTML"
    write_metric "build_containers_running" "$running"
    write_metric "build_containers_stopped" "$stopped"
    write_metric "build_containers_unhealthy" "$unhealthy"
}

abort_build() {
    local code="$1"
    local msg="❌ <b>BUILD ABORTED</b> ❌\n\n"
    msg+="🔢 <b>Exit Code:</b> $code\n"
    msg+="🕐 <b>Time:</b> $(date '+%Y-%m-%d %H:%M:%S')"
    
    send_msg "$msg" "HTML"
    write_metric "build_status" -1
    write_metric "build_end_timestamp" "$(date +%s)"
    
    # Send traceback if exists
    send_traceback_if_exists
    
    exit "$code"
}

check_container_logs() {
    local service="$1"
    local lines="${2:-50}"
    
    if docker-compose ps | grep -q "$service"; then
        docker-compose logs --tail "$lines" "$service" 2>&1 | \
            grep -E "ERROR|Error|Exception|Traceback|CRITICAL|Failed" || true
    fi
}

send_container_errors() {
    echo "🔍 Checking container logs for errors..."
    
    # Get all service names
    local services=$(docker-compose config --services)
    
    for service in $services; do
        local errors=$(check_container_logs "$service" 30)
        
        if [ -n "$errors" ]; then
            local msg="🐳 <b>Container Error: $service</b>\n\n"
            msg+="<pre>$(echo "$errors" | head -c 2000)</pre>"
            
            send_msg "$msg" "HTML"
        fi
    done
}

trap 'abort_build $?; exit 1' INT TERM

# =====================================================
# Main Execution
# =====================================================

# Initialize
: > "$LOG_FILE"
: > "$PROM_FILE"

send_msg "🚀 <b>Starting Docker Compose Build</b>\n\n🕐 <b>Time:</b> $(date '+%Y-%m-%d %H:%M:%S')" "HTML"
write_metric "build_start_timestamp" "$(date +%s)"
write_metric "build_status" 1
write_metric "build_phase" 0  # 0=build

# --- Freeze Watcher (Background) ---
(
    last_size=0
    last_change=$(date +%s)
    send_msg "🩺 <b>Activity Monitor Started</b>\n\nMonitoring for freeze conditions..." "HTML"
    
    while true; do
        size=$(stat -c %s "$LOG_FILE" 2>/dev/null || echo 0)
        now=$(date +%s)
        
        if (( size > last_size )); then
            last_change=$now
            last_size=$size
        elif (( now - last_change > FREEZE_THRESHOLD )); then
            local msg="⚠️ <b>POSSIBLE FREEZE DETECTED</b> ⚠️\n\n"
            msg+="No activity for more than $((FREEZE_THRESHOLD/60)) minutes\n"
            msg+="🕐 <b>Time:</b> $(date '+%Y-%m-%d %H:%M:%S')"
            
            send_msg "$msg" "HTML"
            write_metric "build_freeze_detected" 1
            last_change=$now
        fi
        
        sleep "$CHECK_INTERVAL"
    done
) &

WATCHER_PID=$!

# --- Build Phase ---
echo "🔨 Starting build phase..."
send_msg "🔨 <b>Build Phase Started</b>\n\nBuilding Docker images..." "HTML"

stdbuf -oL docker-compose build --no-cache 2>&1 | tee -a "$LOG_FILE"
BUILD_EXIT=$?

if [ $BUILD_EXIT -ne 0 ]; then
    send_msg "💥 <b>BUILD FAILED</b> 💥\n\n🔢 <b>Exit Code:</b> $BUILD_EXIT" "HTML"
    send_traceback_if_exists
    kill $WATCHER_PID 2>/dev/null || true
    abort_build "$BUILD_EXIT"
fi

send_msg "✅ <b>Build Completed Successfully</b>\n\n🚀 Starting deployment..." "HTML"
write_metric "build_phase" 1  # 1=deploy

# --- Deploy Phase ---
echo "🚀 Starting deploy phase..."
send_msg "🚀 <b>Deploy Phase Started</b>\n\nStarting containers..." "HTML"

stdbuf -oL docker-compose up -d 2>&1 | tee -a "$LOG_FILE"
DEPLOY_EXIT=$?

if [ $DEPLOY_EXIT -eq 0 ]; then
    local msg="🎯 <b>DEPLOYMENT SUCCESSFUL</b> ✅\n\n"
    msg+="All containers started successfully\n"
    msg+="🕐 <b>Time:</b> $(date '+%Y-%m-%d %H:%M:%S')"
    
    send_msg "$msg" "HTML"
    write_metric "build_status" 2
    write_metric "build_end_timestamp" "$(date +%s)"
    
    # Wait a bit for containers to stabilize
    sleep 10
    
    # Health check
    health_check
    
    # Check for any container errors
    send_container_errors
else
    local msg="🚨 <b>DEPLOYMENT FAILED</b> 🚨\n\n"
    msg+="🔢 <b>Exit Code:</b> $DEPLOY_EXIT\n"
    msg+="🕐 <b>Time:</b> $(date '+%Y-%m-%d %H:%M:%S')"
    
    send_msg "$msg" "HTML"
    send_traceback_if_exists
    send_container_errors
    write_metric "build_status" -2
    write_metric "build_end_timestamp" "$(date +%s)"
    
    kill $WATCHER_PID 2>/dev/null || true
    exit "$DEPLOY_EXIT"
fi

# Stop freeze watcher
kill $WATCHER_PID 2>/dev/null || true

# Final success message
local duration=$(($(date +%s) - $(grep build_start_timestamp "$PROM_FILE" | awk '{print $2}')))
local msg="🎉 <b>PIPELINE COMPLETED SUCCESSFULLY</b> 🎉\n\n"
msg+="⏱️ <b>Duration:</b> $((duration/60)) minutes $((duration%60)) seconds\n"
msg+="🕐 <b>Completed:</b> $(date '+%Y-%m-%d %H:%M:%S')\n\n"
msg+="✅ All systems operational"

send_msg "$msg" "HTML"

echo "✅ Pipeline completed without errors."

