"""
Module: maintenance_service_lg
Description: System maintenance tasks, cleanup operations, health checks, and automated maintenance scheduling
Phase: 4
Location: /src/modules/logic/background_services_lg/maintenance_service_lg/
"""

# Standard library imports
import asyncio
import os
import shutil
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Callable, Any, Set
import uuid
import gc
import psutil

# Third-party imports
from croniter import croniter

# Local imports
from ..base_interfaces import (
    IMaintenanceService, MaintenanceTask, MaintenanceResult, MaintenanceType,
    MaintenanceConfig, MaintenanceExecutionResult
)
from src.modules.logic.logging_infrastructure_lg import get_logger
from src.modules.logic.error_handling_lg import ErrorClassifier, ErrorSeverity


class MaintenanceScheduler:
    """
    Schedules and manages maintenance tasks using cron expressions.
    
    Features:
    - Cron-based scheduling
    - Task priority management
    - Concurrent execution control
    - Schedule validation
    """
    
    def __init__(self, max_concurrent: int = 3):
        """Initialize maintenance scheduler."""
        self._logger = get_logger(__name__)
        self._max_concurrent = max_concurrent
        self._scheduled_tasks: Dict[str, MaintenanceTask] = {}
        self._running_tasks: Dict[str, asyncio.Task] = {}
        self._lock = threading.RLock()
        self._running = False
        self._scheduler_task: Optional[asyncio.Task] = None
    
    def schedule_task(self, task: MaintenanceTask) -> bool:
        """Schedule a maintenance task."""
        try:
            # Validate cron expression
            if not self._validate_cron_expression(task.schedule):
                self._logger.error(f"Invalid cron expression for task {task.task_id}: {task.schedule}")
                return False
            
            with self._lock:
                self._scheduled_tasks[task.task_id] = task
                
                # Calculate next run time
                cron = croniter(task.schedule, datetime.now())
                task.next_run = cron.get_next(datetime)
                
                self._logger.info(f"Scheduled maintenance task {task.task_id}: {task.name}")
                return True
                
        except Exception as e:
            self._logger.error(f"Error scheduling maintenance task {task.task_id}: {e}")
            return False
    
    def unschedule_task(self, task_id: str) -> bool:
        """Unschedule a maintenance task."""
        try:
            with self._lock:
                task = self._scheduled_tasks.pop(task_id, None)
                if not task:
                    return False
                
                # Cancel if running
                if task_id in self._running_tasks:
                    self._running_tasks[task_id].cancel()
                    del self._running_tasks[task_id]
                
                self._logger.info(f"Unscheduled maintenance task {task_id}")
                return True
                
        except Exception as e:
            self._logger.error(f"Error unscheduling maintenance task {task_id}: {e}")
            return False
    
    def get_scheduled_tasks(self) -> List[MaintenanceTask]:
        """Get all scheduled tasks."""
        with self._lock:
            return list(self._scheduled_tasks.values())
    
    def get_next_scheduled_tasks(self, limit: int = 10) -> List[MaintenanceTask]:
        """Get next tasks to run."""
        with self._lock:
            now = datetime.now()
            ready_tasks = [
                task for task in self._scheduled_tasks.values()
                if task.enabled and task.next_run and task.next_run <= now
            ]
            
            # Sort by next run time
            ready_tasks.sort(key=lambda t: t.next_run)
            return ready_tasks[:limit]
    
    async def start_scheduler(self) -> None:
        """Start the maintenance scheduler."""
        if self._running:
            return
        
        self._running = True
        self._scheduler_task = asyncio.create_task(self._scheduler_loop())
        self._logger.info("Maintenance scheduler started")
    
    async def stop_scheduler(self) -> None:
        """Stop the maintenance scheduler."""
        if not self._running:
            return
        
        self._running = False
        
        if self._scheduler_task:
            self._scheduler_task.cancel()
            try:
                await self._scheduler_task
            except asyncio.CancelledError:
                pass
        
        # Cancel running tasks
        with self._lock:
            for task in self._running_tasks.values():
                task.cancel()
            self._running_tasks.clear()
        
        self._logger.info("Maintenance scheduler stopped")
    
    async def _scheduler_loop(self) -> None:
        """Main scheduler loop."""
        while self._running:
            try:
                # Get tasks ready to run
                ready_tasks = self.get_next_scheduled_tasks()
                
                # Execute tasks up to concurrent limit
                available_slots = self._max_concurrent - len(self._running_tasks)
                tasks_to_run = ready_tasks[:available_slots]
                
                for task in tasks_to_run:
                    if task.task_id not in self._running_tasks:
                        # Start task execution
                        execution_task = asyncio.create_task(self._execute_task(task))
                        self._running_tasks[task.task_id] = execution_task
                        
                        # Update next run time
                        cron = croniter(task.schedule, datetime.now())
                        task.next_run = cron.get_next(datetime)
                        task.last_run = datetime.now()
                
                # Clean up completed tasks
                completed_tasks = []
                for task_id, task in self._running_tasks.items():
                    if task.done():
                        completed_tasks.append(task_id)
                
                for task_id in completed_tasks:
                    del self._running_tasks[task_id]
                
                # Sleep for a minute before next check
                await asyncio.sleep(60)
                
            except Exception as e:
                self._logger.error(f"Error in maintenance scheduler loop: {e}")
                await asyncio.sleep(60)
    
    async def _execute_task(self, task: MaintenanceTask) -> MaintenanceResult:
        """Execute a maintenance task."""
        start_time = datetime.now()
        
        try:
            self._logger.info(f"Executing maintenance task {task.task_id}: {task.name}")
            
            # Execute with timeout
            if asyncio.iscoroutinefunction(task.function):
                result = await asyncio.wait_for(
                    task.function(),
                    timeout=task.timeout.total_seconds()
                )
            else:
                loop = asyncio.get_event_loop()
                result = await asyncio.wait_for(
                    loop.run_in_executor(None, task.function),
                    timeout=task.timeout.total_seconds()
                )
            
            end_time = datetime.now()
            
            maintenance_result = MaintenanceResult(
                task_id=task.task_id,
                maintenance_type=task.maintenance_type,
                success=True,
                start_time=start_time,
                end_time=end_time,
                details={'result': result}
            )
            
            self._logger.info(f"Maintenance task {task.task_id} completed successfully")
            return maintenance_result
            
        except asyncio.TimeoutError:
            self._logger.warning(f"Maintenance task {task.task_id} timed out")
            return MaintenanceResult(
                task_id=task.task_id,
                maintenance_type=task.maintenance_type,
                success=False,
                start_time=start_time,
                end_time=datetime.now(),
                error_message=f"Task timed out after {task.timeout}"
            )
            
        except Exception as e:
            self._logger.error(f"Error executing maintenance task {task.task_id}: {e}")
            return MaintenanceResult(
                task_id=task.task_id,
                maintenance_type=task.maintenance_type,
                success=False,
                start_time=start_time,
                end_time=datetime.now(),
                error_message=str(e)
            )
    
    def _validate_cron_expression(self, cron_expr: str) -> bool:
        """Validate a cron expression."""
        try:
            croniter(cron_expr)
            return True
        except Exception:
            return False


class CleanupManager:
    """
    Manages system cleanup operations.
    
    Features:
    - Log file cleanup
    - Temporary file cleanup
    - Cache cleanup
    - Database cleanup
    - Memory cleanup
    """
    
    def __init__(self):
        """Initialize cleanup manager."""
        self._logger = get_logger(__name__)
    
    async def cleanup_logs(self, log_dir: Path, max_age_days: int = 7, max_size_mb: int = 100) -> Dict[str, Any]:
        """Clean up old log files."""
        try:
            if not log_dir.exists():
                return {'status': 'skipped', 'reason': 'log directory does not exist'}
            
            cutoff_time = datetime.now() - timedelta(days=max_age_days)
            max_size_bytes = max_size_mb * 1024 * 1024
            
            cleaned_files = []
            total_size_freed = 0
            
            for log_file in log_dir.rglob('*.log*'):
                try:
                    # Check file age
                    file_mtime = datetime.fromtimestamp(log_file.stat().st_mtime)
                    file_size = log_file.stat().st_size
                    
                    should_delete = False
                    reason = ""
                    
                    if file_mtime < cutoff_time:
                        should_delete = True
                        reason = f"older than {max_age_days} days"
                    elif file_size > max_size_bytes:
                        should_delete = True
                        reason = f"larger than {max_size_mb}MB"
                    
                    if should_delete:
                        log_file.unlink()
                        cleaned_files.append({
                            'file': str(log_file),
                            'size': file_size,
                            'reason': reason
                        })
                        total_size_freed += file_size
                        
                except Exception as e:
                    self._logger.warning(f"Error cleaning log file {log_file}: {e}")
            
            result = {
                'status': 'completed',
                'files_cleaned': len(cleaned_files),
                'size_freed_mb': round(total_size_freed / (1024 * 1024), 2),
                'details': cleaned_files
            }
            
            self._logger.info(f"Log cleanup completed: {len(cleaned_files)} files, {result['size_freed_mb']}MB freed")
            return result
            
        except Exception as e:
            self._logger.error(f"Error during log cleanup: {e}")
            return {'status': 'failed', 'error': str(e)}
    
    async def cleanup_temp_files(self, temp_dir: Path, max_age_hours: int = 24) -> Dict[str, Any]:
        """Clean up temporary files."""
        try:
            if not temp_dir.exists():
                return {'status': 'skipped', 'reason': 'temp directory does not exist'}
            
            cutoff_time = datetime.now() - timedelta(hours=max_age_hours)
            
            cleaned_files = []
            total_size_freed = 0
            
            for temp_file in temp_dir.rglob('*'):
                try:
                    if temp_file.is_file():
                        file_mtime = datetime.fromtimestamp(temp_file.stat().st_mtime)
                        
                        if file_mtime < cutoff_time:
                            file_size = temp_file.stat().st_size
                            temp_file.unlink()
                            cleaned_files.append(str(temp_file))
                            total_size_freed += file_size
                            
                except Exception as e:
                    self._logger.warning(f"Error cleaning temp file {temp_file}: {e}")
            
            result = {
                'status': 'completed',
                'files_cleaned': len(cleaned_files),
                'size_freed_mb': round(total_size_freed / (1024 * 1024), 2)
            }
            
            self._logger.info(f"Temp cleanup completed: {len(cleaned_files)} files, {result['size_freed_mb']}MB freed")
            return result
            
        except Exception as e:
            self._logger.error(f"Error during temp cleanup: {e}")
            return {'status': 'failed', 'error': str(e)}
    
    async def cleanup_memory(self) -> Dict[str, Any]:
        """Perform memory cleanup."""
        try:
            # Get memory usage before cleanup
            process = psutil.Process()
            memory_before = process.memory_info().rss / (1024 * 1024)  # MB
            
            # Force garbage collection
            collected = gc.collect()
            
            # Get memory usage after cleanup
            memory_after = process.memory_info().rss / (1024 * 1024)  # MB
            memory_freed = memory_before - memory_after
            
            result = {
                'status': 'completed',
                'objects_collected': collected,
                'memory_before_mb': round(memory_before, 2),
                'memory_after_mb': round(memory_after, 2),
                'memory_freed_mb': round(memory_freed, 2)
            }
            
            self._logger.info(f"Memory cleanup completed: {collected} objects collected, {memory_freed:.2f}MB freed")
            return result
            
        except Exception as e:
            self._logger.error(f"Error during memory cleanup: {e}")
            return {'status': 'failed', 'error': str(e)}


class SystemHealthChecker:
    """
    Performs system health checks as part of maintenance.

    Features:
    - Disk space monitoring
    - Memory usage monitoring
    - CPU usage monitoring
    - Service health checks
    """

    def __init__(self):
        """Initialize system health checker."""
        self._logger = get_logger(__name__)

    async def check_disk_space(self, min_free_gb: float = 1.0) -> Dict[str, Any]:
        """Check available disk space."""
        try:
            disk_usage = shutil.disk_usage('/')
            free_gb = disk_usage.free / (1024 ** 3)
            total_gb = disk_usage.total / (1024 ** 3)
            used_gb = disk_usage.used / (1024 ** 3)
            usage_percent = (used_gb / total_gb) * 100

            status = 'healthy' if free_gb >= min_free_gb else 'warning'

            result = {
                'status': status,
                'free_gb': round(free_gb, 2),
                'used_gb': round(used_gb, 2),
                'total_gb': round(total_gb, 2),
                'usage_percent': round(usage_percent, 2),
                'threshold_gb': min_free_gb
            }

            if status == 'warning':
                self._logger.warning(f"Low disk space: {free_gb:.2f}GB free (threshold: {min_free_gb}GB)")

            return result

        except Exception as e:
            self._logger.error(f"Error checking disk space: {e}")
            return {'status': 'error', 'error': str(e)}

    async def check_memory_usage(self, max_usage_percent: float = 90.0) -> Dict[str, Any]:
        """Check memory usage."""
        try:
            memory = psutil.virtual_memory()
            usage_percent = memory.percent
            available_gb = memory.available / (1024 ** 3)
            total_gb = memory.total / (1024 ** 3)
            used_gb = memory.used / (1024 ** 3)

            status = 'healthy' if usage_percent <= max_usage_percent else 'warning'

            result = {
                'status': status,
                'usage_percent': round(usage_percent, 2),
                'available_gb': round(available_gb, 2),
                'used_gb': round(used_gb, 2),
                'total_gb': round(total_gb, 2),
                'threshold_percent': max_usage_percent
            }

            if status == 'warning':
                self._logger.warning(f"High memory usage: {usage_percent:.2f}% (threshold: {max_usage_percent}%)")

            return result

        except Exception as e:
            self._logger.error(f"Error checking memory usage: {e}")
            return {'status': 'error', 'error': str(e)}

    async def check_cpu_usage(self, max_usage_percent: float = 80.0, interval: float = 1.0) -> Dict[str, Any]:
        """Check CPU usage."""
        try:
            cpu_percent = psutil.cpu_percent(interval=interval)
            cpu_count = psutil.cpu_count()
            load_avg = os.getloadavg() if hasattr(os, 'getloadavg') else (0, 0, 0)

            status = 'healthy' if cpu_percent <= max_usage_percent else 'warning'

            result = {
                'status': status,
                'usage_percent': round(cpu_percent, 2),
                'cpu_count': cpu_count,
                'load_avg_1min': round(load_avg[0], 2),
                'load_avg_5min': round(load_avg[1], 2),
                'load_avg_15min': round(load_avg[2], 2),
                'threshold_percent': max_usage_percent
            }

            if status == 'warning':
                self._logger.warning(f"High CPU usage: {cpu_percent:.2f}% (threshold: {max_usage_percent}%)")

            return result

        except Exception as e:
            self._logger.error(f"Error checking CPU usage: {e}")
            return {'status': 'error', 'error': str(e)}

    async def comprehensive_health_check(self) -> Dict[str, Any]:
        """Perform comprehensive system health check."""
        try:
            results = {
                'timestamp': datetime.now().isoformat(),
                'overall_status': 'healthy',
                'checks': {}
            }

            # Run all health checks
            results['checks']['disk_space'] = await self.check_disk_space()
            results['checks']['memory_usage'] = await self.check_memory_usage()
            results['checks']['cpu_usage'] = await self.check_cpu_usage()

            # Determine overall status
            warning_count = sum(1 for check in results['checks'].values()
                              if check.get('status') == 'warning')
            error_count = sum(1 for check in results['checks'].values()
                            if check.get('status') == 'error')

            if error_count > 0:
                results['overall_status'] = 'error'
            elif warning_count > 0:
                results['overall_status'] = 'warning'

            results['summary'] = {
                'total_checks': len(results['checks']),
                'healthy_checks': len(results['checks']) - warning_count - error_count,
                'warning_checks': warning_count,
                'error_checks': error_count
            }

            self._logger.info(f"Health check completed: {results['overall_status']} "
                            f"({results['summary']['healthy_checks']}/{results['summary']['total_checks']} healthy)")

            return results

        except Exception as e:
            self._logger.error(f"Error during comprehensive health check: {e}")
            return {
                'timestamp': datetime.now().isoformat(),
                'overall_status': 'error',
                'error': str(e)
            }


class MaintenanceService(IMaintenanceService):
    """
    Main maintenance service implementation.

    Features:
    - Scheduled maintenance tasks
    - System cleanup operations
    - Health monitoring
    - Maintenance history tracking
    - Configurable maintenance windows
    """

    def __init__(self, config: Optional[MaintenanceConfig] = None):
        """Initialize maintenance service."""
        self._logger = get_logger(__name__)
        self._config = config or MaintenanceConfig()

        # Core components
        self._scheduler = MaintenanceScheduler(max_concurrent=self._config.max_concurrent_tasks)
        self._cleanup_manager = CleanupManager()
        self._health_checker = SystemHealthChecker()

        # Maintenance history
        self._maintenance_history: List[MaintenanceResult] = []
        self._lock = threading.RLock()

        # Service state
        self._running = False

        self._logger.info("Maintenance service initialized")

    def schedule_maintenance(self, task: MaintenanceTask) -> bool:
        """Schedule a maintenance task."""
        return self._scheduler.schedule_task(task)

    def cancel_maintenance(self, task_id: str) -> bool:
        """Cancel a maintenance task."""
        return self._scheduler.unschedule_task(task_id)

    def get_maintenance_task(self, task_id: str) -> Optional[MaintenanceTask]:
        """Get maintenance task information."""
        scheduled_tasks = self._scheduler.get_scheduled_tasks()
        for task in scheduled_tasks:
            if task.task_id == task_id:
                return task
        return None

    def list_maintenance_tasks(self, maintenance_type: Optional[MaintenanceType] = None) -> List[MaintenanceTask]:
        """List maintenance tasks."""
        tasks = self._scheduler.get_scheduled_tasks()
        if maintenance_type:
            tasks = [t for t in tasks if t.maintenance_type == maintenance_type]
        return tasks

    async def execute_maintenance(self, task_id: str) -> MaintenanceExecutionResult:
        """Execute a maintenance task."""
        try:
            task = self.get_maintenance_task(task_id)
            if not task:
                message = f"Maintenance task {task_id} not found"
                self._logger.error(message)
                return MaintenanceExecutionResult(
                    success=False,
                    task_id=task_id,
                    result=MaintenanceResult(
                        task_id=task_id,
                        maintenance_type=MaintenanceType.CLEANUP,
                        success=False,
                        start_time=datetime.now(),
                        end_time=datetime.now(),
                        error_message=message
                    ),
                    message=message
                )

            # Execute the task
            result = await self._scheduler._execute_task(task)

            # Store in history
            with self._lock:
                self._maintenance_history.append(result)

                # Limit history size
                if len(self._maintenance_history) > 1000:
                    self._maintenance_history = self._maintenance_history[-1000:]

            message = f"Maintenance task {task_id} executed with success: {result.success}"
            self._logger.info(message)

            return MaintenanceExecutionResult(
                success=result.success,
                task_id=task_id,
                result=result,
                message=message
            )

        except Exception as e:
            error_msg = f"Error executing maintenance task {task_id}: {e}"
            self._logger.error(error_msg)

            result = MaintenanceResult(
                task_id=task_id,
                maintenance_type=MaintenanceType.CLEANUP,
                success=False,
                start_time=datetime.now(),
                end_time=datetime.now(),
                error_message=str(e)
            )

            return MaintenanceExecutionResult(
                success=False,
                task_id=task_id,
                result=result,
                message=error_msg
            )

    def get_maintenance_history(self, days: int = 7) -> List[MaintenanceResult]:
        """Get maintenance execution history."""
        cutoff_time = datetime.now() - timedelta(days=days)

        with self._lock:
            return [
                result for result in self._maintenance_history
                if result.start_time >= cutoff_time
            ]

    async def start_service(self) -> None:
        """Start the maintenance service."""
        if self._running:
            self._logger.warning("Maintenance service is already running")
            return

        self._running = True

        # Start scheduler
        await self._scheduler.start_scheduler()

        # Schedule default maintenance tasks if enabled
        if self._config.enabled:
            await self._schedule_default_tasks()

        self._logger.info("Maintenance service started")

    async def stop_service(self) -> None:
        """Stop the maintenance service."""
        if not self._running:
            return

        self._running = False

        # Stop scheduler
        await self._scheduler.stop_scheduler()

        self._logger.info("Maintenance service stopped")

    async def _schedule_default_tasks(self) -> None:
        """Schedule default maintenance tasks."""
        try:
            # Daily log cleanup
            log_cleanup_task = MaintenanceTask(
                task_id=str(uuid.uuid4()),
                name="Daily Log Cleanup",
                maintenance_type=MaintenanceType.CLEANUP,
                function=self._cleanup_manager.cleanup_logs,
                schedule="0 2 * * *",  # 2 AM daily
                timeout=timedelta(minutes=30)
            )
            self.schedule_maintenance(log_cleanup_task)

            # Weekly temp cleanup
            temp_cleanup_task = MaintenanceTask(
                task_id=str(uuid.uuid4()),
                name="Weekly Temp Cleanup",
                maintenance_type=MaintenanceType.CLEANUP,
                function=self._cleanup_manager.cleanup_temp_files,
                schedule="0 3 * * 0",  # 3 AM on Sundays
                timeout=timedelta(minutes=15)
            )
            self.schedule_maintenance(temp_cleanup_task)

            # Hourly memory cleanup
            memory_cleanup_task = MaintenanceTask(
                task_id=str(uuid.uuid4()),
                name="Hourly Memory Cleanup",
                maintenance_type=MaintenanceType.OPTIMIZATION,
                function=self._cleanup_manager.cleanup_memory,
                schedule="0 * * * *",  # Every hour
                timeout=timedelta(minutes=5)
            )
            self.schedule_maintenance(memory_cleanup_task)

            # Health check every 5 minutes
            health_check_task = MaintenanceTask(
                task_id=str(uuid.uuid4()),
                name="System Health Check",
                maintenance_type=MaintenanceType.HEALTH_CHECK,
                function=self._health_checker.comprehensive_health_check,
                schedule="*/5 * * * *",  # Every 5 minutes
                timeout=timedelta(minutes=2)
            )
            self.schedule_maintenance(health_check_task)

            self._logger.info("Default maintenance tasks scheduled")

        except Exception as e:
            self._logger.error(f"Error scheduling default maintenance tasks: {e}")
