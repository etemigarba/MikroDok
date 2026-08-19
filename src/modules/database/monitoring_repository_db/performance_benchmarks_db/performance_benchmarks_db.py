"""
Module: performance_benchmarks_db
Description: Persists model performance test results and hardware configuration data with comprehensive metrics tracking
Phase: 4
Location: /src/modules/database/monitoring_repository_db/performance_benchmarks_db/
"""

# Standard library imports
import sqlite3
import threading
import json
from dataclasses import dataclass, asdict
from datetime import datetime, timezone, timedelta
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any, Union
from uuid import uuid4

# Local imports
from src.modules.logic.logging_infrastructure_lg.log_manager_lg.log_manager_lg import get_logger


class BenchmarkType(Enum):
    """Types of performance benchmarks."""
    INFERENCE = "inference"
    TRAINING = "training"
    MEMORY = "memory"
    THROUGHPUT = "throughput"
    LATENCY = "latency"
    ACCURACY = "accuracy"
    HARDWARE = "hardware"


class BenchmarkStatus(Enum):
    """Status of benchmark execution."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class HardwareConfiguration:
    """Hardware configuration data structure."""
    config_id: str
    cpu_model: str
    cpu_cores: int
    cpu_threads: int
    cpu_frequency_ghz: float
    memory_total_gb: float
    gpu_model: Optional[str] = None
    gpu_memory_gb: Optional[float] = None
    gpu_compute_capability: Optional[str] = None
    storage_type: Optional[str] = None
    storage_capacity_gb: Optional[float] = None
    network_bandwidth_mbps: Optional[float] = None
    created_at: Optional[datetime] = None


@dataclass
class BenchmarkResult:
    """Benchmark result data structure."""
    result_id: str
    benchmark_id: str
    benchmark_type: BenchmarkType
    model_name: str
    model_version: str
    hardware_config_id: str
    status: BenchmarkStatus
    start_time: datetime
    end_time: Optional[datetime]
    duration_seconds: Optional[float]
    metrics: Dict[str, Any]
    error_message: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class PerformanceBenchmarksDB:
    """
    Performance benchmarks database manager.
    
    Handles storage and retrieval of model performance test results,
    hardware configuration data, and comprehensive metrics tracking
    for performance analysis and optimization.
    """
    
    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize the performance benchmarks database.
        
        Args:
            db_path: Path to the database file
        """
        if db_path is None:
            # Default to monitoring data directory
            data_dir = Path.home() / ".mikrodok" / "data" / "monitoring"
            data_dir.mkdir(parents=True, exist_ok=True)
            db_path = str(data_dir / "performance_benchmarks.db")
        
        self._db_path = db_path
        self._lock = threading.RLock()
        self._logger = get_logger(__name__)
        
        # Retention settings
        self._benchmark_retention_days = 365  # Keep benchmarks for 1 year
        self._hardware_config_retention_days = 730  # Keep hardware configs for 2 years
        
        self._initialize_database()
        self._start_cleanup_thread()
        
        self._logger.info(f"PerformanceBenchmarksDB initialized with database: {self._db_path}")
    
    def _initialize_database(self) -> None:
        """Initialize database tables and indexes."""
        try:
            conn = sqlite3.connect(self._db_path)
            cursor = conn.cursor()
            
            # Enable WAL mode for better concurrency
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA synchronous=NORMAL")
            cursor.execute("PRAGMA cache_size=10000")
            cursor.execute("PRAGMA temp_store=MEMORY")
            cursor.execute("PRAGMA foreign_keys=ON")
            
            # Create hardware configurations table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS hardware_configurations (
                    config_id TEXT PRIMARY KEY,
                    cpu_model TEXT NOT NULL,
                    cpu_cores INTEGER NOT NULL,
                    cpu_threads INTEGER NOT NULL,
                    cpu_frequency_ghz REAL NOT NULL,
                    memory_total_gb REAL NOT NULL,
                    gpu_model TEXT,
                    gpu_memory_gb REAL,
                    gpu_compute_capability TEXT,
                    storage_type TEXT,
                    storage_capacity_gb REAL,
                    network_bandwidth_mbps REAL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Create benchmark results table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS benchmark_results (
                    result_id TEXT PRIMARY KEY,
                    benchmark_id TEXT NOT NULL,
                    benchmark_type TEXT NOT NULL,
                    model_name TEXT NOT NULL,
                    model_version TEXT NOT NULL,
                    hardware_config_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    start_time TEXT NOT NULL,
                    end_time TEXT,
                    duration_seconds REAL,
                    metrics TEXT NOT NULL,
                    error_message TEXT,
                    metadata TEXT,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (hardware_config_id) REFERENCES hardware_configurations (config_id)
                )
            """)
            
            # Create benchmark comparisons table for tracking performance trends
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS benchmark_comparisons (
                    comparison_id TEXT PRIMARY KEY,
                    baseline_result_id TEXT NOT NULL,
                    comparison_result_id TEXT NOT NULL,
                    performance_delta_percent REAL,
                    comparison_metrics TEXT,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (baseline_result_id) REFERENCES benchmark_results (result_id),
                    FOREIGN KEY (comparison_result_id) REFERENCES benchmark_results (result_id)
                )
            """)
            
            # Create indexes for efficient queries
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_benchmark_results_type_model 
                ON benchmark_results(benchmark_type, model_name, model_version)
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_benchmark_results_hardware 
                ON benchmark_results(hardware_config_id, start_time)
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_benchmark_results_status_time 
                ON benchmark_results(status, start_time)
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_hardware_configs_specs 
                ON hardware_configurations(cpu_model, gpu_model, memory_total_gb)
            """)
            
            conn.commit()
            conn.close()
            
            self._logger.info("Performance benchmarks database initialized successfully")
            
        except Exception as e:
            self._logger.error(f"Failed to initialize performance benchmarks database: {e}")
            raise

    def _start_cleanup_thread(self) -> None:
        """Start background thread for data cleanup."""
        def cleanup_worker():
            import time
            while True:
                try:
                    time.sleep(86400)  # Run daily
                    self._cleanup_old_data()
                except Exception as e:
                    self._logger.error(f"Cleanup thread error: {e}")

        cleanup_thread = threading.Thread(target=cleanup_worker, daemon=True)
        cleanup_thread.start()
        self._logger.info("Started cleanup thread")

    def store_hardware_configuration(self, cpu_model: str, cpu_cores: int, cpu_threads: int,
                                   cpu_frequency_ghz: float, memory_total_gb: float,
                                   gpu_model: Optional[str] = None, gpu_memory_gb: Optional[float] = None,
                                   gpu_compute_capability: Optional[str] = None,
                                   storage_type: Optional[str] = None,
                                   storage_capacity_gb: Optional[float] = None,
                                   network_bandwidth_mbps: Optional[float] = None) -> str:
        """
        Store hardware configuration.

        Args:
            cpu_model: CPU model name
            cpu_cores: Number of CPU cores
            cpu_threads: Number of CPU threads
            cpu_frequency_ghz: CPU frequency in GHz
            memory_total_gb: Total memory in GB
            gpu_model: Optional GPU model name
            gpu_memory_gb: Optional GPU memory in GB
            gpu_compute_capability: Optional GPU compute capability
            storage_type: Optional storage type (SSD, HDD, NVMe)
            storage_capacity_gb: Optional storage capacity in GB
            network_bandwidth_mbps: Optional network bandwidth in Mbps

        Returns:
            Hardware configuration ID
        """
        config_id = str(uuid4())

        with self._lock:
            try:
                conn = sqlite3.connect(self._db_path)
                cursor = conn.cursor()

                cursor.execute("""
                    INSERT INTO hardware_configurations (
                        config_id, cpu_model, cpu_cores, cpu_threads, cpu_frequency_ghz,
                        memory_total_gb, gpu_model, gpu_memory_gb, gpu_compute_capability,
                        storage_type, storage_capacity_gb, network_bandwidth_mbps
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    config_id, cpu_model, cpu_cores, cpu_threads, cpu_frequency_ghz,
                    memory_total_gb, gpu_model, gpu_memory_gb, gpu_compute_capability,
                    storage_type, storage_capacity_gb, network_bandwidth_mbps
                ))

                conn.commit()
                conn.close()

                self._logger.info(f"Stored hardware configuration: {config_id}")
                return config_id

            except Exception as e:
                self._logger.error(f"Failed to store hardware configuration: {e}")
                raise

    def get_hardware_configuration(self, config_id: str) -> Optional[HardwareConfiguration]:
        """
        Get hardware configuration by ID.

        Args:
            config_id: Hardware configuration ID

        Returns:
            Hardware configuration or None if not found
        """
        with self._lock:
            try:
                conn = sqlite3.connect(self._db_path)
                cursor = conn.cursor()

                cursor.execute("""
                    SELECT config_id, cpu_model, cpu_cores, cpu_threads, cpu_frequency_ghz,
                           memory_total_gb, gpu_model, gpu_memory_gb, gpu_compute_capability,
                           storage_type, storage_capacity_gb, network_bandwidth_mbps, created_at
                    FROM hardware_configurations
                    WHERE config_id = ?
                """, (config_id,))

                row = cursor.fetchone()
                conn.close()

                if row:
                    return HardwareConfiguration(
                        config_id=row[0],
                        cpu_model=row[1],
                        cpu_cores=row[2],
                        cpu_threads=row[3],
                        cpu_frequency_ghz=row[4],
                        memory_total_gb=row[5],
                        gpu_model=row[6],
                        gpu_memory_gb=row[7],
                        gpu_compute_capability=row[8],
                        storage_type=row[9],
                        storage_capacity_gb=row[10],
                        network_bandwidth_mbps=row[11],
                        created_at=datetime.fromisoformat(row[12]) if row[12] else None
                    )

                return None

            except Exception as e:
                self._logger.error(f"Failed to get hardware configuration: {e}")
                raise

    def find_similar_hardware_configuration(self, cpu_model: str, memory_total_gb: float,
                                          gpu_model: Optional[str] = None) -> Optional[str]:
        """
        Find existing hardware configuration with similar specs.

        Args:
            cpu_model: CPU model to match
            memory_total_gb: Memory size to match (within 10% tolerance)
            gpu_model: Optional GPU model to match

        Returns:
            Configuration ID if found, None otherwise
        """
        with self._lock:
            try:
                conn = sqlite3.connect(self._db_path)
                cursor = conn.cursor()

                memory_tolerance = memory_total_gb * 0.1

                if gpu_model:
                    cursor.execute("""
                        SELECT config_id FROM hardware_configurations
                        WHERE cpu_model = ? AND gpu_model = ?
                        AND memory_total_gb BETWEEN ? AND ?
                        ORDER BY created_at DESC LIMIT 1
                    """, (
                        cpu_model, gpu_model,
                        memory_total_gb - memory_tolerance,
                        memory_total_gb + memory_tolerance
                    ))
                else:
                    cursor.execute("""
                        SELECT config_id FROM hardware_configurations
                        WHERE cpu_model = ? AND gpu_model IS NULL
                        AND memory_total_gb BETWEEN ? AND ?
                        ORDER BY created_at DESC LIMIT 1
                    """, (
                        cpu_model,
                        memory_total_gb - memory_tolerance,
                        memory_total_gb + memory_tolerance
                    ))

                row = cursor.fetchone()
                conn.close()

                return row[0] if row else None

            except Exception as e:
                self._logger.error(f"Failed to find similar hardware configuration: {e}")
                raise

    def start_benchmark(self, benchmark_id: str, benchmark_type: BenchmarkType,
                       model_name: str, model_version: str, hardware_config_id: str,
                       metadata: Optional[Dict[str, Any]] = None) -> str:
        """
        Start a new benchmark and return result ID.

        Args:
            benchmark_id: Unique benchmark identifier
            benchmark_type: Type of benchmark
            model_name: Name of the model being benchmarked
            model_version: Version of the model
            hardware_config_id: Hardware configuration ID
            metadata: Optional metadata

        Returns:
            Benchmark result ID
        """
        result_id = str(uuid4())
        start_time = datetime.now(timezone.utc)

        with self._lock:
            try:
                conn = sqlite3.connect(self._db_path)
                cursor = conn.cursor()

                cursor.execute("""
                    INSERT INTO benchmark_results (
                        result_id, benchmark_id, benchmark_type, model_name, model_version,
                        hardware_config_id, status, start_time, metrics, metadata
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    result_id, benchmark_id, benchmark_type.value, model_name, model_version,
                    hardware_config_id, BenchmarkStatus.RUNNING.value, start_time.isoformat(),
                    json.dumps({}), json.dumps(metadata) if metadata else None
                ))

                conn.commit()
                conn.close()

                self._logger.info(f"Started benchmark: {benchmark_id} ({result_id})")
                return result_id

            except Exception as e:
                self._logger.error(f"Failed to start benchmark: {e}")
                raise

    def complete_benchmark(self, result_id: str, metrics: Dict[str, Any],
                          error_message: Optional[str] = None) -> None:
        """
        Complete a benchmark with results.

        Args:
            result_id: Benchmark result ID
            metrics: Performance metrics
            error_message: Optional error message if benchmark failed
        """
        end_time = datetime.now(timezone.utc)
        status = BenchmarkStatus.FAILED if error_message else BenchmarkStatus.COMPLETED

        with self._lock:
            try:
                conn = sqlite3.connect(self._db_path)
                cursor = conn.cursor()

                # Get start time to calculate duration
                cursor.execute("SELECT start_time FROM benchmark_results WHERE result_id = ?", (result_id,))
                row = cursor.fetchone()

                if not row:
                    raise ValueError(f"Benchmark result not found: {result_id}")

                start_time = datetime.fromisoformat(row[0])
                duration_seconds = (end_time - start_time).total_seconds()

                cursor.execute("""
                    UPDATE benchmark_results SET
                        status = ?, end_time = ?, duration_seconds = ?,
                        metrics = ?, error_message = ?
                    WHERE result_id = ?
                """, (
                    status.value, end_time.isoformat(), duration_seconds,
                    json.dumps(metrics), error_message, result_id
                ))

                conn.commit()
                conn.close()

                self._logger.info(f"Completed benchmark: {result_id} ({status.value})")

            except Exception as e:
                self._logger.error(f"Failed to complete benchmark: {e}")
                raise

    def get_benchmark_result(self, result_id: str) -> Optional[BenchmarkResult]:
        """
        Get benchmark result by ID.

        Args:
            result_id: Benchmark result ID

        Returns:
            Benchmark result or None if not found
        """
        with self._lock:
            try:
                conn = sqlite3.connect(self._db_path)
                cursor = conn.cursor()

                cursor.execute("""
                    SELECT result_id, benchmark_id, benchmark_type, model_name, model_version,
                           hardware_config_id, status, start_time, end_time, duration_seconds,
                           metrics, error_message, metadata
                    FROM benchmark_results
                    WHERE result_id = ?
                """, (result_id,))

                row = cursor.fetchone()
                conn.close()

                if row:
                    return BenchmarkResult(
                        result_id=row[0],
                        benchmark_id=row[1],
                        benchmark_type=BenchmarkType(row[2]),
                        model_name=row[3],
                        model_version=row[4],
                        hardware_config_id=row[5],
                        status=BenchmarkStatus(row[6]),
                        start_time=datetime.fromisoformat(row[7]),
                        end_time=datetime.fromisoformat(row[8]) if row[8] else None,
                        duration_seconds=row[9],
                        metrics=json.loads(row[10]) if row[10] else {},
                        error_message=row[11],
                        metadata=json.loads(row[12]) if row[12] else None
                    )

                return None

            except Exception as e:
                self._logger.error(f"Failed to get benchmark result: {e}")
                raise

    def get_benchmark_results_by_model(self, model_name: str, model_version: Optional[str] = None,
                                      benchmark_type: Optional[BenchmarkType] = None,
                                      limit: int = 100) -> List[BenchmarkResult]:
        """
        Get benchmark results for a specific model.

        Args:
            model_name: Name of the model
            model_version: Optional specific version
            benchmark_type: Optional benchmark type filter
            limit: Maximum number of results

        Returns:
            List of benchmark results
        """
        with self._lock:
            try:
                conn = sqlite3.connect(self._db_path)
                cursor = conn.cursor()

                query = """
                    SELECT result_id, benchmark_id, benchmark_type, model_name, model_version,
                           hardware_config_id, status, start_time, end_time, duration_seconds,
                           metrics, error_message, metadata
                    FROM benchmark_results
                    WHERE model_name = ?
                """
                params = [model_name]

                if model_version:
                    query += " AND model_version = ?"
                    params.append(model_version)

                if benchmark_type:
                    query += " AND benchmark_type = ?"
                    params.append(benchmark_type.value)

                query += " ORDER BY start_time DESC LIMIT ?"
                params.append(limit)

                cursor.execute(query, params)
                rows = cursor.fetchall()
                conn.close()

                results = []
                for row in rows:
                    result = BenchmarkResult(
                        result_id=row[0],
                        benchmark_id=row[1],
                        benchmark_type=BenchmarkType(row[2]),
                        model_name=row[3],
                        model_version=row[4],
                        hardware_config_id=row[5],
                        status=BenchmarkStatus(row[6]),
                        start_time=datetime.fromisoformat(row[7]),
                        end_time=datetime.fromisoformat(row[8]) if row[8] else None,
                        duration_seconds=row[9],
                        metrics=json.loads(row[10]) if row[10] else {},
                        error_message=row[11],
                        metadata=json.loads(row[12]) if row[12] else None
                    )
                    results.append(result)

                return results

            except Exception as e:
                self._logger.error(f"Failed to get benchmark results by model: {e}")
                raise

    def get_performance_trends(self, model_name: str, metric_name: str,
                              days: int = 30) -> List[Tuple[datetime, float]]:
        """
        Get performance trends for a model and metric over time.

        Args:
            model_name: Name of the model
            metric_name: Name of the metric to track
            days: Number of days to look back

        Returns:
            List of (timestamp, value) tuples
        """
        end_time = datetime.now(timezone.utc)
        start_time = end_time - timedelta(days=days)

        with self._lock:
            try:
                conn = sqlite3.connect(self._db_path)
                cursor = conn.cursor()

                cursor.execute("""
                    SELECT start_time, metrics FROM benchmark_results
                    WHERE model_name = ? AND status = 'completed'
                    AND start_time >= ? AND start_time <= ?
                    ORDER BY start_time
                """, (model_name, start_time.isoformat(), end_time.isoformat()))

                rows = cursor.fetchall()
                conn.close()

                trends = []
                for row in rows:
                    timestamp = datetime.fromisoformat(row[0])
                    metrics = json.loads(row[1]) if row[1] else {}

                    if metric_name in metrics:
                        trends.append((timestamp, float(metrics[metric_name])))

                return trends

            except Exception as e:
                self._logger.error(f"Failed to get performance trends: {e}")
                raise

    def compare_benchmarks(self, baseline_result_id: str, comparison_result_id: str) -> str:
        """
        Compare two benchmark results and store the comparison.

        Args:
            baseline_result_id: ID of baseline benchmark result
            comparison_result_id: ID of comparison benchmark result

        Returns:
            Comparison ID
        """
        comparison_id = str(uuid4())

        with self._lock:
            try:
                conn = sqlite3.connect(self._db_path)
                cursor = conn.cursor()

                # Get both benchmark results
                cursor.execute("""
                    SELECT metrics FROM benchmark_results WHERE result_id = ?
                """, (baseline_result_id,))
                baseline_row = cursor.fetchone()

                cursor.execute("""
                    SELECT metrics FROM benchmark_results WHERE result_id = ?
                """, (comparison_result_id,))
                comparison_row = cursor.fetchone()

                if not baseline_row or not comparison_row:
                    raise ValueError("One or both benchmark results not found")

                baseline_metrics = json.loads(baseline_row[0]) if baseline_row[0] else {}
                comparison_metrics = json.loads(comparison_row[0]) if comparison_row[0] else {}

                # Calculate performance delta and comparison metrics
                comparison_data = self._calculate_performance_comparison(
                    baseline_metrics, comparison_metrics
                )

                cursor.execute("""
                    INSERT INTO benchmark_comparisons (
                        comparison_id, baseline_result_id, comparison_result_id,
                        performance_delta_percent, comparison_metrics
                    ) VALUES (?, ?, ?, ?, ?)
                """, (
                    comparison_id, baseline_result_id, comparison_result_id,
                    comparison_data['overall_delta_percent'],
                    json.dumps(comparison_data['detailed_comparison'])
                ))

                conn.commit()
                conn.close()

                self._logger.info(f"Created benchmark comparison: {comparison_id}")
                return comparison_id

            except Exception as e:
                self._logger.error(f"Failed to compare benchmarks: {e}")
                raise

    def _calculate_performance_comparison(self, baseline: Dict[str, Any],
                                        comparison: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate performance comparison between two metric sets."""
        detailed_comparison = {}
        deltas = []

        for metric_name in baseline:
            if metric_name in comparison:
                baseline_value = float(baseline[metric_name])
                comparison_value = float(comparison[metric_name])

                if baseline_value != 0:
                    delta_percent = ((comparison_value - baseline_value) / baseline_value) * 100
                    detailed_comparison[metric_name] = {
                        'baseline': baseline_value,
                        'comparison': comparison_value,
                        'delta_percent': delta_percent
                    }
                    deltas.append(delta_percent)

        overall_delta = sum(deltas) / len(deltas) if deltas else 0.0

        return {
            'overall_delta_percent': overall_delta,
            'detailed_comparison': detailed_comparison
        }

    def _cleanup_old_data(self) -> None:
        """Clean up old benchmark data based on retention policies."""
        try:
            current_time = datetime.now(timezone.utc)

            # Clean up old benchmark results
            benchmark_cutoff = current_time - timedelta(days=self._benchmark_retention_days)

            # Clean up old hardware configurations (only if not referenced)
            hardware_cutoff = current_time - timedelta(days=self._hardware_config_retention_days)

            with self._lock:
                conn = sqlite3.connect(self._db_path)
                cursor = conn.cursor()

                # Delete old benchmark results
                cursor.execute("""
                    DELETE FROM benchmark_results WHERE created_at < ?
                """, (benchmark_cutoff.isoformat(),))
                benchmark_deleted = cursor.rowcount

                # Delete old hardware configurations not referenced by recent benchmarks
                cursor.execute("""
                    DELETE FROM hardware_configurations
                    WHERE created_at < ? AND config_id NOT IN (
                        SELECT DISTINCT hardware_config_id FROM benchmark_results
                        WHERE created_at >= ?
                    )
                """, (hardware_cutoff.isoformat(), benchmark_cutoff.isoformat()))
                hardware_deleted = cursor.rowcount

                conn.commit()
                conn.close()

                if benchmark_deleted > 0 or hardware_deleted > 0:
                    self._logger.info(f"Cleaned up {benchmark_deleted} benchmark results and {hardware_deleted} hardware configs")

        except Exception as e:
            self._logger.error(f"Failed to cleanup old data: {e}")

    def close(self) -> None:
        """Close database connections and cleanup resources."""
        try:
            self._logger.info("PerformanceBenchmarksDB closed successfully")
        except Exception as e:
            self._logger.error(f"Error closing PerformanceBenchmarksDB: {e}")
