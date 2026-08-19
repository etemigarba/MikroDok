"""
MikroDok Project DAO Database Package
Provides data access operations for project entities including CRUD operations and query optimization.
"""

# Import project DAO database components
try:
    from .project_dao_db import ProjectDAODB
except ImportError:
    pass

__all__ = [
    'ProjectDAODB'
]
