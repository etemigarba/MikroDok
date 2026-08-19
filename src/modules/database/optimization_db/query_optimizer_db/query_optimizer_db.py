"""
Module: query_optimizer_db
Description: Analyzes and optimizes slow queries with execution plan caching
Phase: 4
Location: /src/modules/database/optimization_db/query_optimizer_db/
"""

# Standard library imports
import sqlite3
import threading
import json
import time
import uuid
import hashlib
import re
from dataclasses import dataclass, asdict
from datetime import datetime, timezone, timedelta
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any, Union, Set

# Local imports
from src.modules.logic.logging_infrastructure_lg.log_manager_lg.log_manager_lg import get_logger


class QueryType(Enum):
    """Types of SQL queries."""
    SELECT = "select"
    INSERT = "insert"
    UPDATE = "update"
    DELETE = "delete"
    CREATE = "create"
    DROP = "drop"
    ALTER = "alter"
    UNKNOWN = "unknown"


class OptimizationLevel(Enum):
    """Query optimization levels."""
    NONE = "none"
    BASIC = "basic"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"
    AGGRESSIVE = "aggressive"


class QueryComplexity(Enum):
    """Query complexity levels."""
    SIMPLE = "simple"        # Single table, basic conditions
    MODERATE = "moderate"    # Multiple tables, joins
    COMPLEX = "complex"      # Subqueries, complex joins
    VERY_COMPLEX = "very_complex"  # Multiple subqueries, CTEs


@dataclass
class QueryInfo:
    """Information about a database query."""
    query_id: str
    query_hash: str
    query_text: str
    query_type: QueryType
    complexity: QueryComplexity
    table_names: List[str]
    execution_count: int
    total_execution_time_ms: float
    avg_execution_time_ms: float
    min_execution_time_ms: float
    max_execution_time_ms: float
    last_executed: datetime
    first_seen: datetime
    is_slow: bool
    slow_threshold_ms: float
    metadata: Dict[str, Any]


@dataclass
class ExecutionPlan:
    """Database query execution plan."""
    plan_id: str
    query_id: str
    plan_hash: str
    plan_json: str
    cost_estimate: float
    rows_estimate: int
    uses_index: bool
    index_names: List[str]
    scan_operations: int
    join_operations: int
    sort_operations: int
    temp_usage: bool
    created_at: datetime
    last_used: datetime
    usage_count: int
    avg_actual_time_ms: float


@dataclass
class OptimizationSuggestion:
    """Query optimization suggestion."""
    suggestion_id: str
    query_id: str
    suggestion_type: str
    priority: int
    description: str
    recommended_action: str
    estimated_improvement: str
    implementation_effort: str
    sql_example: Optional[str]
    index_suggestions: List[str]
    created_at: datetime
    applied: bool
    applied_at: Optional[datetime]
    effectiveness_score: Optional[float]


class QueryOptimizerDB:
    """
    Database query optimizer with execution plan caching and performance analysis.
    
    Analyzes query performance, caches execution plans, and provides optimization
    suggestions to improve database performance. Monitors slow queries and provides
    actionable recommendations for index creation, query rewriting, and schema optimization.
    """
    
    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize the query optimizer database.
        
        Args:
            db_path: Path to the database file
        """
        if db_path is None:
            # Default to optimization data directory
            data_dir = Path.home() / ".mikrodok" / "data" / "optimization"
            data_dir.mkdir(parents=True, exist_ok=True)
            db_path = str(data_dir / "query_optimizer.db")
        
        self._db_path = db_path
        self._lock = threading.RLock()
        self._logger = get_logger(__name__)
        
        # Configuration settings
        self._slow_query_threshold_ms = 1000.0  # Queries > 1s are considered slow
        self._plan_cache_size = 10000  # Maximum cached execution plans
        self._analysis_window_hours = 24  # Analyze queries from last 24 hours
        self._min_execution_count = 5  # Minimum executions before optimization
        
        # Runtime state
        self._query_cache: Dict[str, QueryInfo] = {}
        self._plan_cache: Dict[str, ExecutionPlan] = {}
        
        self._initialize_database()
    
    def _initialize_database(self) -> None:
        """Initialize the database schema."""
        try:
            with self._lock:
                conn = sqlite3.connect(self._db_path)
                cursor = conn.cursor()
                
                # Enable WAL mode and optimize settings
                cursor.execute("PRAGMA journal_mode=WAL")
                cursor.execute("PRAGMA synchronous=NORMAL")
                cursor.execute("PRAGMA cache_size=10000")
                cursor.execute("PRAGMA temp_store=MEMORY")
                cursor.execute("PRAGMA foreign_keys=ON")
                
                # Create queries table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS queries (
                        query_id TEXT PRIMARY KEY,
                        query_hash TEXT NOT NULL UNIQUE,
                        query_text TEXT NOT NULL,
                        query_type TEXT NOT NULL,
                        complexity TEXT NOT NULL,
                        table_names_json TEXT NOT NULL,
                        execution_count INTEGER DEFAULT 0,
                        total_execution_time_ms REAL DEFAULT 0.0,
                        avg_execution_time_ms REAL DEFAULT 0.0,
                        min_execution_time_ms REAL DEFAULT 0.0,
                        max_execution_time_ms REAL DEFAULT 0.0,
                        last_executed TIMESTAMP,
                        first_seen TIMESTAMP NOT NULL,
                        is_slow BOOLEAN DEFAULT FALSE,
                        slow_threshold_ms REAL DEFAULT 1000.0,
                        metadata_json TEXT
                    )
                """)
                
                # Create execution plans table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS execution_plans (
                        plan_id TEXT PRIMARY KEY,
                        query_id TEXT NOT NULL,
                        plan_hash TEXT NOT NULL,
                        plan_json TEXT NOT NULL,
                        cost_estimate REAL DEFAULT 0.0,
                        rows_estimate INTEGER DEFAULT 0,
                        uses_index BOOLEAN DEFAULT FALSE,
                        index_names_json TEXT,
                        scan_operations INTEGER DEFAULT 0,
                        join_operations INTEGER DEFAULT 0,
                        sort_operations INTEGER DEFAULT 0,
                        temp_usage BOOLEAN DEFAULT FALSE,
                        created_at TIMESTAMP NOT NULL,
                        last_used TIMESTAMP NOT NULL,
                        usage_count INTEGER DEFAULT 1,
                        avg_actual_time_ms REAL DEFAULT 0.0,
                        FOREIGN KEY (query_id) REFERENCES queries (query_id)
                    )
                """)
                
                # Create optimization suggestions table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS optimization_suggestions (
                        suggestion_id TEXT PRIMARY KEY,
                        query_id TEXT NOT NULL,
                        suggestion_type TEXT NOT NULL,
                        priority INTEGER DEFAULT 5,
                        description TEXT NOT NULL,
                        recommended_action TEXT NOT NULL,
                        estimated_improvement TEXT,
                        implementation_effort TEXT,
                        sql_example TEXT,
                        index_suggestions_json TEXT,
                        created_at TIMESTAMP NOT NULL,
                        applied BOOLEAN DEFAULT FALSE,
                        applied_at TIMESTAMP,
                        effectiveness_score REAL,
                        FOREIGN KEY (query_id) REFERENCES queries (query_id)
                    )
                """)
                
                # Create performance indexes
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_queries_hash ON queries (query_hash)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_queries_slow ON queries (is_slow, avg_execution_time_ms)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_queries_executed ON queries (last_executed)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_plans_query_hash ON execution_plans (query_id, plan_hash)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_plans_usage ON execution_plans (usage_count, last_used)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_suggestions_query_priority ON optimization_suggestions (query_id, priority)")
                
                conn.commit()
                conn.close()
                
                self._logger.info("Query optimizer database initialized successfully")
                
        except Exception as e:
            self._logger.error(f"Failed to initialize query optimizer database: {e}")
            raise

    def record_query_execution(self, query_text: str, execution_time_ms: float,
                              execution_plan: Optional[str] = None,
                              metadata: Optional[Dict[str, Any]] = None) -> str:
        """
        Record a query execution for analysis.

        Args:
            query_text: SQL query text
            execution_time_ms: Execution time in milliseconds
            execution_plan: Optional execution plan JSON
            metadata: Additional metadata

        Returns:
            Query ID
        """
        # Normalize and hash the query
        normalized_query = self._normalize_query(query_text)
        query_hash = self._hash_query(normalized_query)

        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                # Check if query already exists
                cursor.execute("SELECT query_id FROM queries WHERE query_hash = ?", (query_hash,))
                existing_row = cursor.fetchone()

                if existing_row:
                    query_id = existing_row[0]
                    # Update existing query statistics
                    self._update_query_statistics(cursor, query_id, execution_time_ms)
                else:
                    # Create new query record
                    query_id = str(uuid.uuid4())
                    query_info = self._analyze_query(normalized_query)

                    cursor.execute("""
                        INSERT INTO queries (
                            query_id, query_hash, query_text, query_type, complexity,
                            table_names_json, execution_count, total_execution_time_ms,
                            avg_execution_time_ms, min_execution_time_ms, max_execution_time_ms,
                            last_executed, first_seen, is_slow, slow_threshold_ms, metadata_json
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        query_id, query_hash, normalized_query, query_info['query_type'].value,
                        query_info['complexity'].value, json.dumps(query_info['table_names']),
                        1, execution_time_ms, execution_time_ms, execution_time_ms,
                        execution_time_ms, datetime.now(timezone.utc), datetime.now(timezone.utc),
                        execution_time_ms > self._slow_query_threshold_ms,
                        self._slow_query_threshold_ms, json.dumps(metadata) if metadata else None
                    ))

                # Record execution plan if provided
                if execution_plan:
                    self._record_execution_plan(cursor, query_id, execution_plan, execution_time_ms)

                conn.commit()
                self._logger.debug(f"Recorded query execution: {query_id}")
                return query_id

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to record query execution: {e}")
                raise
            finally:
                conn.close()

    def _normalize_query(self, query_text: str) -> str:
        """
        Normalize query text for consistent analysis.

        Args:
            query_text: Raw SQL query text

        Returns:
            Normalized query text
        """
        # Remove extra whitespace and normalize case
        normalized = re.sub(r'\s+', ' ', query_text.strip())

        # Replace parameter placeholders with generic markers
        normalized = re.sub(r"'[^']*'", "'?'", normalized)  # String literals
        normalized = re.sub(r'\b\d+\b', '?', normalized)    # Numeric literals

        # Normalize keywords to uppercase
        keywords = ['SELECT', 'FROM', 'WHERE', 'JOIN', 'INNER', 'LEFT', 'RIGHT', 'OUTER',
                   'GROUP', 'BY', 'ORDER', 'HAVING', 'LIMIT', 'OFFSET', 'INSERT', 'UPDATE',
                   'DELETE', 'CREATE', 'DROP', 'ALTER', 'INDEX', 'TABLE', 'VIEW']

        for keyword in keywords:
            pattern = r'\b' + keyword.lower() + r'\b'
            normalized = re.sub(pattern, keyword, normalized, flags=re.IGNORECASE)

        return normalized

    def _hash_query(self, query_text: str) -> str:
        """
        Generate a hash for the query text.

        Args:
            query_text: Normalized query text

        Returns:
            Query hash
        """
        return hashlib.sha256(query_text.encode('utf-8')).hexdigest()

    def _analyze_query(self, query_text: str) -> Dict[str, Any]:
        """
        Analyze query to extract metadata.

        Args:
            query_text: Normalized query text

        Returns:
            Dictionary with query analysis results
        """
        # Determine query type
        query_type = QueryType.UNKNOWN
        query_upper = query_text.upper().strip()

        if query_upper.startswith('SELECT'):
            query_type = QueryType.SELECT
        elif query_upper.startswith('INSERT'):
            query_type = QueryType.INSERT
        elif query_upper.startswith('UPDATE'):
            query_type = QueryType.UPDATE
        elif query_upper.startswith('DELETE'):
            query_type = QueryType.DELETE
        elif query_upper.startswith('CREATE'):
            query_type = QueryType.CREATE
        elif query_upper.startswith('DROP'):
            query_type = QueryType.DROP
        elif query_upper.startswith('ALTER'):
            query_type = QueryType.ALTER

        # Extract table names
        table_names = self._extract_table_names(query_text)

        # Determine complexity
        complexity = self._determine_complexity(query_text, table_names)

        return {
            'query_type': query_type,
            'table_names': table_names,
            'complexity': complexity
        }

    def _extract_table_names(self, query_text: str) -> List[str]:
        """
        Extract table names from query text.

        Args:
            query_text: SQL query text

        Returns:
            List of table names
        """
        table_names = []

        # Simple regex patterns for table extraction
        # This is a basic implementation - could be enhanced with proper SQL parsing

        # FROM clause
        from_pattern = r'FROM\s+(\w+)'
        from_matches = re.findall(from_pattern, query_text, re.IGNORECASE)
        table_names.extend(from_matches)

        # JOIN clauses
        join_pattern = r'JOIN\s+(\w+)'
        join_matches = re.findall(join_pattern, query_text, re.IGNORECASE)
        table_names.extend(join_matches)

        # INSERT INTO
        insert_pattern = r'INSERT\s+INTO\s+(\w+)'
        insert_matches = re.findall(insert_pattern, query_text, re.IGNORECASE)
        table_names.extend(insert_matches)

        # UPDATE
        update_pattern = r'UPDATE\s+(\w+)'
        update_matches = re.findall(update_pattern, query_text, re.IGNORECASE)
        table_names.extend(update_matches)

        # DELETE FROM
        delete_pattern = r'DELETE\s+FROM\s+(\w+)'
        delete_matches = re.findall(delete_pattern, query_text, re.IGNORECASE)
        table_names.extend(delete_matches)

        # Remove duplicates and return
        return list(set(table_names))

    def _determine_complexity(self, query_text: str, table_names: List[str]) -> QueryComplexity:
        """
        Determine query complexity based on structure.

        Args:
            query_text: SQL query text
            table_names: List of table names in query

        Returns:
            QueryComplexity enum
        """
        query_upper = query_text.upper()

        # Count complexity indicators
        subquery_count = query_upper.count('SELECT') - 1  # Subtract main SELECT
        join_count = query_upper.count('JOIN')
        cte_count = query_upper.count('WITH')
        union_count = query_upper.count('UNION')

        # Determine complexity
        if (subquery_count >= 2 or cte_count > 0 or
            (subquery_count >= 1 and join_count >= 2) or
            union_count > 0):
            return QueryComplexity.VERY_COMPLEX
        elif subquery_count >= 1 or join_count >= 2 or len(table_names) >= 3:
            return QueryComplexity.COMPLEX
        elif join_count >= 1 or len(table_names) >= 2:
            return QueryComplexity.MODERATE
        else:
            return QueryComplexity.SIMPLE

    def _update_query_statistics(self, cursor: sqlite3.Cursor, query_id: str, execution_time_ms: float) -> None:
        """
        Update statistics for an existing query.

        Args:
            cursor: Database cursor
            query_id: Query identifier
            execution_time_ms: Execution time in milliseconds
        """
        # Get current statistics
        cursor.execute("""
            SELECT execution_count, total_execution_time_ms, min_execution_time_ms, max_execution_time_ms
            FROM queries WHERE query_id = ?
        """, (query_id,))

        row = cursor.fetchone()
        if not row:
            return

        execution_count, total_time, min_time, max_time = row

        # Update statistics
        new_count = execution_count + 1
        new_total = total_time + execution_time_ms
        new_avg = new_total / new_count
        new_min = min(min_time, execution_time_ms)
        new_max = max(max_time, execution_time_ms)
        is_slow = new_avg > self._slow_query_threshold_ms

        cursor.execute("""
            UPDATE queries SET
                execution_count = ?,
                total_execution_time_ms = ?,
                avg_execution_time_ms = ?,
                min_execution_time_ms = ?,
                max_execution_time_ms = ?,
                last_executed = ?,
                is_slow = ?
            WHERE query_id = ?
        """, (
            new_count, new_total, new_avg, new_min, new_max,
            datetime.now(timezone.utc), is_slow, query_id
        ))

    def _record_execution_plan(self, cursor: sqlite3.Cursor, query_id: str,
                              execution_plan: str, execution_time_ms: float) -> str:
        """
        Record an execution plan for a query.

        Args:
            cursor: Database cursor
            query_id: Query identifier
            execution_plan: Execution plan JSON
            execution_time_ms: Actual execution time

        Returns:
            Plan ID
        """
        plan_hash = hashlib.sha256(execution_plan.encode('utf-8')).hexdigest()

        # Check if plan already exists
        cursor.execute("""
            SELECT plan_id, usage_count, avg_actual_time_ms
            FROM execution_plans WHERE query_id = ? AND plan_hash = ?
        """, (query_id, plan_hash))

        existing_row = cursor.fetchone()

        if existing_row:
            # Update existing plan
            plan_id, usage_count, avg_time = existing_row
            new_count = usage_count + 1
            new_avg = ((avg_time * usage_count) + execution_time_ms) / new_count

            cursor.execute("""
                UPDATE execution_plans SET
                    usage_count = ?,
                    avg_actual_time_ms = ?,
                    last_used = ?
                WHERE plan_id = ?
            """, (new_count, new_avg, datetime.now(timezone.utc), plan_id))

            return plan_id
        else:
            # Create new plan
            plan_id = str(uuid.uuid4())
            plan_analysis = self._analyze_execution_plan(execution_plan)

            cursor.execute("""
                INSERT INTO execution_plans (
                    plan_id, query_id, plan_hash, plan_json, cost_estimate,
                    rows_estimate, uses_index, index_names_json, scan_operations,
                    join_operations, sort_operations, temp_usage, created_at,
                    last_used, usage_count, avg_actual_time_ms
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                plan_id, query_id, plan_hash, execution_plan,
                plan_analysis['cost_estimate'], plan_analysis['rows_estimate'],
                plan_analysis['uses_index'], json.dumps(plan_analysis['index_names']),
                plan_analysis['scan_operations'], plan_analysis['join_operations'],
                plan_analysis['sort_operations'], plan_analysis['temp_usage'],
                datetime.now(timezone.utc), datetime.now(timezone.utc),
                1, execution_time_ms
            ))

            return plan_id

    def _analyze_execution_plan(self, execution_plan: str) -> Dict[str, Any]:
        """
        Analyze execution plan to extract performance indicators.

        Args:
            execution_plan: Execution plan JSON string

        Returns:
            Dictionary with plan analysis results
        """
        try:
            plan_data = json.loads(execution_plan)

            # Initialize analysis results
            analysis = {
                'cost_estimate': 0.0,
                'rows_estimate': 0,
                'uses_index': False,
                'index_names': [],
                'scan_operations': 0,
                'join_operations': 0,
                'sort_operations': 0,
                'temp_usage': False
            }

            # Recursively analyze plan nodes
            self._analyze_plan_node(plan_data, analysis)

            return analysis

        except Exception as e:
            self._logger.error(f"Failed to analyze execution plan: {e}")
            return {
                'cost_estimate': 0.0,
                'rows_estimate': 0,
                'uses_index': False,
                'index_names': [],
                'scan_operations': 0,
                'join_operations': 0,
                'sort_operations': 0,
                'temp_usage': False
            }

    def _analyze_plan_node(self, node: Dict[str, Any], analysis: Dict[str, Any]) -> None:
        """
        Recursively analyze a plan node.

        Args:
            node: Plan node data
            analysis: Analysis results to update
        """
        if not isinstance(node, dict):
            return

        # Extract operation type
        operation = node.get('operation', '').lower()

        # Update counters based on operation
        if 'scan' in operation:
            analysis['scan_operations'] += 1
        elif 'join' in operation:
            analysis['join_operations'] += 1
        elif 'sort' in operation:
            analysis['sort_operations'] += 1

        # Check for index usage
        if 'index' in operation or node.get('uses_index', False):
            analysis['uses_index'] = True
            index_name = node.get('index_name')
            if index_name and index_name not in analysis['index_names']:
                analysis['index_names'].append(index_name)

        # Check for temporary table usage
        if 'temp' in operation or node.get('temp_usage', False):
            analysis['temp_usage'] = True

        # Update estimates
        if 'cost' in node:
            analysis['cost_estimate'] += float(node['cost'])
        if 'rows' in node:
            analysis['rows_estimate'] += int(node['rows'])

        # Recursively analyze child nodes
        for key, value in node.items():
            if isinstance(value, dict):
                self._analyze_plan_node(value, analysis)
            elif isinstance(value, list):
                for item in value:
                    if isinstance(item, dict):
                        self._analyze_plan_node(item, analysis)

    def analyze_slow_queries(self, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Analyze slow queries and generate optimization suggestions.

        Args:
            limit: Maximum number of queries to analyze

        Returns:
            List of slow query analysis results
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                # Get slow queries
                cursor.execute("""
                    SELECT query_id, query_text, query_type, complexity, table_names_json,
                           execution_count, avg_execution_time_ms, max_execution_time_ms
                    FROM queries
                    WHERE is_slow = TRUE AND execution_count >= ?
                    ORDER BY avg_execution_time_ms DESC, execution_count DESC
                    LIMIT ?
                """, (self._min_execution_count, limit))

                rows = cursor.fetchall()
                results = []

                for row in rows:
                    query_id, query_text, query_type, complexity, table_names_json, \
                    execution_count, avg_time, max_time = row

                    table_names = json.loads(table_names_json)

                    # Generate optimization suggestions
                    suggestions = self._generate_optimization_suggestions(
                        query_id, query_text, query_type, complexity, table_names,
                        avg_time, execution_count
                    )

                    results.append({
                        'query_id': query_id,
                        'query_text': query_text,
                        'query_type': query_type,
                        'complexity': complexity,
                        'table_names': table_names,
                        'execution_count': execution_count,
                        'avg_execution_time_ms': avg_time,
                        'max_execution_time_ms': max_time,
                        'optimization_suggestions': suggestions
                    })

                return results

            except Exception as e:
                self._logger.error(f"Failed to analyze slow queries: {e}")
                return []
            finally:
                conn.close()

    def _generate_optimization_suggestions(self, query_id: str, query_text: str,
                                         query_type: str, complexity: str,
                                         table_names: List[str], avg_time_ms: float,
                                         execution_count: int) -> List[Dict[str, Any]]:
        """
        Generate optimization suggestions for a query.

        Args:
            query_id: Query identifier
            query_text: SQL query text
            query_type: Type of query
            complexity: Query complexity level
            table_names: Tables involved in query
            avg_time_ms: Average execution time
            execution_count: Number of executions

        Returns:
            List of optimization suggestions
        """
        suggestions = []

        # Index suggestions for SELECT queries
        if query_type == QueryType.SELECT.value and table_names:
            # Suggest indexes for WHERE clauses
            where_columns = self._extract_where_columns(query_text)
            for table_name in table_names:
                table_columns = [col for col in where_columns if table_name in col or '.' not in col]
                if table_columns:
                    suggestions.append({
                        'type': 'create_index',
                        'priority': 8 if avg_time_ms > 5000 else 6,
                        'description': f'Create index on {table_name} for WHERE clause optimization',
                        'recommended_action': f'CREATE INDEX idx_{table_name}_where ON {table_name} ({", ".join(table_columns[:3])})',
                        'estimated_improvement': f'Could reduce query time by 30-70%',
                        'implementation_effort': 'Low'
                    })

        # JOIN optimization suggestions
        if 'JOIN' in query_text.upper() and len(table_names) > 1:
            suggestions.append({
                'type': 'optimize_joins',
                'priority': 7,
                'description': 'Optimize JOIN operations with proper indexing',
                'recommended_action': 'Ensure foreign key columns have indexes',
                'estimated_improvement': 'Could reduce query time by 20-50%',
                'implementation_effort': 'Medium'
            })

        # Query rewriting suggestions for complex queries
        if complexity in [QueryComplexity.COMPLEX.value, QueryComplexity.VERY_COMPLEX.value]:
            suggestions.append({
                'type': 'rewrite_query',
                'priority': 5,
                'description': 'Consider breaking down complex query into simpler parts',
                'recommended_action': 'Use CTEs or temporary tables to simplify logic',
                'estimated_improvement': 'Could improve readability and performance',
                'implementation_effort': 'High'
            })

        # Caching suggestions for frequently executed queries
        if execution_count > 100:
            suggestions.append({
                'type': 'implement_caching',
                'priority': 4,
                'description': 'Implement result caching for frequently executed query',
                'recommended_action': 'Cache query results with appropriate TTL',
                'estimated_improvement': 'Could eliminate query execution overhead',
                'implementation_effort': 'Medium'
            })

        return suggestions

    def _extract_where_columns(self, query_text: str) -> List[str]:
        """
        Extract column names from WHERE clauses.

        Args:
            query_text: SQL query text

        Returns:
            List of column names
        """
        columns = []

        # Simple regex to find WHERE clause columns
        # This is a basic implementation - could be enhanced with proper SQL parsing
        where_pattern = r'WHERE\s+.*?(?:GROUP|ORDER|LIMIT|$)'
        where_match = re.search(where_pattern, query_text, re.IGNORECASE | re.DOTALL)

        if where_match:
            where_clause = where_match.group(0)
            # Extract column references (simplified)
            column_pattern = r'\b(\w+(?:\.\w+)?)\s*[=<>!]'
            column_matches = re.findall(column_pattern, where_clause, re.IGNORECASE)
            columns.extend(column_matches)

        return list(set(columns))

    def get_query_performance_report(self, hours: int = 24) -> Dict[str, Any]:
        """
        Generate a comprehensive query performance report.

        Args:
            hours: Number of hours to analyze

        Returns:
            Performance report dictionary
        """
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours)

        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                # Get overall statistics
                cursor.execute("""
                    SELECT COUNT(*) as total_queries,
                           COUNT(CASE WHEN is_slow THEN 1 END) as slow_queries,
                           AVG(avg_execution_time_ms) as overall_avg_time,
                           MAX(max_execution_time_ms) as slowest_query_time,
                           SUM(execution_count) as total_executions
                    FROM queries
                    WHERE last_executed >= ?
                """, (cutoff_time,))

                stats_row = cursor.fetchone()

                # Get top slow queries
                cursor.execute("""
                    SELECT query_id, query_text, avg_execution_time_ms, execution_count
                    FROM queries
                    WHERE is_slow = TRUE AND last_executed >= ?
                    ORDER BY avg_execution_time_ms DESC
                    LIMIT 10
                """, (cutoff_time,))

                slow_queries = cursor.fetchall()

                # Get query type distribution
                cursor.execute("""
                    SELECT query_type, COUNT(*) as count, AVG(avg_execution_time_ms) as avg_time
                    FROM queries
                    WHERE last_executed >= ?
                    GROUP BY query_type
                    ORDER BY count DESC
                """, (cutoff_time,))

                type_distribution = cursor.fetchall()

                return {
                    'analysis_period_hours': hours,
                    'total_unique_queries': stats_row[0] if stats_row else 0,
                    'slow_queries_count': stats_row[1] if stats_row else 0,
                    'overall_avg_time_ms': stats_row[2] if stats_row else 0.0,
                    'slowest_query_time_ms': stats_row[3] if stats_row else 0.0,
                    'total_executions': stats_row[4] if stats_row else 0,
                    'slow_query_percentage': (stats_row[1] / stats_row[0] * 100) if stats_row and stats_row[0] > 0 else 0.0,
                    'top_slow_queries': [
                        {
                            'query_id': row[0],
                            'query_text': row[1][:200] + '...' if len(row[1]) > 200 else row[1],
                            'avg_time_ms': row[2],
                            'execution_count': row[3]
                        }
                        for row in slow_queries
                    ],
                    'query_type_distribution': [
                        {
                            'query_type': row[0],
                            'count': row[1],
                            'avg_time_ms': row[2]
                        }
                        for row in type_distribution
                    ]
                }

            except Exception as e:
                self._logger.error(f"Failed to generate performance report: {e}")
                return {}
            finally:
                conn.close()

    def cleanup_old_data(self, retention_days: int = 30) -> int:
        """
        Clean up old query data and execution plans.

        Args:
            retention_days: Number of days to retain data

        Returns:
            Number of records deleted
        """
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=retention_days)

        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()

                # Delete old queries with low execution count
                cursor.execute("""
                    DELETE FROM queries
                    WHERE last_executed < ? AND execution_count < ?
                """, (cutoff_date, self._min_execution_count))

                deleted_queries = cursor.rowcount

                # Delete orphaned execution plans
                cursor.execute("""
                    DELETE FROM execution_plans
                    WHERE query_id NOT IN (SELECT query_id FROM queries)
                """, )

                deleted_plans = cursor.rowcount

                # Delete old optimization suggestions
                cursor.execute("""
                    DELETE FROM optimization_suggestions
                    WHERE created_at < ? AND applied = FALSE
                """, (cutoff_date,))

                deleted_suggestions = cursor.rowcount

                total_deleted = deleted_queries + deleted_plans + deleted_suggestions

                conn.commit()
                self._logger.info(f"Cleaned up {total_deleted} old query optimizer records")
                return total_deleted

            except Exception as e:
                conn.rollback()
                self._logger.error(f"Failed to cleanup old data: {e}")
                return 0
            finally:
                conn.close()
