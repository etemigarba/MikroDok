"""
Module: model_versions_db
Description: Manages model version history with Git-style branching and semantic versioning support
Phase: 4
Location: /src/modules/database/model_repository_db/model_versions_db/
"""

# Standard library imports
import json
import sqlite3
import threading
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

# Local imports
from src.modules.logic.logging_infrastructure_lg.log_manager_lg.log_manager_lg import get_logger


class VersionType(Enum):
    """Version type enumeration."""
    MAJOR = "major"
    MINOR = "minor"
    PATCH = "patch"
    PRERELEASE = "prerelease"
    BUILD = "build"


class BranchType(Enum):
    """Branch type enumeration."""
    MAIN = "main"
    FEATURE = "feature"
    HOTFIX = "hotfix"
    RELEASE = "release"
    EXPERIMENTAL = "experimental"


@dataclass
class ModelVersion:
    """Model version data structure."""
    version_id: str
    model_id: str
    version_number: str
    major_version: int
    minor_version: int
    patch_version: int
    prerelease: Optional[str] = None
    build_metadata: Optional[str] = None
    parent_version_id: Optional[str] = None
    branch_name: str = "main"
    branch_type: BranchType = BranchType.MAIN
    commit_message: Optional[str] = None
    created_at: datetime = None
    created_by: Optional[str] = None
    tags: Optional[List[str]] = None
    is_stable: bool = False
    is_release: bool = False
    is_latest: bool = False
    compatibility_version: Optional[str] = None
    changelog: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now(timezone.utc)
        if self.tags is None:
            self.tags = []


@dataclass
class VersionComparison:
    """Version comparison result."""
    version1: str
    version2: str
    comparison_result: int  # -1: v1 < v2, 0: v1 == v2, 1: v1 > v2
    major_diff: int
    minor_diff: int
    patch_diff: int
    is_compatible: bool
    breaking_changes: List[str]


class ModelVersionsDB:
    """
    Model versions database for managing version history with Git-style branching.
    
    Provides comprehensive version management including semantic versioning,
    branching strategies, compatibility tracking, and version comparison.
    """
    
    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize the model versions database.
        
        Args:
            db_path: Path to the database file
        """
        if db_path is None:
            # Default to model repository data directory
            data_dir = Path.home() / ".mikrodok" / "data" / "model_repository"
            data_dir.mkdir(parents=True, exist_ok=True)
            db_path = str(data_dir / "model_versions.db")
        
        self._db_path = db_path
        self._lock = threading.RLock()
        self._logger = get_logger(__name__)
        
        # Configuration settings
        self._max_versions_per_model = 1000  # Maximum versions per model
        self._version_retention_days = 365  # Keep versions for 1 year
        self._max_branches_per_model = 50  # Maximum branches per model
        
        self._initialize_database()
    
    def _initialize_database(self) -> None:
        """Initialize the database schema."""
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()
                
                # Enable WAL mode for better concurrency
                cursor.execute("PRAGMA journal_mode=WAL")
                cursor.execute("PRAGMA synchronous=NORMAL")
                cursor.execute("PRAGMA cache_size=10000")
                cursor.execute("PRAGMA temp_store=MEMORY")
                
                # Create model versions table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS model_versions (
                        version_id TEXT PRIMARY KEY,
                        model_id TEXT NOT NULL,
                        version_number TEXT NOT NULL,
                        major_version INTEGER NOT NULL,
                        minor_version INTEGER NOT NULL,
                        patch_version INTEGER NOT NULL,
                        prerelease TEXT,
                        build_metadata TEXT,
                        parent_version_id TEXT,
                        branch_name TEXT NOT NULL DEFAULT 'main',
                        branch_type TEXT NOT NULL DEFAULT 'main',
                        commit_message TEXT,
                        created_at TEXT NOT NULL,
                        created_by TEXT,
                        tags_json TEXT,
                        is_stable BOOLEAN DEFAULT 0,
                        is_release BOOLEAN DEFAULT 0,
                        is_latest BOOLEAN DEFAULT 0,
                        compatibility_version TEXT,
                        changelog TEXT,
                        metadata_json TEXT,
                        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        
                        CONSTRAINT valid_branch_type CHECK (branch_type IN ('main', 'feature', 'hotfix', 'release', 'experimental')),
                        FOREIGN KEY (parent_version_id) REFERENCES model_versions(version_id)
                    )
                """)
                
                # Create performance-optimized indexes
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_versions_model_version 
                    ON model_versions(model_id, version_number)
                """)
                
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_versions_model_branch 
                    ON model_versions(model_id, branch_name, created_at DESC)
                """)
                
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_versions_semantic 
                    ON model_versions(model_id, major_version DESC, minor_version DESC, patch_version DESC)
                """)
                
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_versions_latest 
                    ON model_versions(model_id, is_latest, is_stable)
                """)
                
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_versions_parent 
                    ON model_versions(parent_version_id)
                """)
                
                # Create version dependencies table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS version_dependencies (
                        dependency_id TEXT PRIMARY KEY,
                        version_id TEXT NOT NULL,
                        dependency_type TEXT NOT NULL,
                        dependency_name TEXT NOT NULL,
                        dependency_version TEXT NOT NULL,
                        is_required BOOLEAN DEFAULT 1,
                        compatibility_range TEXT,
                        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        
                        FOREIGN KEY (version_id) REFERENCES model_versions(version_id) ON DELETE CASCADE
                    )
                """)
                
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_dependencies_version 
                    ON version_dependencies(version_id, dependency_type)
                """)
                
                # Create version changes table for detailed change tracking
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS version_changes (
                        change_id TEXT PRIMARY KEY,
                        version_id TEXT NOT NULL,
                        change_type TEXT NOT NULL,
                        change_category TEXT NOT NULL,
                        change_description TEXT NOT NULL,
                        affected_component TEXT,
                        breaking_change BOOLEAN DEFAULT 0,
                        migration_notes TEXT,
                        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        
                        CONSTRAINT valid_change_type CHECK (change_type IN ('added', 'modified', 'removed', 'deprecated', 'fixed')),
                        CONSTRAINT valid_change_category CHECK (change_category IN ('feature', 'bugfix', 'performance', 'security', 'documentation', 'breaking')),
                        FOREIGN KEY (version_id) REFERENCES model_versions(version_id) ON DELETE CASCADE
                    )
                """)
                
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_changes_version_type 
                    ON version_changes(version_id, change_type, breaking_change)
                """)
                
                # Create branch management table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS model_branches (
                        branch_id TEXT PRIMARY KEY,
                        model_id TEXT NOT NULL,
                        branch_name TEXT NOT NULL,
                        branch_type TEXT NOT NULL,
                        base_version_id TEXT,
                        head_version_id TEXT,
                        is_active BOOLEAN DEFAULT 1,
                        is_protected BOOLEAN DEFAULT 0,
                        created_at TEXT NOT NULL,
                        created_by TEXT,
                        description TEXT,
                        merge_strategy TEXT DEFAULT 'merge',
                        
                        CONSTRAINT valid_branch_type CHECK (branch_type IN ('main', 'feature', 'hotfix', 'release', 'experimental')),
                        CONSTRAINT valid_merge_strategy CHECK (merge_strategy IN ('merge', 'squash', 'rebase')),
                        UNIQUE(model_id, branch_name),
                        FOREIGN KEY (base_version_id) REFERENCES model_versions(version_id),
                        FOREIGN KEY (head_version_id) REFERENCES model_versions(version_id)
                    )
                """)
                
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_branches_model_active 
                    ON model_branches(model_id, is_active, branch_type)
                """)
                
                conn.commit()
                self._logger.info("Model versions database initialized successfully")

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to initialize model versions database: {e}")
                raise
            finally:
                conn.close()

    def create_version(self, model_version: ModelVersion) -> str:
        """
        Create a new model version.

        Args:
            model_version: Model version data

        Returns:
            Version ID of the created version

        Raises:
            ValueError: If version data is invalid
        """
        if not model_version.version_id:
            model_version.version_id = str(uuid.uuid4())

        # Validate required fields
        if not model_version.model_id:
            raise ValueError("Model ID is required")
        if not model_version.version_number:
            raise ValueError("Version number is required")

        # Parse semantic version if not provided
        if not all([model_version.major_version, model_version.minor_version, model_version.patch_version]):
            self._parse_semantic_version(model_version)

        model_version.created_at = datetime.now(timezone.utc)

        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                # Check if version already exists
                cursor.execute("""
                    SELECT version_id FROM model_versions
                    WHERE model_id = ? AND version_number = ?
                """, (model_version.model_id, model_version.version_number))

                if cursor.fetchone():
                    raise ValueError(f"Version {model_version.version_number} already exists for model {model_version.model_id}")

                # Clear previous latest flag if this is latest
                if model_version.is_latest:
                    cursor.execute("""
                        UPDATE model_versions
                        SET is_latest = 0
                        WHERE model_id = ? AND is_latest = 1
                    """, (model_version.model_id,))

                # Insert version record
                cursor.execute("""
                    INSERT INTO model_versions (
                        version_id, model_id, version_number, major_version, minor_version,
                        patch_version, prerelease, build_metadata, parent_version_id,
                        branch_name, branch_type, commit_message, created_at, created_by,
                        tags_json, is_stable, is_release, is_latest, compatibility_version,
                        changelog, metadata_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    model_version.version_id,
                    model_version.model_id,
                    model_version.version_number,
                    model_version.major_version,
                    model_version.minor_version,
                    model_version.patch_version,
                    model_version.prerelease,
                    model_version.build_metadata,
                    model_version.parent_version_id,
                    model_version.branch_name,
                    model_version.branch_type.value,
                    model_version.commit_message,
                    model_version.created_at.isoformat(),
                    model_version.created_by,
                    json.dumps(model_version.tags) if model_version.tags else None,
                    model_version.is_stable,
                    model_version.is_release,
                    model_version.is_latest,
                    model_version.compatibility_version,
                    model_version.changelog,
                    json.dumps(model_version.metadata) if model_version.metadata else None
                ))

                # Update branch head if this is the latest version on the branch
                self._update_branch_head(cursor, model_version.model_id, model_version.branch_name, model_version.version_id)

                conn.commit()
                self._logger.info(f"Created model version: {model_version.version_id}")
                return model_version.version_id

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to create model version {model_version.version_id}: {e}")
                raise
            finally:
                conn.close()

    def get_version(self, version_id: str) -> Optional[ModelVersion]:
        """
        Retrieve a model version by ID.

        Args:
            version_id: Version identifier

        Returns:
            Model version or None if not found
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                cursor.execute("""
                    SELECT version_id, model_id, version_number, major_version, minor_version,
                           patch_version, prerelease, build_metadata, parent_version_id,
                           branch_name, branch_type, commit_message, created_at, created_by,
                           tags_json, is_stable, is_release, is_latest, compatibility_version,
                           changelog, metadata_json
                    FROM model_versions
                    WHERE version_id = ?
                """, (version_id,))

                row = cursor.fetchone()
                if not row:
                    return None

                return self._row_to_model_version(row)

            except Exception as e:
                self._logger.error(f"Failed to get model version {version_id}: {e}")
                raise
            finally:
                conn.close()

    def get_latest_version(self, model_id: str, branch_name: str = "main") -> Optional[ModelVersion]:
        """
        Get the latest version for a model on a specific branch.

        Args:
            model_id: Model identifier
            branch_name: Branch name

        Returns:
            Latest model version or None if not found
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                cursor.execute("""
                    SELECT version_id, model_id, version_number, major_version, minor_version,
                           patch_version, prerelease, build_metadata, parent_version_id,
                           branch_name, branch_type, commit_message, created_at, created_by,
                           tags_json, is_stable, is_release, is_latest, compatibility_version,
                           changelog, metadata_json
                    FROM model_versions
                    WHERE model_id = ? AND branch_name = ?
                    ORDER BY major_version DESC, minor_version DESC, patch_version DESC, created_at DESC
                    LIMIT 1
                """, (model_id, branch_name))

                row = cursor.fetchone()
                if not row:
                    return None

                return self._row_to_model_version(row)

            except Exception as e:
                self._logger.error(f"Failed to get latest version for model {model_id}: {e}")
                raise
            finally:
                conn.close()

    def list_versions(self, model_id: str, branch_name: Optional[str] = None,
                     include_prereleases: bool = True, limit: int = 100,
                     offset: int = 0) -> List[ModelVersion]:
        """
        List versions for a model with optional filtering.

        Args:
            model_id: Model identifier
            branch_name: Filter by branch name
            include_prereleases: Include prerelease versions
            limit: Maximum number of results
            offset: Number of results to skip

        Returns:
            List of model versions
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                # Build query with filters
                query = """
                    SELECT version_id, model_id, version_number, major_version, minor_version,
                           patch_version, prerelease, build_metadata, parent_version_id,
                           branch_name, branch_type, commit_message, created_at, created_by,
                           tags_json, is_stable, is_release, is_latest, compatibility_version,
                           changelog, metadata_json
                    FROM model_versions
                    WHERE model_id = ?
                """
                params = [model_id]

                if branch_name:
                    query += " AND branch_name = ?"
                    params.append(branch_name)

                if not include_prereleases:
                    query += " AND (prerelease IS NULL OR prerelease = '')"

                query += " ORDER BY major_version DESC, minor_version DESC, patch_version DESC, created_at DESC"
                query += " LIMIT ? OFFSET ?"
                params.extend([limit, offset])

                cursor.execute(query, params)
                rows = cursor.fetchall()

                return [self._row_to_model_version(row) for row in rows]

            except Exception as e:
                self._logger.error(f"Failed to list versions for model {model_id}: {e}")
                raise
            finally:
                conn.close()

    def create_branch(self, model_id: str, branch_name: str, branch_type: BranchType,
                     base_version_id: Optional[str] = None, description: Optional[str] = None,
                     created_by: Optional[str] = None) -> str:
        """
        Create a new branch for a model.

        Args:
            model_id: Model identifier
            branch_name: Name of the new branch
            branch_type: Type of branch
            base_version_id: Base version to branch from
            description: Branch description
            created_by: User creating the branch

        Returns:
            Branch ID
        """
        branch_id = str(uuid.uuid4())

        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                # Check if branch already exists
                cursor.execute("""
                    SELECT branch_id FROM model_branches
                    WHERE model_id = ? AND branch_name = ?
                """, (model_id, branch_name))

                if cursor.fetchone():
                    raise ValueError(f"Branch {branch_name} already exists for model {model_id}")

                # If no base version specified, use latest from main
                if not base_version_id:
                    latest_version = self.get_latest_version(model_id, "main")
                    if latest_version:
                        base_version_id = latest_version.version_id

                cursor.execute("""
                    INSERT INTO model_branches (
                        branch_id, model_id, branch_name, branch_type, base_version_id,
                        head_version_id, created_at, created_by, description
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    branch_id, model_id, branch_name, branch_type.value,
                    base_version_id, base_version_id,
                    datetime.now(timezone.utc).isoformat(),
                    created_by, description
                ))

                conn.commit()
                self._logger.info(f"Created branch {branch_name} for model {model_id}")
                return branch_id

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to create branch {branch_name} for model {model_id}: {e}")
                raise
            finally:
                conn.close()

    def compare_versions(self, version1_id: str, version2_id: str) -> VersionComparison:
        """
        Compare two model versions.

        Args:
            version1_id: First version ID
            version2_id: Second version ID

        Returns:
            Version comparison result
        """
        version1 = self.get_version(version1_id)
        version2 = self.get_version(version2_id)

        if not version1 or not version2:
            raise ValueError("One or both versions not found")

        # Compare semantic versions
        v1_tuple = (version1.major_version, version1.minor_version, version1.patch_version)
        v2_tuple = (version2.major_version, version2.minor_version, version2.patch_version)

        if v1_tuple < v2_tuple:
            comparison_result = -1
        elif v1_tuple > v2_tuple:
            comparison_result = 1
        else:
            comparison_result = 0

        # Calculate differences
        major_diff = version2.major_version - version1.major_version
        minor_diff = version2.minor_version - version1.minor_version
        patch_diff = version2.patch_version - version1.patch_version

        # Check compatibility (major version changes are breaking)
        is_compatible = major_diff == 0

        # Get breaking changes
        breaking_changes = self._get_breaking_changes(version1_id, version2_id)

        return VersionComparison(
            version1=version1.version_number,
            version2=version2.version_number,
            comparison_result=comparison_result,
            major_diff=major_diff,
            minor_diff=minor_diff,
            patch_diff=patch_diff,
            is_compatible=is_compatible,
            breaking_changes=breaking_changes
        )

    def add_version_change(self, version_id: str, change_type: str, change_category: str,
                          change_description: str, affected_component: Optional[str] = None,
                          breaking_change: bool = False, migration_notes: Optional[str] = None) -> str:
        """
        Add a change record for a version.

        Args:
            version_id: Version identifier
            change_type: Type of change (added, modified, removed, deprecated, fixed)
            change_category: Category of change (feature, bugfix, performance, security, etc.)
            change_description: Description of the change
            affected_component: Component affected by the change
            breaking_change: Whether this is a breaking change
            migration_notes: Notes for migrating from previous version

        Returns:
            Change ID
        """
        change_id = str(uuid.uuid4())

        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                cursor.execute("""
                    INSERT INTO version_changes (
                        change_id, version_id, change_type, change_category,
                        change_description, affected_component, breaking_change, migration_notes
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    change_id, version_id, change_type, change_category,
                    change_description, affected_component, breaking_change, migration_notes
                ))

                conn.commit()
                self._logger.info(f"Added change record for version {version_id}")
                return change_id

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to add change record for version {version_id}: {e}")
                raise
            finally:
                conn.close()

    def get_version_changes(self, version_id: str) -> List[Dict[str, Any]]:
        """
        Get change records for a version.

        Args:
            version_id: Version identifier

        Returns:
            List of change records
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                cursor.execute("""
                    SELECT change_id, change_type, change_category, change_description,
                           affected_component, breaking_change, migration_notes, created_at
                    FROM version_changes
                    WHERE version_id = ?
                    ORDER BY created_at ASC
                """, (version_id,))

                rows = cursor.fetchall()
                changes = []

                for row in rows:
                    change = {
                        'change_id': row[0],
                        'change_type': row[1],
                        'change_category': row[2],
                        'change_description': row[3],
                        'affected_component': row[4],
                        'breaking_change': bool(row[5]),
                        'migration_notes': row[6],
                        'created_at': row[7]
                    }
                    changes.append(change)

                return changes

            except Exception as e:
                self._logger.error(f"Failed to get changes for version {version_id}: {e}")
                raise
            finally:
                conn.close()

    def _parse_semantic_version(self, model_version: ModelVersion) -> None:
        """Parse semantic version string into components."""
        version_parts = model_version.version_number.split('.')

        if len(version_parts) < 3:
            raise ValueError(f"Invalid semantic version: {model_version.version_number}")

        try:
            model_version.major_version = int(version_parts[0])
            model_version.minor_version = int(version_parts[1])

            # Handle patch version with prerelease/build metadata
            patch_part = version_parts[2]
            if '-' in patch_part:
                patch_str, prerelease = patch_part.split('-', 1)
                model_version.patch_version = int(patch_str)
                if '+' in prerelease:
                    prerelease, build = prerelease.split('+', 1)
                    model_version.build_metadata = build
                model_version.prerelease = prerelease
            elif '+' in patch_part:
                patch_str, build = patch_part.split('+', 1)
                model_version.patch_version = int(patch_str)
                model_version.build_metadata = build
            else:
                model_version.patch_version = int(patch_part)

        except ValueError as e:
            raise ValueError(f"Invalid semantic version format: {model_version.version_number}") from e

    def _update_branch_head(self, cursor: sqlite3.Cursor, model_id: str, branch_name: str, version_id: str) -> None:
        """Update the head version of a branch."""
        cursor.execute("""
            UPDATE model_branches
            SET head_version_id = ?
            WHERE model_id = ? AND branch_name = ?
        """, (version_id, model_id, branch_name))

        # Create branch if it doesn't exist
        if cursor.rowcount == 0:
            cursor.execute("""
                INSERT INTO model_branches (
                    branch_id, model_id, branch_name, branch_type, head_version_id,
                    created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
            """, (
                str(uuid.uuid4()), model_id, branch_name, 'main',
                version_id, datetime.now(timezone.utc).isoformat()
            ))

    def _get_breaking_changes(self, version1_id: str, version2_id: str) -> List[str]:
        """Get breaking changes between two versions."""
        with sqlite3.connect(self._db_path) as conn:
            cursor = conn.cursor()

            cursor.execute("""
                SELECT change_description
                FROM version_changes
                WHERE version_id = ? AND breaking_change = 1
            """, (version2_id,))

            return [row[0] for row in cursor.fetchall()]

    def _row_to_model_version(self, row: Tuple) -> ModelVersion:
        """Convert database row to ModelVersion object."""
        return ModelVersion(
            version_id=row[0],
            model_id=row[1],
            version_number=row[2],
            major_version=row[3],
            minor_version=row[4],
            patch_version=row[5],
            prerelease=row[6],
            build_metadata=row[7],
            parent_version_id=row[8],
            branch_name=row[9],
            branch_type=BranchType(row[10]),
            commit_message=row[11],
            created_at=datetime.fromisoformat(row[12]) if row[12] else None,
            created_by=row[13],
            tags=json.loads(row[14]) if row[14] else [],
            is_stable=bool(row[15]),
            is_release=bool(row[16]),
            is_latest=bool(row[17]),
            compatibility_version=row[18],
            changelog=row[19],
            metadata=json.loads(row[20]) if row[20] else None
        )

    def get_version_tree(self, model_id: str) -> Dict[str, Any]:
        """
        Get the version tree for a model showing parent-child relationships.

        Args:
            model_id: Model identifier

        Returns:
            Dictionary representing the version tree
        """
        versions = self.list_versions(model_id, limit=1000)

        # Build tree structure
        tree = {}
        version_map = {v.version_id: v for v in versions}

        for version in versions:
            if not version.parent_version_id:
                # Root version
                tree[version.version_id] = {
                    'version': version,
                    'children': []
                }
            else:
                # Child version
                if version.parent_version_id in tree:
                    tree[version.parent_version_id]['children'].append({
                        'version': version,
                        'children': []
                    })

        return tree

    def cleanup_old_versions(self, retention_days: Optional[int] = None) -> int:
        """
        Clean up old versions based on retention policy.

        Args:
            retention_days: Number of days to retain versions

        Returns:
            Number of versions cleaned up
        """
        if retention_days is None:
            retention_days = self._version_retention_days

        cutoff_date = datetime.now(timezone.utc) - timedelta(days=retention_days)

        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                # Don't delete stable releases or latest versions
                cursor.execute("""
                    DELETE FROM model_versions
                    WHERE created_at < ? AND is_stable = 0 AND is_release = 0 AND is_latest = 0
                """, (cutoff_date.isoformat(),))

                deleted_count = cursor.rowcount
                conn.commit()

                self._logger.info(f"Cleaned up {deleted_count} old versions")
                return deleted_count

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to cleanup old versions: {e}")
                raise
            finally:
                conn.close()
