---
title: Terraform/OpenTofu state, secrets and delivery practices
categories: [terraform, cicd, gitops, devsecops]
license: CC-BY-4.0
attribution: CareerPilot AI contributors
---
# State

Terraform and OpenTofu record what they manage in a **state file**. Teams keep it in a **remote backend**
(object storage or an HTTP backend) with **locking**, so there is one source of truth and two concurrent
`apply` runs cannot corrupt it.

State can contain secrets **in plain text**, even for values marked `sensitive = true`. That flag only hides
values from CLI output. Encrypt the backend, restrict who can read it, and prefer fetching secrets at run
time from a secret manager.

Structure projects with reusable **modules** and one root configuration per environment, keep provider
versions pinned, and run `plan` in CI so reviewers see the change before `apply`.

# Release strategies

- **Rolling update**: replace instances gradually; simple, but old and new versions run side by side.
- **Blue-green**: two full environments; switch traffic at once, and roll back by switching back. Costs
  double capacity during the switch.
- **Canary**: send a small share of traffic to the new version and promote it only when its error rate,
  latency and saturation stay within the SLO, compared with the stable version, over a meaningful period.
- **Feature flags** decouple deployment from release.

# CI/CD hygiene

Build once and promote the same immutable artifact through environments. Pin third-party CI actions to commit
SHAs. Give pipelines short-lived cloud credentials through OIDC federation instead of stored keys.
