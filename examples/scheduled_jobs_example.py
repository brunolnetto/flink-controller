"""
Example demonstrating scheduled job management with the Flink Controller.

This example shows how to:
1. Create scheduled jobs with cron expressions
2. Integrate with the reconciler for job execution
3. Monitor scheduled job execution
4. Handle job lifecycle management
"""

import asyncio
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from datetime import datetime, timezone
from src.core.reconciler import ScheduledJobReconciler
from src.core.scheduler import ScheduledJobManager, ScheduledJobSpec
from src.core.reconciler import JobType


class MockFlinkClient:
    """Mock Flink client for demonstration."""
    
    def __init__(self):
        self.jobs = {}
        self.job_counter = 0
    
    async def health_check(self):
        return True
    
    async def get_job_id_by_name(self, job_name):
        return self.jobs.get(job_name, {}).get('id')
    
    async def get_job_details(self, job_id):
        for job_name, job_info in self.jobs.items():
            if job_info['id'] == job_id:
                return {'state': job_info.get('state', 'RUNNING')}
        return {'state': 'UNKNOWN'}
    
    async def deploy_job(self, artifact_path, config):
        self.job_counter += 1
        job_id = f"flink_job_{self.job_counter}"
        job_name = config.get('job_name', f'job_{self.job_counter}')
        self.jobs[job_name] = {
            'id': job_id,
            'state': 'RUNNING',
            'artifact_path': artifact_path
        }
        print(f"✓ Deployed job {job_name} with ID {job_id}")
        return job_id


async def main():
    """Main demonstration function."""
    
    print("=== Flink Controller Scheduled Jobs Demo ===\n")
    
    # 1. Setup mock dependencies
    flink_client = MockFlinkClient()
    
    # 2. Create scheduled reconciler
    reconciler = ScheduledJobReconciler(flink_client=flink_client)
    
    # 3. Create scheduler manager
    scheduler_manager = ScheduledJobManager(reconciler, check_interval=5)  # Check every 5 seconds
    reconciler.set_scheduler_manager(scheduler_manager)
    
    # 4. Define scheduled jobs
    scheduled_jobs = [
        ScheduledJobSpec(
            job_id="daily_batch_job",
            job_type=JobType.BATCH,
            artifact_path="s3://my-bucket/daily-batch.jar",
            parallelism=4,
            memory="2g",
            cpu_cores=2,
            cron_expression="0 2 * * *",  # Daily at 2 AM
            timezone="UTC",
            max_executions=None,  # Unlimited
            execution_timeout=7200,  # 2 hours
            max_retries=2
        ),
        ScheduledJobSpec(
            job_id="hourly_streaming_job",
            job_type=JobType.STREAMING,
            artifact_path="s3://my-bucket/hourly-stream.jar",
            parallelism=2,
            memory="1g", 
            cpu_cores=1,
            cron_expression="0 * * * *",  # Every hour
            timezone="UTC",
            max_executions=100,
            execution_timeout=3600,  # 1 hour
            max_retries=3
        ),
        ScheduledJobSpec(
            job_id="demo_job",
            job_type=JobType.BATCH,
            artifact_path="s3://my-bucket/demo.jar",
            parallelism=1,
            memory="512m",
            cpu_cores=1,
            cron_expression="* * * * *",  # Every minute (for demo)
            timezone="UTC",
            max_executions=3,
            execution_timeout=300,  # 5 minutes
            max_retries=1
        )
    ]
    
    try:
        # 5. Start scheduler
        print("Starting scheduled job manager...")
        await reconciler.start_scheduled_jobs()
        print("✓ Scheduler started\n")
        
        # 6. Add scheduled jobs
        print("Adding scheduled jobs:")
        for job_spec in scheduled_jobs:
            success = await reconciler.add_scheduled_job(job_spec)
            status = "✓ Added" if success else "✗ Failed to add"
            print(f"  {status}: {job_spec.job_id} ({job_spec.cron_expression})")
        print()
        
        # 7. Display initial status
        jobs = reconciler.get_scheduled_jobs()
        stats = reconciler.get_scheduler_statistics()
        
        print(f"Scheduled Jobs: {len(jobs)}")
        print(f"Scheduler Stats: {stats}")
        print()
        
        # 8. Monitor execution for demo (runs demo job that executes every minute)
        print("Monitoring scheduled job execution (5 seconds)...")
        for i in range(1):  # 1 iteration of 5 seconds = 5 seconds
            await asyncio.sleep(5)
            
            # Check execution history
            demo_history = reconciler.get_execution_history("demo_job", limit=5)
            if demo_history:
                print(f"Demo job executions: {len(demo_history)}")
                for record in demo_history[:2]:  # Show last 2 executions
                    print(f"  - {record.scheduled_time.strftime('%H:%M:%S')}: {record.status.value}")
            
            # Show updated stats
            updated_stats = reconciler.get_scheduler_statistics()
            print(f"Active executions: {updated_stats.get('active_executions', 0)}")
            print()
        
        # 9. Show final results
        print("Final Results:")
        all_history = reconciler.get_execution_history("demo_job")
        print(f"Total demo job executions: {len(all_history)}")
        
        final_stats = reconciler.get_scheduler_statistics()
        print(f"Final scheduler statistics: {final_stats}")
        
    finally:
        # 10. Cleanup
        print("\nStopping scheduler...")
        await reconciler.stop_scheduled_jobs()
        print("✓ Scheduler stopped")


if __name__ == "__main__":
    # Run the demonstration
    asyncio.run(main())