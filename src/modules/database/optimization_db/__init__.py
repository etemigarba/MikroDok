"""
MikroDok Database Optimization Package
Provides database optimization modules for index management, vacuum scheduling, and query optimization.
"""

# Import optimization database components
try:
    from .index_manager_db.index_manager_db import IndexManagerDB
except ImportError:
    pass

try:
    from .vacuum_scheduler_db.vacuum_scheduler_db import VacuumSchedulerDB
except ImportError:
    pass

try:
    from .query_optimizer_db.query_optimizer_db import QueryOptimizerDB
except ImportError:
    pass

__all__ = [
    'IndexManagerDB',
    'VacuumSchedulerDB',
    'QueryOptimizerDB'
]
