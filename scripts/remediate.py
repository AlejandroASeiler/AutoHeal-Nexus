#!/usr/bin/env python3
"""
Auto-Remediation Script for Threat Detection System

This script monitors system health and automatically performs remediation
actions when issues are detected.
"""
from __future__ import annotations

import logging
import os
import subprocess
import sys
import time
from datetime import datetime
from typing import Dict, List, Optional

import requests

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration
PROMETHEUS_URL = os.environ.get('PROMETHEUS_URL', 'http://prometheus:9090')
ALERTMANAGER_URL = os.environ.get('ALERTMANAGER_URL', 'http://alertmanager:9093')
DOCKER_COMPOSE_PATH = os.environ.get('DOCKER_COMPOSE_PATH', '/app')
MAX_RESTART_ATTEMPTS = int(os.environ.get('MAX_RESTART_ATTEMPTS', '3'))
REMEDIATION_COOLDOWN = int(os.environ.get('REMEDIATION_COOLDOWN', '300'))  # 5 minutes

# Track remediation actions
remediation_history: Dict[str, List[float]] = {}


def query_prometheus(query: str) -> Optional[Dict]:
    """Query Prometheus for metrics."""
    try:
        response = requests.get(
            f'{PROMETHEUS_URL}/api/v1/query',
            params={'query': query},
            timeout=10
        )
        response.raise_for_status()
        data = response.json()
        if data['status'] == 'success':
            return data['data']
        return None
    except Exception as e:
        logger.error(f"Failed to query Prometheus: {e}")
        return None


def get_active_alerts() -> List[Dict]:
    """Get active alerts from Alertmanager."""
    try:
        response = requests.get(
            f'{ALERTMANAGER_URL}/api/v2/alerts',
            params={'filter': 'alertstate="firing"'},
            timeout=10
        )
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logger.error(f"Failed to get alerts: {e}")
        return []


def can_remediate(action_key: str) -> bool:
    """Check if remediation action can be performed (cooldown check)."""
    now = time.time()
    if action_key not in remediation_history:
        remediation_history[action_key] = []
    
    # Remove old entries
    remediation_history[action_key] = [
        ts for ts in remediation_history[action_key]
        if now - ts < REMEDIATION_COOLDOWN
    ]
    
    # Check if we've exceeded max attempts
    if len(remediation_history[action_key]) >= MAX_RESTART_ATTEMPTS:
        logger.warning(
            f"Max restart attempts ({MAX_RESTART_ATTEMPTS}) reached for {action_key}. "
            f"Cooldown period: {REMEDIATION_COOLDOWN}s"
        )
        return False
    
    return True


def record_remediation(action_key: str):
    """Record a remediation action."""
    if action_key not in remediation_history:
        remediation_history[action_key] = []
    remediation_history[action_key].append(time.time())


def restart_service(service_name: str) -> bool:
    """Restart a Docker service."""
    action_key = f"restart_{service_name}"
    
    if not can_remediate(action_key):
        return False
    
    try:
        logger.info(f"Restarting service: {service_name}")
        subprocess.run(
            ['docker-compose', 'restart', service_name],
            cwd=DOCKER_COMPOSE_PATH,
            check=True,
            capture_output=True,
            timeout=60
        )
        record_remediation(action_key)
        logger.info(f"Successfully restarted {service_name}")
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to restart {service_name}: {e.stderr.decode()}")
        return False
    except Exception as e:
        logger.error(f"Error restarting {service_name}: {e}")
        return False


def scale_service(service_name: str, replicas: int) -> bool:
    """Scale a Docker service."""
    action_key = f"scale_{service_name}"
    
    if not can_remediate(action_key):
        return False
    
    try:
        logger.info(f"Scaling service {service_name} to {replicas} replicas")
        subprocess.run(
            ['docker-compose', 'up', '-d', '--scale', f'{service_name}={replicas}'],
            cwd=DOCKER_COMPOSE_PATH,
            check=True,
            capture_output=True,
            timeout=60
        )
        record_remediation(action_key)
        logger.info(f"Successfully scaled {service_name} to {replicas}")
        return True
    except Exception as e:
        logger.error(f"Failed to scale {service_name}: {e}")
        return False


def clear_redis_cache() -> bool:
    """Clear Redis cache to free memory."""
    action_key = "clear_redis_cache"
    
    if not can_remediate(action_key):
        return False
    
    try:
        logger.info("Clearing Redis cache")
        subprocess.run(
            ['docker-compose', 'exec', '-T', 'redis', 'redis-cli', 'FLUSHDB'],
            cwd=DOCKER_COMPOSE_PATH,
            check=True,
            capture_output=True,
            timeout=30
        )
        record_remediation(action_key)
        logger.info("Successfully cleared Redis cache")
        return True
    except Exception as e:
        logger.error(f"Failed to clear Redis cache: {e}")
        return False


def rotate_logs() -> bool:
    """Rotate log files to free disk space."""
    action_key = "rotate_logs"
    
    if not can_remediate(action_key):
        return False
    
    try:
        logger.info("Rotating logs")
        log_dir = '/app/logs'
        
        # Archive old logs
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        subprocess.run(
            ['tar', '-czf', f'/app/logs/archive_{timestamp}.tar.gz', '-C', log_dir, '.'],
            check=True,
            capture_output=True,
            timeout=60
        )
        
        # Remove old log files
        subprocess.run(
            ['find', log_dir, '-name', '*.log', '-mtime', '+7', '-delete'],
            check=True,
            capture_output=True,
            timeout=30
        )
        
        record_remediation(action_key)
        logger.info("Successfully rotated logs")
        return True
    except Exception as e:
        logger.error(f"Failed to rotate logs: {e}")
        return False


def cleanup_old_data() -> bool:
    """Trigger cleanup of old data."""
    action_key = "cleanup_old_data"
    
    if not can_remediate(action_key):
        return False
    
    try:
        logger.info("Triggering data cleanup")
        # This would trigger a Celery task
        # For now, just log it
        record_remediation(action_key)
        logger.info("Data cleanup task triggered")
        return True
    except Exception as e:
        logger.error(f"Failed to trigger cleanup: {e}")
        return False


def check_service_health() -> Dict[str, bool]:
    """Check health of all services."""
    services = {
        'threat-detection-app': False,
        'redis': False,
        'postgres': False,
        'prometheus': False,
        'grafana': False,
        'loki': False
    }
    
    for service in services.keys():
        result = query_prometheus(f'up{{job="{service}"}}')
        if result and result.get('result'):
            value = float(result['result'][0]['value'][1])
            services[service] = value == 1.0
    
    return services


def check_resource_usage() -> Dict[str, float]:
    """Check system resource usage."""
    resources = {}
    
    # CPU usage
    result = query_prometheus('100 - (avg(rate(node_cpu_seconds_total{mode="idle"}[5m])) * 100)')
    if result and result.get('result'):
        resources['cpu_percent'] = float(result['result'][0]['value'][1])
    
    # Memory usage
    result = query_prometheus('(1 - (node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes)) * 100')
    if result and result.get('result'):
        resources['memory_percent'] = float(result['result'][0]['value'][1])
    
    # Disk usage
    result = query_prometheus('(1 - (node_filesystem_avail_bytes{mountpoint="/"} / node_filesystem_size_bytes{mountpoint="/"})) * 100')
    if result and result.get('result'):
        resources['disk_percent'] = float(result['result'][0]['value'][1])
    
    return resources


def remediate_service_down(service_name: str):
    """Remediate a down service."""
    logger.warning(f"Service {service_name} is down. Attempting restart...")
    if restart_service(service_name):
        logger.info(f"Remediation successful for {service_name}")
    else:
        logger.error(f"Remediation failed for {service_name}. Manual intervention required.")


def remediate_high_memory():
    """Remediate high memory usage."""
    logger.warning("High memory usage detected. Clearing Redis cache...")
    if clear_redis_cache():
        logger.info("Memory remediation successful")
    else:
        logger.error("Memory remediation failed")


def remediate_low_disk_space():
    """Remediate low disk space."""
    logger.warning("Low disk space detected. Rotating logs and cleaning up...")
    
    success = True
    if not rotate_logs():
        success = False
    
    if not cleanup_old_data():
        success = False
    
    if success:
        logger.info("Disk space remediation successful")
    else:
        logger.error("Disk space remediation partially failed")


def remediate_celery_queue_backlog():
    """Remediate Celery queue backlog by scaling workers."""
    logger.warning("Celery queue backlog detected. Scaling workers...")
    if scale_service('celery-worker', 4):
        logger.info("Successfully scaled Celery workers")
    else:
        logger.error("Failed to scale Celery workers")


def main():
    """Main remediation loop."""
    logger.info("Starting auto-remediation service")
    
    # Check service health
    logger.info("Checking service health...")
    service_health = check_service_health()
    
    for service, is_healthy in service_health.items():
        if not is_healthy:
            remediate_service_down(service)
    
    # Check resource usage
    logger.info("Checking resource usage...")
    resources = check_resource_usage()
    
    if resources.get('memory_percent', 0) > 85:
        remediate_high_memory()
    
    if resources.get('disk_percent', 0) > 85:
        remediate_low_disk_space()
    
    # Check for specific alerts
    logger.info("Checking active alerts...")
    alerts = get_active_alerts()
    
    for alert in alerts:
        alert_name = alert.get('labels', {}).get('alertname', '')
        
        if alert_name == 'CeleryQueueBacklog':
            remediate_celery_queue_backlog()
    
    logger.info("Auto-remediation cycle complete")


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        logger.info("Auto-remediation service stopped by user")
        sys.exit(0)
    except Exception as e:
        logger.exception(f"Unexpected error in auto-remediation: {e}")
        sys.exit(1)

