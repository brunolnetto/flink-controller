"""
Job specification change tracking for Flink Job Controller.

This module tracks changes to job specifications using deterministic hashing
and maintains persistent state for reconciliation decisions.
"""

import asyncio
import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

import aiosqlite
from pydantic import BaseModel, Field

from .reconciler import JobSpec


class ChangeRecord(BaseModel):
    """Record of a job specification change."""

    job_id: str = Field(..., description="Job identifier")
    spec_hash: str = Field(..., description="Hash of the job specification")
    previous_hash: Optional[str] = Field(None, description="Previous hash value")
    changed_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="When change was detected",
    )
    change_type: str = Field(
        ..., description="Type of change (created, updated, deleted)"
    )
    changed_fields: List[str] = Field(
        default_factory=list, description="List of fields that changed"
    )


class JobSpecTracker:
    """Tracks job specification changes with persistent state."""

    def __init__(self, state_file: str = "job_tracker.db"):
        """
        Initialize the job specification tracker.

        Args:
            state_file: SQLite database file for persistent state
        """
        self.state_file = Path(state_file)
        self._lock = asyncio.Lock()
        self._connection: Optional[aiosqlite.Connection] = None
        self._tracked_specs: Dict[str, str] = {}  # job_id -> spec_hash cache

    async def __aenter__(self):
        """Async context manager entry."""
        await self._initialize_db()
        await self._load_tracked_specs()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self._connection:
            await self._connection.close()
            self._connection = None

    async def _initialize_db(self):
        """Initialize the SQLite database."""
        self._connection = await aiosqlite.connect(self.state_file)

        # Create tables if they don't exist
        await self._connection.execute(
            """
            CREATE TABLE IF NOT EXISTS tracked_specs (
                job_id TEXT PRIMARY KEY,
                spec_hash TEXT NOT NULL,
                last_updated TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """
        )

        await self._connection.execute(
            """
            CREATE TABLE IF NOT EXISTS change_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id TEXT NOT NULL,
                spec_hash TEXT NOT NULL,
                previous_hash TEXT,
                changed_at TEXT NOT NULL,
                change_type TEXT NOT NULL,
                changed_fields TEXT,
                FOREIGN KEY (job_id) REFERENCES tracked_specs (job_id)
            )
        """
        )

        await self._connection.commit()

    async def _load_tracked_specs(self):
        """Load tracked specifications from database into cache."""
        async with self._lock:
            cursor = await self._connection.execute(
                "SELECT job_id, spec_hash FROM tracked_specs"
            )
            rows = await cursor.fetchall()

            self._tracked_specs = {row[0]: row[1] for row in rows}

    def calculate_spec_hash(self, spec: JobSpec) -> str:
        """
        Calculate deterministic hash of job specification.

        Args:
            spec: Job specification

        Returns:
            SHA-256 hash of the specification
        """
        # Create a normalized dictionary for hashing
        spec_dict = spec.dict()

        # Remove fields that shouldn't trigger changes
        exclude_fields = {"created_at", "updated_at"}
        normalized_dict = {
            k: v for k, v in spec_dict.items() if k not in exclude_fields
        }

        # Convert enum values to strings for JSON serialization
        if "job_type" in normalized_dict and hasattr(
            normalized_dict["job_type"], "value"
        ):
            normalized_dict["job_type"] = normalized_dict["job_type"].value

        # Sort for deterministic hashing
        spec_json = json.dumps(normalized_dict, sort_keys=True, separators=(",", ":"))

        return hashlib.sha256(spec_json.encode("utf-8")).hexdigest()

    async def has_changed(self, job_id: str, spec: JobSpec) -> bool:
        """
        Check if job specification has changed using deterministic hashing.

        Args:
            job_id: Job identifier
            spec: Current job specification

        Returns:
            True if specification has changed
        """
        current_hash = self.calculate_spec_hash(spec)

        async with self._lock:
            previous_hash = self._tracked_specs.get(job_id)
            return previous_hash != current_hash

    async def detect_changes(self, current_specs: List[JobSpec]) -> List[ChangeRecord]:
        """
        Detect changes between current specs and tracked specs.

        Args:
            current_specs: List of current job specifications

        Returns:
            List of change records
        """
        changes = []
        current_job_ids = set()

        for spec in current_specs:
            current_job_ids.add(spec.job_id)
            current_hash = self.calculate_spec_hash(spec)

            async with self._lock:
                previous_hash = self._tracked_specs.get(spec.job_id)

            if previous_hash is None:
                # New job
                changes.append(
                    ChangeRecord(
                        job_id=spec.job_id,
                        spec_hash=current_hash,
                        previous_hash=None,
                        change_type="created",
                    )
                )
            elif previous_hash != current_hash:
                # Updated job
                changed_fields = await self._identify_changed_fields(spec.job_id, spec)
                changes.append(
                    ChangeRecord(
                        job_id=spec.job_id,
                        spec_hash=current_hash,
                        previous_hash=previous_hash,
                        change_type="updated",
                        changed_fields=changed_fields,
                    )
                )

        # Check for deleted jobs
        async with self._lock:
            tracked_job_ids = set(self._tracked_specs.keys())

        deleted_job_ids = tracked_job_ids - current_job_ids
        for job_id in deleted_job_ids:
            async with self._lock:
                previous_hash = self._tracked_specs.get(job_id)

            changes.append(
                ChangeRecord(
                    job_id=job_id,
                    spec_hash="",
                    previous_hash=previous_hash,
                    change_type="deleted",
                )
            )

        return changes

    async def _identify_changed_fields(
        self, job_id: str, new_spec: JobSpec
    ) -> List[str]:
        """
        Identify which fields have changed in a job specification.

        Args:
            job_id: Job identifier
            new_spec: New job specification

        Returns:
            List of field names that changed
        """
        # For now, return empty list
        # In a full implementation, this would compare field by field
        return []

    async def update_tracker(self, job_id: str, spec: JobSpec) -> None:
        """
        Update tracker with new specification hash.

        Args:
            job_id: Job identifier
            spec: Job specification
        """
        spec_hash = self.calculate_spec_hash(spec)
        current_time = datetime.now(timezone.utc).isoformat()

        async with self._lock:
            # Update cache
            previous_hash = self._tracked_specs.get(job_id)
            self._tracked_specs[job_id] = spec_hash

            # Update database
            await self._connection.execute(
                """
                INSERT OR REPLACE INTO tracked_specs (job_id, spec_hash, last_updated, created_at)
                VALUES (?, ?, ?, COALESCE(
                    (SELECT created_at FROM tracked_specs WHERE job_id = ?),
                    ?
                ))
            """,
                (job_id, spec_hash, current_time, job_id, current_time),
            )

            await self._connection.commit()

    async def record_change(self, change: ChangeRecord) -> None:
        """
        Record a change in the change history.

        Args:
            change: Change record to store
        """
        changed_fields_json = json.dumps(change.changed_fields)

        await self._connection.execute(
            """
            INSERT INTO change_history (
                job_id, spec_hash, previous_hash, changed_at, 
                change_type, changed_fields
            ) VALUES (?, ?, ?, ?, ?, ?)
        """,
            (
                change.job_id,
                change.spec_hash,
                change.previous_hash,
                change.changed_at,
                change.change_type,
                changed_fields_json,
            ),
        )

        await self._connection.commit()

    async def get_tracked_jobs(self) -> Dict[str, str]:
        """
        Get all tracked jobs and their current hashes.

        Returns:
            Dictionary mapping job_id to spec_hash
        """
        async with self._lock:
            return self._tracked_specs.copy()

    async def get_change_history(
        self, job_id: Optional[str] = None, limit: int = 100
    ) -> List[ChangeRecord]:
        """
        Get change history for a specific job or all jobs.

        Args:
            job_id: Optional job identifier to filter by
            limit: Maximum number of records to return

        Returns:
            List of change records
        """
        if job_id:
            cursor = await self._connection.execute(
                """
                SELECT job_id, spec_hash, previous_hash, changed_at, change_type, changed_fields
                FROM change_history 
                WHERE job_id = ?
                ORDER BY changed_at DESC 
                LIMIT ?
            """,
                (job_id, limit),
            )
        else:
            cursor = await self._connection.execute(
                """
                SELECT job_id, spec_hash, previous_hash, changed_at, change_type, changed_fields
                FROM change_history 
                ORDER BY changed_at DESC 
                LIMIT ?
            """,
                (limit,),
            )

        rows = await cursor.fetchall()

        records = []
        for row in rows:
            changed_fields = json.loads(row[5]) if row[5] else []
            records.append(
                ChangeRecord(
                    job_id=row[0],
                    spec_hash=row[1],
                    previous_hash=row[2],
                    changed_at=row[3],
                    change_type=row[4],
                    changed_fields=changed_fields,
                )
            )

        return records

    async def remove_tracked_job(self, job_id: str) -> bool:
        """
        Remove a job from tracking.

        Args:
            job_id: Job identifier to remove

        Returns:
            True if job was removed, False if not found
        """
        async with self._lock:
            if job_id not in self._tracked_specs:
                return False

            # Remove from cache
            del self._tracked_specs[job_id]

            # Remove from database
            await self._connection.execute(
                "DELETE FROM tracked_specs WHERE job_id = ?", (job_id,)
            )
            await self._connection.commit()

            return True

    async def clear_all_tracking(self) -> None:
        """Clear all tracking data."""
        async with self._lock:
            self._tracked_specs.clear()

            await self._connection.execute("DELETE FROM tracked_specs")
            await self._connection.execute("DELETE FROM change_history")
            await self._connection.commit()

    async def get_statistics(self) -> Dict[str, Any]:
        """Get tracking statistics."""
        async with self._lock:
            total_tracked = len(self._tracked_specs)

        cursor = await self._connection.execute("SELECT COUNT(*) FROM change_history")
        total_changes = (await cursor.fetchone())[0]

        cursor = await self._connection.execute(
            """
            SELECT change_type, COUNT(*) 
            FROM change_history 
            GROUP BY change_type
        """
        )
        change_type_counts = {row[0]: row[1] for row in await cursor.fetchall()}

        return {
            "total_tracked_jobs": total_tracked,
            "total_changes": total_changes,
            "change_type_counts": change_type_counts,
            "database_file": str(self.state_file),
        }

    def get_cached_hash(self, job_id: str) -> Optional[str]:
        """Get cached hash for a job without database access."""
        return self._tracked_specs.get(job_id)

    async def batch_update_tracker(self, specs: List[JobSpec]) -> int:
        """
        Update tracker for multiple specs in a batch.

        Args:
            specs: List of job specifications

        Returns:
            Number of specs updated
        """
        updates = []
        current_time = datetime.now(timezone.utc).isoformat()

        for spec in specs:
            spec_hash = self.calculate_spec_hash(spec)
            updates.append((spec.job_id, spec_hash, current_time))

        async with self._lock:
            await self._connection.executemany(
                """
                INSERT OR REPLACE INTO tracked_specs (job_id, spec_hash, last_updated, created_at)
                VALUES (?, ?, ?, COALESCE(
                    (SELECT created_at FROM tracked_specs WHERE job_id = ?),
                    ?
                ))
            """,
                [
                    (job_id, spec_hash, current_time, job_id, current_time)
                    for job_id, spec_hash, current_time in updates
                ],
            )

            await self._connection.commit()

            # Update cache
            for job_id, spec_hash, _ in updates:
                self._tracked_specs[job_id] = spec_hash

        return len(updates)
