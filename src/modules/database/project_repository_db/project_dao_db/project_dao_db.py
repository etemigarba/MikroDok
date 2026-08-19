"""
Module: project_dao_db
Description: Data access operations for project entities including CRUD operations and query optimization
Phase: 4
Location: /src/modules/database/project_repository_db/project_dao_db/
"""

# Standard library imports
import json
import logging
import sqlite3
import threading
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

# Local imports
from ..entities import Project, ProjectStatus, ProjectType
from ...database_core_db.connection_manager_db.connection_manager_db import ConnectionManagerDB


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance."""
    return logging.getLogger(name)


class ProjectDAODB:
    """
    Data Access Object for project entities with optimized CRUD operations.
    
    Provides thread-safe database operations for project management including
    creation, retrieval, updates, deletion, and advanced querying with
    performance optimization and connection pooling.
    """
    
    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize the project DAO database.
        
        Args:
            db_path: Path to the database file
        """
        if db_path is None:
            # Default to projects data directory
            data_dir = Path.home() / ".mikrodok" / "data" / "projects"
            data_dir.mkdir(parents=True, exist_ok=True)
            db_path = str(data_dir / "projects.db")
        
        self._db_path = db_path
        self._lock = threading.RLock()
        self._logger = get_logger(__name__)
        self._connection_manager = ConnectionManagerDB(db_path)
        self._initialize_database()
    
    def _initialize_database(self):
        """Initialize the database schema."""
        try:
            with self._connection_manager.get_connection() as conn:
                cursor = conn.cursor()
                
                # Create projects table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS projects (
                        id TEXT PRIMARY KEY,
                        name TEXT NOT NULL UNIQUE,
                        description TEXT,
                        project_type TEXT NOT NULL DEFAULT 'fine_tuning',
                        status TEXT NOT NULL DEFAULT 'active',
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL,
                        settings TEXT,  -- JSON
                        metadata TEXT,  -- JSON
                        project_directory TEXT,
                        data_directory TEXT,
                        output_directory TEXT,
                        document_count INTEGER DEFAULT 0,
                        model_count INTEGER DEFAULT 0,
                        training_session_count INTEGER DEFAULT 0,
                        total_size_bytes INTEGER DEFAULT 0,
                        CONSTRAINT chk_status CHECK (status IN ('active', 'archived', 'deleted')),
                        CONSTRAINT chk_project_type CHECK (project_type IN ('fine_tuning', 'rag_training', 'custom_model', 'inference_only'))
                    )
                """)
                
                # Create indexes for performance
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_projects_status ON projects(status)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_projects_type ON projects(project_type)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_projects_created ON projects(created_at)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_projects_updated ON projects(updated_at)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_projects_name ON projects(name)")
                
                # Create trigger for automatic updated_at timestamp
                cursor.execute("""
                    CREATE TRIGGER IF NOT EXISTS update_projects_timestamp 
                    AFTER UPDATE ON projects
                    FOR EACH ROW
                    BEGIN
                        UPDATE projects SET updated_at = datetime('now') WHERE id = NEW.id;
                    END
                """)
                
                conn.commit()
                self._logger.debug("Project DAO database initialized successfully")
                
        except Exception as e:
            self._logger.error(f"Failed to initialize project DAO database: {e}")
            raise
    
    def create_project(self, project: Project) -> bool:
        """
        Create a new project in the database.
        
        Args:
            project: Project entity to create
            
        Returns:
            bool: True if successful
            
        Raises:
            ValueError: If project data is invalid
            sqlite3.IntegrityError: If project name already exists
        """
        try:
            with self._lock:
                # Validate project data
                if not project.name.strip():
                    raise ValueError("Project name cannot be empty")
                
                # Ensure timestamps are set
                if not project.created_at:
                    project.created_at = datetime.now(timezone.utc)
                if not project.updated_at:
                    project.updated_at = datetime.now(timezone.utc)
                
                with self._connection_manager.get_connection() as conn:
                    cursor = conn.cursor()
                    
                    cursor.execute("""
                        INSERT INTO projects (
                            id, name, description, project_type, status,
                            created_at, updated_at, settings, metadata,
                            project_directory, data_directory, output_directory,
                            document_count, model_count, training_session_count, total_size_bytes
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        project.id,
                        project.name,
                        project.description,
                        project.project_type.value,
                        project.status.value,
                        project.created_at.isoformat(),
                        project.updated_at.isoformat(),
                        json.dumps(project.settings.to_dict()),
                        json.dumps(project.metadata.to_dict()),
                        project.project_directory,
                        project.data_directory,
                        project.output_directory,
                        project.document_count,
                        project.model_count,
                        project.training_session_count,
                        project.total_size_bytes
                    ))
                    
                    conn.commit()
                    self._logger.info(f"Created project: {project.name} ({project.id})")
                    return True
                    
        except sqlite3.IntegrityError as e:
            if "UNIQUE constraint failed" in str(e):
                self._logger.error(f"Project name already exists: {project.name}")
                raise ValueError(f"Project name '{project.name}' already exists")
            else:
                self._logger.error(f"Database integrity error creating project: {e}")
                raise
        except Exception as e:
            self._logger.error(f"Failed to create project {project.name}: {e}")
            raise
    
    def get_project_by_id(self, project_id: str) -> Optional[Project]:
        """
        Retrieve a project by its ID.
        
        Args:
            project_id: Project identifier
            
        Returns:
            Project entity or None if not found
        """
        try:
            with self._connection_manager.get_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    SELECT * FROM projects WHERE id = ?
                """, (project_id,))
                
                row = cursor.fetchone()
                if row:
                    return self._row_to_project(row)
                return None
                
        except Exception as e:
            self._logger.error(f"Failed to get project by ID {project_id}: {e}")
            raise
    
    def get_project_by_name(self, name: str) -> Optional[Project]:
        """
        Retrieve a project by its name.
        
        Args:
            name: Project name
            
        Returns:
            Project entity or None if not found
        """
        try:
            with self._connection_manager.get_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    SELECT * FROM projects WHERE name = ?
                """, (name,))
                
                row = cursor.fetchone()
                if row:
                    return self._row_to_project(row)
                return None
                
        except Exception as e:
            self._logger.error(f"Failed to get project by name {name}: {e}")
            raise
    
    def update_project(self, project: Project) -> bool:
        """
        Update an existing project.
        
        Args:
            project: Project entity with updated data
            
        Returns:
            bool: True if successful
        """
        try:
            with self._lock:
                # Update timestamp
                project.update_timestamp()
                
                with self._connection_manager.get_connection() as conn:
                    cursor = conn.cursor()
                    
                    cursor.execute("""
                        UPDATE projects SET
                            name = ?, description = ?, project_type = ?, status = ?,
                            updated_at = ?, settings = ?, metadata = ?,
                            project_directory = ?, data_directory = ?, output_directory = ?,
                            document_count = ?, model_count = ?, training_session_count = ?, total_size_bytes = ?
                        WHERE id = ?
                    """, (
                        project.name,
                        project.description,
                        project.project_type.value,
                        project.status.value,
                        project.updated_at.isoformat(),
                        json.dumps(project.settings.to_dict()),
                        json.dumps(project.metadata.to_dict()),
                        project.project_directory,
                        project.data_directory,
                        project.output_directory,
                        project.document_count,
                        project.model_count,
                        project.training_session_count,
                        project.total_size_bytes,
                        project.id
                    ))
                    
                    if cursor.rowcount > 0:
                        conn.commit()
                        self._logger.info(f"Updated project: {project.name} ({project.id})")
                        return True
                    else:
                        self._logger.warning(f"Project not found for update: {project.id}")
                        return False
                        
        except Exception as e:
            self._logger.error(f"Failed to update project {project.id}: {e}")
            raise
    
    def delete_project(self, project_id: str, soft_delete: bool = True) -> bool:
        """
        Delete a project (soft or hard delete).
        
        Args:
            project_id: Project identifier
            soft_delete: If True, mark as deleted; if False, remove from database
            
        Returns:
            bool: True if successful
        """
        try:
            with self._lock:
                with self._connection_manager.get_connection() as conn:
                    cursor = conn.cursor()
                    
                    if soft_delete:
                        # Soft delete - mark as deleted
                        cursor.execute("""
                            UPDATE projects SET 
                                status = 'deleted',
                                updated_at = ?
                            WHERE id = ?
                        """, (datetime.now(timezone.utc).isoformat(), project_id))
                    else:
                        # Hard delete - remove from database
                        cursor.execute("DELETE FROM projects WHERE id = ?", (project_id,))
                    
                    if cursor.rowcount > 0:
                        conn.commit()
                        delete_type = "soft" if soft_delete else "hard"
                        self._logger.info(f"Performed {delete_type} delete on project: {project_id}")
                        return True
                    else:
                        self._logger.warning(f"Project not found for deletion: {project_id}")
                        return False
                        
        except Exception as e:
            self._logger.error(f"Failed to delete project {project_id}: {e}")
            raise

    def list_projects(self,
                     status: Optional[ProjectStatus] = None,
                     project_type: Optional[ProjectType] = None,
                     limit: Optional[int] = None,
                     offset: int = 0,
                     order_by: str = "updated_at",
                     order_desc: bool = True) -> List[Project]:
        """
        List projects with optional filtering and pagination.

        Args:
            status: Filter by project status
            project_type: Filter by project type
            limit: Maximum number of results
            offset: Number of results to skip
            order_by: Column to order by
            order_desc: If True, order descending

        Returns:
            List of Project entities
        """
        try:
            with self._connection_manager.get_connection() as conn:
                cursor = conn.cursor()

                # Build query with filters
                query = "SELECT * FROM projects WHERE 1=1"
                params = []

                if status:
                    query += " AND status = ?"
                    params.append(status.value)

                if project_type:
                    query += " AND project_type = ?"
                    params.append(project_type.value)

                # Add ordering
                order_direction = "DESC" if order_desc else "ASC"
                query += f" ORDER BY {order_by} {order_direction}"

                # Add pagination
                if limit:
                    query += " LIMIT ?"
                    params.append(limit)

                if offset > 0:
                    query += " OFFSET ?"
                    params.append(offset)

                cursor.execute(query, params)
                rows = cursor.fetchall()

                return [self._row_to_project(row) for row in rows]

        except Exception as e:
            self._logger.error(f"Failed to list projects: {e}")
            raise

    def search_projects(self, search_term: str, limit: Optional[int] = None) -> List[Project]:
        """
        Search projects by name or description.

        Args:
            search_term: Search term to match
            limit: Maximum number of results

        Returns:
            List of matching Project entities
        """
        try:
            with self._connection_manager.get_connection() as conn:
                cursor = conn.cursor()

                query = """
                    SELECT * FROM projects
                    WHERE (name LIKE ? OR description LIKE ?)
                    AND status != 'deleted'
                    ORDER BY
                        CASE
                            WHEN name LIKE ? THEN 1
                            WHEN description LIKE ? THEN 2
                            ELSE 3
                        END,
                        updated_at DESC
                """

                search_pattern = f"%{search_term}%"
                params = [search_pattern, search_pattern, f"{search_term}%", f"{search_term}%"]

                if limit:
                    query += " LIMIT ?"
                    params.append(limit)

                cursor.execute(query, params)
                rows = cursor.fetchall()

                return [self._row_to_project(row) for row in rows]

        except Exception as e:
            self._logger.error(f"Failed to search projects: {e}")
            raise

    def get_project_count(self, status: Optional[ProjectStatus] = None) -> int:
        """
        Get the total count of projects.

        Args:
            status: Optional status filter

        Returns:
            Total number of projects
        """
        try:
            with self._connection_manager.get_connection() as conn:
                cursor = conn.cursor()

                if status:
                    cursor.execute("SELECT COUNT(*) FROM projects WHERE status = ?", (status.value,))
                else:
                    cursor.execute("SELECT COUNT(*) FROM projects")

                return cursor.fetchone()[0]

        except Exception as e:
            self._logger.error(f"Failed to get project count: {e}")
            raise

    def update_project_statistics(self, project_id: str,
                                document_count: Optional[int] = None,
                                model_count: Optional[int] = None,
                                training_session_count: Optional[int] = None,
                                total_size_bytes: Optional[int] = None) -> bool:
        """
        Update project statistics.

        Args:
            project_id: Project identifier
            document_count: Number of documents
            model_count: Number of models
            training_session_count: Number of training sessions
            total_size_bytes: Total size in bytes

        Returns:
            bool: True if successful
        """
        try:
            with self._lock:
                with self._connection_manager.get_connection() as conn:
                    cursor = conn.cursor()

                    # Build update query dynamically
                    updates = []
                    params = []

                    if document_count is not None:
                        updates.append("document_count = ?")
                        params.append(document_count)

                    if model_count is not None:
                        updates.append("model_count = ?")
                        params.append(model_count)

                    if training_session_count is not None:
                        updates.append("training_session_count = ?")
                        params.append(training_session_count)

                    if total_size_bytes is not None:
                        updates.append("total_size_bytes = ?")
                        params.append(total_size_bytes)

                    if not updates:
                        return True  # Nothing to update

                    updates.append("updated_at = ?")
                    params.append(datetime.now(timezone.utc).isoformat())
                    params.append(project_id)

                    query = f"UPDATE projects SET {', '.join(updates)} WHERE id = ?"
                    cursor.execute(query, params)

                    if cursor.rowcount > 0:
                        conn.commit()
                        self._logger.debug(f"Updated statistics for project: {project_id}")
                        return True
                    else:
                        self._logger.warning(f"Project not found for statistics update: {project_id}")
                        return False

        except Exception as e:
            self._logger.error(f"Failed to update project statistics {project_id}: {e}")
            raise

    def _row_to_project(self, row: sqlite3.Row) -> Project:
        """
        Convert database row to Project entity.

        Args:
            row: Database row

        Returns:
            Project entity
        """
        try:
            # Parse JSON fields
            settings_data = json.loads(row["settings"]) if row["settings"] else {}
            metadata_data = json.loads(row["metadata"]) if row["metadata"] else {}

            # Create project from row data
            project_data = {
                "id": row["id"],
                "name": row["name"],
                "description": row["description"] or "",
                "project_type": row["project_type"],
                "status": row["status"],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
                "settings": settings_data,
                "metadata": metadata_data,
                "project_directory": row["project_directory"],
                "data_directory": row["data_directory"],
                "output_directory": row["output_directory"],
                "document_count": row["document_count"],
                "model_count": row["model_count"],
                "training_session_count": row["training_session_count"],
                "total_size_bytes": row["total_size_bytes"]
            }

            return Project.from_dict(project_data)

        except Exception as e:
            self._logger.error(f"Failed to convert row to project: {e}")
            raise

    def close(self):
        """Close database connections and cleanup resources."""
        try:
            if hasattr(self, '_connection_manager'):
                self._connection_manager.close()
            self._logger.debug("Project DAO database closed")
        except Exception as e:
            self._logger.error(f"Error closing project DAO database: {e}")

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
