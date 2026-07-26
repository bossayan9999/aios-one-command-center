# Network and CCNA Check
## Purpose
Diagnose authorized adapter, gateway, DNS, latency, packet, listener, and route state.
## When to use
Use for local, tunnel, DNS, or service reachability incidents.
## Required inputs
Authorized target, expected route, and scope.
## Permitted tools
Adapter/route reads, DNS lookup, bounded ping, and HTTP health probes.
## Prohibited actions
No scanning third parties, config changes, exploitation, or credential capture.
## Execution steps
Map adapter to gateway, DNS, backend, tunnel, and public route.
## Evidence requirements
Record targets, latency, status, packet result, and unavailable checks.
## Output format
Path diagram, failure boundary, confidence, and safe next step.
## Validation and rollback
Re-probe after approved change; diagnostic operations require no rollback.
