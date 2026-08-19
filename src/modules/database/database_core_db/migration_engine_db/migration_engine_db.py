"""
Module: migration_engine_db
Description: Handles schema versioning, database migrations, and backward compatibility with rollback support
Phase: 4
Location: /src/modules/database/database_core_db/migration_engine_db/
"""

# Standard library imports
import hashlib
import json
import sqlite3
import threading
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any, Callable, Union

# Local imports
from src.modules.logic.logging_infrastructure_lg.log_manager_lg.log_manager_lg import get_logger


class MigrationStatus(Enum):
    """Migration execution status."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


class MigrationType(Enum):
    """Types of database migrations."""
    SCHEMA = "schema"
    DATA = "data"
    INDEX = "index"
    TRIGGER = "trigger"
    VIEW = "view"


@dataclass
class Migration:
    """Database migration definition."""
    version: str
    name: str
    description: str
    migration_type: MigrationType
    up_sql: str
    down_sql: str
    checksum: str
    dependencies: List[str]
    created_at: datetime
    author: str
    
    def __post_init__(self):
        """Calculate checksum after initialization."""
        if not self.checksum:
            content = f"{self.up_sql}{self.down_sql}{self.version}"
            self.checksum = hashlib.sha256(content.encode()).hexdigest()


@dataclass
class MigrationRecord:
    """Migration execution record."""
    migration_id: str
    version: str
    name: str
    status: MigrationStatus
    checksum: str
    executed_at: Optional[datetime]
    execution_time_ms: Optional[int]
    error_message: Optional[str]
    rolled_back_at: Optional[datetime]
    rollback_reason: Optional[str]


class MigrationEngineDB:
    """
    Database migration engine with versioning and rollback support.
    
    Handles schema versioning, database migrations, and backward compatibility
    with rollback support. Provides safe migration execution, dependency
    resolution, and comprehensive migration tracking.
    """
    
    def __init__(self, db_path: Optional[str] = None, migrations_dir: Optional[str] = None):
        """
        Initialize the migration engine.
        
        Args:
            db_path: Path to the database file
            migrations_dir: Directory containing migration files
        """
        if db_path is None:
            # Default to core database directory
            data_dir = Path.home() / ".mikrodok" / "data" / "core"
            data_dir.mkdir(parents=True, exist_ok=True)
            db_path = str(data_dir / "mikrodok_core.db")
        
        if migrations_dir is None:
            migrations_dir = str(Path(__file__).parent / "migrations")
        
        self._db_path = db_path
        self._migrations_dir = Path(migrations_dir)
        self._migrations_dir.mkdir(parents=True, exist_ok=True)
        
        # Thread safety
        self._lock = threading.RLock()
        
        # Migration tracking
        self._loaded_migrations: Dict[str, Migration] = {}
        self._migration_records: Dict[str, MigrationRecord] = {}
        
        # Logger
        self._logger = get_logger(__name__)
        
        # Initialize migration tracking
        self._initialize_migration_tracking()
        self._load_migrations()
        
        self._logger.info(f"MigrationEngineDB initialized with database: {self._db_path}")
    
    def _initialize_migration_tracking(self) -> None:
        """Initialize migration tracking tables."""
        try:
            conn = sqlite3.connect(self._db_path)
            cursor = conn.cursor()
            
            # Create migration tracking table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    migration_id TEXT PRIMARY KEY,
                    version TEXT NOT NULL,
                    name TEXT NOT NULL,
                    migration_type TEXT NOT NULL,
                    status TEXT NOT NULL,
                    checksum TEXT NOT NULL,
                    executed_at TEXT,
                    execution_time_ms INTEGER,
                    error_message TEXT,
                    rolled_back_at TEXT,
                    rollback_reason TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)
            
            # Create migration dependencies table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS migration_dependencies (
                    migration_id TEXT NOT NULL,
                    dependency_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY (migration_id, dependency_id),
                    FOREIGN KEY (migration_id) REFERENCES schema_migrations(migration_id),
                    FOREIGN KEY (dependency_id) REFERENCES schema_migrations(migration_id)
                )
            """)
            
            # Create schema version table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS schema_version (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    current_version TEXT NOT NULL,
                    previous_version TEXT,
                    updated_at TEXT NOT NULL,
                    updated_by TEXT NOT NULL
                )
            """)
            
            # Initialize schema version if not exists
            cursor.execute("SELECT COUNT(*) FROM schema_version")
            if cursor.fetchone()[0] == 0:
                cursor.execute("""
                    INSERT INTO schema_version (id, current_version, updated_at, updated_by)
                    VALUES (1, '0.0.0', ?, 'migration_engine')
                """, (datetime.now(timezone.utc).isoformat(),))
            
            conn.commit()
            conn.close()
            
            self._logger.info("Migration tracking tables initialized")
            
        except Exception as e:
            self._logger.error(f"Failed to initialize migration tracking: {e}")
            raise
    
    def _load_migrations(self) -> None:
        """Load migration definitions from files."""
        try:
            migration_files = list(self._migrations_dir.glob("*.json"))
            
            for migration_file in migration_files:
                try:
                    with open(migration_file, 'r', encoding='utf-8') as f:
                        migration_data = json.load(f)
                    
                    migration = Migration(
                        version=migration_data['version'],
                        name=migration_data['name'],
                        description=migration_data['description'],
                        migration_type=MigrationType(migration_data['migration_type']),
                        up_sql=migration_data['up_sql'],
                        down_sql=migration_data['down_sql'],
                        checksum=migration_data.get('checksum', ''),
                        dependencies=migration_data.get('dependencies', []),
                        created_at=datetime.fromisoformat(migration_data['created_at']),
                        author=migration_data['author']
                    )
                    
                    self._loaded_migrations[migration.version] = migration
                    
                except Exception as e:
                    self._logger.warning(f"Failed to load migration from {migration_file}: {e}")
            
            # Load migration records from database
            self._load_migration_records()
            
            self._logger.info(f"Loaded {len(self._loaded_migrations)} migrations")
            
        except Exception as e:
            self._logger.error(f"Failed to load migrations: {e}")
            raise
    
    def _load_migration_records(self) -> None:
        """Load migration execution records from database."""
        try:
            conn = sqlite3.connect(self._db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT migration_id, version, name, status, checksum,
                       executed_at, execution_time_ms, error_message,
                       rolled_back_at, rollback_reason
                FROM schema_migrations
            """)
            
            for row in cursor.fetchall():
                record = MigrationRecord(
                    migration_id=row[0],
                    version=row[1],
                    name=row[2],
                    status=MigrationStatus(row[3]),
                    checksum=row[4],
                    executed_at=datetime.fromisoformat(row[5]) if row[5] else None,
                    execution_time_ms=row[6],
                    error_message=row[7],
                    rolled_back_at=datetime.fromisoformat(row[8]) if row[8] else None,
                    rollback_reason=row[9]
                )
                
                self._migration_records[record.version] = record
            
            conn.close()
            
        except Exception as e:
            self._logger.error(f"Failed to load migration records: {e}")
            raise

    def create_migration(self, name: str, description: str, migration_type: MigrationType,
                        up_sql: str, down_sql: str, dependencies: Optional[List[str]] = None,
                        author: str = "system") -> Migration:
        """
        Create a new migration definition.

        Args:
            name: Migration name
            description: Migration description
            migration_type: Type of migration
            up_sql: SQL for applying migration
            down_sql: SQL for rolling back migration
            dependencies: List of dependency versions
            author: Migration author

        Returns:
            Created migration object
        """
        try:
            # Generate version based on timestamp
            version = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

            migration = Migration(
                version=version,
                name=name,
                description=description,
                migration_type=migration_type,
                up_sql=up_sql,
                down_sql=down_sql,
                checksum='',  # Will be calculated in __post_init__
                dependencies=dependencies or [],
                created_at=datetime.now(timezone.utc),
                author=author
            )

            # Save migration to file
            migration_file = self._migrations_dir / f"{version}_{name.replace(' ', '_')}.json"
            with open(migration_file, 'w', encoding='utf-8') as f:
                migration_dict = asdict(migration)
                migration_dict['created_at'] = migration.created_at.isoformat()
                migration_dict['migration_type'] = migration.migration_type.value
                json.dump(migration_dict, f, indent=2)

            # Add to loaded migrations
            self._loaded_migrations[version] = migration

            self._logger.info(f"Created migration: {version} - {name}")
            return migration

        except Exception as e:
            self._logger.error(f"Failed to create migration: {e}")
            raise

    def get_pending_migrations(self) -> List[Migration]:
        """
        Get list of pending migrations in dependency order.

        Returns:
            List of migrations to be executed
        """
        try:
            pending = []

            for version, migration in self._loaded_migrations.items():
                record = self._migration_records.get(version)

                if not record or record.status in [MigrationStatus.PENDING, MigrationStatus.FAILED]:
                    pending.append(migration)

            # Sort by dependency order
            return self._sort_by_dependencies(pending)

        except Exception as e:
            self._logger.error(f"Failed to get pending migrations: {e}")
            return []

    def _sort_by_dependencies(self, migrations: List[Migration]) -> List[Migration]:
        """Sort migrations by dependency order using topological sort."""
        try:
            # Create dependency graph
            graph = {m.version: set(m.dependencies) for m in migrations}
            migration_map = {m.version: m for m in migrations}

            # Topological sort
            sorted_versions = []
            visited = set()
            temp_visited = set()

            def visit(version: str):
                if version in temp_visited:
                    raise ValueError(f"Circular dependency detected involving {version}")
                if version in visited:
                    return

                temp_visited.add(version)

                for dep in graph.get(version, set()):
                    if dep in graph:  # Only consider dependencies that are in our migration set
                        visit(dep)

                temp_visited.remove(version)
                visited.add(version)
                sorted_versions.append(version)

            for version in graph:
                if version not in visited:
                    visit(version)

            return [migration_map[v] for v in sorted_versions if v in migration_map]

        except Exception as e:
            self._logger.error(f"Failed to sort migrations by dependencies: {e}")
            # Fallback to version-based sorting
            return sorted(migrations, key=lambda m: m.version)

    def execute_migration(self, migration: Migration) -> bool:
        """
        Execute a single migration.

        Args:
            migration: Migration to execute

        Returns:
            True if successful, False otherwise
        """
        with self._lock:
            try:
                start_time = datetime.now(timezone.utc)
                migration_id = f"{migration.version}_{migration.name.replace(' ', '_')}"

                # Check if already executed
                record = self._migration_records.get(migration.version)
                if record and record.status == MigrationStatus.COMPLETED:
                    self._logger.info(f"Migration {migration.version} already executed")
                    return True

                # Validate dependencies
                for dep_version in migration.dependencies:
                    dep_record = self._migration_records.get(dep_version)
                    if not dep_record or dep_record.status != MigrationStatus.COMPLETED:
                        raise ValueError(f"Dependency {dep_version} not satisfied")

                # Update status to running
                self._update_migration_record(migration_id, migration, MigrationStatus.RUNNING)

                # Execute migration
                conn = sqlite3.connect(self._db_path)
                try:
                    cursor = conn.cursor()

                    # Begin transaction
                    cursor.execute("BEGIN IMMEDIATE")

                    # Execute migration SQL
                    for statement in migration.up_sql.split(';'):
                        statement = statement.strip()
                        if statement:
                            cursor.execute(statement)

                    # Commit transaction
                    conn.commit()

                    # Calculate execution time
                    execution_time = int((datetime.now(timezone.utc) - start_time).total_seconds() * 1000)

                    # Update status to completed
                    self._update_migration_record(
                        migration_id, migration, MigrationStatus.COMPLETED,
                        executed_at=datetime.now(timezone.utc),
                        execution_time_ms=execution_time
                    )

                    # Update schema version
                    self._update_schema_version(migration.version)

                    self._logger.info(f"Successfully executed migration: {migration.version}")
                    return True

                except Exception as e:
                    # Rollback transaction
                    conn.rollback()

                    # Update status to failed
                    self._update_migration_record(
                        migration_id, migration, MigrationStatus.FAILED,
                        error_message=str(e)
                    )

                    self._logger.error(f"Failed to execute migration {migration.version}: {e}")
                    return False

                finally:
                    conn.close()

            except Exception as e:
                self._logger.error(f"Migration execution error: {e}")
                return False

    def rollback_migration(self, version: str, reason: str = "Manual rollback") -> bool:
        """
        Rollback a migration.

        Args:
            version: Version to rollback
            reason: Reason for rollback

        Returns:
            True if successful, False otherwise
        """
        with self._lock:
            try:
                migration = self._loaded_migrations.get(version)
                if not migration:
                    raise ValueError(f"Migration {version} not found")

                record = self._migration_records.get(version)
                if not record or record.status != MigrationStatus.COMPLETED:
                    raise ValueError(f"Migration {version} not in completed state")

                # Check for dependent migrations
                dependent_migrations = self._get_dependent_migrations(version)
                if dependent_migrations:
                    raise ValueError(f"Cannot rollback {version}: has dependent migrations {dependent_migrations}")

                # Execute rollback
                conn = sqlite3.connect(self._db_path)
                try:
                    cursor = conn.cursor()

                    # Begin transaction
                    cursor.execute("BEGIN IMMEDIATE")

                    # Execute rollback SQL
                    for statement in migration.down_sql.split(';'):
                        statement = statement.strip()
                        if statement:
                            cursor.execute(statement)

                    # Commit transaction
                    conn.commit()

                    # Update migration record
                    migration_id = f"{migration.version}_{migration.name.replace(' ', '_')}"
                    self._update_migration_record(
                        migration_id, migration, MigrationStatus.ROLLED_BACK,
                        rolled_back_at=datetime.now(timezone.utc),
                        rollback_reason=reason
                    )

                    self._logger.info(f"Successfully rolled back migration: {version}")
                    return True

                except Exception as e:
                    # Rollback transaction
                    conn.rollback()
                    self._logger.error(f"Failed to rollback migration {version}: {e}")
                    return False

                finally:
                    conn.close()

            except Exception as e:
                self._logger.error(f"Rollback error: {e}")
                return False

    def _get_dependent_migrations(self, version: str) -> List[str]:
        """Get migrations that depend on the given version."""
        dependents = []

        for migration in self._loaded_migrations.values():
            if version in migration.dependencies:
                record = self._migration_records.get(migration.version)
                if record and record.status == MigrationStatus.COMPLETED:
                    dependents.append(migration.version)

        return dependents

    def _update_migration_record(self, migration_id: str, migration: Migration,
                                status: MigrationStatus, executed_at: Optional[datetime] = None,
                                execution_time_ms: Optional[int] = None, error_message: Optional[str] = None,
                                rolled_back_at: Optional[datetime] = None, rollback_reason: Optional[str] = None) -> None:
        """Update migration execution record."""
        try:
            conn = sqlite3.connect(self._db_path)
            cursor = conn.cursor()

            now = datetime.now(timezone.utc).isoformat()

            cursor.execute("""
                INSERT OR REPLACE INTO schema_migrations (
                    migration_id, version, name, migration_type, status, checksum,
                    executed_at, execution_time_ms, error_message, rolled_back_at,
                    rollback_reason, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                migration_id, migration.version, migration.name, migration.migration_type.value,
                status.value, migration.checksum,
                executed_at.isoformat() if executed_at else None,
                execution_time_ms, error_message,
                rolled_back_at.isoformat() if rolled_back_at else None,
                rollback_reason, migration.created_at.isoformat(), now
            ))

            # Update dependencies
            cursor.execute("DELETE FROM migration_dependencies WHERE migration_id = ?", (migration_id,))
            for dep in migration.dependencies:
                cursor.execute("""
                    INSERT INTO migration_dependencies (migration_id, dependency_id, created_at)
                    VALUES (?, ?, ?)
                """, (migration_id, dep, now))

            conn.commit()
            conn.close()

            # Update in-memory record
            record = MigrationRecord(
                migration_id=migration_id,
                version=migration.version,
                name=migration.name,
                status=status,
                checksum=migration.checksum,
                executed_at=executed_at,
                execution_time_ms=execution_time_ms,
                error_message=error_message,
                rolled_back_at=rolled_back_at,
                rollback_reason=rollback_reason
            )

            self._migration_records[migration.version] = record

        except Exception as e:
            self._logger.error(f"Failed to update migration record: {e}")
            raise

    def _update_schema_version(self, version: str) -> None:
        """Update the current schema version."""
        try:
            conn = sqlite3.connect(self._db_path)
            cursor = conn.cursor()

            # Get current version
            cursor.execute("SELECT current_version FROM schema_version WHERE id = 1")
            row = cursor.fetchone()
            previous_version = row[0] if row else "0.0.0"

            # Update version
            cursor.execute("""
                UPDATE schema_version
                SET current_version = ?, previous_version = ?, updated_at = ?, updated_by = ?
                WHERE id = 1
            """, (version, previous_version, datetime.now(timezone.utc).isoformat(), "migration_engine"))

            conn.commit()
            conn.close()

        except Exception as e:
            self._logger.error(f"Failed to update schema version: {e}")
            raise

    def migrate_to_latest(self) -> bool:
        """
        Execute all pending migrations to bring database to latest version.

        Returns:
            True if all migrations successful, False otherwise
        """
        try:
            pending_migrations = self.get_pending_migrations()

            if not pending_migrations:
                self._logger.info("No pending migrations")
                return True

            self._logger.info(f"Executing {len(pending_migrations)} pending migrations")

            for migration in pending_migrations:
                if not self.execute_migration(migration):
                    self._logger.error(f"Migration failed, stopping at {migration.version}")
                    return False

            self._logger.info("All migrations completed successfully")
            return True

        except Exception as e:
            self._logger.error(f"Failed to migrate to latest: {e}")
            return False

    def get_current_version(self) -> str:
        """
        Get the current schema version.

        Returns:
            Current schema version string
        """
        try:
            conn = sqlite3.connect(self._db_path)
            cursor = conn.cursor()

            cursor.execute("SELECT current_version FROM schema_version WHERE id = 1")
            row = cursor.fetchone()

            conn.close()

            return row[0] if row else "0.0.0"

        except Exception as e:
            self._logger.error(f"Failed to get current version: {e}")
            return "0.0.0"

    def get_migration_history(self) -> List[MigrationRecord]:
        """
        Get migration execution history.

        Returns:
            List of migration records ordered by execution time
        """
        try:
            records = list(self._migration_records.values())
            return sorted(records, key=lambda r: r.executed_at or datetime.min.replace(tzinfo=timezone.utc))

        except Exception as e:
            self._logger.error(f"Failed to get migration history: {e}")
            return []

    def validate_migrations(self) -> Dict[str, List[str]]:
        """
        Validate all migrations for consistency and dependencies.

        Returns:
            Dictionary with validation results
        """
        try:
            issues = {
                'missing_dependencies': [],
                'checksum_mismatches': [],
                'circular_dependencies': [],
                'invalid_sql': []
            }

            # Check dependencies
            for migration in self._loaded_migrations.values():
                for dep in migration.dependencies:
                    if dep not in self._loaded_migrations:
                        issues['missing_dependencies'].append(f"{migration.version} depends on missing {dep}")

            # Check checksums
            for version, record in self._migration_records.items():
                migration = self._loaded_migrations.get(version)
                if migration and migration.checksum != record.checksum:
                    issues['checksum_mismatches'].append(f"{version} checksum mismatch")

            # Check for circular dependencies
            try:
                self._sort_by_dependencies(list(self._loaded_migrations.values()))
            except ValueError as e:
                issues['circular_dependencies'].append(str(e))

            return issues

        except Exception as e:
            self._logger.error(f"Failed to validate migrations: {e}")
            return {'validation_error': [str(e)]}

    def get_migration_stats(self) -> Dict[str, Any]:
        """
        Get migration statistics.

        Returns:
            Dictionary with migration statistics
        """
        try:
            total_migrations = len(self._loaded_migrations)
            completed = len([r for r in self._migration_records.values() if r.status == MigrationStatus.COMPLETED])
            failed = len([r for r in self._migration_records.values() if r.status == MigrationStatus.FAILED])
            pending = total_migrations - completed - failed

            return {
                'total_migrations': total_migrations,
                'completed_migrations': completed,
                'failed_migrations': failed,
                'pending_migrations': pending,
                'current_version': self.get_current_version(),
                'migrations_directory': str(self._migrations_dir),
                'database_path': self._db_path
            }

        except Exception as e:
            self._logger.error(f"Failed to get migration stats: {e}")
            return {}
