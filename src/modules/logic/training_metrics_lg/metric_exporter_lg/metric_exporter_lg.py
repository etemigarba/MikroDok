"""
Module: metric_exporter_lg
Description: Exports training metrics in various formats for analysis and integration with monitoring systems
Phase: 4
Location: /src/modules/logic/training_metrics_lg/metric_exporter_lg/
"""

# Standard library imports
import csv
import json
import threading
import time
import gzip
import zipfile
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional, Union, IO
import os

# Third-party imports
import numpy as np

# Local imports
from ..base_interfaces import (
    IMetricExporter, ExportFormat, ExportConfiguration,
    MetricResult, AggregatedMetrics, ExportResult
)
from src.modules.logic.logging_infrastructure_lg import get_logger
from src.modules.logic.error_handling_lg import ErrorClassifier, ErrorSeverity


class JSONExporter:
    """Exports metrics to JSON format with compression support."""
    
    def __init__(self):
        """Initialize JSON exporter."""
        self._logger = get_logger(__name__)
    
    def export(
        self,
        data: Union[List[MetricResult], AggregatedMetrics],
        output_path: Path,
        config: ExportConfiguration
    ) -> ExportResult:
        """Export data to JSON format."""
        try:
            # Prepare data for JSON serialization
            if isinstance(data, list):
                json_data = self._prepare_metric_list(data, config)
            else:
                json_data = self._prepare_aggregated_metrics(data, config)
            
            # Add metadata if requested
            if config.include_metadata:
                json_data['export_metadata'] = {
                    'export_timestamp': datetime.now().isoformat(),
                    'format': 'json',
                    'record_count': len(data) if isinstance(data, list) else 1,
                    'compression': config.compression,
                    'exporter_version': '1.0.0'
                }
            
            # Write to file
            file_size = self._write_json_file(json_data, output_path, config.compression)
            
            return ExportResult(
                success=True,
                output_path=output_path,
                format=ExportFormat.JSON,
                record_count=len(data) if isinstance(data, list) else 1,
                file_size_bytes=file_size,
                timestamp=datetime.now()
            )
            
        except Exception as e:
            self._logger.error(f"Error exporting to JSON: {e}")
            return ExportResult(
                success=False,
                output_path=output_path,
                format=ExportFormat.JSON,
                record_count=0,
                file_size_bytes=0,
                timestamp=datetime.now(),
                error_message=str(e)
            )
    
    def _prepare_metric_list(
        self,
        metrics: List[MetricResult],
        config: ExportConfiguration
    ) -> Dict[str, Any]:
        """Prepare metric list for JSON serialization."""
        return {
            'metrics': [
                {
                    'metric_value': metric.metric_value,
                    'metric_type': metric.metric_type.value,
                    'epoch': metric.epoch,
                    'step': metric.step,
                    'timestamp': metric.timestamp.isoformat(),
                    'metadata': metric.metadata
                }
                for metric in metrics
            ]
        }
    
    def _prepare_aggregated_metrics(
        self,
        aggregated: AggregatedMetrics,
        config: ExportConfiguration
    ) -> Dict[str, Any]:
        """Prepare aggregated metrics for JSON serialization."""
        return {
            'aggregated_metrics': {
                'metrics': aggregated.metrics,
                'aggregation_strategy': aggregated.aggregation_strategy.value,
                'window_size': aggregated.window_size,
                'timestamp': aggregated.timestamp.isoformat(),
                'confidence_score': aggregated.confidence_score,
                'metadata': aggregated.metadata
            }
        }
    
    def _write_json_file(
        self,
        data: Dict[str, Any],
        output_path: Path,
        compression: Optional[str]
    ) -> int:
        """Write JSON data to file with optional compression."""
        # Ensure directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        json_str = json.dumps(data, indent=2, ensure_ascii=False)
        
        if compression == "gzip":
            with gzip.open(output_path, 'wt', encoding='utf-8') as f:
                f.write(json_str)
        elif compression == "zip":
            with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zf:
                zf.writestr(output_path.stem + '.json', json_str)
        else:
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(json_str)
        
        return output_path.stat().st_size


class CSVExporter:
    """Exports metrics to CSV format with customizable columns."""
    
    def __init__(self):
        """Initialize CSV exporter."""
        self._logger = get_logger(__name__)
    
    def export(
        self,
        data: Union[List[MetricResult], AggregatedMetrics],
        output_path: Path,
        config: ExportConfiguration
    ) -> ExportResult:
        """Export data to CSV format."""
        try:
            if isinstance(data, list):
                file_size = self._export_metric_list(data, output_path, config)
                record_count = len(data)
            else:
                file_size = self._export_aggregated_metrics(data, output_path, config)
                record_count = 1
            
            return ExportResult(
                success=True,
                output_path=output_path,
                format=ExportFormat.CSV,
                record_count=record_count,
                file_size_bytes=file_size,
                timestamp=datetime.now()
            )
            
        except Exception as e:
            self._logger.error(f"Error exporting to CSV: {e}")
            return ExportResult(
                success=False,
                output_path=output_path,
                format=ExportFormat.CSV,
                record_count=0,
                file_size_bytes=0,
                timestamp=datetime.now(),
                error_message=str(e)
            )
    
    def _export_metric_list(
        self,
        metrics: List[MetricResult],
        output_path: Path,
        config: ExportConfiguration
    ) -> int:
        """Export metric list to CSV."""
        # Ensure directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        fieldnames = ['metric_value', 'metric_type', 'epoch', 'step', 'timestamp']
        
        # Add metadata columns if requested
        if config.include_metadata and metrics:
            metadata_keys = set()
            for metric in metrics:
                metadata_keys.update(metric.metadata.keys())
            fieldnames.extend(sorted(metadata_keys))
        
        with open(output_path, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            
            for metric in metrics:
                row = {
                    'metric_value': metric.metric_value,
                    'metric_type': metric.metric_type.value,
                    'epoch': metric.epoch,
                    'step': metric.step,
                    'timestamp': metric.timestamp.isoformat()
                }
                
                # Add metadata columns
                if config.include_metadata:
                    for key, value in metric.metadata.items():
                        row[key] = value
                
                writer.writerow(row)
        
        return output_path.stat().st_size
    
    def _export_aggregated_metrics(
        self,
        aggregated: AggregatedMetrics,
        output_path: Path,
        config: ExportConfiguration
    ) -> int:
        """Export aggregated metrics to CSV."""
        # Ensure directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        fieldnames = ['metric_name', 'metric_value', 'aggregation_strategy', 
                     'window_size', 'confidence_score', 'timestamp']
        
        # Add metadata columns if requested
        if config.include_metadata:
            metadata_keys = sorted(aggregated.metadata.keys())
            fieldnames.extend(metadata_keys)
        
        with open(output_path, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            
            for metric_name, metric_value in aggregated.metrics.items():
                row = {
                    'metric_name': metric_name,
                    'metric_value': metric_value,
                    'aggregation_strategy': aggregated.aggregation_strategy.value,
                    'window_size': aggregated.window_size,
                    'confidence_score': aggregated.confidence_score,
                    'timestamp': aggregated.timestamp.isoformat()
                }
                
                # Add metadata columns
                if config.include_metadata:
                    for key, value in aggregated.metadata.items():
                        row[key] = value
                
                writer.writerow(row)
        
        return output_path.stat().st_size


class TensorBoardExporter:
    """Exports metrics to TensorBoard log format."""
    
    def __init__(self):
        """Initialize TensorBoard exporter."""
        self._logger = get_logger(__name__)
        self._writer = None
    
    def export(
        self,
        data: Union[List[MetricResult], AggregatedMetrics],
        output_path: Path,
        config: ExportConfiguration
    ) -> ExportResult:
        """Export data to TensorBoard format."""
        try:
            # Note: This is a simplified implementation
            # In a real scenario, you would use tensorboard's SummaryWriter
            
            if isinstance(data, list):
                record_count = len(data)
                self._export_metric_list_to_tensorboard(data, output_path, config)
            else:
                record_count = 1
                self._export_aggregated_to_tensorboard(data, output_path, config)
            
            # Calculate approximate file size
            file_size = output_path.stat().st_size if output_path.exists() else 0
            
            return ExportResult(
                success=True,
                output_path=output_path,
                format=ExportFormat.TENSORBOARD,
                record_count=record_count,
                file_size_bytes=file_size,
                timestamp=datetime.now()
            )
            
        except Exception as e:
            self._logger.error(f"Error exporting to TensorBoard: {e}")
            return ExportResult(
                success=False,
                output_path=output_path,
                format=ExportFormat.TENSORBOARD,
                record_count=0,
                file_size_bytes=0,
                timestamp=datetime.now(),
                error_message=str(e)
            )
    
    def _export_metric_list_to_tensorboard(
        self,
        metrics: List[MetricResult],
        output_path: Path,
        config: ExportConfiguration
    ) -> None:
        """Export metric list to TensorBoard format."""
        # Ensure directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Group metrics by type for better organization
        grouped_metrics = {}
        for metric in metrics:
            metric_type = metric.metric_type.value
            if metric_type not in grouped_metrics:
                grouped_metrics[metric_type] = []
            grouped_metrics[metric_type].append(metric)
        
        # Create a simple text-based log (simplified TensorBoard format)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write("# TensorBoard-style metrics log\n")
            f.write(f"# Generated at: {datetime.now().isoformat()}\n\n")
            
            for metric_type, type_metrics in grouped_metrics.items():
                f.write(f"# Metric Type: {metric_type}\n")
                for metric in type_metrics:
                    f.write(f"step:{metric.step}\t{metric_type}:{metric.metric_value}\t"
                           f"epoch:{metric.epoch}\ttimestamp:{metric.timestamp.isoformat()}\n")
                f.write("\n")
    
    def _export_aggregated_to_tensorboard(
        self,
        aggregated: AggregatedMetrics,
        output_path: Path,
        config: ExportConfiguration
    ) -> None:
        """Export aggregated metrics to TensorBoard format."""
        # Ensure directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write("# TensorBoard-style aggregated metrics log\n")
            f.write(f"# Generated at: {datetime.now().isoformat()}\n")
            f.write(f"# Aggregation Strategy: {aggregated.aggregation_strategy.value}\n")
            f.write(f"# Window Size: {aggregated.window_size}\n")
            f.write(f"# Confidence Score: {aggregated.confidence_score}\n\n")
            
            for metric_name, metric_value in aggregated.metrics.items():
                f.write(f"aggregated_{metric_name}:{metric_value}\t"
                       f"timestamp:{aggregated.timestamp.isoformat()}\n")


class MetricExporter(IMetricExporter):
    """Main metric exporter with support for multiple formats."""
    
    def __init__(self):
        """Initialize metric exporter."""
        self._logger = get_logger(__name__)
        self._error_classifier = ErrorClassifier()
        self._lock = threading.Lock()
        
        # Initialize format-specific exporters
        self._json_exporter = JSONExporter()
        self._csv_exporter = CSVExporter()
        self._tensorboard_exporter = TensorBoardExporter()
        
        # Performance tracking
        self._export_times = {}
        self._export_counts = {}
    
    def export_metrics(
        self,
        metrics: List[MetricResult],
        config: ExportConfiguration
    ) -> ExportResult:
        """Export metrics to specified format."""
        start_time = time.time()
        
        try:
            # Select appropriate exporter
            if config.format == ExportFormat.JSON:
                result = self._json_exporter.export(metrics, config.output_path, config)
            elif config.format == ExportFormat.CSV:
                result = self._csv_exporter.export(metrics, config.output_path, config)
            elif config.format == ExportFormat.TENSORBOARD:
                result = self._tensorboard_exporter.export(metrics, config.output_path, config)
            else:
                raise ValueError(f"Unsupported export format: {config.format}")
            
            # Track performance
            export_time = (time.time() - start_time) * 1000
            with self._lock:
                format_name = config.format.value
                if format_name not in self._export_times:
                    self._export_times[format_name] = []
                    self._export_counts[format_name] = 0
                
                self._export_times[format_name].append(export_time)
                self._export_counts[format_name] += 1
                
                # Keep only recent times
                if len(self._export_times[format_name]) > 1000:
                    self._export_times[format_name] = self._export_times[format_name][-1000:]
            
            # Add performance metadata to result
            if result.success:
                result.metadata['export_time_ms'] = export_time
            
            return result
            
        except Exception as e:
            self._logger.error(f"Error exporting metrics: {e}")
            classification = self._error_classifier.classify_error(e)
            
            return ExportResult(
                success=False,
                output_path=config.output_path,
                format=config.format,
                record_count=0,
                file_size_bytes=0,
                timestamp=datetime.now(),
                error_message=str(e),
                metadata={
                    'error_severity': classification.severity.value,
                    'export_time_ms': (time.time() - start_time) * 1000
                }
            )
    
    def export_aggregated_metrics(
        self,
        aggregated_metrics: AggregatedMetrics,
        config: ExportConfiguration
    ) -> ExportResult:
        """Export aggregated metrics."""
        start_time = time.time()
        
        try:
            # Select appropriate exporter
            if config.format == ExportFormat.JSON:
                result = self._json_exporter.export(aggregated_metrics, config.output_path, config)
            elif config.format == ExportFormat.CSV:
                result = self._csv_exporter.export(aggregated_metrics, config.output_path, config)
            elif config.format == ExportFormat.TENSORBOARD:
                result = self._tensorboard_exporter.export(aggregated_metrics, config.output_path, config)
            else:
                raise ValueError(f"Unsupported export format: {config.format}")
            
            # Track performance
            export_time = (time.time() - start_time) * 1000
            if result.success:
                result.metadata['export_time_ms'] = export_time
            
            return result
            
        except Exception as e:
            self._logger.error(f"Error exporting aggregated metrics: {e}")
            classification = self._error_classifier.classify_error(e)
            
            return ExportResult(
                success=False,
                output_path=config.output_path,
                format=config.format,
                record_count=0,
                file_size_bytes=0,
                timestamp=datetime.now(),
                error_message=str(e),
                metadata={
                    'error_severity': classification.severity.value,
                    'export_time_ms': (time.time() - start_time) * 1000
                }
            )

    def get_export_statistics(self) -> Dict[str, Any]:
        """Get export performance statistics."""
        with self._lock:
            stats = {}

            for format_name, times in self._export_times.items():
                if times:
                    times_array = np.array(times)
                    stats[format_name] = {
                        'total_exports': self._export_counts[format_name],
                        'avg_export_time_ms': float(np.mean(times_array)),
                        'min_export_time_ms': float(np.min(times_array)),
                        'max_export_time_ms': float(np.max(times_array)),
                        'std_export_time_ms': float(np.std(times_array))
                    }
                else:
                    stats[format_name] = {
                        'total_exports': 0,
                        'avg_export_time_ms': 0.0,
                        'min_export_time_ms': 0.0,
                        'max_export_time_ms': 0.0,
                        'std_export_time_ms': 0.0
                    }

            return stats

    def batch_export(
        self,
        metrics: List[MetricResult],
        configs: List[ExportConfiguration]
    ) -> List[ExportResult]:
        """Export metrics to multiple formats simultaneously."""
        results = []

        for config in configs:
            try:
                result = self.export_metrics(metrics, config)
                results.append(result)

                if result.success:
                    self._logger.info(f"Successfully exported {result.record_count} metrics to {config.format.value}")
                else:
                    self._logger.error(f"Failed to export to {config.format.value}: {result.error_message}")

            except Exception as e:
                self._logger.error(f"Error in batch export for {config.format.value}: {e}")
                results.append(ExportResult(
                    success=False,
                    output_path=config.output_path,
                    format=config.format,
                    record_count=0,
                    file_size_bytes=0,
                    timestamp=datetime.now(),
                    error_message=str(e)
                ))

        return results

    def validate_export_path(self, output_path: Path, format: ExportFormat) -> bool:
        """Validate if the export path is suitable for the format."""
        try:
            # Check if directory is writable
            output_path.parent.mkdir(parents=True, exist_ok=True)

            # Check file extension matches format
            expected_extensions = {
                ExportFormat.JSON: ['.json', '.json.gz', '.json.zip'],
                ExportFormat.CSV: ['.csv', '.csv.gz', '.csv.zip'],
                ExportFormat.TENSORBOARD: ['.log', '.tb', '.tensorboard']
            }

            if format in expected_extensions:
                valid_extensions = expected_extensions[format]
                if not any(str(output_path).endswith(ext) for ext in valid_extensions):
                    self._logger.warning(f"File extension may not match format {format.value}")

            # Test write permissions
            test_file = output_path.parent / f".test_write_{int(time.time())}"
            try:
                test_file.touch()
                test_file.unlink()
                return True
            except Exception:
                return False

        except Exception as e:
            self._logger.error(f"Error validating export path: {e}")
            return False

    def cleanup_old_exports(
        self,
        directory: Path,
        max_age_days: int = 30,
        format_filter: Optional[ExportFormat] = None
    ) -> int:
        """Clean up old export files."""
        try:
            if not directory.exists():
                return 0

            cutoff_time = datetime.now().timestamp() - (max_age_days * 24 * 3600)
            deleted_count = 0

            # Define file patterns for each format
            patterns = {
                ExportFormat.JSON: ['*.json', '*.json.gz', '*.json.zip'],
                ExportFormat.CSV: ['*.csv', '*.csv.gz', '*.csv.zip'],
                ExportFormat.TENSORBOARD: ['*.log', '*.tb', '*.tensorboard']
            }

            # Get patterns to check
            if format_filter:
                check_patterns = patterns.get(format_filter, [])
            else:
                check_patterns = []
                for pattern_list in patterns.values():
                    check_patterns.extend(pattern_list)

            # Find and delete old files
            for pattern in check_patterns:
                for file_path in directory.glob(pattern):
                    if file_path.is_file() and file_path.stat().st_mtime < cutoff_time:
                        try:
                            file_path.unlink()
                            deleted_count += 1
                            self._logger.debug(f"Deleted old export file: {file_path}")
                        except Exception as e:
                            self._logger.warning(f"Failed to delete {file_path}: {e}")

            self._logger.info(f"Cleaned up {deleted_count} old export files")
            return deleted_count

        except Exception as e:
            self._logger.error(f"Error cleaning up old exports: {e}")
            return 0
