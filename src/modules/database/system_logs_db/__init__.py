"""
MikroDok System Logs Database Package
Provides database modules for comprehensive system logging, audit trails, error tracking, and performance metrics storage.
"""

# Import system logs database components
try:
    from .log_entries_db.log_entries_db import LogEntriesDB
except ImportError:
    pass

try:
    from .audit_trail_db.audit_trail_db import AuditTrailDB
except ImportError:
    pass

try:
    from .error_history_db.error_history_db import ErrorHistoryDB
except ImportError:
    pass

try:
    from .performance_metrics_db.performance_metrics_db import PerformanceMetricsDB
except ImportError:
    pass

__all__ = [
    'LogEntriesDB',
    'AuditTrailDB',
    'ErrorHistoryDB',
    'PerformanceMetricsDB'
]
