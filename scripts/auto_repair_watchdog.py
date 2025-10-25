#!/usr/bin/env python3
"""
Auto-Repair Watchdog Service
Kubernetes-style self-healing for Docker Compose
"""

import os
import sys
import time
import json
import logging
import subprocess
import requests
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict
from collections import defaultdict

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
    handlers=[
        logging.FileHandler('/app/logs/auto_repair.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


@dataclass
class ServiceHealth:
    """Service health status"""
    name: str
    status: str
    health: str
    restarts: int
    uptime: str
    last_check: datetime
    consecutive_failures: int = 0
    last_repair_attempt: Optional[datetime] = None


@dataclass
class RepairAction:
    """Repair action record"""
    timestamp: datetime
    service: str
    action: str
    reason: str
    success: bool
    details: str


class AutoRepairWatchdog:
    """
    Auto-repair watchdog for Docker Compose services
    Provides Kubernetes-style self-healing capabilities
    """
    
    def __init__(self):
        self.compose_file = os.getenv('COMPOSE_FILE', 'docker-compose.yml')
        self.project_name = os.getenv('COMPOSE_PROJECT_NAME', 'cybersec_enhanced')
        self.check_interval = int(os.getenv('WATCHDOG_INTERVAL', '30'))
        self.max_restart_attempts = int(os.getenv('MAX_RESTART_ATTEMPTS', '3'))
        self.restart_cooldown = int(os.getenv('RESTART_COOLDOWN', '300'))  # 5 minutes
        self.prometheus_url = os.getenv('PROMETHEUS_URL', 'http://prometheus:9090')
        self.alertmanager_url = os.getenv('ALERTMANAGER_URL', 'http://alertmanager:9093')
        
        self.service_health: Dict[str, ServiceHealth] = {}
        self.repair_history: List[RepairAction] = []
        self.failure_counts: Dict[str, int] = defaultdict(int)
        
        # Critical services that should always be running
        self.critical_services = [
            'postgres',
            'redis',
            'prometheus',
            'grafana',
            'loki',
            'threat-detection-app',
            'dashboard'
        ]
        
        # Repair strategies
        self.repair_strategies = {
            'unhealthy': self.repair_unhealthy_service,
            'exited': self.repair_exited_service,
            'restarting': self.repair_restarting_service,
            'high_memory': self.repair_high_memory,
            'high_cpu': self.repair_high_cpu,
            'disk_full': self.repair_disk_full,
            'network_issue': self.repair_network_issue,
        }
    
    def run(self):
        """Main watchdog loop"""
        logger.info("🐕 Auto-Repair Watchdog started")
        logger.info(f"Monitoring interval: {self.check_interval}s")
        logger.info(f"Critical services: {', '.join(self.critical_services)}")
        
        while True:
            try:
                self.check_and_repair()
                time.sleep(self.check_interval)
            except KeyboardInterrupt:
                logger.info("Watchdog stopped by user")
                break
            except Exception as e:
                logger.error(f"Watchdog error: {e}", exc_info=True)
                time.sleep(self.check_interval)
    
    def check_and_repair(self):
        """Check all services and perform repairs if needed"""
        logger.info("🔍 Checking service health...")
        
        # Get service status
        services = self.get_service_status()
        
        # Check each service
        for service in services:
            service_name = service['name']
            
            # Update health status
            health = ServiceHealth(
                name=service_name,
                status=service['status'],
                health=service.get('health', 'unknown'),
                restarts=service.get('restarts', 0),
                uptime=service.get('uptime', 'unknown'),
                last_check=datetime.now()
            )
            
            # Check if service needs repair
            if self.needs_repair(health):
                self.attempt_repair(health)
            
            self.service_health[service_name] = health
        
        # Check Prometheus alerts
        self.check_prometheus_alerts()
        
        # Check resource usage
        self.check_resource_usage()
        
        # Auto-scale if needed
        self.auto_scale()
        
        # Clean old repair history
        self.cleanup_history()
    
    def get_service_status(self) -> List[Dict]:
        """Get status of all Docker Compose services"""
        try:
            cmd = ['docker-compose', 'ps', '--format', 'json']
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            
            services = []
            for line in result.stdout.strip().split('\n'):
                if line:
                    try:
                        service = json.loads(line)
                        services.append(service)
                    except json.JSONDecodeError:
                        continue
            
            return services
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to get service status: {e}")
            return []
    
    def needs_repair(self, health: ServiceHealth) -> bool:
        """Determine if a service needs repair"""
        # Check if service is critical
        is_critical = health.name in self.critical_services
        
        # Check status
        if health.status in ['exited', 'dead', 'removing']:
            logger.warning(f"⚠️  {health.name} is {health.status}")
            return True
        
        # Check health
        if health.health == 'unhealthy' and is_critical:
            logger.warning(f"⚠️  {health.name} is unhealthy")
            return True
        
        # Check if restarting too frequently
        if health.status == 'restarting':
            logger.warning(f"⚠️  {health.name} is stuck restarting")
            return True
        
        # Check restart count
        if health.restarts > 5:
            logger.warning(f"⚠️  {health.name} has restarted {health.restarts} times")
            return True
        
        return False
    
    def attempt_repair(self, health: ServiceHealth):
        """Attempt to repair a service"""
        service_name = health.name
        
        # Check cooldown period
        if health.last_repair_attempt:
            cooldown_end = health.last_repair_attempt + timedelta(seconds=self.restart_cooldown)
            if datetime.now() < cooldown_end:
                logger.info(f"⏳ {service_name} in cooldown period, skipping repair")
                return
        
        # Check max attempts
        if self.failure_counts[service_name] >= self.max_restart_attempts:
            logger.error(f"❌ {service_name} exceeded max restart attempts, manual intervention required")
            self.send_alert(service_name, "Max restart attempts exceeded")
            return
        
        logger.info(f"🔧 Attempting to repair {service_name}...")
        
        # Determine repair strategy
        if health.status in ['exited', 'dead']:
            success = self.repair_exited_service(service_name)
        elif health.health == 'unhealthy':
            success = self.repair_unhealthy_service(service_name)
        elif health.status == 'restarting':
            success = self.repair_restarting_service(service_name)
        else:
            success = self.repair_generic(service_name)
        
        # Record repair action
        action = RepairAction(
            timestamp=datetime.now(),
            service=service_name,
            action='restart',
            reason=f"status={health.status}, health={health.health}",
            success=success,
            details=f"Restarts: {health.restarts}"
        )
        self.repair_history.append(action)
        
        # Update failure count
        if success:
            self.failure_counts[service_name] = 0
            logger.info(f"✅ {service_name} repaired successfully")
        else:
            self.failure_counts[service_name] += 1
            logger.error(f"❌ Failed to repair {service_name}")
        
        # Update last repair attempt
        health.last_repair_attempt = datetime.now()
    
    def repair_exited_service(self, service_name: str) -> bool:
        """Repair an exited service"""
        try:
            logger.info(f"🔄 Restarting exited service: {service_name}")
            subprocess.run(['docker-compose', 'start', service_name], check=True)
            time.sleep(5)
            return self.verify_service_running(service_name)
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to restart {service_name}: {e}")
            return False
    
    def repair_unhealthy_service(self, service_name: str) -> bool:
        """Repair an unhealthy service"""
        try:
            logger.info(f"🔄 Restarting unhealthy service: {service_name}")
            subprocess.run(['docker-compose', 'restart', service_name], check=True)
            time.sleep(10)
            return self.verify_service_healthy(service_name)
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to restart {service_name}: {e}")
            return False
    
    def repair_restarting_service(self, service_name: str) -> bool:
        """Repair a service stuck in restarting state"""
        try:
            logger.info(f"🛑 Stopping stuck service: {service_name}")
            subprocess.run(['docker-compose', 'stop', service_name], check=True)
            time.sleep(5)
            
            logger.info(f"🔄 Starting service: {service_name}")
            subprocess.run(['docker-compose', 'start', service_name], check=True)
            time.sleep(10)
            
            return self.verify_service_running(service_name)
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to repair restarting {service_name}: {e}")
            return False
    
    def repair_high_memory(self, service_name: str) -> bool:
        """Repair service with high memory usage"""
        try:
            logger.info(f"💾 Restarting service due to high memory: {service_name}")
            subprocess.run(['docker-compose', 'restart', service_name], check=True)
            time.sleep(10)
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to restart {service_name}: {e}")
            return False
    
    def repair_high_cpu(self, service_name: str) -> bool:
        """Repair service with high CPU usage"""
        try:
            logger.info(f"⚡ Restarting service due to high CPU: {service_name}")
            subprocess.run(['docker-compose', 'restart', service_name], check=True)
            time.sleep(10)
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to restart {service_name}: {e}")
            return False
    
    def repair_disk_full(self, service_name: str) -> bool:
        """Repair disk full issue"""
        try:
            logger.info(f"💿 Cleaning up disk space for: {service_name}")
            # Clean Docker system
            subprocess.run(['docker', 'system', 'prune', '-f'], check=True)
            # Clean logs
            subprocess.run(['find', '/app/logs', '-name', '*.log', '-mtime', '+7', '-delete'], check=False)
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to clean disk: {e}")
            return False
    
    def repair_network_issue(self, service_name: str) -> bool:
        """Repair network connectivity issues"""
        try:
            logger.info(f"🌐 Restarting service due to network issue: {service_name}")
            subprocess.run(['docker-compose', 'restart', service_name], check=True)
            time.sleep(10)
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to restart {service_name}: {e}")
            return False
    
    def repair_generic(self, service_name: str) -> bool:
        """Generic repair strategy"""
        try:
            logger.info(f"🔄 Generic restart for: {service_name}")
            subprocess.run(['docker-compose', 'restart', service_name], check=True)
            time.sleep(10)
            return self.verify_service_running(service_name)
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to restart {service_name}: {e}")
            return False
    
    def verify_service_running(self, service_name: str) -> bool:
        """Verify a service is running"""
        try:
            result = subprocess.run(
                ['docker-compose', 'ps', '-q', service_name],
                capture_output=True,
                text=True,
                check=True
            )
            container_id = result.stdout.strip()
            
            if not container_id:
                return False
            
            result = subprocess.run(
                ['docker', 'inspect', '-f', '{{.State.Running}}', container_id],
                capture_output=True,
                text=True,
                check=True
            )
            
            return result.stdout.strip() == 'true'
        except subprocess.CalledProcessError:
            return False
    
    def verify_service_healthy(self, service_name: str) -> bool:
        """Verify a service is healthy"""
        try:
            result = subprocess.run(
                ['docker-compose', 'ps', '-q', service_name],
                capture_output=True,
                text=True,
                check=True
            )
            container_id = result.stdout.strip()
            
            if not container_id:
                return False
            
            result = subprocess.run(
                ['docker', 'inspect', '-f', '{{.State.Health.Status}}', container_id],
                capture_output=True,
                text=True,
                check=False
            )
            
            health_status = result.stdout.strip()
            return health_status == 'healthy' or health_status == ''
        except subprocess.CalledProcessError:
            return False
    
    def check_prometheus_alerts(self):
        """Check Prometheus for active alerts and trigger repairs"""
        try:
            response = requests.get(f"{self.prometheus_url}/api/v1/alerts", timeout=5)
            if response.status_code == 200:
                data = response.json()
                alerts = data.get('data', {}).get('alerts', [])
                
                for alert in alerts:
                    if alert['state'] == 'firing':
                        self.handle_prometheus_alert(alert)
        except Exception as e:
            logger.debug(f"Could not check Prometheus alerts: {e}")
    
    def handle_prometheus_alert(self, alert: Dict):
        """Handle a Prometheus alert"""
        alert_name = alert.get('labels', {}).get('alertname')
        service = alert.get('labels', {}).get('service')
        
        logger.warning(f"🚨 Prometheus alert: {alert_name} for service: {service}")
        
        # Trigger appropriate repair
        if service and service in self.service_health:
            health = self.service_health[service]
            self.attempt_repair(health)
    
    def check_resource_usage(self):
        """Check resource usage and trigger repairs if needed"""
        try:
            # Get container stats
            result = subprocess.run(
                ['docker', 'stats', '--no-stream', '--format', '{{.Name}}\t{{.CPUPerc}}\t{{.MemPerc}}'],
                capture_output=True,
                text=True,
                check=True
            )
            
            for line in result.stdout.strip().split('\n'):
                if not line:
                    continue
                
                parts = line.split('\t')
                if len(parts) != 3:
                    continue
                
                container_name, cpu_perc, mem_perc = parts
                
                # Extract service name
                service_name = container_name.replace('threat-detection-', '')
                
                # Check CPU usage
                try:
                    cpu = float(cpu_perc.rstrip('%'))
                    if cpu > 90:
                        logger.warning(f"⚡ High CPU usage for {service_name}: {cpu}%")
                        self.repair_high_cpu(service_name)
                except ValueError:
                    pass
                
                # Check memory usage
                try:
                    mem = float(mem_perc.rstrip('%'))
                    if mem > 90:
                        logger.warning(f"💾 High memory usage for {service_name}: {mem}%")
                        self.repair_high_memory(service_name)
                except ValueError:
                    pass
        except subprocess.CalledProcessError as e:
            logger.debug(f"Could not check resource usage: {e}")
    
    def auto_scale(self):
        """Auto-scale services based on metrics"""
        # This would integrate with Prometheus metrics to scale Celery workers
        # For now, it's a placeholder for future implementation
        pass
    
    def send_alert(self, service: str, message: str):
        """Send alert to monitoring system"""
        logger.error(f"🚨 ALERT: {service} - {message}")
        
        # Send to Alertmanager
        try:
            alert_data = [{
                'labels': {
                    'alertname': 'AutoRepairFailed',
                    'service': service,
                    'severity': 'critical'
                },
                'annotations': {
                    'summary': f'Auto-repair failed for {service}',
                    'description': message
                }
            }]
            
            requests.post(
                f"{self.alertmanager_url}/api/v1/alerts",
                json=alert_data,
                timeout=5
            )
        except Exception as e:
            logger.debug(f"Could not send alert: {e}")
    
    def cleanup_history(self):
        """Clean up old repair history"""
        cutoff = datetime.now() - timedelta(days=7)
        self.repair_history = [
            action for action in self.repair_history
            if action.timestamp > cutoff
        ]
    
    def get_status_report(self) -> Dict:
        """Get current status report"""
        return {
            'timestamp': datetime.now().isoformat(),
            'services': {
                name: asdict(health)
                for name, health in self.service_health.items()
            },
            'recent_repairs': [
                asdict(action)
                for action in self.repair_history[-10:]
            ],
            'failure_counts': dict(self.failure_counts)
        }


if __name__ == '__main__':
    watchdog = AutoRepairWatchdog()
    watchdog.run()

