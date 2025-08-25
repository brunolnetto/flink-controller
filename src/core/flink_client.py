"""
Flink REST API client for job deployment and management.

This module provides a comprehensive client for interacting with Flink's REST API
to deploy, monitor, and manage streaming and batch jobs.
"""

import asyncio
import aiohttp
import json
import time
from typing import Dict, List, Optional, Any, Union
from datetime import datetime, timezone
from pydantic import BaseModel, Field
from enum import Enum

from ..security.auth import FlinkAuthManager, AuthResult
from ..resilience.circuit_breaker import CircuitBreaker, CircuitBreakerError


class FlinkJobState(Enum):
    """Flink job states from REST API."""
    CREATED = "CREATED"
    RUNNING = "RUNNING" 
    FAILING = "FAILING"
    FAILED = "FAILED"
    CANCELLING = "CANCELLING"
    CANCELLED = "CANCELLED"
    FINISHED = "FINISHED"
    RESTARTING = "RESTARTING"
    SUSPENDED = "SUSPENDED"
    RECONCILING = "RECONCILING"


class FlinkClusterInfo(BaseModel):
    """Flink cluster information."""
    
    cluster_id: str = Field(..., description="Cluster identifier")
    flink_version: str = Field(..., description="Flink version")
    task_managers: int = Field(..., description="Number of task managers")
    slots_total: int = Field(..., description="Total number of slots")
    slots_available: int = Field(..., description="Available slots")
    jobs_running: int = Field(..., description="Number of running jobs")


class FlinkJobInfo(BaseModel):
    """Information about a Flink job."""
    
    job_id: str = Field(..., description="Flink job ID")
    job_name: str = Field(..., description="Job name")
    state: FlinkJobState = Field(..., description="Current job state")
    start_time: Optional[str] = Field(None, description="Job start time")
    end_time: Optional[str] = Field(None, description="Job end time")
    duration: Optional[int] = Field(None, description="Job duration in ms")
    parallelism: int = Field(..., description="Job parallelism")
    
    # Streaming-specific fields
    last_checkpoint: Optional[str] = Field(None, description="Last checkpoint time")
    checkpoint_count: int = Field(0, description="Number of completed checkpoints")
    savepoint_count: int = Field(0, description="Number of savepoints")


class DeploymentConfig(BaseModel):
    """Configuration for job deployment."""
    
    entry_class: Optional[str] = Field(None, description="Main class for the job")
    program_args: List[str] = Field(default_factory=list, description="Program arguments")
    parallelism: Optional[int] = Field(None, description="Job parallelism")
    savepoint_path: Optional[str] = Field(None, description="Savepoint to restore from")
    allow_non_restored_state: bool = Field(False, description="Allow non-restored state")


class FlinkAPIError(Exception):
    """Exception raised when Flink API calls fail."""
    def __init__(self, message: str, status_code: Optional[int] = None, response_data: Optional[Dict] = None):
        super().__init__(message)
        self.status_code = status_code
        self.response_data = response_data


class FlinkRESTClient:
    """Client for interacting with Flink REST API."""
    
    def __init__(
        self, 
        base_url: str = "http://localhost:8081",
        auth_manager: Optional[FlinkAuthManager] = None,
        circuit_breaker_config: Optional[Dict] = None,
        timeout: int = 30
    ):
        """
        Initialize Flink REST client.
        
        Args:
            base_url: Flink JobManager REST API URL
            auth_manager: Authentication manager
            circuit_breaker_config: Circuit breaker configuration
            timeout: Request timeout in seconds
        """
        self.base_url = base_url.rstrip('/')
        self.auth_manager = auth_manager
        self.timeout = timeout
        
        # Initialize circuit breaker
        cb_config = circuit_breaker_config or {}
        self.circuit_breaker = CircuitBreaker(
            failure_threshold=cb_config.get('failure_threshold', 3),
            recovery_timeout=cb_config.get('recovery_timeout', 30.0),
            expected_exception=(aiohttp.ClientError, asyncio.TimeoutError, FlinkAPIError)
        )
        
        self._session: Optional[aiohttp.ClientSession] = None
    
    async def __aenter__(self):
        """Async context manager entry."""
        await self._ensure_session()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self._session:
            await self._session.close()
            self._session = None
    
    async def _ensure_session(self):
        """Ensure HTTP session exists."""
        if not self._session:
            timeout = aiohttp.ClientTimeout(total=self.timeout)
            self._session = aiohttp.ClientSession(timeout=timeout)
    
    async def _make_request(
        self, 
        method: str, 
        endpoint: str, 
        data: Optional[Union[Dict, bytes]] = None,
        params: Optional[Dict] = None,
        headers: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Make HTTP request to Flink API with circuit breaker protection.
        
        Args:
            method: HTTP method
            endpoint: API endpoint
            data: Request data
            params: Query parameters
            headers: Additional headers
            
        Returns:
            Response JSON data
        """
        async def make_request():
            await self._ensure_session()
            
            url = f"{self.base_url}{endpoint}"
            request_headers = {"Content-Type": "application/json"}
            
            # Add authentication headers if available
            if self.auth_manager:
                auth_headers = self.auth_manager.get_auth_headers("api_key", api_key="dummy")
                request_headers.update(auth_headers)
            
            if headers:
                request_headers.update(headers)
            
            # Prepare request data
            if data and isinstance(data, dict):
                data = json.dumps(data).encode()
            
            async with self._session.request(
                method=method,
                url=url,
                data=data,
                params=params,
                headers=request_headers
            ) as response:
                response_text = await response.text()
                
                if response.status >= 400:
                    try:
                        error_data = json.loads(response_text)
                    except:
                        error_data = {"message": response_text}
                    
                    raise FlinkAPIError(
                        f"Flink API error: {error_data.get('message', 'Unknown error')}",
                        status_code=response.status,
                        response_data=error_data
                    )
                
                try:
                    return json.loads(response_text) if response_text else {}
                except json.JSONDecodeError:
                    return {"raw_response": response_text}
        
        try:
            return self.circuit_breaker.call(make_request)
        except CircuitBreakerError:
            raise FlinkAPIError("Flink cluster is unavailable (circuit breaker open)")
    
    async def get_cluster_info(self) -> FlinkClusterInfo:
        """Get Flink cluster information."""
        try:
            # Get cluster overview
            overview = await self._make_request("GET", "/overview")
            
            # Get taskmanagers info
            taskmanagers = await self._make_request("GET", "/taskmanagers")
            
            # Get jobs overview
            jobs = await self._make_request("GET", "/jobs")
            
            return FlinkClusterInfo(
                cluster_id=overview.get("cluster-id", "unknown"),
                flink_version=overview.get("flink-version", "unknown"),
                task_managers=len(taskmanagers.get("taskmanagers", [])),
                slots_total=overview.get("slots-total", 0),
                slots_available=overview.get("slots-available", 0),
                jobs_running=len([j for j in jobs.get("jobs", []) if j.get("status") == "RUNNING"])
            )
        except Exception as e:
            raise FlinkAPIError(f"Failed to get cluster info: {str(e)}")
    
    async def list_jobs(self) -> List[FlinkJobInfo]:
        """List all jobs in the Flink cluster."""
        try:
            response = await self._make_request("GET", "/jobs")
            jobs_data = response.get("jobs", [])
            
            jobs = []
            for job_data in jobs_data:
                # Get detailed job info
                job_id = job_data["id"]
                try:
                    job_details = await self.get_job_details(job_id)
                    jobs.append(job_details)
                except Exception as e:
                    # If we can't get details, create basic info
                    jobs.append(FlinkJobInfo(
                        job_id=job_id,
                        job_name=job_data.get("name", "unknown"),
                        state=FlinkJobState(job_data.get("status", "UNKNOWN")),
                        parallelism=job_data.get("parallelism", 1)
                    ))
            
            return jobs
        except Exception as e:
            raise FlinkAPIError(f"Failed to list jobs: {str(e)}")
    
    async def get_job_details(self, job_id: str) -> FlinkJobInfo:
        """Get detailed information about a specific job."""
        try:
            response = await self._make_request("GET", f"/jobs/{job_id}")
            
            # Get checkpointing info for streaming jobs
            checkpoint_info = {}
            try:
                checkpoint_response = await self._make_request("GET", f"/jobs/{job_id}/checkpoints")
                checkpoint_info = checkpoint_response
            except:
                pass  # Checkpointing might not be enabled
            
            return FlinkJobInfo(
                job_id=job_id,
                job_name=response.get("name", "unknown"),
                state=FlinkJobState(response.get("state", "UNKNOWN")),
                start_time=datetime.fromtimestamp(response.get("start-time", 0) / 1000, tz=timezone.utc).isoformat() if response.get("start-time") else None,
                end_time=datetime.fromtimestamp(response.get("end-time", 0) / 1000, tz=timezone.utc).isoformat() if response.get("end-time") else None,
                duration=response.get("duration", 0),
                parallelism=response.get("parallelism", 1),
                checkpoint_count=checkpoint_info.get("count", 0),
                last_checkpoint=checkpoint_info.get("latest", {}).get("completed_timestamp", "")
            )
        except Exception as e:
            raise FlinkAPIError(f"Failed to get job details for {job_id}: {str(e)}")
    
    async def deploy_job(
        self, 
        jar_file_path: str, 
        config: DeploymentConfig,
        job_name: Optional[str] = None
    ) -> str:
        """
        Deploy a job to Flink cluster.
        
        Args:
            jar_file_path: Path to JAR file
            config: Deployment configuration
            job_name: Optional job name
            
        Returns:
            Flink job ID
        """
        try:
            # First, upload the JAR file
            jar_id = await self._upload_jar(jar_file_path)
            
            # Then submit the job
            job_id = await self._submit_job(jar_id, config, job_name)
            
            return job_id
        except Exception as e:
            raise FlinkAPIError(f"Failed to deploy job: {str(e)}")
    
    async def _upload_jar(self, jar_file_path: str) -> str:
        """Upload JAR file to Flink cluster."""
        try:
            # This would implement actual file upload
            # For now, simulate upload and return mock jar_id
            await asyncio.sleep(0.1)  # Simulate upload time
            return f"jar-{int(time.time())}"
        except Exception as e:
            raise FlinkAPIError(f"Failed to upload JAR: {str(e)}")
    
    async def _submit_job(self, jar_id: str, config: DeploymentConfig, job_name: Optional[str]) -> str:
        """Submit job using uploaded JAR."""
        try:
            payload = {
                "entryClass": config.entry_class,
                "parallelism": config.parallelism,
                "programArgs": " ".join(config.program_args) if config.program_args else "",
                "allowNonRestoredState": config.allow_non_restored_state
            }
            
            if config.savepoint_path:
                payload["savepointPath"] = config.savepoint_path
            
            endpoint = f"/jars/{jar_id}/run"
            response = await self._make_request("POST", endpoint, data=payload)
            
            return response.get("jobid", "unknown")
        except Exception as e:
            raise FlinkAPIError(f"Failed to submit job: {str(e)}")
    
    async def stop_job(self, job_id: str, savepoint_path: Optional[str] = None, drain: bool = False) -> Optional[str]:
        """
        Stop a running job.
        
        Args:
            job_id: Flink job ID
            savepoint_path: Path to save savepoint
            drain: Whether to drain the job
            
        Returns:
            Savepoint path if created, None otherwise
        """
        try:
            if savepoint_path or drain:
                # Stop with savepoint
                endpoint = f"/jobs/{job_id}/stop"
                payload = {
                    "targetDirectory": savepoint_path,
                    "drain": drain
                }
                response = await self._make_request("POST", endpoint, data=payload)
                return response.get("request-id")
            else:
                # Cancel job
                endpoint = f"/jobs/{job_id}"
                await self._make_request("PATCH", endpoint)
                return None
        except Exception as e:
            raise FlinkAPIError(f"Failed to stop job {job_id}: {str(e)}")
    
    async def trigger_savepoint(self, job_id: str, savepoint_dir: str) -> str:
        """
        Trigger savepoint for a running job.
        
        Args:
            job_id: Flink job ID
            savepoint_dir: Directory to save savepoint
            
        Returns:
            Savepoint trigger request ID
        """
        try:
            endpoint = f"/jobs/{job_id}/savepoints"
            payload = {"target-directory": savepoint_dir}
            
            response = await self._make_request("POST", endpoint, data=payload)
            return response.get("request-id", "unknown")
        except Exception as e:
            raise FlinkAPIError(f"Failed to trigger savepoint for {job_id}: {str(e)}")
    
    async def get_savepoint_status(self, job_id: str, request_id: str) -> Dict[str, Any]:
        """Get status of savepoint operation."""
        try:
            endpoint = f"/jobs/{job_id}/savepoints/{request_id}"
            return await self._make_request("GET", endpoint)
        except Exception as e:
            raise FlinkAPIError(f"Failed to get savepoint status: {str(e)}")
    
    async def cancel_job(self, job_id: str) -> bool:
        """Cancel a running job."""
        try:
            endpoint = f"/jobs/{job_id}"
            await self._make_request("PATCH", endpoint)
            return True
        except Exception as e:
            raise FlinkAPIError(f"Failed to cancel job {job_id}: {str(e)}")
    
    async def restart_job(self, job_id: str) -> bool:
        """Restart a job (cancel and resubmit)."""
        try:
            # First cancel the job
            await self.cancel_job(job_id)
            
            # Wait a bit for the job to stop
            await asyncio.sleep(2)
            
            # Job would need to be resubmitted by the reconciler
            return True
        except Exception as e:
            raise FlinkAPIError(f"Failed to restart job {job_id}: {str(e)}")
    
    async def get_job_metrics(self, job_id: str) -> Dict[str, Any]:
        """Get metrics for a specific job."""
        try:
            endpoint = f"/jobs/{job_id}/metrics"
            return await self._make_request("GET", endpoint)
        except Exception as e:
            raise FlinkAPIError(f"Failed to get metrics for {job_id}: {str(e)}")
    
    async def health_check(self) -> bool:
        """Check if Flink cluster is healthy and accessible."""
        try:
            await self._make_request("GET", "/config")
            return True
        except:
            return False
    
    async def close(self):
        """Close the HTTP session."""
        if self._session:
            await self._session.close()
            self._session = None