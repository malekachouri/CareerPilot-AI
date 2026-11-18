---
title: Docker images, layers, caching and security
categories: [docker, devsecops]
license: CC-BY-4.0
attribution: CareerPilot AI contributors
---
# Layers and the build cache

Each Dockerfile instruction produces a layer. When an instruction and its inputs have not changed, the
builder reuses the cached layer; once one layer changes, every following layer is rebuilt.

That is why you copy the dependency manifest (`requirements.txt`, `package.json` + lockfile) and install
dependencies **before** copying the application code: code edits then reuse the slow dependency layer.

# Small and safe production images

- **Multi-stage builds**: compile and install in a build stage, copy only the runtime artifacts into a slim
  final image. Compilers, package managers and build secrets stay out of production.
- **Pin base images** by version (or digest), not `latest`, so builds are reproducible.
- **Run as a non-root user** (`USER app`) and keep the root filesystem read-only where possible.
- **Apply OS security updates** in the final stage and scan images (for example with Trivy) in CI.
- Never bake secrets into an image: build arguments and layers are visible to anyone with the image.
  Use runtime secrets or BuildKit secret mounts.

# Storage

- **Named volumes** are managed by Docker and survive container re-creation: the usual choice for databases.
- **Bind mounts** map a host path into the container: handy for development, tied to the host.
- **tmpfs** lives in memory and disappears when the container stops.
- `docker compose down -v` also removes the project's named volumes, so the data is deleted.
