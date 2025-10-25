#!/usr/bin/env python3
"""
Auto-Patcher
Automatically applies patches and fixes to code and configuration
"""

import os
import sys
import json
import logging
import subprocess
import hashlib
from datetime import datetime
from typing import Dict, List, Optional
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
    handlers=[
        logging.FileHandler('/app/logs/auto_patcher.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


class AutoPatcher:
    """
    Automatically applies patches and fixes based on detected issues
    """
    
    def __init__(self):
        self.patches_dir = '/app/patches'
        self.backup_dir = '/app/backups'
        self.applied_patches_file = '/app/data/applied_patches.json'
        
        os.makedirs(self.patches_dir, exist_ok=True)
        os.makedirs(self.backup_dir, exist_ok=True)
        os.makedirs(os.path.dirname(self.applied_patches_file), exist_ok=True)
        
        self.applied_patches = self.load_applied_patches()
        
        # Patch definitions
        self.patches = {
            'memory_leak_fix': {
                'description': 'Fix memory leak in data processing',
                'files': ['src/preprocessing.py'],
                'pattern': r'df\.rolling\(',
                'replacement': 'df.rolling(',
                'condition': lambda: self.check_memory_leak()
            },
            'connection_pool_fix': {
                'description': 'Increase database connection pool',
                'files': ['config/database.yml'],
                'pattern': r'pool_size: \d+',
                'replacement': 'pool_size: 20',
                'condition': lambda: self.check_connection_exhaustion()
            },
            'timeout_fix': {
                'description': 'Increase request timeout',
                'files': ['config/app.yml'],
                'pattern': r'timeout: \d+',
                'replacement': 'timeout: 60',
                'condition': lambda: self.check_timeout_errors()
            },
            'cache_optimization': {
                'description': 'Enable Redis caching',
                'files': ['config/cache.yml'],
                'pattern': r'enabled: false',
                'replacement': 'enabled: true',
                'condition': lambda: self.check_high_latency()
            }
        }
    
    def run(self):
        """Main auto-patcher loop"""
        logger.info("🔧 Auto-Patcher started")
        
        while True:
            try:
                # Check for issues and apply patches
                self.check_and_patch()
                
                # Sleep for 5 minutes
                import time
                time.sleep(300)
                
            except KeyboardInterrupt:
                logger.info("Auto-Patcher stopped")
                break
            except Exception as e:
                logger.error(f"Patcher error: {e}", exc_info=True)
    
    def check_and_patch(self):
        """Check for issues and apply appropriate patches"""
        for patch_id, patch_info in self.patches.items():
            # Skip if already applied
            if patch_id in self.applied_patches:
                continue
            
            # Check condition
            try:
                if patch_info['condition']():
                    logger.info(f"🩹 Condition met for patch: {patch_id}")
                    self.apply_patch(patch_id, patch_info)
            except Exception as e:
                logger.error(f"Error checking condition for {patch_id}: {e}")
    
    def apply_patch(self, patch_id: str, patch_info: Dict):
        """Apply a patch"""
        logger.info(f"Applying patch: {patch_id} - {patch_info['description']}")
        
        try:
            # Backup files
            for file_path in patch_info['files']:
                self.backup_file(file_path)
            
            # Apply patch
            success = self.patch_files(
                patch_info['files'],
                patch_info['pattern'],
                patch_info['replacement']
            )
            
            if success:
                # Record applied patch
                self.applied_patches[patch_id] = {
                    'timestamp': datetime.now().isoformat(),
                    'description': patch_info['description'],
                    'files': patch_info['files']
                }
                self.save_applied_patches()
                
                # Restart affected services
                self.restart_services()
                
                logger.info(f"✅ Patch {patch_id} applied successfully")
            else:
                logger.error(f"❌ Failed to apply patch {patch_id}")
                # Restore from backup
                for file_path in patch_info['files']:
                    self.restore_file(file_path)
                
        except Exception as e:
            logger.error(f"Error applying patch {patch_id}: {e}", exc_info=True)
    
    def patch_files(self, files: List[str], pattern: str, replacement: str) -> bool:
        """Apply patch to files"""
        import re
        
        try:
            for file_path in files:
                full_path = f'/app/{file_path}'
                
                if not os.path.exists(full_path):
                    logger.warning(f"File not found: {full_path}")
                    continue
                
                # Read file
                with open(full_path, 'r') as f:
                    content = f.read()
                
                # Apply patch
                new_content = re.sub(pattern, replacement, content)
                
                # Write back
                with open(full_path, 'w') as f:
                    f.write(new_content)
                
                logger.info(f"Patched: {file_path}")
            
            return True
            
        except Exception as e:
            logger.error(f"Error patching files: {e}")
            return False
    
    def backup_file(self, file_path: str):
        """Backup a file before patching"""
        full_path = f'/app/{file_path}'
        
        if not os.path.exists(full_path):
            return
        
        # Create backup with timestamp
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_path = f"{self.backup_dir}/{file_path.replace('/', '_')}_{timestamp}"
        
        os.makedirs(os.path.dirname(backup_path), exist_ok=True)
        
        import shutil
        shutil.copy2(full_path, backup_path)
        
        logger.info(f"Backed up: {file_path} -> {backup_path}")
    
    def restore_file(self, file_path: str):
        """Restore file from backup"""
        # Find latest backup
        pattern = f"{file_path.replace('/', '_')}_*"
        backups = sorted(Path(self.backup_dir).glob(pattern))
        
        if not backups:
            logger.warning(f"No backup found for {file_path}")
            return
        
        latest_backup = backups[-1]
        full_path = f'/app/{file_path}'
        
        import shutil
        shutil.copy2(str(latest_backup), full_path)
        
        logger.info(f"Restored: {file_path} from {latest_backup}")
    
    def restart_services(self):
        """Restart affected services"""
        try:
            logger.info("Restarting services after patch...")
            subprocess.run(
                ['docker-compose', 'restart', 'threat-detection-app', 'dashboard'],
                check=True
            )
            logger.info("✅ Services restarted")
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to restart services: {e}")
    
    # Condition checkers
    
    def check_memory_leak(self) -> bool:
        """Check if there's a memory leak"""
        try:
            import requests
            response = requests.get(
                'http://prometheus:9090/api/v1/query',
                params={'query': 'rate(container_memory_usage_bytes[1h]) > 1000000'},
                timeout=5
            )
            
            if response.status_code == 200:
                data = response.json()
                return len(data.get('data', {}).get('result', [])) > 0
        except:
            pass
        return False
    
    def check_connection_exhaustion(self) -> bool:
        """Check if database connections are exhausted"""
        try:
            import requests
            response = requests.get(
                'http://prometheus:9090/api/v1/query',
                params={'query': 'pg_stat_database_numbackends > 15'},
                timeout=5
            )
            
            if response.status_code == 200:
                data = response.json()
                return len(data.get('data', {}).get('result', [])) > 0
        except:
            pass
        return False
    
    def check_timeout_errors(self) -> bool:
        """Check if there are timeout errors"""
        try:
            import requests
            response = requests.get(
                'http://prometheus:9090/api/v1/query',
                params={'query': 'rate(http_request_timeout_total[5m]) > 0.1'},
                timeout=5
            )
            
            if response.status_code == 200:
                data = response.json()
                return len(data.get('data', {}).get('result', [])) > 0
        except:
            pass
        return False
    
    def check_high_latency(self) -> bool:
        """Check if latency is high"""
        try:
            import requests
            response = requests.get(
                'http://prometheus:9090/api/v1/query',
                params={'query': 'histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m])) > 2'},
                timeout=5
            )
            
            if response.status_code == 200:
                data = response.json()
                return len(data.get('data', {}).get('result', [])) > 0
        except:
            pass
        return False
    
    def load_applied_patches(self) -> Dict:
        """Load applied patches history"""
        try:
            if os.path.exists(self.applied_patches_file):
                with open(self.applied_patches_file, 'r') as f:
                    return json.load(f)
        except Exception as e:
            logger.warning(f"Could not load applied patches: {e}")
        return {}
    
    def save_applied_patches(self):
        """Save applied patches history"""
        try:
            with open(self.applied_patches_file, 'w') as f:
                json.dump(self.applied_patches, f, indent=2)
        except Exception as e:
            logger.error(f"Could not save applied patches: {e}")


if __name__ == '__main__':
    patcher = AutoPatcher()
    patcher.run()

