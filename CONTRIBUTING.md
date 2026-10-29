# Contributing

## Publishing

The GitHub Actions workflow in `.github/workflows/publish.yml` tests and publishes
the tagged commit to `ghcr.io/chiv2-community/c2serverbrowserbackend` when a
`vMAJOR.MINOR.PATCH` tag is pushed.
The Docker tags are the version without `v` and `latest`.
The version comes from the Git tag, not `pyproject.toml`.

The workflow caches uv dependencies and stores Docker build layers in the GHCR
`buildcache` tag for reuse across releases. This tag is build cache, not a runnable
release image.

The workflow authenticates with the built-in `GITHUB_TOKEN` using
`packages: write`; no registry secrets are required. Organization policies must
allow the workflow to create packages. After the first publish, set the package
visibility to public in its GitHub package settings to allow anonymous pulls.

After the workflow is merged into `main`, tag the desired release commit:

```bash
git switch main
git pull --ff-only origin main
git tag v1.1.0
git push origin refs/tags/v1.1.0
```

Use a new version for each release. Every successful publish also updates `latest`.
Do not run `publish.sh` or `publish.ps1` for tag-triggered releases; those scripts
publish to Docker Hub and create tags themselves.
