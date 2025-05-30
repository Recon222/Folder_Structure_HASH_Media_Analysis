#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Batch recovery manager for handling crashes and resuming interrupted batches
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QObject, QTimer, Signal
from PySide6.QtWidgets import QMessageBox

from .batch_queue import BatchQueue


class BatchRecoveryManager(QObject):
    """Handle crashes and resume interrupted batches"""
    
    # Signals
    recovery_available = Signal(Path)  # Emitted when recovery file is found
    
    def __init__(self, auto_save_interval: int = 300):  # 5 minutes default
        super().__init__()
        self.auto_save_interval = auto_save_interval * 1000  # Convert to milliseconds
        self.auto_save_timer = QTimer()
        self.auto_save_timer.timeout.connect(self._auto_save_state)
        
        # Recovery file location
        self.recovery_dir = Path.home() / '.folder_structure_utility'
        self.recovery_dir.mkdir(exist_ok=True)
        self.recovery_file = self.recovery_dir / 'batch_autosave.json'
        self.backup_file = self.recovery_dir / 'batch_backup.json'
        
        self.batch_queue: Optional[BatchQueue] = None
        self.processing_active = False
        
    def set_batch_queue(self, batch_queue: BatchQueue):
        """Set the batch queue to monitor"""
        self.batch_queue = batch_queue
        
        # Connect to queue changes for immediate saves during processing
        batch_queue.queue_changed.connect(self._on_queue_changed)
        
    def start_monitoring(self):
        """Start auto-save monitoring"""
        if self.auto_save_interval > 0:
            self.auto_save_timer.start(self.auto_save_interval)
            
    def stop_monitoring(self):
        """Stop auto-save monitoring"""
        self.auto_save_timer.stop()
        
    def set_processing_active(self, active: bool):
        """Set whether batch processing is currently active"""
        self.processing_active = active
        if active:
            # Save immediately when processing starts
            self._auto_save_state()
            # Increase save frequency during processing
            if self.auto_save_timer.isActive():
                self.auto_save_timer.stop()
                self.auto_save_timer.start(30000)  # Every 30 seconds during processing
        else:
            # Restore normal save frequency
            if self.auto_save_timer.isActive():
                self.auto_save_timer.stop()
                self.auto_save_timer.start(self.auto_save_interval)
                
    def _on_queue_changed(self):
        """Handle queue changes - save immediately if processing"""
        if self.processing_active:
            self._auto_save_state()
            
    def _auto_save_state(self):
        """Periodically save batch state"""
        if not self.batch_queue or not self.batch_queue.jobs:
            return
            
        try:
            # Create backup of previous save
            if self.recovery_file.exists():
                if self.backup_file.exists():
                    self.backup_file.unlink()
                self.recovery_file.rename(self.backup_file)
                
            # Save current state
            recovery_data = {
                'version': '1.0',
                'saved_at': datetime.now().isoformat(),
                'processing_active': self.processing_active,
                'auto_save': True,
                'queue_data': {
                    'jobs': [job.to_dict() for job in self.batch_queue.jobs],
                    'current_job_index': self.batch_queue.current_job_index
                }
            }
            
            with open(self.recovery_file, 'w') as f:
                json.dump(recovery_data, f, indent=2)
                
        except Exception as e:
            print(f"Warning: Failed to auto-save batch state: {e}")
            
    def check_for_recovery(self) -> Optional[dict]:
        """Check if there's an interrupted batch to recover"""
        if not self.recovery_file.exists():
            return None
            
        try:
            with open(self.recovery_file, 'r') as f:
                recovery_data = json.load(f)
                
            # Check if this is a valid recovery file
            if not recovery_data.get('auto_save'):
                return None
                
            # Check if there are pending or processing jobs
            jobs_data = recovery_data.get('queue_data', {}).get('jobs', [])
            has_incomplete_jobs = any(
                job.get('status') in ['pending', 'processing'] 
                for job in jobs_data
            )
            
            if has_incomplete_jobs:
                return recovery_data
                
        except Exception as e:
            print(f"Warning: Failed to read recovery file: {e}")
            
        return None
        
    def prompt_recovery(self, parent_widget=None) -> bool:
        """Prompt user to recover interrupted batch"""
        recovery_data = self.check_for_recovery()
        if not recovery_data:
            return False
            
        jobs_data = recovery_data.get('queue_data', {}).get('jobs', [])
        pending_count = sum(1 for job in jobs_data if job.get('status') == 'pending')
        processing_count = sum(1 for job in jobs_data if job.get('status') == 'processing')
        
        saved_time = recovery_data.get('saved_at', 'unknown')
        if saved_time != 'unknown':
            try:
                saved_dt = datetime.fromisoformat(saved_time)
                time_str = saved_dt.strftime('%Y-%m-%d %H:%M:%S')
            except:
                time_str = saved_time
        else:
            time_str = 'unknown time'
            
        message = f"An interrupted batch processing session was found!\n\n"
        message += f"Last saved: {time_str}\n"
        message += f"Pending jobs: {pending_count}\n"
        message += f"Processing jobs: {processing_count}\n\n"
        message += "Would you like to recover and continue this batch?"
        
        reply = QMessageBox.question(
            parent_widget,
            "Batch Recovery Available",
            message,
            QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel
        )
        
        if reply == QMessageBox.Yes:
            return self._restore_from_recovery(recovery_data)
        elif reply == QMessageBox.No:
            # User doesn't want to recover - clean up recovery files
            self.clear_recovery_files()
            
        return False
        
    def _restore_from_recovery(self, recovery_data: dict) -> bool:
        """Restore batch queue from recovery data"""
        if not self.batch_queue:
            return False
            
        try:
            # Clear current queue
            self.batch_queue.clear_queue()
            
            # Restore jobs
            jobs_data = recovery_data.get('queue_data', {}).get('jobs', [])
            
            for job_data in jobs_data:
                # Reset processing jobs to pending
                if job_data.get('status') == 'processing':
                    job_data['status'] = 'pending'
                    job_data['start_time'] = None
                    job_data['end_time'] = None
                    job_data['error_message'] = ''
                    
                from .models import BatchJob
                job = BatchJob.from_dict(job_data)
                self.batch_queue.jobs.append(job)
                
            # Restore queue index
            self.batch_queue.current_job_index = recovery_data.get('queue_data', {}).get('current_job_index', -1)
            
            # Emit queue changed signal
            self.batch_queue.queue_changed.emit()
            
            # Clean up recovery files after successful restore
            self.clear_recovery_files()
            
            return True
            
        except Exception as e:
            print(f"Error restoring from recovery: {e}")
            return False
            
    def clear_recovery_files(self):
        """Clear recovery files"""
        try:
            if self.recovery_file.exists():
                self.recovery_file.unlink()
            if self.backup_file.exists():
                self.backup_file.unlink()
        except Exception as e:
            print(f"Warning: Failed to clear recovery files: {e}")
            
    def export_recovery_log(self, file_path: Path):
        """Export detailed recovery information"""
        recovery_data = self.check_for_recovery()
        if not recovery_data:
            return
            
        log_data = {
            'export_date': datetime.now().isoformat(),
            'recovery_session': recovery_data,
            'recovery_file_path': str(self.recovery_file),
            'backup_file_path': str(self.backup_file)
        }
        
        with open(file_path, 'w') as f:
            json.dump(log_data, f, indent=2)
            
    def get_recovery_statistics(self) -> dict:
        """Get statistics about recovery state"""
        recovery_data = self.check_for_recovery()
        if not recovery_data:
            return {
                'has_recovery': False,
                'jobs': 0,
                'pending': 0,
                'processing': 0,
                'completed': 0,
                'failed': 0
            }
            
        jobs_data = recovery_data.get('queue_data', {}).get('jobs', [])
        
        stats = {
            'has_recovery': True,
            'jobs': len(jobs_data),
            'pending': sum(1 for job in jobs_data if job.get('status') == 'pending'),
            'processing': sum(1 for job in jobs_data if job.get('status') == 'processing'),
            'completed': sum(1 for job in jobs_data if job.get('status') == 'completed'),
            'failed': sum(1 for job in jobs_data if job.get('status') == 'failed'),
            'last_saved': recovery_data.get('saved_at', 'unknown')
        }
        
        return stats