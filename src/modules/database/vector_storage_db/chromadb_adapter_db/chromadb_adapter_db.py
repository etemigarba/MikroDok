"""
Module: chromadb_adapter_db
Description: ChromaDB integration layer for vector storage and retrieval
Phase: 4
Location: /src/modules/database/vector_storage_db/chromadb_adapter_db/
"""

# Standard library imports
import json
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union
import numpy as np

# Third-party imports
try:
    import chromadb
    from chromadb.config import Settings
    from chromadb.api.types import Collection, Documents, EmbeddingFunction, Embeddings, IDs, Metadatas
    CHROMADB_AVAILABLE = True
except ImportError:
    CHROMADB_AVAILABLE = False
    # Define placeholder types when chromadb is not available
    Collection = Any
    Documents = Any
    EmbeddingFunction = Any
    Embeddings = Any
    IDs = Any
    Metadatas = Any

# Local imports
from src.modules.logic.logging_infrastructure_lg.log_manager_lg.log_manager_lg import get_logger


class ChromaDBAdapterDB:
    """
    ChromaDB integration layer for vector storage and retrieval.
    
    Provides a high-level interface for ChromaDB operations including
    collection management, vector storage, similarity search, and metadata handling.
    Designed for offline operation with persistent storage.
    """
    
    def __init__(self, persist_directory: Optional[str] = None, 
                 collection_name: str = "document_embeddings"):
        """
        Initialize the ChromaDB adapter.
        
        Args:
            persist_directory: Directory for persistent storage
            collection_name: Default collection name
        """
        if not CHROMADB_AVAILABLE:
            raise ImportError("ChromaDB is not available. Please install chromadb package.")
        
        if persist_directory is None:
            # Default to vector storage data directory
            data_dir = Path.home() / ".mikrodok" / "data" / "vectors"
            data_dir.mkdir(parents=True, exist_ok=True)
            persist_directory = str(data_dir)
        
        self._persist_directory = persist_directory
        self._default_collection_name = collection_name
        self._lock = threading.RLock()
        self._logger = get_logger(__name__)
        
        # ChromaDB client and collections cache
        self._client: Optional[chromadb.PersistentClient] = None
        self._collections: Dict[str, Collection] = {}
        
        # Connection settings
        self._settings = Settings(
            persist_directory=persist_directory,
            anonymized_telemetry=False,
            allow_reset=True
        )
        
        self._initialize_client()
    
    def _initialize_client(self) -> None:
        """Initialize ChromaDB client with persistent storage."""
        try:
            with self._lock:
                self._client = chromadb.PersistentClient(
                    path=self._persist_directory,
                    settings=self._settings
                )
                
                # Create default collection if it doesn't exist
                self._get_or_create_collection(self._default_collection_name)
                
                self._logger.info(f"ChromaDB client initialized with persist directory: {self._persist_directory}")
                
        except Exception as e:
            self._logger.error(f"Failed to initialize ChromaDB client: {e}")
            raise
    
    def _get_or_create_collection(self, collection_name: str, 
                                  metadata: Optional[Dict[str, Any]] = None,
                                  embedding_function: Optional[EmbeddingFunction] = None) -> Collection:
        """
        Get or create a ChromaDB collection.
        
        Args:
            collection_name: Name of the collection
            metadata: Collection metadata
            embedding_function: Custom embedding function
            
        Returns:
            ChromaDB Collection object
        """
        try:
            with self._lock:
                if collection_name in self._collections:
                    return self._collections[collection_name]
                
                if not self._client:
                    raise RuntimeError("ChromaDB client not initialized")
                
                # Try to get existing collection first
                try:
                    collection = self._client.get_collection(
                        name=collection_name,
                        embedding_function=embedding_function
                    )
                    self._logger.info(f"Retrieved existing collection: {collection_name}")
                    
                except Exception:
                    # Collection doesn't exist, create it
                    collection = self._client.create_collection(
                        name=collection_name,
                        metadata=metadata or {},
                        embedding_function=embedding_function
                    )
                    self._logger.info(f"Created new collection: {collection_name}")
                
                self._collections[collection_name] = collection
                return collection
                
        except Exception as e:
            self._logger.error(f"Failed to get or create collection {collection_name}: {e}")
            raise
    
    def add_vectors(self, vectors: Union[List[List[float]], np.ndarray], 
                   vector_ids: List[str], documents: Optional[List[str]] = None,
                   metadatas: Optional[List[Dict[str, Any]]] = None,
                   collection_name: Optional[str] = None) -> bool:
        """
        Add vectors to a collection.
        
        Args:
            vectors: List of vectors or numpy array
            vector_ids: Unique identifiers for vectors
            documents: Optional document texts
            metadatas: Optional metadata for each vector
            collection_name: Target collection name
            
        Returns:
            True if successful, False otherwise
        """
        try:
            with self._lock:
                collection_name = collection_name or self._default_collection_name
                collection = self._get_or_create_collection(collection_name)
                
                # Convert numpy array to list if needed
                if isinstance(vectors, np.ndarray):
                    vectors = vectors.tolist()
                
                # Prepare data for ChromaDB
                add_kwargs = {
                    'ids': vector_ids,
                    'embeddings': vectors
                }
                
                if documents:
                    add_kwargs['documents'] = documents
                
                if metadatas:
                    add_kwargs['metadatas'] = metadatas
                
                collection.add(**add_kwargs)
                
                self._logger.info(f"Added {len(vector_ids)} vectors to collection {collection_name}")
                return True
                
        except Exception as e:
            self._logger.error(f"Failed to add vectors to collection {collection_name}: {e}")
            return False
    
    def search_vectors(self, query_vectors: Union[List[List[float]], np.ndarray],
                      n_results: int = 10, collection_name: Optional[str] = None,
                      where: Optional[Dict[str, Any]] = None,
                      where_document: Optional[Dict[str, Any]] = None,
                      include: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Search for similar vectors in a collection.
        
        Args:
            query_vectors: Query vectors for similarity search
            n_results: Number of results to return
            collection_name: Target collection name
            where: Metadata filter conditions
            where_document: Document filter conditions
            include: Fields to include in results
            
        Returns:
            Search results dictionary
        """
        try:
            with self._lock:
                collection_name = collection_name or self._default_collection_name
                collection = self._get_or_create_collection(collection_name)
                
                # Convert numpy array to list if needed
                if isinstance(query_vectors, np.ndarray):
                    query_vectors = query_vectors.tolist()
                
                # Default include fields
                if include is None:
                    include = ['metadatas', 'documents', 'distances']
                
                results = collection.query(
                    query_embeddings=query_vectors,
                    n_results=n_results,
                    where=where,
                    where_document=where_document,
                    include=include
                )
                
                self._logger.info(f"Searched collection {collection_name} with {len(query_vectors)} queries")
                return results
                
        except Exception as e:
            self._logger.error(f"Failed to search vectors in collection {collection_name}: {e}")
            return {}
    
    def get_vectors(self, vector_ids: Optional[List[str]] = None,
                   collection_name: Optional[str] = None,
                   where: Optional[Dict[str, Any]] = None,
                   limit: Optional[int] = None,
                   offset: Optional[int] = None,
                   include: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Get vectors from a collection.
        
        Args:
            vector_ids: Specific vector IDs to retrieve
            collection_name: Target collection name
            where: Metadata filter conditions
            limit: Maximum number of results
            offset: Number of results to skip
            include: Fields to include in results
            
        Returns:
            Retrieved vectors dictionary
        """
        try:
            with self._lock:
                collection_name = collection_name or self._default_collection_name
                collection = self._get_or_create_collection(collection_name)
                
                # Default include fields
                if include is None:
                    include = ['metadatas', 'documents', 'embeddings']
                
                results = collection.get(
                    ids=vector_ids,
                    where=where,
                    limit=limit,
                    offset=offset,
                    include=include
                )
                
                self._logger.info(f"Retrieved vectors from collection {collection_name}")
                return results
                
        except Exception as e:
            self._logger.error(f"Failed to get vectors from collection {collection_name}: {e}")
            return {}

    def update_vectors(self, vector_ids: List[str],
                      vectors: Optional[Union[List[List[float]], np.ndarray]] = None,
                      documents: Optional[List[str]] = None,
                      metadatas: Optional[List[Dict[str, Any]]] = None,
                      collection_name: Optional[str] = None) -> bool:
        """
        Update existing vectors in a collection.

        Args:
            vector_ids: Vector IDs to update
            vectors: New vector values
            documents: New document texts
            metadatas: New metadata
            collection_name: Target collection name

        Returns:
            True if successful, False otherwise
        """
        try:
            with self._lock:
                collection_name = collection_name or self._default_collection_name
                collection = self._get_or_create_collection(collection_name)

                # Prepare update data
                update_kwargs = {'ids': vector_ids}

                if vectors is not None:
                    if isinstance(vectors, np.ndarray):
                        vectors = vectors.tolist()
                    update_kwargs['embeddings'] = vectors

                if documents is not None:
                    update_kwargs['documents'] = documents

                if metadatas is not None:
                    update_kwargs['metadatas'] = metadatas

                collection.update(**update_kwargs)

                self._logger.info(f"Updated {len(vector_ids)} vectors in collection {collection_name}")
                return True

        except Exception as e:
            self._logger.error(f"Failed to update vectors in collection {collection_name}: {e}")
            return False

    def delete_vectors(self, vector_ids: Optional[List[str]] = None,
                      where: Optional[Dict[str, Any]] = None,
                      collection_name: Optional[str] = None) -> bool:
        """
        Delete vectors from a collection.

        Args:
            vector_ids: Specific vector IDs to delete
            where: Metadata filter for deletion
            collection_name: Target collection name

        Returns:
            True if successful, False otherwise
        """
        try:
            with self._lock:
                collection_name = collection_name or self._default_collection_name
                collection = self._get_or_create_collection(collection_name)

                collection.delete(ids=vector_ids, where=where)

                count = len(vector_ids) if vector_ids else "filtered"
                self._logger.info(f"Deleted {count} vectors from collection {collection_name}")
                return True

        except Exception as e:
            self._logger.error(f"Failed to delete vectors from collection {collection_name}: {e}")
            return False

    def create_collection(self, collection_name: str,
                         metadata: Optional[Dict[str, Any]] = None,
                         embedding_function: Optional[EmbeddingFunction] = None) -> bool:
        """
        Create a new collection.

        Args:
            collection_name: Name of the new collection
            metadata: Collection metadata
            embedding_function: Custom embedding function

        Returns:
            True if successful, False otherwise
        """
        try:
            with self._lock:
                if not self._client:
                    raise RuntimeError("ChromaDB client not initialized")

                collection = self._client.create_collection(
                    name=collection_name,
                    metadata=metadata or {},
                    embedding_function=embedding_function
                )

                self._collections[collection_name] = collection
                self._logger.info(f"Created collection: {collection_name}")
                return True

        except Exception as e:
            self._logger.error(f"Failed to create collection {collection_name}: {e}")
            return False

    def delete_collection(self, collection_name: str) -> bool:
        """
        Delete a collection.

        Args:
            collection_name: Name of the collection to delete

        Returns:
            True if successful, False otherwise
        """
        try:
            with self._lock:
                if not self._client:
                    raise RuntimeError("ChromaDB client not initialized")

                self._client.delete_collection(name=collection_name)

                # Remove from cache
                if collection_name in self._collections:
                    del self._collections[collection_name]

                self._logger.info(f"Deleted collection: {collection_name}")
                return True

        except Exception as e:
            self._logger.error(f"Failed to delete collection {collection_name}: {e}")
            return False

    def list_collections(self) -> List[str]:
        """
        List all available collections.

        Returns:
            List of collection names
        """
        try:
            with self._lock:
                if not self._client:
                    raise RuntimeError("ChromaDB client not initialized")

                collections = self._client.list_collections()
                collection_names = [col.name for col in collections]

                self._logger.info(f"Listed {len(collection_names)} collections")
                return collection_names

        except Exception as e:
            self._logger.error(f"Failed to list collections: {e}")
            return []

    def get_collection_info(self, collection_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Get information about a collection.

        Args:
            collection_name: Target collection name

        Returns:
            Collection information dictionary
        """
        try:
            with self._lock:
                collection_name = collection_name or self._default_collection_name
                collection = self._get_or_create_collection(collection_name)

                # Get collection count and metadata
                count = collection.count()
                metadata = collection.metadata

                info = {
                    'name': collection_name,
                    'count': count,
                    'metadata': metadata,
                    'id': collection.id
                }

                self._logger.info(f"Retrieved info for collection {collection_name}")
                return info

        except Exception as e:
            self._logger.error(f"Failed to get collection info for {collection_name}: {e}")
            return {}

    def reset_database(self) -> bool:
        """
        Reset the entire database (delete all collections).

        Returns:
            True if successful, False otherwise
        """
        try:
            with self._lock:
                if not self._client:
                    raise RuntimeError("ChromaDB client not initialized")

                self._client.reset()
                self._collections.clear()

                self._logger.warning("Database reset - all collections deleted")
                return True

        except Exception as e:
            self._logger.error(f"Failed to reset database: {e}")
            return False

    def get_client_info(self) -> Dict[str, Any]:
        """
        Get ChromaDB client information.

        Returns:
            Client information dictionary
        """
        try:
            with self._lock:
                if not self._client:
                    return {'status': 'not_initialized'}

                info = {
                    'status': 'initialized',
                    'persist_directory': self._persist_directory,
                    'default_collection': self._default_collection_name,
                    'cached_collections': list(self._collections.keys()),
                    'settings': {
                        'persist_directory': self._settings.persist_directory,
                        'anonymized_telemetry': self._settings.anonymized_telemetry,
                        'allow_reset': self._settings.allow_reset
                    }
                }

                return info

        except Exception as e:
            self._logger.error(f"Failed to get client info: {e}")
            return {'status': 'error', 'error': str(e)}

    def close(self) -> None:
        """Close the ChromaDB client and clean up resources."""
        try:
            with self._lock:
                self._collections.clear()
                self._client = None
                self._logger.info("ChromaDB adapter closed")

        except Exception as e:
            self._logger.error(f"Error closing ChromaDB adapter: {e}")

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
