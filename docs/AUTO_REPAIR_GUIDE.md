# Auto-Repair System Guide
## Kubernetes-Style Self-Healing for Docker Compose

This project includes a comprehensive auto-repair system that provides Kubernetes-style self-healing capabilities for Docker Compose deployments.

## 🎯 Features

### 1. **Auto-Repair Watchdog**
Continuously monitors all services and automatically repairs failures:
- ✅ Detects unhealthy containers
- ✅ Restarts crashed services
- ✅ Fixes stuck/restarting containers
- ✅ Handles high resource usage
- ✅ Cleans up disk space
- ✅ Repairs network issues
- ✅ Integrates with Prometheus alerts

### 2. **Auto-Scaling**
Dynamically scales services based on load:
- ✅ CPU-based scaling
- ✅ Memory-based scaling
- ✅ Queue depth-based scaling
- ✅ Configurable min/max replicas
- ✅ Scale-up and scale-down thresholds

### 3. **Intelligent Restart Policies**
- ✅ Cooldown periods between restarts
- ✅ Maximum restart attempts
- ✅ Exponential backoff
- ✅ Service dependency awareness

### 4. **Prometheus Integration**
- ✅ 20+ auto-repair alert rules
- ✅ Automatic remediation triggers
- ✅ Repair action tracking
- ✅ Failure rate monitoring

### 5. **Comprehensive Logging**
- ✅ All repair actions logged
- ✅ Success/failure tracking
- ✅ Historical repair data
- ✅ Grafana dashboards

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────┐
│                                                         │
│  Prometheus                                             │
│  ├─ Monitors all services                              │
│  ├─ Evaluates alert rules                              │
│  └─ Triggers alerts                                     │
│                                                         │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  Auto-Repair Watchdog                                  │
│  ├─ Checks service health (every 30s)                  │
│  ├─ Listens to Prometheus alerts                       │
│  ├─ Executes repair strategies                         │
│  ├─ Tracks repair history                              │
│  └─ Sends critical alerts                              │
│                                                         │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  Auto-Scaler                                           │
│  ├─ Monitors resource usage                            │
│  ├─ Scales services up/down                            │
│  └─ Respects min/max limits                            │
│                                                         │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  Docker Compose Services                               │
│  ├─ Health checks configured                           │
│  ├─ Restart policies set                               │
│  └─ Monitored by watchdog                              │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

## 🚀 Quick Start

### Enable Auto-Repair

The watchdog service is included in `docker-compose.yml`:

```bash
# Start all services including watchdog
docker-compose up -d

# Check watchdog status
docker-compose ps watchdog

# View watchdog logs
docker-compose logs -f watchdog
```

### Configuration

Environment variables in `.env`:

```bash
# Watchdog settings
WATCHDOG_INTERVAL=30              # Check interval in seconds
MAX_RESTART_ATTEMPTS=3            # Max restart attempts before alerting
RESTART_COOLDOWN=300              # Cooldown period between restarts (seconds)

# Auto-scaler settings
SCALER_INTERVAL=60                # Scaling check interval
MIN_REPLICAS=1                    # Minimum service replicas
MAX_REPLICAS=5                    # Maximum service replicas
```

## 📋 Repair Strategies

### 1. Unhealthy Service
**Trigger:** Health check fails  
**Action:** Restart the service  
**Cooldown:** 5 minutes  
**Max Attempts:** 3

```python
# Automatically detects and repairs
docker-compose restart <service>
```

### 2. Exited Service
**Trigger:** Container exits  
**Action:** Start the service  
**Cooldown:** 5 minutes  
**Max Attempts:** 3

```python
# Automatically starts stopped services
docker-compose start <service>
```

### 3. Stuck Restarting
**Trigger:** Service stuck in restarting state  
**Action:** Stop then start  
**Cooldown:** 5 minutes  
**Max Attempts:** 3

```python
# Force stop and clean start
docker-compose stop <service>
docker-compose start <service>
```

### 4. High Memory Usage
**Trigger:** Memory usage > 90%  
**Action:** Restart to free memory  
**Cooldown:** 10 minutes  
**Max Attempts:** 2

### 5. High CPU Usage
**Trigger:** CPU usage > 90% for 10 minutes  
**Action:** Restart service  
**Cooldown:** 10 minutes  
**Max Attempts:** 2

### 6. Disk Space Low
**Trigger:** Disk usage > 90%  
**Action:** Clean Docker system and old logs  
**Cooldown:** 1 hour  
**Max Attempts:** 1

```bash
# Automatic cleanup
docker system prune -f
find /app/logs -name "*.log" -mtime +7 -delete
```

### 7. Network Issues
**Trigger:** High network errors  
**Action:** Restart affected service  
**Cooldown:** 5 minutes  
**Max Attempts:** 3

## 🎛️ Prometheus Alert Rules

### Critical Alerts (Auto-Repair Enabled)

| Alert | Threshold | Duration | Action |
|-------|-----------|----------|--------|
| ContainerUnhealthy | health != healthy | 2 min | Restart |
| ContainerDown | up == 0 | 1 min | Start |
| ContainerRestarting | restart rate > 0.1 | 5 min | Investigate |
| HighMemoryUsage | memory > 90% | 5 min | Restart |
| HighCPUUsage | CPU > 90% | 10 min | Restart |
| DiskSpaceLow | disk < 10% | 5 min | Cleanup |
| HighErrorRate | 5xx rate > 10% | 5 min | Restart |
| DatabaseConnectionsHigh | connections > 80 | 5 min | Restart app |
| CeleryQueueBacklog | queue > 1000 | 10 min | Scale workers |
| CeleryWorkerDown | workers == 0 | 2 min | Start workers |

### Warning Alerts (Manual Intervention)

| Alert | Threshold | Duration | Action |
|-------|-----------|----------|--------|
| WatchdogDown | up == 0 | 2 min | Manual |
| TooManyRepairAttempts | attempts > 10/hour | 5 min | Manual |

## 📊 Monitoring

### Watchdog Metrics

The watchdog exports Prometheus metrics:

```
# Repair attempts
repair_attempts_total{service="<name>", action="<action>", success="<bool>"}

# Service health status
service_health_status{service="<name>", status="<status>"}

# Failure counts
service_failure_count{service="<name>"}

# Last repair timestamp
service_last_repair_timestamp{service="<name>"}
```

### Grafana Dashboard

Access the Auto-Repair dashboard:
```
http://localhost:3000/d/auto-repair/auto-repair-system
```

**Panels:**
- Service health overview
- Repair attempts timeline
- Success/failure rates
- Most repaired services
- Cooldown status
- Failure counts

### Logs

View repair logs:

```bash
# Real-time logs
docker-compose logs -f watchdog

# Recent repairs
tail -f logs/auto_repair.log

# Search for specific service
grep "threat-detection-app" logs/auto_repair.log
```

## 🔧 Manual Operations

### Disable Auto-Repair for a Service

Add label to service in `docker-compose.yml`:

```yaml
services:
  my-service:
    labels:
      - "auto_repair=false"
```

### Trigger Manual Repair

```bash
# Restart a service manually
docker-compose restart <service>

# Force recreation
docker-compose up -d --force-recreate <service>

# View service logs
docker-compose logs <service>
```

### Check Repair History

```bash
# View all repairs
cat logs/auto_repair.log | grep "Repair"

# Count repairs by service
cat logs/auto_repair.log | grep "Repair" | awk '{print $6}' | sort | uniq -c

# Recent failures
cat logs/auto_repair.log | grep "Failed"
```

## 🎯 Best Practices

### 1. Configure Appropriate Health Checks

```yaml
services:
  my-service:
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8080/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s
```

### 2. Set Restart Policies

```yaml
services:
  my-service:
    restart: unless-stopped  # Recommended for most services
```

### 3. Configure Resource Limits

```yaml
services:
  my-service:
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 2G
        reservations:
          cpus: '1'
          memory: 1G
```

### 4. Monitor Watchdog Health

```bash
# Ensure watchdog is running
docker-compose ps watchdog

# Check watchdog logs
docker-compose logs watchdog | tail -50

# Verify Prometheus integration
curl http://localhost:9090/api/v1/alerts | jq '.data.alerts[] | select(.labels.auto_repair=="true")'
```

### 5. Test Auto-Repair

```bash
# Test 1: Stop a service
docker-compose stop threat-detection-app
# Watchdog should restart it within 30-60 seconds

# Test 2: Make a service unhealthy
docker-compose exec threat-detection-app kill -STOP 1
# Watchdog should detect and restart

# Test 3: Simulate high memory
# Watchdog should restart after threshold
```

## 🚨 Troubleshooting

### Watchdog Not Starting

**Check:**
```bash
docker-compose logs watchdog
```

**Common Issues:**
- Docker socket not mounted: Check `/var/run/docker.sock` volume
- Prometheus not accessible: Check network connectivity
- Permission denied: Ensure watchdog has access to Docker socket

**Fix:**
```bash
docker-compose down
docker-compose up -d watchdog
```

### Services Not Being Repaired

**Check:**
1. Watchdog is running: `docker-compose ps watchdog`
2. Service is in critical list: Check `auto_repair_watchdog.py`
3. Cooldown period: Wait 5 minutes between repairs
4. Max attempts: Check if limit reached

**View Logs:**
```bash
docker-compose logs watchdog | grep <service-name>
```

### Too Many Repair Attempts

**Cause:** Underlying issue not resolved by restart

**Action:**
1. Check service logs: `docker-compose logs <service>`
2. Check resource usage: `docker stats`
3. Check dependencies: Are required services running?
4. Manual investigation required

**Disable Auto-Repair:**
```bash
# Stop watchdog temporarily
docker-compose stop watchdog

# Fix the underlying issue
# ...

# Restart watchdog
docker-compose start watchdog
```

### Alerts Not Triggering

**Check Prometheus:**
```bash
# View active alerts
curl http://localhost:9090/api/v1/alerts

# Check alert rules
curl http://localhost:9090/api/v1/rules
```

**Verify Alertmanager:**
```bash
# Check Alertmanager status
curl http://localhost:9093/api/v1/status

# View alert configuration
docker-compose exec prometheus cat /etc/prometheus/alerts/auto_repair.yml
```

## 📈 Scaling Configuration

### Configure Auto-Scaling

Edit `scripts/auto_scaler.py`:

```python
self.scaling_config = {
    'celery-worker': {
        'min_replicas': 2,        # Minimum workers
        'max_replicas': 10,       # Maximum workers
        'scale_up_threshold': 0.8,   # Scale up at 80% CPU
        'scale_down_threshold': 0.2, # Scale down at 20% CPU
        'metric': 'cpu_usage'
    }
}
```

### Manual Scaling

```bash
# Scale up
docker-compose up -d --scale celery-worker=5

# Scale down
docker-compose up -d --scale celery-worker=2

# Check current scale
docker-compose ps celery-worker
```

## 🔐 Security Considerations

### Docker Socket Access

The watchdog requires access to the Docker socket:

```yaml
volumes:
  - /var/run/docker.sock:/var/run/docker.sock:ro  # Read-only
```

**Security:**
- Socket is mounted read-only when possible
- Watchdog runs with minimal privileges
- All actions are logged

### Alert Notifications

Configure secure alert channels in `monitoring/alertmanager/alertmanager.yml`:

```yaml
receivers:
  - name: 'critical'
    slack_configs:
      - api_url: '<webhook-url>'
        channel: '#alerts'
    pagerduty_configs:
      - service_key: '<key>'
```

## 📊 Metrics and Reporting

### Daily Report

Generate daily auto-repair report:

```bash
# View repairs in last 24 hours
cat logs/auto_repair.log | grep "$(date +%Y-%m-%d)"

# Count by service
cat logs/auto_repair.log | grep "$(date +%Y-%m-%d)" | grep "Repair" | awk '{print $6}' | sort | uniq -c
```

### Prometheus Queries

```promql
# Total repairs in last hour
increase(repair_attempts_total[1h])

# Success rate
sum(repair_attempts_total{success="true"}) / sum(repair_attempts_total)

# Most repaired service
topk(5, sum by (service) (repair_attempts_total))

# Average time between repairs
avg(time() - service_last_repair_timestamp)
```

## 🎓 Advanced Features

### Custom Repair Strategies

Add custom repair logic in `auto_repair_watchdog.py`:

```python
def repair_custom_issue(self, service_name: str) -> bool:
    """Custom repair strategy"""
    try:
        # Your custom repair logic
        logger.info(f"Applying custom repair to {service_name}")
        # ...
        return True
    except Exception as e:
        logger.error(f"Custom repair failed: {e}")
        return False

# Register strategy
self.repair_strategies['custom_issue'] = self.repair_custom_issue
```

### Webhook Integration

Trigger repairs via webhook:

```python
# Add to auto_repair_watchdog.py
from flask import Flask, request

app = Flask(__name__)

@app.route('/repair/<service>', methods=['POST'])
def trigger_repair(service):
    if service in self.service_health:
        self.attempt_repair(self.service_health[service])
        return {'status': 'repair triggered'}
    return {'error': 'service not found'}, 404
```

## 📚 Summary

The auto-repair system provides:

✅ **Automatic failure detection** - Continuous monitoring
✅ **Intelligent repair strategies** - Multiple repair approaches
✅ **Cooldown and limits** - Prevents repair loops
✅ **Prometheus integration** - Alert-driven repairs
✅ **Auto-scaling** - Dynamic resource adjustment
✅ **Comprehensive logging** - Full audit trail
✅ **Grafana dashboards** - Visual monitoring
✅ **Manual override** - Full control when needed

This creates a **self-healing infrastructure** similar to Kubernetes, but optimized for Docker Compose deployments.

---

**For more information:**
- Watchdog script: `scripts/auto_repair_watchdog.py`
- Alert rules: `monitoring/prometheus/alerts/auto_repair.yml`
- Logs: `logs/auto_repair.log`
- Dashboard: http://localhost:3000/d/auto-repair

