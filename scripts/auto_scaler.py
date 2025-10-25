#!/usr/bin/env python3
"""
Auto-Scaler for Docker Compose Services
Scale services based on metrics (CPU, memory, queue depth)
"""

import os
import sys
import time
import logging
import subprocess
import requests
from datetime import datetime
from typing import Dict, Optional

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s'
)
logger = logging.getLogger(__name__)


class AutoScaler:
    """Auto-scale Docker Compose services based on metrics"""
    
    def __init__(self):
        self.prometheus_url = os.getenv('PROMETHEUS_URL', 'http://prometheus:9090')
        self.check_interval = int(os.getenv('SCALER_INTERVAL', '60'))
        
        # Scaling configuration
        self.scaling_config = {
            'celery-worker': {
                'min_replicas': 1,
                'max_replicas': 5,
                'scale_up_threshold': 0.8,  # 80% CPU
                'scale_down_threshold': 0.2,  # 20% CPU
                'metric': 'cpu_usage'
            }
        }
    
    def run(self):
        """Main auto-scaler loop"""
        logger.info("📊 Auto-Scaler started")
        
        while True:
            try:
                self.check_and_scale()
                time.sleep(self.check_interval)
            except KeyboardInterrupt:
                logger.info("Auto-Scaler stopped")
                break
            except Exception as e:
                logger.error(f"Scaler error: {e}", exc_info=True)
                time.sleep(self.check_interval)
    
    def check_and_scale(self):
        """Check metrics and scale services"""
        for service, config in self.scaling_config.items():
            current_replicas = self.get_replica_count(service)
            metric_value = self.get_metric_value(service, config['metric'])
            
            if metric_value is None:
                continue
            
            # Determine if scaling is needed
            if metric_value > config['scale_up_threshold']:
                if current_replicas < config['max_replicas']:
                    self.scale_up(service, current_replicas + 1)
            elif metric_value < config['scale_down_threshold']:
                if current_replicas > config['min_replicas']:
                    self.scale_down(service, current_replicas - 1)
    
    def get_replica_count(self, service: str) -> int:
        """Get current replica count for a service"""
        try:
            result = subprocess.run(
                ['docker-compose', 'ps', '-q', service],
                capture_output=True,
                text=True,
                check=True
            )
            return len([line for line in result.stdout.strip().split('\n') if line])
        except subprocess.CalledProcessError:
            return 0
    
    def get_metric_value(self, service: str, metric: str) -> Optional[float]:
        """Get metric value from Prometheus"""
        try:
            query = f'container_cpu_usage_seconds_total{{container_label_com_docker_compose_service="{service}"}}'
            response = requests.get(
                f"{self.prometheus_url}/api/v1/query",
                params={'query': query},
                timeout=5
            )
            
            if response.status_code == 200:
                data = response.json()
                results = data.get('data', {}).get('result', [])
                if results:
                    return float(results[0]['value'][1])
            return None
        except Exception as e:
            logger.debug(f"Could not get metric: {e}")
            return None
    
    def scale_up(self, service: str, replicas: int):
        """Scale up a service"""
        try:
            logger.info(f"📈 Scaling up {service} to {replicas} replicas")
            subprocess.run(
                ['docker-compose', 'up', '-d', '--scale', f'{service}={replicas}'],
                check=True
            )
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to scale up {service}: {e}")
    
    def scale_down(self, service: str, replicas: int):
        """Scale down a service"""
        try:
            logger.info(f"📉 Scaling down {service} to {replicas} replicas")
            subprocess.run(
                ['docker-compose', 'up', '-d', '--scale', f'{service}={replicas}'],
                check=True
            )
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to scale down {service}: {e}")


if __name__ == '__main__':
    scaler = AutoScaler()
    scaler.run()

