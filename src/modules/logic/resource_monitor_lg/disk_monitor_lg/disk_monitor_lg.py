"""
Module: disk_monitor_lg
Description: Monitors NVMe and storage I/O performance, available space, and read/write throughput for virtual memory operations
Phase: 2
Location: /src/modules/logic/resource_monitor_lg/disk_monitor_lg/
"""

# Standard library imports
import asyncio
import platform
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
import psutil

# Local imports
from src.modules.logic.app_state_lg.app_state_lg import AppStateManager
from src.modules.logic.logging_infrastructure_lg.log_manager_lg.log_manager_lg import get_log_manager
from src.modules.logic.error_handling_lg.validation_engine_lg.validation_engine_lg import ValidationEngine


class StorageType(Enum):
    """Types of storage devices."""
    HDD = "HDD"
    SSD = "SSD"
    NVME = "NVME"
    NETWORK = "NETWORK"
    UNKNOWN = "UNKNOWN"


class FileSystemType(Enum):
    """File system types."""
    NTFS = "NTFS"
    FAT32 = "FAT32"
    EXT4 = "EXT4"
    EXT3 = "EXT3"
    XFS = "XFS"
    BTRFS = "BTRFS"
    APFS = "APFS"
    HFS_PLUS = "HFS+"
    UNKNOWN = "UNKNOWN"


@dataclass
class StorageInfo:
    """Detailed storage device information."""
    device_path: str
    mount_point: str
    file_system: FileSystemType
    storage_type: StorageType
    total_gb: float
    used_gb: float
    free_gb: float
    usage_percent: float
    is_removable: bool
    is_system_drive: bool
    device_name: Optional[str] = None
    serial_number: Optional[str] = None
    model: Optional[str] = None
    interface: Optional[str] = None


@dataclass
class IOPerformanceMetrics:
    """I/O performance metrics for a storage device."""
    device_path: str
    timestamp: datetime
    read_bytes_per_sec: float
    write_bytes_per_sec: float
    read_iops: float  # I/O operations per second
    write_iops: float
    read_latency_ms: Optional[float]
    write_latency_ms: Optional[float]
    queue_depth: Optional[int]
    utilization_percent: Optional[float]
    total_read_bytes: int
    total_write_bytes: int
    total_read_operations: int
    total_write_operations: int


@dataclass
class DiskMetrics:
    """Comprehensive disk metrics."""
    timestamp: datetime
    storage_devices: List[StorageInfo]
    io_performance: List[IOPerformanceMetrics]
    total_storage_gb: float
    total_used_gb: float
    total_free_gb: float
    overall_usage_percent: float
    aggregate_read_mb_per_sec: float
    aggregate_write_mb_per_sec: float
    aggregate_iops: float
    fastest_device_read_speed: float
    fastest_device_write_speed: float
    slowest_device_read_speed: float
    slowest_device_write_speed: float


class DiskMonitor:
    """Advanced disk monitoring with NVMe optimization and I/O analysis."""
    
    def __init__(self, app_state_manager: Optional[AppStateManager] = None):
        """Initialize the disk monitor."""
        self._app_state_manager = app_state_manager or AppStateManager()
        self._log_manager = get_log_manager(self._app_state_manager)
        self._logger = self._log_manager.get_logger("disk_monitor")
        self._validation_engine = ValidationEngine()
        
        # Monitoring state
        self._lock = threading.RLock()
        self._monitoring_enabled = False
        self._monitoring_task: Optional[asyncio.Task] = None
        self._sampling_interval = 1.0
        self._history_retention_minutes = 60
        
        # Metrics storage
        self._metrics_history: List[DiskMetrics] = []
        self._current_metrics: Optional[DiskMetrics] = None
        
        # I/O tracking
        self._last_io_stats: Dict[str, Any] = {}
        self._last_measurement_time: Optional[datetime] = None
        
        # Storage device cache
        self._storage_devices: List[StorageInfo] = []
        self._device_refresh_interval = 60  # Refresh device list every minute
        self._last_device_refresh: Optional[datetime] = None
        
        # Performance thresholds
        self._space_warning_threshold = 85.0  # Percent
        self._space_critical_threshold = 95.0  # Percent
        self._io_latency_warning_ms = 100.0
        self._io_latency_critical_ms = 500.0
        
        # Initialize storage detection
        self._refresh_storage_devices()
        
        self._logger.info(f"Disk monitor initialized with {len(self._storage_devices)} storage devices")
    
    def _refresh_storage_devices(self) -> None:
        """Refresh the list of storage devices."""
        try:
            self._storage_devices.clear()
            
            # Get disk partitions
            partitions = psutil.disk_partitions()
            
            for partition in partitions:
                try:
                    # Get usage information
                    usage = psutil.disk_usage(partition.mountpoint)
                    
                    # Determine storage type
                    storage_type = self._detect_storage_type(partition.device)
                    
                    # Determine file system type
                    fs_type = self._parse_filesystem_type(partition.fstype)
                    
                    # Check if it's a system drive
                    is_system_drive = self._is_system_drive(partition.mountpoint)
                    
                    # Check if removable
                    is_removable = 'removable' in partition.opts.lower() if partition.opts else False
                    
                    storage_info = StorageInfo(
                        device_path=partition.device,
                        mount_point=partition.mountpoint,
                        file_system=fs_type,
                        storage_type=storage_type,
                        total_gb=usage.total / (1024**3),
                        used_gb=usage.used / (1024**3),
                        free_gb=usage.free / (1024**3),
                        usage_percent=(usage.used / usage.total) * 100 if usage.total > 0 else 0,
                        is_removable=is_removable,
                        is_system_drive=is_system_drive,
                        device_name=self._get_device_name(partition.device),
                        model=self._get_device_model(partition.device),
                        interface=self._get_device_interface(partition.device)
                    )
                    
                    self._storage_devices.append(storage_info)
                    
                except (PermissionError, OSError, FileNotFoundError) as e:
                    self._logger.debug(f"Cannot access partition {partition.device}: {str(e)}")
                    continue
            
            self._last_device_refresh = datetime.now(timezone.utc)
            
        except Exception as e:
            self._logger.error(f"Error refreshing storage devices: {str(e)}")
    
    def _detect_storage_type(self, device_path: str) -> StorageType:
        """Detect the type of storage device."""
        try:
            device_path_lower = device_path.lower()
            
            # Check for NVMe
            if 'nvme' in device_path_lower:
                return StorageType.NVME
            
            # Check for network drives
            if device_path.startswith('\\\\') or 'network' in device_path_lower:
                return StorageType.NETWORK
            
            # For Windows, try to determine if it's SSD or HDD
            if platform.system() == "Windows":
                try:
                    import subprocess
                    # Use PowerShell to check if drive is SSD
                    cmd = f'Get-PhysicalDisk | Where-Object {{$_.DeviceID -like "*{device_path[0]}*"}} | Select-Object MediaType'
                    result = subprocess.run(
                        ["powershell", "-Command", cmd],
                        capture_output=True,
                        text=True,
                        timeout=5
                    )
                    
                    if result.returncode == 0 and 'SSD' in result.stdout:
                        return StorageType.SSD
                    elif result.returncode == 0 and 'HDD' in result.stdout:
                        return StorageType.HDD
                        
                except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError):
                    pass
            
            # For Linux, check /sys/block for rotational
            elif platform.system() == "Linux":
                try:
                    device_name = device_path.split('/')[-1].rstrip('0123456789')
                    rotational_path = f"/sys/block/{device_name}/queue/rotational"
                    
                    if Path(rotational_path).exists():
                        with open(rotational_path, 'r') as f:
                            rotational = f.read().strip()
                            return StorageType.HDD if rotational == '1' else StorageType.SSD
                            
                except (OSError, FileNotFoundError):
                    pass
            
            # Default assumption based on common patterns
            if any(keyword in device_path_lower for keyword in ['ssd', 'solid']):
                return StorageType.SSD
            elif any(keyword in device_path_lower for keyword in ['hdd', 'hard']):
                return StorageType.HDD
            
            return StorageType.UNKNOWN
            
        except Exception as e:
            self._logger.debug(f"Error detecting storage type for {device_path}: {str(e)}")
            return StorageType.UNKNOWN
    
    def _parse_filesystem_type(self, fstype: str) -> FileSystemType:
        """Parse file system type from string."""
        if not fstype:
            return FileSystemType.UNKNOWN
        
        fstype_lower = fstype.lower()
        
        if fstype_lower == 'ntfs':
            return FileSystemType.NTFS
        elif fstype_lower in ['fat32', 'vfat']:
            return FileSystemType.FAT32
        elif fstype_lower == 'ext4':
            return FileSystemType.EXT4
        elif fstype_lower == 'ext3':
            return FileSystemType.EXT3
        elif fstype_lower == 'xfs':
            return FileSystemType.XFS
        elif fstype_lower == 'btrfs':
            return FileSystemType.BTRFS
        elif fstype_lower == 'apfs':
            return FileSystemType.APFS
        elif fstype_lower in ['hfs+', 'hfsplus']:
            return FileSystemType.HFS_PLUS
        else:
            return FileSystemType.UNKNOWN
    
    def _is_system_drive(self, mount_point: str) -> bool:
        """Check if the mount point is a system drive."""
        system_mount_points = ['/', '/boot', '/usr', '/var', '/etc']
        
        if platform.system() == "Windows":
            # On Windows, C: is typically the system drive
            return mount_point.upper().startswith('C:')
        else:
            # On Unix-like systems
            return mount_point in system_mount_points or mount_point == '/'
    
    def _get_device_name(self, device_path: str) -> Optional[str]:
        """Get a human-readable device name."""
        try:
            if platform.system() == "Windows":
                # Extract drive letter for Windows
                if len(device_path) >= 2 and device_path[1] == ':':
                    return f"Drive {device_path[0].upper()}"
            else:
                # For Unix-like systems, use the device path
                return device_path.split('/')[-1]
            
            return device_path
            
        except Exception:
            return None
    
    def _get_device_model(self, device_path: str) -> Optional[str]:
        """Get device model information."""
        # This would require platform-specific implementations
        # For now, return None as a placeholder
        return None
    
    def _get_device_interface(self, device_path: str) -> Optional[str]:
        """Get device interface type (SATA, NVMe, USB, etc.)."""
        device_path_lower = device_path.lower()
        
        if 'nvme' in device_path_lower:
            return "NVMe"
        elif 'usb' in device_path_lower:
            return "USB"
        elif 'sata' in device_path_lower:
            return "SATA"
        else:
            return None

    async def start_monitoring(self, sampling_interval: float = 1.0) -> None:
        """Start disk monitoring."""
        with self._lock:
            if self._monitoring_enabled:
                self._logger.warning("Disk monitoring already started")
                return

            self._sampling_interval = sampling_interval
            self._monitoring_enabled = True
            self._monitoring_task = asyncio.create_task(self._monitoring_loop())
            self._logger.info("Disk monitoring started")

    async def stop_monitoring(self) -> None:
        """Stop disk monitoring."""
        with self._lock:
            if not self._monitoring_enabled:
                return

            self._monitoring_enabled = False

            if self._monitoring_task:
                self._monitoring_task.cancel()
                try:
                    await self._monitoring_task
                except asyncio.CancelledError:
                    pass
                self._monitoring_task = None

            self._logger.info("Disk monitoring stopped")

    async def _monitoring_loop(self) -> None:
        """Main disk monitoring loop."""
        try:
            while self._monitoring_enabled:
                start_time = time.time()

                # Refresh device list periodically
                current_time = datetime.now(timezone.utc)
                if (self._last_device_refresh is None or
                    (current_time - self._last_device_refresh).total_seconds() > self._device_refresh_interval):
                    self._refresh_storage_devices()

                # Collect metrics
                metrics = self._collect_disk_metrics()

                with self._lock:
                    self._current_metrics = metrics
                    self._metrics_history.append(metrics)

                    # Cleanup old metrics
                    cutoff_time = datetime.now(timezone.utc) - timedelta(
                        minutes=self._history_retention_minutes
                    )
                    self._metrics_history = [
                        m for m in self._metrics_history if m.timestamp >= cutoff_time
                    ]

                # Calculate sleep time
                elapsed = time.time() - start_time
                sleep_time = max(0, self._sampling_interval - elapsed)

                if sleep_time > 0:
                    await asyncio.sleep(sleep_time)

        except asyncio.CancelledError:
            self._logger.info("Disk monitoring loop cancelled")
            raise
        except Exception as e:
            self._logger.error(f"Error in disk monitoring loop: {str(e)}")
            raise

    def _collect_disk_metrics(self) -> DiskMetrics:
        """Collect comprehensive disk metrics."""
        try:
            current_time = datetime.now(timezone.utc)

            # Update storage device usage
            updated_devices = []
            for device in self._storage_devices:
                try:
                    usage = psutil.disk_usage(device.mount_point)

                    updated_device = StorageInfo(
                        device_path=device.device_path,
                        mount_point=device.mount_point,
                        file_system=device.file_system,
                        storage_type=device.storage_type,
                        total_gb=usage.total / (1024**3),
                        used_gb=usage.used / (1024**3),
                        free_gb=usage.free / (1024**3),
                        usage_percent=(usage.used / usage.total) * 100 if usage.total > 0 else 0,
                        is_removable=device.is_removable,
                        is_system_drive=device.is_system_drive,
                        device_name=device.device_name,
                        serial_number=device.serial_number,
                        model=device.model,
                        interface=device.interface
                    )

                    updated_devices.append(updated_device)

                except (PermissionError, OSError, FileNotFoundError):
                    # Device might have been removed
                    continue

            # Collect I/O performance metrics
            io_performance = []
            current_io_stats = psutil.disk_io_counters(perdisk=True)

            if current_io_stats:
                for device_name, io_stats in current_io_stats.items():
                    io_metrics = self._calculate_io_metrics(device_name, io_stats, current_time)
                    if io_metrics:
                        io_performance.append(io_metrics)

            # Calculate aggregate metrics
            total_storage_gb = sum(device.total_gb for device in updated_devices)
            total_used_gb = sum(device.used_gb for device in updated_devices)
            total_free_gb = sum(device.free_gb for device in updated_devices)
            overall_usage_percent = (total_used_gb / total_storage_gb) * 100 if total_storage_gb > 0 else 0

            aggregate_read_mb_per_sec = sum(io.read_bytes_per_sec for io in io_performance) / (1024**2)
            aggregate_write_mb_per_sec = sum(io.write_bytes_per_sec for io in io_performance) / (1024**2)
            aggregate_iops = sum(io.read_iops + io.write_iops for io in io_performance)

            # Find fastest and slowest devices
            read_speeds = [io.read_bytes_per_sec / (1024**2) for io in io_performance if io.read_bytes_per_sec > 0]
            write_speeds = [io.write_bytes_per_sec / (1024**2) for io in io_performance if io.write_bytes_per_sec > 0]

            fastest_read = max(read_speeds) if read_speeds else 0.0
            slowest_read = min(read_speeds) if read_speeds else 0.0
            fastest_write = max(write_speeds) if write_speeds else 0.0
            slowest_write = min(write_speeds) if write_speeds else 0.0

            return DiskMetrics(
                timestamp=current_time,
                storage_devices=updated_devices,
                io_performance=io_performance,
                total_storage_gb=total_storage_gb,
                total_used_gb=total_used_gb,
                total_free_gb=total_free_gb,
                overall_usage_percent=overall_usage_percent,
                aggregate_read_mb_per_sec=aggregate_read_mb_per_sec,
                aggregate_write_mb_per_sec=aggregate_write_mb_per_sec,
                aggregate_iops=aggregate_iops,
                fastest_device_read_speed=fastest_read,
                fastest_device_write_speed=fastest_write,
                slowest_device_read_speed=slowest_read,
                slowest_device_write_speed=slowest_write
            )

        except Exception as e:
            self._logger.error(f"Error collecting disk metrics: {str(e)}")
            # Return default metrics on error
            return DiskMetrics(
                timestamp=datetime.now(timezone.utc),
                storage_devices=[],
                io_performance=[],
                total_storage_gb=0.0,
                total_used_gb=0.0,
                total_free_gb=0.0,
                overall_usage_percent=0.0,
                aggregate_read_mb_per_sec=0.0,
                aggregate_write_mb_per_sec=0.0,
                aggregate_iops=0.0,
                fastest_device_read_speed=0.0,
                fastest_device_write_speed=0.0,
                slowest_device_read_speed=0.0,
                slowest_device_write_speed=0.0
            )

    def _calculate_io_metrics(self, device_name: str, io_stats: Any,
                            current_time: datetime) -> Optional[IOPerformanceMetrics]:
        """Calculate I/O performance metrics for a device."""
        try:
            # Get previous stats for rate calculation
            if device_name in self._last_io_stats and self._last_measurement_time:
                last_stats = self._last_io_stats[device_name]
                time_delta = (current_time - self._last_measurement_time).total_seconds()

                if time_delta > 0:
                    # Calculate rates
                    read_bytes_delta = io_stats.read_bytes - last_stats.read_bytes
                    write_bytes_delta = io_stats.write_bytes - last_stats.write_bytes
                    read_ops_delta = io_stats.read_count - last_stats.read_count
                    write_ops_delta = io_stats.write_count - last_stats.write_count

                    read_bytes_per_sec = read_bytes_delta / time_delta
                    write_bytes_per_sec = write_bytes_delta / time_delta
                    read_iops = read_ops_delta / time_delta
                    write_iops = write_ops_delta / time_delta
                else:
                    read_bytes_per_sec = write_bytes_per_sec = 0.0
                    read_iops = write_iops = 0.0
            else:
                read_bytes_per_sec = write_bytes_per_sec = 0.0
                read_iops = write_iops = 0.0

            # Store current stats for next calculation
            self._last_io_stats[device_name] = io_stats

            # Calculate latency (if available)
            read_latency_ms = None
            write_latency_ms = None

            if hasattr(io_stats, 'read_time') and hasattr(io_stats, 'read_count'):
                if io_stats.read_count > 0:
                    read_latency_ms = io_stats.read_time / io_stats.read_count

            if hasattr(io_stats, 'write_time') and hasattr(io_stats, 'write_count'):
                if io_stats.write_count > 0:
                    write_latency_ms = io_stats.write_time / io_stats.write_count

            return IOPerformanceMetrics(
                device_path=device_name,
                timestamp=current_time,
                read_bytes_per_sec=read_bytes_per_sec,
                write_bytes_per_sec=write_bytes_per_sec,
                read_iops=read_iops,
                write_iops=write_iops,
                read_latency_ms=read_latency_ms,
                write_latency_ms=write_latency_ms,
                queue_depth=None,  # Not available in psutil
                utilization_percent=None,  # Not available in psutil
                total_read_bytes=io_stats.read_bytes,
                total_write_bytes=io_stats.write_bytes,
                total_read_operations=io_stats.read_count,
                total_write_operations=io_stats.write_count
            )

        except Exception as e:
            self._logger.debug(f"Error calculating I/O metrics for {device_name}: {str(e)}")
            return None

    def get_current_metrics(self) -> Optional[DiskMetrics]:
        """Get the most recent disk metrics."""
        with self._lock:
            if self._current_metrics is None:
                return self._collect_disk_metrics()
            return self._current_metrics

    def get_metrics_history(self, minutes: int = 5) -> List[DiskMetrics]:
        """Get historical disk metrics."""
        with self._lock:
            cutoff_time = datetime.now(timezone.utc) - timedelta(minutes=minutes)
            return [m for m in self._metrics_history if m.timestamp >= cutoff_time]

    def get_storage_devices(self) -> List[StorageInfo]:
        """Get information about all storage devices."""
        with self._lock:
            return self._storage_devices.copy()

    def get_device_by_mount_point(self, mount_point: str) -> Optional[StorageInfo]:
        """Get storage device information by mount point."""
        with self._lock:
            for device in self._storage_devices:
                if device.mount_point == mount_point:
                    return device
            return None

    def get_system_drives(self) -> List[StorageInfo]:
        """Get all system drives."""
        with self._lock:
            return [device for device in self._storage_devices if device.is_system_drive]

    def get_nvme_drives(self) -> List[StorageInfo]:
        """Get all NVMe drives."""
        with self._lock:
            return [device for device in self._storage_devices if device.storage_type == StorageType.NVME]

    def get_ssd_drives(self) -> List[StorageInfo]:
        """Get all SSD drives."""
        with self._lock:
            return [device for device in self._storage_devices if device.storage_type == StorageType.SSD]

    def get_disk_summary(self) -> Dict[str, Any]:
        """Get a comprehensive disk usage summary."""
        with self._lock:
            current = self.get_current_metrics()
            if not current:
                return {"error": "No metrics available"}

            device_summaries = []
            for device in current.storage_devices:
                device_summaries.append({
                    "device_path": device.device_path,
                    "mount_point": device.mount_point,
                    "device_name": device.device_name,
                    "storage_type": device.storage_type.value,
                    "file_system": device.file_system.value,
                    "total_gb": device.total_gb,
                    "used_gb": device.used_gb,
                    "free_gb": device.free_gb,
                    "usage_percent": device.usage_percent,
                    "is_system_drive": device.is_system_drive,
                    "interface": device.interface
                })

            return {
                "total_storage_gb": current.total_storage_gb,
                "total_used_gb": current.total_used_gb,
                "total_free_gb": current.total_free_gb,
                "overall_usage_percent": current.overall_usage_percent,
                "aggregate_read_mb_per_sec": current.aggregate_read_mb_per_sec,
                "aggregate_write_mb_per_sec": current.aggregate_write_mb_per_sec,
                "aggregate_iops": current.aggregate_iops,
                "fastest_read_speed_mb_per_sec": current.fastest_device_read_speed,
                "fastest_write_speed_mb_per_sec": current.fastest_device_write_speed,
                "device_count": len(current.storage_devices),
                "nvme_count": len([d for d in current.storage_devices if d.storage_type == StorageType.NVME]),
                "ssd_count": len([d for d in current.storage_devices if d.storage_type == StorageType.SSD]),
                "hdd_count": len([d for d in current.storage_devices if d.storage_type == StorageType.HDD]),
                "devices": device_summaries
            }

    def get_io_performance_summary(self) -> Dict[str, Any]:
        """Get I/O performance summary."""
        with self._lock:
            current = self.get_current_metrics()
            if not current or not current.io_performance:
                return {"error": "No I/O performance data available"}

            io_summaries = []
            for io_perf in current.io_performance:
                io_summaries.append({
                    "device": io_perf.device_path,
                    "read_mb_per_sec": io_perf.read_bytes_per_sec / (1024**2),
                    "write_mb_per_sec": io_perf.write_bytes_per_sec / (1024**2),
                    "read_iops": io_perf.read_iops,
                    "write_iops": io_perf.write_iops,
                    "read_latency_ms": io_perf.read_latency_ms,
                    "write_latency_ms": io_perf.write_latency_ms,
                    "total_read_gb": io_perf.total_read_bytes / (1024**3),
                    "total_write_gb": io_perf.total_write_bytes / (1024**3)
                })

            return {
                "aggregate_read_mb_per_sec": current.aggregate_read_mb_per_sec,
                "aggregate_write_mb_per_sec": current.aggregate_write_mb_per_sec,
                "aggregate_iops": current.aggregate_iops,
                "device_performance": io_summaries
            }

    def check_disk_space_alerts(self) -> List[Dict[str, Any]]:
        """Check for disk space alerts."""
        alerts = []

        with self._lock:
            for device in self._storage_devices:
                if device.usage_percent >= self._space_critical_threshold:
                    alerts.append({
                        "severity": "CRITICAL",
                        "device": device.device_path,
                        "mount_point": device.mount_point,
                        "usage_percent": device.usage_percent,
                        "free_gb": device.free_gb,
                        "message": f"Critical: Disk space very low on {device.mount_point} ({device.usage_percent:.1f}% used)"
                    })
                elif device.usage_percent >= self._space_warning_threshold:
                    alerts.append({
                        "severity": "WARNING",
                        "device": device.device_path,
                        "mount_point": device.mount_point,
                        "usage_percent": device.usage_percent,
                        "free_gb": device.free_gb,
                        "message": f"Warning: Disk space low on {device.mount_point} ({device.usage_percent:.1f}% used)"
                    })

        return alerts

    def get_fastest_storage_device(self) -> Optional[StorageInfo]:
        """Get the fastest storage device based on type priority."""
        with self._lock:
            # Priority: NVMe > SSD > HDD
            nvme_devices = [d for d in self._storage_devices if d.storage_type == StorageType.NVME]
            if nvme_devices:
                return max(nvme_devices, key=lambda d: d.total_gb)  # Largest NVMe

            ssd_devices = [d for d in self._storage_devices if d.storage_type == StorageType.SSD]
            if ssd_devices:
                return max(ssd_devices, key=lambda d: d.total_gb)  # Largest SSD

            hdd_devices = [d for d in self._storage_devices if d.storage_type == StorageType.HDD]
            if hdd_devices:
                return max(hdd_devices, key=lambda d: d.total_gb)  # Largest HDD

            return None

    def get_available_space_gb(self, mount_point: Optional[str] = None) -> float:
        """Get available space in GB for a specific mount point or total."""
        with self._lock:
            if mount_point:
                device = self.get_device_by_mount_point(mount_point)
                return device.free_gb if device else 0.0
            else:
                return sum(device.free_gb for device in self._storage_devices)

    def configure_thresholds(self, space_warning: float = 85.0,
                           space_critical: float = 95.0,
                           latency_warning_ms: float = 100.0,
                           latency_critical_ms: float = 500.0) -> None:
        """Configure disk monitoring thresholds."""
        with self._lock:
            self._space_warning_threshold = space_warning
            self._space_critical_threshold = space_critical
            self._io_latency_warning_ms = latency_warning_ms
            self._io_latency_critical_ms = latency_critical_ms
            self._logger.info(f"Disk thresholds updated: space_warning={space_warning}%, "
                            f"space_critical={space_critical}%, latency_warning={latency_warning_ms}ms")

    def refresh_devices(self) -> None:
        """Manually refresh the storage device list."""
        with self._lock:
            self._logger.info("Manually refreshing storage devices")
            self._refresh_storage_devices()

    def __del__(self):
        """Cleanup on destruction."""
        if self._monitoring_enabled:
            asyncio.create_task(self.stop_monitoring())
