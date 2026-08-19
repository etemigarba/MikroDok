"""
MikroDok Database Core Package
Provides core database infrastructure components for connection management, migrations, transactions, and backups.
"""

# Import database core components
try:
    from .connection_manager_db.connection_manager_db import ConnectionManagerDB
except ImportError:
    pass

try:
    from .migration_engine_db.migration_engine_db import MigrationEngineDB
except ImportError:
    pass

try:
    from .transaction_coordinator_db.transaction_coordinator_db import TransactionCoordinatorDB
except ImportError:
    pass

try:
    from .backup_service_db.backup_service_db import BackupServiceDB
except ImportError:
    pass

__all__ = [
    'ConnectionManagerDB',
    'MigrationEngineDB',
    'TransactionCoordinatorDB',
    'BackupServiceDB'
]
