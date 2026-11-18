---
title: Kubernetes probes and pod troubleshooting
categories: [kubernetes, troubleshooting]
license: CC-BY-4.0
attribution: CareerPilot AI contributors
---
# Liveness, readiness and startup probes

A **liveness probe** answers "is this container still healthy?". When it fails repeatedly, the kubelet
restarts the container. Use it to recover from deadlocks, not to check dependencies: a liveness probe that
calls the database will restart every pod during a database outage and make things worse.

A **readiness probe** answers "can this pod receive traffic now?". When it fails, the pod is removed from the
Service endpoints but is not restarted. Use it during start-up, while warming caches, or when the pod is
temporarily overloaded.

A **startup probe** protects slow-starting applications: liveness and readiness checks only begin once it
succeeds, so a long start does not trigger restarts.

# Investigating a failing pod, in order

1. `kubectl get pods -o wide`: status, restarts, node.
2. `kubectl describe pod <pod>`: events at the bottom (scheduling failures, image pull errors, probe failures,
   OOMKilled, failed mounts).
3. `kubectl logs <pod> --previous`: the logs of the crashed container instance, where the crash reason
   usually is. Add `-c <container>` for multi-container pods.
4. `kubectl get events --sort-by=.lastTimestamp` for cluster-wide context.
5. Check resources: `kubectl top pod` and the container limits. A container over its **memory limit** is
   OOM-killed; a container over its **CPU limit** is throttled, not killed.

# Common causes of CrashLoopBackOff

- The process exits immediately: wrong command, missing configuration or environment variable.
- A missing Secret or ConfigMap key referenced by the pod.
- A liveness probe that is too aggressive (no startup probe, too short `initialDelaySeconds`).
- Memory limit too low, so the container is OOMKilled repeatedly.

# Interview tip

Describe the order of investigation and why. Interviewers value a calm, systematic approach, from the
cheapest checks to the deepest, more than a long list of commands.
