# Performance Profiling
## Purpose
Measure API, model, worker, connector, polling, memory, and frontend latency.
## When to use
Use for slow tasks, UI lag, resource pressure, or release baselines.
## Required inputs
Target operation, bounded duration, and expected threshold.
## Permitted tools
Metrics/process reads, loopback probes, and scoped logs.
## Prohibited actions
No destructive load tests, secret capture, or continuous expensive probes.
## Execution steps
Establish baseline, sample bounded operations, classify bottlenecks, and stop.
## Evidence requirements
Record sample count, percentiles, resources, and environment.
## Output format
Baseline, bottleneck, confidence, and low-risk recommendation.
## Validation and rollback
Repeat the same bounded profile after an approved change.
