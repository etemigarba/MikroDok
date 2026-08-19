"""
Module: checkpoint_versioning_db
Description: Manages checkpoint versioning and relationships, providing comprehensive version tracking, parent-child relationships, and dependency management for checkpoint lineage
Phase: 4
Location: /src/modules/database/checkpoints_db/checkpoint_versioning_db/
"""

# Standard library imports
import sqlite3
import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple, Set
from dataclasses import dataclass
from enum import Enum

# Local imports
from src.modules.logic.logging_infrastructure_lg.log_manager_lg.log_manager_lg import get_logger


class VersionRelationType(Enum):
    """Types of version relationships between checkpoints."""
    PARENT_CHILD = "parent_child"
    BRANCH = "branch"
    MERGE = "merge"
    FORK = "fork"
    REBASE = "rebase"
    ROLLBACK = "rollback"


@dataclass
class CheckpointVersion:
    """Represents a checkpoint version with metadata."""
    checkpoint_id: str
    version_number: str
    major_version: int
    minor_version: int
    patch_version: int
    parent_checkpoint_id: Optional[str]
    branch_name: str
    commit_message: str
    created_at: datetime
    created_by: str
    tags: Set[str]
    is_stable: bool
    is_release: bool
    compatibility_version: str
    metadata: Dict[str, Any]


@dataclass
class VersionRelationship:
    """Represents a relationship between checkpoint versions."""
    relationship_id: str
    source_checkpoint_id: str
    target_checkpoint_id: str
    relationship_type: VersionRelationType
    created_at: datetime
    metadata: Dict[str, Any]


class CheckpointVersioningDB:
    """
    Database layer for checkpoint versioning and relationship management.
    
    Provides comprehensive version tracking, lineage management, and relationship
    mapping for checkpoints with support for branching, merging, and complex
    version hierarchies.
    """
    
    def __init__(self, db_path: str = "data/checkpoint_versioning.db"):
        """
        Initialize checkpoint versioning database.
        
        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._logger = get_logger(__name__)
        
        # Initialize database schema
        self._init_database()
        
        self._logger.info(f"CheckpointVersioningDB initialized with database: {self.db_path}")
    
    def _init_database(self) -> None:
        """Initialize database schema with versioning tables and indexes."""
        with self._lock:
            conn = sqlite3.connect(str(self.db_path))
            try:
                cursor = conn.cursor()
                
                # Enable WAL mode for better concurrency
                cursor.execute("PRAGMA journal_mode=WAL")
                cursor.execute("PRAGMA synchronous=NORMAL")
                cursor.execute("PRAGMA cache_size=10000")
                cursor.execute("PRAGMA temp_store=MEMORY")
                
                # Create checkpoint versions table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS checkpoint_versions (
                        checkpoint_id TEXT PRIMARY KEY,
                        version_number TEXT NOT NULL,
                        major_version INTEGER NOT NULL,
                        minor_version INTEGER NOT NULL,
                        patch_version INTEGER NOT NULL,
                        parent_checkpoint_id TEXT,
                        branch_name TEXT NOT NULL DEFAULT 'main',
                        commit_message TEXT,
                        created_at TEXT NOT NULL,
                        created_by TEXT NOT NULL,
                        tags_json TEXT,
                        is_stable BOOLEAN DEFAULT FALSE,
                        is_release BOOLEAN DEFAULT FALSE,
                        compatibility_version TEXT NOT NULL,
                        metadata_json TEXT,
                        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (parent_checkpoint_id) REFERENCES checkpoint_versions(checkpoint_id)
                    )
                """)
                
                # Create version relationships table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS version_relationships (
                        relationship_id TEXT PRIMARY KEY,
                        source_checkpoint_id TEXT NOT NULL,
                        target_checkpoint_id TEXT NOT NULL,
                        relationship_type TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        metadata_json TEXT,
                        FOREIGN KEY (source_checkpoint_id) REFERENCES checkpoint_versions(checkpoint_id),
                        FOREIGN KEY (target_checkpoint_id) REFERENCES checkpoint_versions(checkpoint_id),
                        UNIQUE(source_checkpoint_id, target_checkpoint_id, relationship_type)
                    )
                """)
                
                # Create version branches table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS version_branches (
                        branch_id TEXT PRIMARY KEY,
                        branch_name TEXT NOT NULL UNIQUE,
                        base_checkpoint_id TEXT,
                        head_checkpoint_id TEXT,
                        created_at TEXT NOT NULL,
                        created_by TEXT NOT NULL,
                        description TEXT,
                        is_active BOOLEAN DEFAULT TRUE,
                        is_protected BOOLEAN DEFAULT FALSE,
                        merge_strategy TEXT DEFAULT 'auto',
                        metadata_json TEXT,
                        FOREIGN KEY (base_checkpoint_id) REFERENCES checkpoint_versions(checkpoint_id),
                        FOREIGN KEY (head_checkpoint_id) REFERENCES checkpoint_versions(checkpoint_id)
                    )
                """)
                
                # Create version tags table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS version_tags (
                        tag_id TEXT PRIMARY KEY,
                        tag_name TEXT NOT NULL,
                        checkpoint_id TEXT NOT NULL,
                        tag_type TEXT DEFAULT 'user',
                        created_at TEXT NOT NULL,
                        created_by TEXT NOT NULL,
                        description TEXT,
                        metadata_json TEXT,
                        FOREIGN KEY (checkpoint_id) REFERENCES checkpoint_versions(checkpoint_id),
                        UNIQUE(tag_name, checkpoint_id)
                    )
                """)
                
                # Create compatibility matrix table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS version_compatibility (
                        compatibility_id TEXT PRIMARY KEY,
                        version_a TEXT NOT NULL,
                        version_b TEXT NOT NULL,
                        compatibility_level TEXT NOT NULL,
                        compatibility_score REAL NOT NULL,
                        breaking_changes_json TEXT,
                        migration_required BOOLEAN DEFAULT FALSE,
                        migration_script TEXT,
                        tested_at TEXT,
                        tested_by TEXT,
                        notes TEXT,
                        UNIQUE(version_a, version_b)
                    )
                """)
                
                # Create performance-optimized indexes
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_versions_branch_version 
                    ON checkpoint_versions(branch_name, major_version DESC, minor_version DESC, patch_version DESC)
                """)
                
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_versions_parent 
                    ON checkpoint_versions(parent_checkpoint_id)
                """)
                
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_versions_created 
                    ON checkpoint_versions(created_at DESC)
                """)
                
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_versions_stable_release 
                    ON checkpoint_versions(is_stable, is_release, created_at DESC)
                """)
                
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_relationships_source 
                    ON version_relationships(source_checkpoint_id, relationship_type)
                """)
                
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_relationships_target 
                    ON version_relationships(target_checkpoint_id, relationship_type)
                """)
                
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_branches_active 
                    ON version_branches(is_active, branch_name)
                """)
                
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_tags_name 
                    ON version_tags(tag_name, checkpoint_id)
                """)
                
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_compatibility_versions 
                    ON version_compatibility(version_a, version_b, compatibility_level)
                """)
                
                conn.commit()
                
                # Verify tables were created
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
                tables = [row[0] for row in cursor.fetchall()]
                expected_tables = [
                    'checkpoint_versions', 'version_relationships', 'version_branches',
                    'version_tags', 'version_compatibility'
                ]
                
                for table in expected_tables:
                    if table not in tables:
                        raise Exception(f"Failed to create table: {table}")
                
                self._logger.info("Checkpoint versioning database initialized successfully")
                
            except Exception as e:
                self._logger.error(f"Failed to initialize checkpoint versioning database: {e}")
                raise
            finally:
                conn.close()

    def create_version(self, version: CheckpointVersion) -> bool:
        """
        Create a new checkpoint version.

        Args:
            version: CheckpointVersion object to create

        Returns:
            True if creation successful, False otherwise
        """
        try:
            with self._lock:
                conn = sqlite3.connect(str(self.db_path))
                try:
                    cursor = conn.cursor()

                    # Convert version to database format
                    data = (
                        version.checkpoint_id,
                        version.version_number,
                        version.major_version,
                        version.minor_version,
                        version.patch_version,
                        version.parent_checkpoint_id,
                        version.branch_name,
                        version.commit_message,
                        version.created_at.isoformat(),
                        version.created_by,
                        json.dumps(list(version.tags)) if version.tags else None,
                        version.is_stable,
                        version.is_release,
                        version.compatibility_version,
                        json.dumps(version.metadata) if version.metadata else None,
                        datetime.now(timezone.utc).isoformat()
                    )

                    # Insert version record
                    cursor.execute("""
                        INSERT INTO checkpoint_versions (
                            checkpoint_id, version_number, major_version, minor_version, patch_version,
                            parent_checkpoint_id, branch_name, commit_message, created_at, created_by,
                            tags_json, is_stable, is_release, compatibility_version, metadata_json, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, data)

                    # Create tags if present
                    if version.tags:
                        for tag in version.tags:
                            tag_id = f"{version.checkpoint_id}_{tag}_{datetime.now().timestamp()}"
                            cursor.execute("""
                                INSERT OR IGNORE INTO version_tags (
                                    tag_id, tag_name, checkpoint_id, created_at, created_by
                                ) VALUES (?, ?, ?, ?, ?)
                            """, (tag_id, tag, version.checkpoint_id, version.created_at.isoformat(), version.created_by))

                    # Update branch head if this is the latest version
                    cursor.execute("""
                        UPDATE version_branches
                        SET head_checkpoint_id = ?
                        WHERE branch_name = ? AND (
                            head_checkpoint_id IS NULL OR
                            head_checkpoint_id IN (
                                SELECT checkpoint_id FROM checkpoint_versions
                                WHERE created_at < ?
                            )
                        )
                    """, (version.checkpoint_id, version.branch_name, version.created_at.isoformat()))

                    conn.commit()

                    self._logger.info(f"Version created successfully: {version.checkpoint_id} v{version.version_number}")
                    return True

                except Exception as e:
                    conn.rollback()
                    self._logger.error(f"Failed to create version {version.checkpoint_id}: {e}")
                    return False
                finally:
                    conn.close()

        except Exception as e:
            self._logger.error(f"Database connection error during version creation: {e}")
            return False

    def get_version(self, checkpoint_id: str) -> Optional[CheckpointVersion]:
        """
        Retrieve checkpoint version by ID.

        Args:
            checkpoint_id: Unique checkpoint identifier

        Returns:
            CheckpointVersion if found, None otherwise
        """
        try:
            with self._lock:
                conn = sqlite3.connect(str(self.db_path))
                try:
                    cursor = conn.cursor()

                    # Get version record
                    cursor.execute("""
                        SELECT * FROM checkpoint_versions WHERE checkpoint_id = ?
                    """, (checkpoint_id,))

                    row = cursor.fetchone()
                    if not row:
                        return None

                    # Convert to version object
                    version = self._db_format_to_version(row)

                    self._logger.debug(f"Retrieved version: {checkpoint_id}")
                    return version

                except Exception as e:
                    self._logger.error(f"Failed to retrieve version {checkpoint_id}: {e}")
                    return None
                finally:
                    conn.close()

        except Exception as e:
            self._logger.error(f"Database connection error during version retrieval: {e}")
            return None

    def create_relationship(self, relationship: VersionRelationship) -> bool:
        """
        Create a relationship between checkpoint versions.

        Args:
            relationship: VersionRelationship object to create

        Returns:
            True if creation successful, False otherwise
        """
        try:
            with self._lock:
                conn = sqlite3.connect(str(self.db_path))
                try:
                    cursor = conn.cursor()

                    # Insert relationship record
                    cursor.execute("""
                        INSERT OR REPLACE INTO version_relationships (
                            relationship_id, source_checkpoint_id, target_checkpoint_id,
                            relationship_type, created_at, metadata_json
                        ) VALUES (?, ?, ?, ?, ?, ?)
                    """, (
                        relationship.relationship_id,
                        relationship.source_checkpoint_id,
                        relationship.target_checkpoint_id,
                        relationship.relationship_type.value,
                        relationship.created_at.isoformat(),
                        json.dumps(relationship.metadata) if relationship.metadata else None
                    ))

                    conn.commit()

                    self._logger.info(f"Relationship created: {relationship.source_checkpoint_id} -> {relationship.target_checkpoint_id}")
                    return True

                except Exception as e:
                    conn.rollback()
                    self._logger.error(f"Failed to create relationship: {e}")
                    return False
                finally:
                    conn.close()

        except Exception as e:
            self._logger.error(f"Database connection error during relationship creation: {e}")
            return False

    def get_version_lineage(self, checkpoint_id: str, depth: int = 10) -> List[CheckpointVersion]:
        """
        Get version lineage (ancestors) for a checkpoint.

        Args:
            checkpoint_id: Starting checkpoint ID
            depth: Maximum depth to traverse

        Returns:
            List of checkpoint versions in lineage order
        """
        try:
            with self._lock:
                conn = sqlite3.connect(str(self.db_path))
                try:
                    cursor = conn.cursor()

                    lineage = []
                    current_id = checkpoint_id

                    for _ in range(depth):
                        if not current_id:
                            break

                        # Get current version
                        cursor.execute("""
                            SELECT * FROM checkpoint_versions WHERE checkpoint_id = ?
                        """, (current_id,))

                        row = cursor.fetchone()
                        if not row:
                            break

                        version = self._db_format_to_version(row)
                        if version:
                            lineage.append(version)
                            current_id = version.parent_checkpoint_id
                        else:
                            break

                    self._logger.debug(f"Retrieved lineage of {len(lineage)} versions for {checkpoint_id}")
                    return lineage

                except Exception as e:
                    self._logger.error(f"Failed to get version lineage for {checkpoint_id}: {e}")
                    return []
                finally:
                    conn.close()

        except Exception as e:
            self._logger.error(f"Database connection error during lineage retrieval: {e}")
            return []

    def get_version_children(self, checkpoint_id: str) -> List[CheckpointVersion]:
        """
        Get direct children of a checkpoint version.

        Args:
            checkpoint_id: Parent checkpoint ID

        Returns:
            List of child checkpoint versions
        """
        try:
            with self._lock:
                conn = sqlite3.connect(str(self.db_path))
                try:
                    cursor = conn.cursor()

                    # Get child versions
                    cursor.execute("""
                        SELECT * FROM checkpoint_versions
                        WHERE parent_checkpoint_id = ?
                        ORDER BY created_at ASC
                    """, (checkpoint_id,))

                    rows = cursor.fetchall()

                    # Convert to version objects
                    children = []
                    for row in rows:
                        version = self._db_format_to_version(row)
                        if version:
                            children.append(version)

                    self._logger.debug(f"Retrieved {len(children)} children for {checkpoint_id}")
                    return children

                except Exception as e:
                    self._logger.error(f"Failed to get version children for {checkpoint_id}: {e}")
                    return []
                finally:
                    conn.close()

        except Exception as e:
            self._logger.error(f"Database connection error during children retrieval: {e}")
            return []

    def get_branch_versions(self, branch_name: str, limit: int = 100) -> List[CheckpointVersion]:
        """
        Get all versions in a specific branch.

        Args:
            branch_name: Name of the branch
            limit: Maximum number of versions to return

        Returns:
            List of checkpoint versions in the branch
        """
        try:
            with self._lock:
                conn = sqlite3.connect(str(self.db_path))
                try:
                    cursor = conn.cursor()

                    # Get branch versions
                    cursor.execute("""
                        SELECT * FROM checkpoint_versions
                        WHERE branch_name = ?
                        ORDER BY major_version DESC, minor_version DESC, patch_version DESC, created_at DESC
                        LIMIT ?
                    """, (branch_name, limit))

                    rows = cursor.fetchall()

                    # Convert to version objects
                    versions = []
                    for row in rows:
                        version = self._db_format_to_version(row)
                        if version:
                            versions.append(version)

                    self._logger.debug(f"Retrieved {len(versions)} versions for branch {branch_name}")
                    return versions

                except Exception as e:
                    self._logger.error(f"Failed to get branch versions for {branch_name}: {e}")
                    return []
                finally:
                    conn.close()

        except Exception as e:
            self._logger.error(f"Database connection error during branch versions retrieval: {e}")
            return []

    def get_stable_versions(self, limit: int = 50) -> List[CheckpointVersion]:
        """
        Get all stable checkpoint versions.

        Args:
            limit: Maximum number of versions to return

        Returns:
            List of stable checkpoint versions
        """
        try:
            with self._lock:
                conn = sqlite3.connect(str(self.db_path))
                try:
                    cursor = conn.cursor()

                    # Get stable versions
                    cursor.execute("""
                        SELECT * FROM checkpoint_versions
                        WHERE is_stable = TRUE
                        ORDER BY created_at DESC
                        LIMIT ?
                    """, (limit,))

                    rows = cursor.fetchall()

                    # Convert to version objects
                    versions = []
                    for row in rows:
                        version = self._db_format_to_version(row)
                        if version:
                            versions.append(version)

                    self._logger.debug(f"Retrieved {len(versions)} stable versions")
                    return versions

                except Exception as e:
                    self._logger.error(f"Failed to get stable versions: {e}")
                    return []
                finally:
                    conn.close()

        except Exception as e:
            self._logger.error(f"Database connection error during stable versions retrieval: {e}")
            return []

    def create_branch(self, branch_name: str, base_checkpoint_id: Optional[str],
                     created_by: str, description: Optional[str] = None) -> bool:
        """
        Create a new version branch.

        Args:
            branch_name: Name of the new branch
            base_checkpoint_id: Base checkpoint for the branch
            created_by: User creating the branch
            description: Optional branch description

        Returns:
            True if creation successful, False otherwise
        """
        try:
            with self._lock:
                conn = sqlite3.connect(str(self.db_path))
                try:
                    cursor = conn.cursor()

                    # Check if branch already exists
                    cursor.execute("""
                        SELECT branch_name FROM version_branches WHERE branch_name = ?
                    """, (branch_name,))

                    if cursor.fetchone():
                        self._logger.warning(f"Branch already exists: {branch_name}")
                        return False

                    # Create branch
                    branch_id = f"branch_{branch_name}_{datetime.now().timestamp()}"
                    cursor.execute("""
                        INSERT INTO version_branches (
                            branch_id, branch_name, base_checkpoint_id, created_at, created_by, description
                        ) VALUES (?, ?, ?, ?, ?, ?)
                    """, (
                        branch_id, branch_name, base_checkpoint_id,
                        datetime.now(timezone.utc).isoformat(), created_by, description
                    ))

                    conn.commit()

                    self._logger.info(f"Branch created successfully: {branch_name}")
                    return True

                except Exception as e:
                    conn.rollback()
                    self._logger.error(f"Failed to create branch {branch_name}: {e}")
                    return False
                finally:
                    conn.close()

        except Exception as e:
            self._logger.error(f"Database connection error during branch creation: {e}")
            return False

    def get_version_statistics(self) -> Dict[str, Any]:
        """
        Get comprehensive version statistics.

        Returns:
            Dictionary with various statistics
        """
        try:
            with self._lock:
                conn = sqlite3.connect(str(self.db_path))
                try:
                    cursor = conn.cursor()

                    stats = {}

                    # Total versions count
                    cursor.execute("SELECT COUNT(*) FROM checkpoint_versions")
                    stats['total_versions'] = cursor.fetchone()[0]

                    # Count by branch
                    cursor.execute("""
                        SELECT branch_name, COUNT(*) FROM checkpoint_versions
                        GROUP BY branch_name
                    """)
                    stats['by_branch'] = dict(cursor.fetchall())

                    # Stable and release counts
                    cursor.execute("SELECT COUNT(*) FROM checkpoint_versions WHERE is_stable = TRUE")
                    stats['stable_versions'] = cursor.fetchone()[0]

                    cursor.execute("SELECT COUNT(*) FROM checkpoint_versions WHERE is_release = TRUE")
                    stats['release_versions'] = cursor.fetchone()[0]

                    # Relationship counts
                    cursor.execute("""
                        SELECT relationship_type, COUNT(*) FROM version_relationships
                        GROUP BY relationship_type
                    """)
                    stats['relationships'] = dict(cursor.fetchall())

                    # Active branches
                    cursor.execute("SELECT COUNT(*) FROM version_branches WHERE is_active = TRUE")
                    stats['active_branches'] = cursor.fetchone()[0]

                    self._logger.debug("Retrieved version statistics")
                    return stats

                except Exception as e:
                    self._logger.error(f"Failed to get version statistics: {e}")
                    return {}
                finally:
                    conn.close()

        except Exception as e:
            self._logger.error(f"Database connection error during statistics retrieval: {e}")
            return {}

    def _db_format_to_version(self, row: Tuple) -> Optional[CheckpointVersion]:
        """Convert database row to CheckpointVersion object."""
        try:
            if not row:
                return None

            # Parse JSON fields safely
            tags = set(json.loads(row[10])) if row[10] else set()
            metadata = json.loads(row[14]) if row[14] else {}

            # Create version object
            version = CheckpointVersion(
                checkpoint_id=row[0],
                version_number=row[1],
                major_version=row[2],
                minor_version=row[3],
                patch_version=row[4],
                parent_checkpoint_id=row[5],
                branch_name=row[6],
                commit_message=row[7],
                created_at=datetime.fromisoformat(row[8]),
                created_by=row[9],
                tags=tags,
                is_stable=bool(row[11]),
                is_release=bool(row[12]),
                compatibility_version=row[13],
                metadata=metadata
            )

            return version

        except Exception as e:
            self._logger.error(f"Failed to convert database row to version: {e}")
            return None

    def close(self) -> None:
        """Close database connections and cleanup resources."""
        with self._lock:
            self._logger.info("CheckpointVersioningDB closed")

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
