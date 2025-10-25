#!/usr/bin/env python3
"""
Telegram Error Notifier
Sends all errors, exceptions, and tracebacks to Telegram
"""

import os
import sys
import json
import time
import logging
import traceback
import requests
import subprocess
from datetime import datetime
from typing import Optional, Dict, List
from pathlib import Path
import re

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
    handlers=[
        logging.FileHandler('/app/logs/telegram_notifier.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


class TelegramNotifier:
    """
    Comprehensive Telegram notification system for all errors
    """
    
    def __init__(self):
        self.bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
        self.chat_id = os.getenv('TELEGRAM_CHAT_ID')
        self.api_url = f"https://api.telegram.org/bot{self.bot_token}"
        
        if not self.bot_token or not self.chat_id:
            logger.error("TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID must be set!")
            sys.exit(1)
        
        self.check_interval = int(os.getenv('NOTIFIER_INTERVAL', '30'))
        self.max_message_length = 4096  # Telegram limit
        self.prometheus_url = os.getenv('PROMETHEUS_URL', 'http://prometheus:9090')
        
        # Track sent errors to avoid duplicates
        self.sent_errors = set()
        self.last_log_positions = {}
        
        # Log files to monitor
        self.log_files = [
            '/app/logs/auto_repair.log',
            '/app/logs/predictive_repair.log',
            '/app/logs/auto_patcher.log',
            '/app/logs/telegram_notifier.log',
            '/var/log/docker.log',
        ]
        
        # Test connection
        self.test_connection()
    
    def test_connection(self):
        """Test Telegram bot connection"""
        try:
            response = requests.get(f"{self.api_url}/getMe", timeout=10)
            if response.status_code == 200:
                bot_info = response.json()
                logger.info(f"✅ Connected to Telegram bot: {bot_info['result']['username']}")
                self.send_message("🤖 Telegram Error Notifier started and monitoring for errors!")
            else:
                logger.error(f"Failed to connect to Telegram: {response.text}")
        except Exception as e:
            logger.error(f"Telegram connection test failed: {e}")
    
    def send_message(self, message: str, parse_mode: str = 'HTML') -> bool:
        """Send message to Telegram"""
        try:
            # Split long messages
            if len(message) > self.max_message_length:
                chunks = self.split_message(message)
                for chunk in chunks:
                    self._send_chunk(chunk, parse_mode)
                    time.sleep(1)  # Avoid rate limiting
                return True
            else:
                return self._send_chunk(message, parse_mode)
        except Exception as e:
            logger.error(f"Failed to send Telegram message: {e}")
            return False
    
    def _send_chunk(self, message: str, parse_mode: str) -> bool:
        """Send a single message chunk"""
        try:
            data = {
                'chat_id': self.chat_id,
                'text': message,
                'parse_mode': parse_mode,
                'disable_web_page_preview': True
            }
            
            response = requests.post(
                f"{self.api_url}/sendMessage",
                json=data,
                timeout=10
            )
            
            if response.status_code == 200:
                return True
            else:
                logger.error(f"Telegram API error: {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to send message chunk: {e}")
            return False
    
    def split_message(self, message: str) -> List[str]:
        """Split long message into chunks"""
        chunks = []
        current_chunk = ""
        
        for line in message.split('\n'):
            if len(current_chunk) + len(line) + 1 > self.max_message_length - 100:
                chunks.append(current_chunk)
                current_chunk = line + '\n'
            else:
                current_chunk += line + '\n'
        
        if current_chunk:
            chunks.append(current_chunk)
        
        return chunks
    
    def format_error_message(self, error_type: str, service: str, error: str, 
                           traceback_str: Optional[str] = None, 
                           context: Optional[Dict] = None) -> str:
        """Format error message for Telegram"""
        
        # Emoji based on error type
        emoji = {
            'docker': '🐳',
            'runtime': '⚠️',
            'application': '🔴',
            'monitoring': '📊',
            'prediction': '🔮',
            'repair': '🔧',
            'patch': '🩹',
            'test': '🧪',
            'network': '🌐',
            'database': '💾',
            'critical': '🚨'
        }.get(error_type.lower(), '❌')
        
        message = f"{emoji} <b>{error_type.upper()} ERROR</b>\n\n"
        message += f"🕐 <b>Time:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        message += f"🏷️ <b>Service:</b> <code>{service}</code>\n"
        message += f"📝 <b>Error:</b>\n<pre>{self.escape_html(error[:500])}</pre>\n"
        
        if traceback_str:
            message += f"\n📋 <b>Traceback:</b>\n<pre>{self.escape_html(traceback_str[:1000])}</pre>\n"
        
        if context:
            message += f"\n📌 <b>Context:</b>\n"
            for key, value in context.items():
                message += f"  • {key}: <code>{value}</code>\n"
        
        message += f"\n🔗 <b>Dashboard:</b> http://localhost:3000"
        
        return message
    
    def escape_html(self, text: str) -> str:
        """Escape HTML special characters"""
        return (text
                .replace('&', '&amp;')
                .replace('<', '&lt;')
                .replace('>', '&gt;'))
    
    def run(self):
        """Main monitoring loop"""
        logger.info("📱 Telegram Error Notifier started")
        logger.info(f"Monitoring interval: {self.check_interval}s")
        
        while True:
            try:
                # Check Docker container errors
                self.check_docker_errors()
                
                # Check log files for errors
                self.check_log_files()
                
                # Check Prometheus alerts
                self.check_prometheus_alerts()
                
                # Check application health
                self.check_application_health()
                
                time.sleep(self.check_interval)
                
            except KeyboardInterrupt:
                logger.info("Notifier stopped by user")
                self.send_message("🛑 Telegram Error Notifier stopped")
                break
            except Exception as e:
                logger.error(f"Notifier error: {e}", exc_info=True)
                time.sleep(self.check_interval)
    
    def check_docker_errors(self):
        """Check for Docker container errors"""
        try:
            # Get container status
            result = subprocess.run(
                ['docker-compose', 'ps', '--format', 'json'],
                capture_output=True,
                text=True,
                check=True
            )
            
            for line in result.stdout.strip().split('\n'):
                if not line:
                    continue
                
                try:
                    container = json.loads(line)
                    service = container.get('Service', 'unknown')
                    status = container.get('State', 'unknown')
                    
                    # Check for error states
                    if status in ['exited', 'dead', 'removing']:
                        error_id = f"docker_{service}_{status}"
                        
                        if error_id not in self.sent_errors:
                            # Get container logs
                            logs = self.get_container_logs(service, lines=50)
                            
                            message = self.format_error_message(
                                error_type='Docker',
                                service=service,
                                error=f"Container is in '{status}' state",
                                traceback_str=logs,
                                context={
                                    'Status': status,
                                    'Container': container.get('Name', 'unknown')
                                }
                            )
                            
                            if self.send_message(message):
                                self.sent_errors.add(error_id)
                    
                    # Check for unhealthy status
                    health = container.get('Health', '')
                    if 'unhealthy' in health.lower():
                        error_id = f"docker_{service}_unhealthy"
                        
                        if error_id not in self.sent_errors:
                            logs = self.get_container_logs(service, lines=50)
                            
                            message = self.format_error_message(
                                error_type='Docker',
                                service=service,
                                error=f"Container is unhealthy",
                                traceback_str=logs,
                                context={'Health': health}
                            )
                            
                            if self.send_message(message):
                                self.sent_errors.add(error_id)
                
                except json.JSONDecodeError:
                    continue
                    
        except subprocess.CalledProcessError as e:
            logger.debug(f"Could not check Docker status: {e}")
    
    def get_container_logs(self, service: str, lines: int = 50) -> str:
        """Get recent container logs"""
        try:
            result = subprocess.run(
                ['docker-compose', 'logs', '--tail', str(lines), service],
                capture_output=True,
                text=True,
                check=True
            )
            return result.stdout
        except subprocess.CalledProcessError:
            return "Could not retrieve logs"
    
    def check_log_files(self):
        """Check log files for errors"""
        for log_file in self.log_files:
            if not os.path.exists(log_file):
                continue
            
            try:
                # Get last read position
                last_pos = self.last_log_positions.get(log_file, 0)
                
                with open(log_file, 'r') as f:
                    # Seek to last position
                    f.seek(last_pos)
                    
                    # Read new lines
                    new_lines = f.readlines()
                    
                    # Update position
                    self.last_log_positions[log_file] = f.tell()
                
                # Check for errors
                self.parse_log_errors(log_file, new_lines)
                
            except Exception as e:
                logger.debug(f"Could not read log file {log_file}: {e}")
    
    def parse_log_errors(self, log_file: str, lines: List[str]):
        """Parse log lines for errors"""
        error_patterns = [
            (r'ERROR', 'Application'),
            (r'CRITICAL', 'Critical'),
            (r'Exception', 'Runtime'),
            (r'Traceback', 'Runtime'),
            (r'Failed', 'Application'),
            (r'failed', 'Application'),
            (r'error:', 'Application'),
            (r'Error:', 'Application'),
        ]
        
        current_error = []
        in_traceback = False
        
        for line in lines:
            # Check if line contains error
            is_error = False
            error_type = 'Application'
            
            for pattern, etype in error_patterns:
                if re.search(pattern, line, re.IGNORECASE):
                    is_error = True
                    error_type = etype
                    break
            
            if is_error or in_traceback:
                current_error.append(line)
                
                # Check if we're in a traceback
                if 'Traceback' in line:
                    in_traceback = True
                elif in_traceback and line.strip() and not line.startswith(' '):
                    # End of traceback
                    in_traceback = False
                    self.send_log_error(log_file, current_error, error_type)
                    current_error = []
            
            # Send standalone errors
            elif current_error and not in_traceback:
                self.send_log_error(log_file, current_error, error_type)
                current_error = []
    
    def send_log_error(self, log_file: str, error_lines: List[str], error_type: str):
        """Send log error to Telegram"""
        if not error_lines:
            return
        
        error_text = ''.join(error_lines)
        error_id = f"log_{log_file}_{hash(error_text)}"
        
        # Avoid duplicates
        if error_id in self.sent_errors:
            return
        
        # Extract error message and traceback
        error_msg = error_lines[0].strip()
        traceback_str = ''.join(error_lines[1:]) if len(error_lines) > 1 else None
        
        service = Path(log_file).stem
        
        message = self.format_error_message(
            error_type=error_type,
            service=service,
            error=error_msg,
            traceback_str=traceback_str,
            context={'Log File': log_file}
        )
        
        if self.send_message(message):
            self.sent_errors.add(error_id)
            
            # Limit sent_errors size
            if len(self.sent_errors) > 1000:
                self.sent_errors = set(list(self.sent_errors)[-500:])
    
    def check_prometheus_alerts(self):
        """Check Prometheus for firing alerts"""
        try:
            response = requests.get(
                f"{self.prometheus_url}/api/v1/alerts",
                timeout=5
            )
            
            if response.status_code == 200:
                data = response.json()
                alerts = data.get('data', {}).get('alerts', [])
                
                for alert in alerts:
                    if alert['state'] == 'firing':
                        alert_name = alert.get('labels', {}).get('alertname', 'Unknown')
                        service = alert.get('labels', {}).get('service', 'Unknown')
                        severity = alert.get('labels', {}).get('severity', 'warning')
                        
                        error_id = f"alert_{alert_name}_{service}"
                        
                        if error_id not in self.sent_errors:
                            annotations = alert.get('annotations', {})
                            summary = annotations.get('summary', 'No summary')
                            description = annotations.get('description', 'No description')
                            
                            message = self.format_error_message(
                                error_type='Monitoring',
                                service=service,
                                error=f"Alert: {alert_name}\n{summary}",
                                traceback_str=description,
                                context={
                                    'Severity': severity,
                                    'Alert': alert_name,
                                    'State': 'FIRING'
                                }
                            )
                            
                            if self.send_message(message):
                                self.sent_errors.add(error_id)
                                
        except Exception as e:
            logger.debug(f"Could not check Prometheus alerts: {e}")
    
    def check_application_health(self):
        """Check application health endpoints"""
        health_checks = [
            ('Dashboard', 'http://dashboard:8050/'),
            ('Prometheus', 'http://prometheus:9090/-/healthy'),
            ('Grafana', 'http://grafana:3000/api/health'),
            ('Loki', 'http://loki:3100/ready'),
        ]
        
        for service, url in health_checks:
            try:
                response = requests.get(url, timeout=5)
                
                if response.status_code >= 500:
                    error_id = f"health_{service}_{response.status_code}"
                    
                    if error_id not in self.sent_errors:
                        message = self.format_error_message(
                            error_type='Application',
                            service=service,
                            error=f"Health check failed with status {response.status_code}",
                            traceback_str=response.text[:500],
                            context={
                                'URL': url,
                                'Status Code': response.status_code
                            }
                        )
                        
                        if self.send_message(message):
                            self.sent_errors.add(error_id)
                            
            except requests.exceptions.RequestException as e:
                error_id = f"health_{service}_connection"
                
                if error_id not in self.sent_errors:
                    message = self.format_error_message(
                        error_type='Network',
                        service=service,
                        error=f"Cannot connect to {service}",
                        traceback_str=str(e),
                        context={'URL': url}
                    )
                    
                    if self.send_message(message):
                        self.sent_errors.add(error_id)
                        
                        # Clear after some time to allow re-notification
                        time.sleep(300)  # 5 minutes
                        self.sent_errors.discard(error_id)


def setup_exception_handler(notifier: TelegramNotifier):
    """Setup global exception handler"""
    def exception_handler(exc_type, exc_value, exc_traceback):
        """Handle uncaught exceptions"""
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return
        
        # Format traceback
        tb_lines = traceback.format_exception(exc_type, exc_value, exc_traceback)
        tb_str = ''.join(tb_lines)
        
        # Send to Telegram
        message = notifier.format_error_message(
            error_type='Critical',
            service='Telegram Notifier',
            error=f"{exc_type.__name__}: {exc_value}",
            traceback_str=tb_str,
            context={'Type': 'Uncaught Exception'}
        )
        
        notifier.send_message(message)
        
        # Call default handler
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
    
    sys.excepthook = exception_handler


if __name__ == '__main__':
    notifier = TelegramNotifier()
    setup_exception_handler(notifier)
    notifier.run()

