---
title: System design interview checklist
categories: [system-design, cloud-architecture, databases, apis]
license: CC-BY-4.0
attribution: CareerPilot AI contributors
---
# 1. Clarify the problem

Functional requirements (what users do), non-functional requirements (latency, availability target,
consistency, data retention, compliance), and scale: users, requests per second (average and peak), data
size and growth. State your assumptions out loud.

# 2. Estimate

Back-of-the-envelope numbers decide the design: requests per second, storage per day, bandwidth, and
whether the working set fits in memory.

# 3. High-level design

Clients, load balancer, stateless services, data stores, caches, queues, and external dependencies. Draw the
request path for the main use case.

# 4. Deep dives and trade-offs

- **Scalability**: horizontal scaling of stateless services, partitioning/sharding, caching (what is cached,
  invalidation), async processing with queues to absorb bursts.
- **Availability**: redundancy across zones, health checks, graceful degradation, retries with backoff and
  idempotency, backups with tested restores, RPO (acceptable data loss) and RTO (time to recover).
- **Consistency**: where strong consistency is needed and where eventual consistency is acceptable.
- **Security**: authentication, authorisation, encryption in transit and at rest, rate limiting, abuse.
- **Cost**: what dominates the bill (compute, storage, egress) and cheaper alternatives.

# 5. Wrap up

Summarise the design, the main risks, and what you would monitor (latency, errors, saturation).
