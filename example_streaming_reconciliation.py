#!/usr/bin/env python3
"""
Example demonstrating streaming job reconciliation capabilities.

This script shows how to use the Flink Job Controller to reconcile
streaming jobs during development.
"""

import asyncio
import os
from pathlib import Path

from src.core.reconciler import JobReconciler, JobSpec, JobType
from src.core.jobs import JobSpecManager
from src.core.tracker import JobSpecTracker
from src.core.flink_client import FlinkRESTClient


async def main():
    """Demonstrate streaming job reconciliation."""
    print("🚀 Flink Job Controller - Streaming Job Reconciliation Example")
    print("=" * 60)
    
    # Create sample job specifications
    streaming_specs = [
        JobSpec(
            job_id="data-pipeline-streaming",
            job_type=JobType.STREAMING,
            artifact_path="/artifacts/data-pipeline.jar",
            parallelism=4,
            checkpoint_interval=60000,  # 1 minute checkpoints
            savepoint_trigger_interval=300000,  # 5 minute savepoints
            memory="2g",
            cpu_cores=2,
            restart_strategy="fixed-delay",
            max_restart_attempts=3
        ),
        JobSpec(
            job_id="real-time-analytics",
            job_type=JobType.STREAMING,
            artifact_path="/artifacts/analytics.jar",
            parallelism=2,
            checkpoint_interval=30000,  # 30 second checkpoints
            memory="1g",
            cpu_cores=1
        ),
        JobSpec(
            job_id="event-processor",
            job_type=JobType.STREAMING,
            artifact_path="/artifacts/processor.jar",
            parallelism=3,
            checkpoint_interval=45000,
            savepoint_trigger_interval=600000,  # 10 minute savepoints
            memory="1.5g",
            cpu_cores=1
        )
    ]
    
    print(f"📋 Created {len(streaming_specs)} streaming job specifications:")
    for spec in streaming_specs:
        print(f"  • {spec.job_id} (parallelism: {spec.parallelism}, checkpoints: {spec.checkpoint_interval}ms)")
    print()
    
    # Initialize components
    print("🔧 Initializing reconciliation components...")
    
    # Create job spec manager
    spec_manager = JobSpecManager(spec_directory="job-specs")
    
    # Initialize change tracker
    async with JobSpecTracker(state_file="example_tracker.db") as tracker:
        print("✅ Change tracker initialized")
        
        # Initialize reconciler (without real Flink client for demo)
        reconciler = JobReconciler(
            flink_client=None,  # Would be FlinkRESTClient("http://localhost:8081") in real usage
            state_store=None,   # Would be actual state store in real usage
            circuit_breaker_config={
                'failure_threshold': 3,
                'recovery_timeout': 30.0
            }
        )
        print("✅ Job reconciler initialized")
        print()
        
        # Save specifications
        print("💾 Saving job specifications...")
        for spec in streaming_specs:
            await spec_manager.save_spec(spec, persist_to_file=True)
            print(f"  • Saved: {spec.job_id}")
        print()
        
        # Initial reconciliation - all jobs will be new
        print("🔄 Performing initial reconciliation...")
        changes = await tracker.detect_changes(streaming_specs)
        print(f"📊 Detected {len(changes)} changes:")
        for change in changes:
            print(f"  • {change.job_id}: {change.change_type}")
        
        # Record changes in tracker
        for change in changes:
            await tracker.record_change(change)
            # Update tracker with new spec hash
            spec = next(s for s in streaming_specs if s.job_id == change.job_id)
            await tracker.update_tracker(spec.job_id, spec)
        
        # Perform reconciliation
        results = await reconciler.reconcile_all(streaming_specs)
        
        print("\n🎯 Reconciliation Results:")
        for result in results:
            status = "✅ SUCCESS" if result.success else "❌ FAILED"
            print(f"  • {result.job_id}: {result.action_taken.value} - {status}")
            if not result.success:
                print(f"    Error: {result.error_message}")
        print()
        
        # Simulate spec changes for demonstration
        print("🔧 Simulating specification changes...")
        
        # Update the first job's parallelism
        updated_spec = streaming_specs[0].copy(update={'parallelism': 6})
        streaming_specs[0] = updated_spec
        
        # Update the second job's checkpoint interval
        updated_spec2 = streaming_specs[1].copy(update={'checkpoint_interval': 15000})
        streaming_specs[1] = updated_spec2
        
        print(f"  • Updated {streaming_specs[0].job_id}: parallelism 4 → 6")
        print(f"  • Updated {streaming_specs[1].job_id}: checkpoint interval 30s → 15s")
        print()
        
        # Detect changes after updates
        print("🔍 Detecting changes after updates...")
        changes = await tracker.detect_changes(streaming_specs)
        print(f"📊 Detected {len(changes)} changes:")
        for change in changes:
            print(f"  • {change.job_id}: {change.change_type}")
            if change.changed_fields:
                print(f"    Fields: {', '.join(change.changed_fields)}")
        print()
        
        # Reconcile changes
        print("🔄 Reconciling changes...")
        results = await reconciler.reconcile_all(streaming_specs)
        
        print("🎯 Reconciliation Results:")
        for result in results:
            status = "✅ SUCCESS" if result.success else "❌ FAILED"
            action_emoji = {
                'deploy': '🚀',
                'update': '🔄',
                'stop': '⏹️',
                'restart': '♻️',
                'no_action': '✋'
            }.get(result.action_taken.value, '🔧')
            
            print(f"  {action_emoji} {result.job_id}: {result.action_taken.value} - {status}")
            print(f"    Duration: {result.duration_ms}ms")
            if not result.success:
                print(f"    Error: {result.error_message}")
        print()
        
        # Update tracker with new hashes
        for change in changes:
            await tracker.record_change(change)
            spec = next(s for s in streaming_specs if s.job_id == change.job_id)
            await tracker.update_tracker(spec.job_id, spec)
        
        # Show tracker statistics
        stats = await tracker.get_statistics()
        print("📈 Tracker Statistics:")
        print(f"  • Total tracked jobs: {stats['total_tracked_jobs']}")
        print(f"  • Total changes: {stats['total_changes']}")
        print(f"  • Change types: {stats['change_type_counts']}")
        print()
        
        # Show change history
        history = await tracker.get_change_history(limit=10)
        if history:
            print("📜 Recent Change History:")
            for record in history[:5]:  # Show last 5 changes
                print(f"  • {record.changed_at[:19]}: {record.job_id} - {record.change_type}")
        
        print()
        print("✨ Streaming job reconciliation demonstration completed!")
        print()
        print("💡 In a real environment, this would:")
        print("  • Connect to actual Flink cluster")
        print("  • Deploy/update streaming jobs with savepoints")
        print("  • Monitor job health and handle failures")
        print("  • Provide real-time reconciliation during development")


def create_sample_job_spec_files():
    """Create sample job specification files for demonstration."""
    spec_dir = Path("job-specs")
    spec_dir.mkdir(exist_ok=True)
    
    sample_spec = {
        'job_id': 'sample-streaming-job',
        'job_type': 'streaming',
        'artifact_path': '/artifacts/sample.jar',
        'parallelism': 2,
        'checkpoint_interval': 60000,
        'savepoint_trigger_interval': 300000,
        'memory': '1g',
        'cpu_cores': 1,
        'restart_strategy': 'fixed-delay',
        'max_restart_attempts': 3
    }
    
    import yaml
    with open(spec_dir / "sample-streaming-job.yaml", 'w') as f:
        yaml.dump(sample_spec, f, indent=2)
    
    print(f"📁 Created sample job specification in {spec_dir}/sample-streaming-job.yaml")


if __name__ == "__main__":
    # Create sample files
    create_sample_job_spec_files()
    
    # Run the demonstration
    asyncio.run(main())