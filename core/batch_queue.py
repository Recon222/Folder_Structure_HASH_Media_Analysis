#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Batch queue management for processing multiple jobs sequentially
"""

import json
from datetime import datetime
from pathlib import Path
from typing import List, Optional
from PySide6.QtCore import QObject, Signal

from .models import BatchJob


class BatchQueue(QObject):
    """Manages the batch processing queue"""
    
    # Signals
    job_added = Signal(BatchJob)
    job_removed = Signal(str)  # job_id
    job_updated = Signal(BatchJob)
    queue_changed = Signal()
    
    def __init__(self):
        super().__init__()
        self.jobs: List[BatchJob] = []
        self.current_job_index: int = -1
        
    def add_job(self, job: BatchJob) -> None:
        """Add a job to the queue"""
        # Validate job before adding
        errors = job.validate()
        if errors:
            raise ValueError(f"Invalid job: {', '.join(errors)}")
            
        self.jobs.append(job)
        self.job_added.emit(job)
        self.queue_changed.emit()
        
    def remove_job(self, job_id: str) -> bool:
        """Remove a job by ID"""
        initial_count = len(self.jobs)
        self.jobs = [j for j in self.jobs if j.job_id != job_id]
        
        if len(self.jobs) < initial_count:
            self.job_removed.emit(job_id)
            self.queue_changed.emit()
            return True
        return False
        
    def get_job_by_id(self, job_id: str) -> Optional[BatchJob]:
        """Get a job by its ID"""
        for job in self.jobs:
            if job.job_id == job_id:
                return job
        return None
        
    def update_job(self, job: BatchJob) -> bool:
        """Update an existing job"""
        for i, existing_job in enumerate(self.jobs):
            if existing_job.job_id == job.job_id:
                self.jobs[i] = job
                self.job_updated.emit(job)
                self.queue_changed.emit()
                return True
        return False
        
    def reorder_jobs(self, from_index: int, to_index: int) -> None:
        """Reorder jobs in queue"""
        if 0 <= from_index < len(self.jobs) and 0 <= to_index < len(self.jobs):
            job = self.jobs.pop(from_index)
            self.jobs.insert(to_index, job)
            self.queue_changed.emit()
            
    def get_next_pending_job(self) -> Optional[BatchJob]:
        """Get the next job to process"""
        for i, job in enumerate(self.jobs):
            if job.status == "pending":
                self.current_job_index = i
                return job
        return None
        
    def get_current_job(self) -> Optional[BatchJob]:
        """Get the currently processing job"""
        if 0 <= self.current_job_index < len(self.jobs):
            return self.jobs[self.current_job_index]
        return None
        
    def clear_queue(self) -> None:
        """Clear all jobs from queue"""
        self.jobs.clear()
        self.current_job_index = -1
        self.queue_changed.emit()
        
    def get_pending_jobs(self) -> List[BatchJob]:
        """Get all pending jobs"""
        return [job for job in self.jobs if job.status == "pending"]
        
    def get_completed_jobs(self) -> List[BatchJob]:
        """Get all completed jobs"""
        return [job for job in self.jobs if job.status == "completed"]
        
    def get_failed_jobs(self) -> List[BatchJob]:
        """Get all failed jobs"""
        return [job for job in self.jobs if job.status == "failed"]
        
    def get_statistics(self) -> dict:
        """Get queue statistics"""
        total = len(self.jobs)
        pending = len(self.get_pending_jobs())
        completed = len(self.get_completed_jobs())
        failed = len(self.get_failed_jobs())
        processing = len([j for j in self.jobs if j.status == "processing"])
        
        return {
            'total': total,
            'pending': pending,
            'completed': completed,
            'failed': failed,
            'processing': processing
        }
        
    def reset_failed_jobs(self) -> int:
        """Reset all failed jobs to pending status"""
        reset_count = 0
        for job in self.jobs:
            if job.status == "failed":
                job.status = "pending"
                job.error_message = ""
                job.start_time = None
                job.end_time = None
                reset_count += 1
                
        if reset_count > 0:
            self.queue_changed.emit()
            
        return reset_count
        
    def save_to_file(self, file_path: Path) -> None:
        """Save queue to JSON file"""
        data = {
            'version': '1.0',
            'created_at': datetime.now().isoformat(),
            'total_jobs': len(self.jobs),
            'jobs': [job.to_dict() for job in self.jobs]
        }
        
        file_path.parent.mkdir(parents=True, exist_ok=True)
        with open(file_path, 'w') as f:
            json.dump(data, f, indent=2)
            
    def load_from_file(self, file_path: Path) -> None:
        """Load queue from JSON file"""
        if not file_path.exists():
            raise FileNotFoundError(f"Queue file not found: {file_path}")
            
        with open(file_path, 'r') as f:
            data = json.load(f)
            
        # Validate file format
        if 'jobs' not in data:
            raise ValueError("Invalid queue file format")
            
        # Clear current queue and load jobs
        self.clear_queue()
        
        for job_data in data['jobs']:
            try:
                job = BatchJob.from_dict(job_data)
                # Reset processing status to pending on load
                if job.status == "processing":
                    job.status = "pending"
                    job.start_time = None
                    job.end_time = None
                    job.error_message = ""
                    
                self.jobs.append(job)
            except Exception as e:
                print(f"Warning: Failed to load job {job_data.get('job_id', 'unknown')}: {e}")
                
        self.queue_changed.emit()
        
    def export_report(self, file_path: Path) -> None:
        """Export detailed queue report"""
        stats = self.get_statistics()
        
        report_data = {
            'export_date': datetime.now().isoformat(),
            'queue_statistics': stats,
            'jobs': []
        }
        
        for job in self.jobs:
            job_report = {
                'job_name': job.job_name,
                'occurrence_number': job.form_data.occurrence_number,
                'status': job.status,
                'file_count': job.get_file_count(),
                'duration_seconds': job.get_duration(),
                'start_time': job.start_time.isoformat() if job.start_time else None,
                'end_time': job.end_time.isoformat() if job.end_time else None,
                'error_message': job.error_message
            }
            report_data['jobs'].append(job_report)
            
        file_path.parent.mkdir(parents=True, exist_ok=True)
        with open(file_path, 'w') as f:
            json.dump(report_data, f, indent=2)
            
    def validate_all_jobs(self) -> dict:
        """Validate all jobs in the queue"""
        validation_results = {
            'valid_jobs': [],
            'invalid_jobs': [],
            'total_errors': 0
        }
        
        for job in self.jobs:
            errors = job.validate()
            if errors:
                validation_results['invalid_jobs'].append({
                    'job_id': job.job_id,
                    'job_name': job.job_name,
                    'errors': errors
                })
                validation_results['total_errors'] += len(errors)
            else:
                validation_results['valid_jobs'].append(job.job_id)
                
        return validation_results