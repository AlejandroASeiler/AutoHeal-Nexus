#!/usr/bin/env python3
"""
Predictive Repair Agent
ML/RL-based system that predicts failures and automatically patches issues
"""

import os
import sys
import json
import time
import pickle
import logging
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
from collections import deque
import requests
import subprocess

# ML/RL imports
try:
    from sklearn.ensemble import RandomForestClassifier, IsolationForest
    from sklearn.preprocessing import StandardScaler
    import joblib
except ImportError:
    print("Installing required ML packages...")
    subprocess.run([sys.executable, '-m', 'pip', 'install', 'scikit-learn', 'joblib'], check=True)
    from sklearn.ensemble import RandomForestClassifier, IsolationForest
    from sklearn.preprocessing import StandardScaler
    import joblib

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
    handlers=[
        logging.FileHandler('/app/logs/predictive_repair.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


@dataclass
class ServiceMetrics:
    """Service metrics snapshot"""
    timestamp: datetime
    service: str
    cpu_usage: float
    memory_usage: float
    disk_usage: float
    network_errors: int
    restart_count: int
    health_status: str
    response_time: float
    error_rate: float
    request_rate: float
    
    def to_features(self) -> np.ndarray:
        """Convert to feature vector for ML"""
        return np.array([
            self.cpu_usage,
            self.memory_usage,
            self.disk_usage,
            self.network_errors,
            self.restart_count,
            1 if self.health_status == 'unhealthy' else 0,
            self.response_time,
            self.error_rate,
            self.request_rate
        ])


@dataclass
class FailurePrediction:
    """Failure prediction result"""
    service: str
    probability: float
    predicted_failure_time: datetime
    recommended_action: str
    confidence: float
    features_importance: Dict[str, float]


@dataclass
class RepairAction:
    """Repair action with outcome"""
    timestamp: datetime
    service: str
    action: str
    metrics_before: ServiceMetrics
    metrics_after: Optional[ServiceMetrics]
    success: bool
    reward: float


class PredictiveRepairAgent:
    """
    ML/RL-based predictive repair agent
    Learns from past failures and metrics to predict and prevent issues
    """
    
    def __init__(self):
        self.prometheus_url = os.getenv('PROMETHEUS_URL', 'http://prometheus:9090')
        self.check_interval = int(os.getenv('PREDICTOR_INTERVAL', '60'))
        self.prediction_horizon = int(os.getenv('PREDICTION_HORIZON', '300'))  # 5 minutes
        self.model_path = '/app/models/predictive_repair'
        self.data_path = '/app/data/repair_history.json'
        
        # ML models
        self.failure_predictor: Optional[RandomForestClassifier] = None
        self.anomaly_detector: Optional[IsolationForest] = None
        self.scaler: Optional[StandardScaler] = None
        
        # RL components
        self.q_table: Dict[Tuple[str, str], float] = {}  # (state, action) -> Q-value
        self.learning_rate = 0.1
        self.discount_factor = 0.95
        self.epsilon = 0.1  # Exploration rate
        
        # Historical data
        self.metrics_history: deque = deque(maxlen=10000)
        self.repair_history: List[RepairAction] = []
        self.failure_history: List[Dict] = []
        
        # Actions
        self.actions = [
            'restart',
            'scale_up',
            'scale_down',
            'clear_cache',
            'optimize_config',
            'rollback',
            'no_action'
        ]
        
        # Load or initialize models
        self.load_models()
        self.load_history()
    
    def run(self):
        """Main prediction loop"""
        logger.info("🤖 Predictive Repair Agent started")
        logger.info(f"Prediction horizon: {self.prediction_horizon}s")
        
        while True:
            try:
                # Collect current metrics
                metrics = self.collect_metrics()
                
                # Store metrics
                for metric in metrics:
                    self.metrics_history.append(metric)
                
                # Predict failures
                predictions = self.predict_failures(metrics)
                
                # Take preventive actions
                for prediction in predictions:
                    if prediction.probability > 0.7:  # High probability threshold
                        self.take_preventive_action(prediction)
                
                # Detect anomalies
                anomalies = self.detect_anomalies(metrics)
                for anomaly in anomalies:
                    self.handle_anomaly(anomaly)
                
                # Train models periodically
                if len(self.metrics_history) % 100 == 0:
                    self.train_models()
                
                # Save models and history
                if len(self.metrics_history) % 500 == 0:
                    self.save_models()
                    self.save_history()
                
                time.sleep(self.check_interval)
                
            except KeyboardInterrupt:
                logger.info("Predictive agent stopped")
                self.save_models()
                self.save_history()
                break
            except Exception as e:
                logger.error(f"Prediction error: {e}", exc_info=True)
                time.sleep(self.check_interval)
    
    def collect_metrics(self) -> List[ServiceMetrics]:
        """Collect current metrics from Prometheus"""
        metrics = []
        services = ['threat-detection-app', 'dashboard', 'postgres', 'redis', 
                   'prometheus', 'grafana', 'celery-worker']
        
        for service in services:
            try:
                metric = ServiceMetrics(
                    timestamp=datetime.now(),
                    service=service,
                    cpu_usage=self.get_prometheus_metric(
                        f'rate(container_cpu_usage_seconds_total{{container_label_com_docker_compose_service="{service}"}}[1m])'
                    ),
                    memory_usage=self.get_prometheus_metric(
                        f'container_memory_usage_bytes{{container_label_com_docker_compose_service="{service}"}} / container_spec_memory_limit_bytes'
                    ),
                    disk_usage=self.get_prometheus_metric(
                        'node_filesystem_avail_bytes / node_filesystem_size_bytes'
                    ),
                    network_errors=int(self.get_prometheus_metric(
                        f'rate(container_network_receive_errors_total{{container_label_com_docker_compose_service="{service}"}}[5m])'
                    ) or 0),
                    restart_count=int(self.get_prometheus_metric(
                        f'container_restart_count{{container_label_com_docker_compose_service="{service}"}}'
                    ) or 0),
                    health_status=self.get_health_status(service),
                    response_time=self.get_prometheus_metric(
                        f'histogram_quantile(0.95, rate(http_request_duration_seconds_bucket{{service="{service}"}}[5m]))'
                    ),
                    error_rate=self.get_prometheus_metric(
                        f'rate(http_requests_total{{service="{service}", status=~"5.."}}[5m])'
                    ),
                    request_rate=self.get_prometheus_metric(
                        f'rate(http_requests_total{{service="{service}"}}[5m])'
                    )
                )
                metrics.append(metric)
            except Exception as e:
                logger.debug(f"Could not collect metrics for {service}: {e}")
        
        return metrics
    
    def get_prometheus_metric(self, query: str) -> float:
        """Query Prometheus for a metric"""
        try:
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
            return 0.0
        except Exception as e:
            logger.debug(f"Prometheus query failed: {e}")
            return 0.0
    
    def get_health_status(self, service: str) -> str:
        """Get service health status"""
        try:
            result = subprocess.run(
                ['docker-compose', 'ps', '-q', service],
                capture_output=True,
                text=True,
                check=True
            )
            container_id = result.stdout.strip()
            
            if not container_id:
                return 'down'
            
            result = subprocess.run(
                ['docker', 'inspect', '-f', '{{.State.Health.Status}}', container_id],
                capture_output=True,
                text=True,
                check=False
            )
            
            health = result.stdout.strip()
            return health if health else 'unknown'
        except:
            return 'unknown'
    
    def predict_failures(self, current_metrics: List[ServiceMetrics]) -> List[FailurePrediction]:
        """Predict potential failures using ML"""
        predictions = []
        
        if not self.failure_predictor or not self.scaler:
            return predictions
        
        for metric in current_metrics:
            try:
                # Prepare features
                features = metric.to_features().reshape(1, -1)
                features_scaled = self.scaler.transform(features)
                
                # Predict failure probability
                failure_prob = self.failure_predictor.predict_proba(features_scaled)[0][1]
                
                # Get feature importance
                feature_names = ['cpu', 'memory', 'disk', 'network_errors', 'restarts',
                               'health', 'response_time', 'error_rate', 'request_rate']
                importance = dict(zip(feature_names, self.failure_predictor.feature_importances_))
                
                # Determine recommended action using RL
                state = self.get_state(metric)
                action = self.select_action(state)
                
                # Calculate predicted failure time
                if failure_prob > 0.5:
                    # Estimate time to failure based on trend
                    time_to_failure = self.estimate_time_to_failure(metric)
                    predicted_time = datetime.now() + timedelta(seconds=time_to_failure)
                else:
                    predicted_time = datetime.now() + timedelta(hours=24)
                
                prediction = FailurePrediction(
                    service=metric.service,
                    probability=failure_prob,
                    predicted_failure_time=predicted_time,
                    recommended_action=action,
                    confidence=max(failure_prob, 1 - failure_prob),
                    features_importance=importance
                )
                
                predictions.append(prediction)
                
                # Log high-probability predictions
                if failure_prob > 0.7:
                    logger.warning(
                        f"🔮 High failure probability for {metric.service}: "
                        f"{failure_prob:.2%} - Recommended: {action}"
                    )
                
            except Exception as e:
                logger.debug(f"Prediction failed for {metric.service}: {e}")
        
        return predictions
    
    def detect_anomalies(self, current_metrics: List[ServiceMetrics]) -> List[ServiceMetrics]:
        """Detect anomalies using Isolation Forest"""
        anomalies = []
        
        if not self.anomaly_detector or not self.scaler:
            return anomalies
        
        for metric in current_metrics:
            try:
                features = metric.to_features().reshape(1, -1)
                features_scaled = self.scaler.transform(features)
                
                # -1 for anomaly, 1 for normal
                prediction = self.anomaly_detector.predict(features_scaled)[0]
                
                if prediction == -1:
                    logger.warning(f"🚨 Anomaly detected in {metric.service}")
                    anomalies.append(metric)
            except Exception as e:
                logger.debug(f"Anomaly detection failed: {e}")
        
        return anomalies
    
    def take_preventive_action(self, prediction: FailurePrediction):
        """Take preventive action based on prediction"""
        logger.info(
            f"🛡️  Taking preventive action for {prediction.service}: "
            f"{prediction.recommended_action} (probability: {prediction.probability:.2%})"
        )
        
        # Get current metrics
        current_metrics = [m for m in self.collect_metrics() if m.service == prediction.service]
        if not current_metrics:
            return
        
        metrics_before = current_metrics[0]
        
        # Execute action
        success = self.execute_action(prediction.service, prediction.recommended_action)
        
        # Wait and collect metrics after action
        time.sleep(30)
        metrics_after_list = [m for m in self.collect_metrics() if m.service == prediction.service]
        metrics_after = metrics_after_list[0] if metrics_after_list else None
        
        # Calculate reward
        reward = self.calculate_reward(metrics_before, metrics_after, success)
        
        # Record action
        action = RepairAction(
            timestamp=datetime.now(),
            service=prediction.service,
            action=prediction.recommended_action,
            metrics_before=metrics_before,
            metrics_after=metrics_after,
            success=success,
            reward=reward
        )
        self.repair_history.append(action)
        
        # Update Q-table (RL learning)
        state = self.get_state(metrics_before)
        self.update_q_value(state, prediction.recommended_action, reward)
        
        logger.info(
            f"{'✅' if success else '❌'} Preventive action completed: "
            f"{prediction.recommended_action} (reward: {reward:.2f})"
        )
    
    def handle_anomaly(self, metric: ServiceMetrics):
        """Handle detected anomaly"""
        logger.warning(f"🔧 Handling anomaly in {metric.service}")
        
        # Use RL to select best action
        state = self.get_state(metric)
        action = self.select_action(state)
        
        # Execute action
        success = self.execute_action(metric.service, action)
        
        if success:
            logger.info(f"✅ Anomaly resolved in {metric.service} using {action}")
        else:
            logger.error(f"❌ Failed to resolve anomaly in {metric.service}")
    
    def execute_action(self, service: str, action: str) -> bool:
        """Execute a repair action"""
        try:
            if action == 'restart':
                subprocess.run(['docker-compose', 'restart', service], check=True)
                return True
            
            elif action == 'scale_up':
                current_scale = self.get_service_scale(service)
                subprocess.run(
                    ['docker-compose', 'up', '-d', '--scale', f'{service}={current_scale + 1}'],
                    check=True
                )
                return True
            
            elif action == 'scale_down':
                current_scale = self.get_service_scale(service)
                if current_scale > 1:
                    subprocess.run(
                        ['docker-compose', 'up', '-d', '--scale', f'{service}={current_scale - 1}'],
                        check=True
                    )
                    return True
                return False
            
            elif action == 'clear_cache':
                if service == 'redis':
                    subprocess.run(
                        ['docker-compose', 'exec', '-T', 'redis', 'redis-cli', 'FLUSHDB'],
                        check=True
                    )
                    return True
                return False
            
            elif action == 'optimize_config':
                # Placeholder for configuration optimization
                logger.info(f"Optimizing configuration for {service}")
                return True
            
            elif action == 'rollback':
                # Placeholder for rollback logic
                logger.info(f"Rolling back {service}")
                return True
            
            elif action == 'no_action':
                return True
            
            return False
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Action {action} failed for {service}: {e}")
            return False
    
    def get_service_scale(self, service: str) -> int:
        """Get current service scale"""
        try:
            result = subprocess.run(
                ['docker-compose', 'ps', '-q', service],
                capture_output=True,
                text=True,
                check=True
            )
            return len([line for line in result.stdout.strip().split('\n') if line])
        except:
            return 1
    
    def get_state(self, metric: ServiceMetrics) -> str:
        """Convert metrics to discrete state for RL"""
        # Discretize continuous values
        cpu_state = 'high' if metric.cpu_usage > 0.7 else 'medium' if metric.cpu_usage > 0.3 else 'low'
        mem_state = 'high' if metric.memory_usage > 0.7 else 'medium' if metric.memory_usage > 0.3 else 'low'
        health_state = 'unhealthy' if metric.health_status == 'unhealthy' else 'healthy'
        
        return f"{metric.service}_{cpu_state}_{mem_state}_{health_state}"
    
    def select_action(self, state: str) -> str:
        """Select action using epsilon-greedy policy"""
        # Exploration
        if np.random.random() < self.epsilon:
            return np.random.choice(self.actions)
        
        # Exploitation - select best action
        q_values = {action: self.q_table.get((state, action), 0.0) for action in self.actions}
        return max(q_values, key=q_values.get)
    
    def update_q_value(self, state: str, action: str, reward: float):
        """Update Q-value using Q-learning"""
        current_q = self.q_table.get((state, action), 0.0)
        
        # Q(s,a) = Q(s,a) + α[R + γ max Q(s',a') - Q(s,a)]
        # Simplified: Q(s,a) = Q(s,a) + α[R - Q(s,a)]
        new_q = current_q + self.learning_rate * (reward - current_q)
        
        self.q_table[(state, action)] = new_q
    
    def calculate_reward(self, before: ServiceMetrics, after: Optional[ServiceMetrics], 
                        success: bool) -> float:
        """Calculate reward for RL"""
        if not success:
            return -10.0
        
        if not after:
            return 0.0
        
        reward = 0.0
        
        # Reward for improving metrics
        if after.cpu_usage < before.cpu_usage:
            reward += 5.0 * (before.cpu_usage - after.cpu_usage)
        
        if after.memory_usage < before.memory_usage:
            reward += 5.0 * (before.memory_usage - after.memory_usage)
        
        if after.error_rate < before.error_rate:
            reward += 10.0 * (before.error_rate - after.error_rate)
        
        if after.response_time < before.response_time:
            reward += 3.0 * (before.response_time - after.response_time)
        
        # Reward for maintaining health
        if after.health_status == 'healthy':
            reward += 5.0
        
        # Penalty for making things worse
        if after.cpu_usage > before.cpu_usage:
            reward -= 3.0
        
        if after.memory_usage > before.memory_usage:
            reward -= 3.0
        
        return reward
    
    def estimate_time_to_failure(self, metric: ServiceMetrics) -> int:
        """Estimate time to failure in seconds"""
        # Simple heuristic based on current metrics
        if metric.cpu_usage > 0.9:
            return 60  # 1 minute
        elif metric.cpu_usage > 0.8:
            return 300  # 5 minutes
        elif metric.memory_usage > 0.9:
            return 120  # 2 minutes
        elif metric.error_rate > 0.5:
            return 180  # 3 minutes
        else:
            return 600  # 10 minutes
    
    def train_models(self):
        """Train ML models on historical data"""
        if len(self.metrics_history) < 100:
            logger.info("Not enough data to train models")
            return
        
        logger.info("🎓 Training predictive models...")
        
        try:
            # Prepare training data
            X = []
            y = []
            
            for i, metric in enumerate(list(self.metrics_history)[:-10]):
                X.append(metric.to_features())
                
                # Label: did service fail in next 5 minutes?
                future_metrics = list(self.metrics_history)[i+1:i+6]
                failed = any(
                    m.service == metric.service and 
                    (m.health_status == 'unhealthy' or m.restart_count > metric.restart_count)
                    for m in future_metrics
                )
                y.append(1 if failed else 0)
            
            X = np.array(X)
            y = np.array(y)
            
            # Train scaler
            self.scaler = StandardScaler()
            X_scaled = self.scaler.fit_transform(X)
            
            # Train failure predictor
            self.failure_predictor = RandomForestClassifier(
                n_estimators=100,
                max_depth=10,
                random_state=42
            )
            self.failure_predictor.fit(X_scaled, y)
            
            # Train anomaly detector
            self.anomaly_detector = IsolationForest(
                contamination=0.1,
                random_state=42
            )
            self.anomaly_detector.fit(X_scaled)
            
            logger.info("✅ Models trained successfully")
            
        except Exception as e:
            logger.error(f"Model training failed: {e}", exc_info=True)
    
    def load_models(self):
        """Load trained models"""
        try:
            os.makedirs(self.model_path, exist_ok=True)
            
            predictor_path = f"{self.model_path}/failure_predictor.pkl"
            anomaly_path = f"{self.model_path}/anomaly_detector.pkl"
            scaler_path = f"{self.model_path}/scaler.pkl"
            qtable_path = f"{self.model_path}/q_table.pkl"
            
            if os.path.exists(predictor_path):
                self.failure_predictor = joblib.load(predictor_path)
                logger.info("Loaded failure predictor")
            
            if os.path.exists(anomaly_path):
                self.anomaly_detector = joblib.load(anomaly_path)
                logger.info("Loaded anomaly detector")
            
            if os.path.exists(scaler_path):
                self.scaler = joblib.load(scaler_path)
                logger.info("Loaded scaler")
            
            if os.path.exists(qtable_path):
                self.q_table = joblib.load(qtable_path)
                logger.info(f"Loaded Q-table with {len(self.q_table)} entries")
            
        except Exception as e:
            logger.warning(f"Could not load models: {e}")
    
    def save_models(self):
        """Save trained models"""
        try:
            os.makedirs(self.model_path, exist_ok=True)
            
            if self.failure_predictor:
                joblib.dump(self.failure_predictor, f"{self.model_path}/failure_predictor.pkl")
            
            if self.anomaly_detector:
                joblib.dump(self.anomaly_detector, f"{self.model_path}/anomaly_detector.pkl")
            
            if self.scaler:
                joblib.dump(self.scaler, f"{self.model_path}/scaler.pkl")
            
            if self.q_table:
                joblib.dump(self.q_table, f"{self.model_path}/q_table.pkl")
            
            logger.info("✅ Models saved")
            
        except Exception as e:
            logger.error(f"Could not save models: {e}")
    
    def load_history(self):
        """Load historical data"""
        try:
            if os.path.exists(self.data_path):
                with open(self.data_path, 'r') as f:
                    data = json.load(f)
                    self.failure_history = data.get('failures', [])
                    logger.info(f"Loaded {len(self.failure_history)} historical failures")
        except Exception as e:
            logger.warning(f"Could not load history: {e}")
    
    def save_history(self):
        """Save historical data"""
        try:
            os.makedirs(os.path.dirname(self.data_path), exist_ok=True)
            
            data = {
                'failures': self.failure_history[-1000:],  # Keep last 1000
                'last_updated': datetime.now().isoformat()
            }
            
            with open(self.data_path, 'w') as f:
                json.dump(data, f, indent=2)
            
            logger.info("✅ History saved")
            
        except Exception as e:
            logger.error(f"Could not save history: {e}")


if __name__ == '__main__':
    agent = PredictiveRepairAgent()
    agent.run()

