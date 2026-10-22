# Releasing

Release artifacts are published on GitHub. PyPI publishing is not configured.

1. Make a focused PR. Change `web_crawling.__version__` (the single package-version source), update the changelog, and add `docs/releases/vX.Y.Z.md`.
2. Review compatibility changes and all five test jobs, the dependency audit and three package jobs. Package checks install the wheel and declared dependencies into a fresh environment, then exercise it outside the checkout.
3. Merge the reviewed PR after CI passes. Tag the merged commit with `vX.Y.Z` and push that tag. Do not move or reuse a published tag.
4. The Release workflow reruns the reusable CI gates. Publication requires the tagged commit to belong to the default branch, both distributions to match the tag, and release notes to exist.
5. The workflow publishes the validated Linux-built universal wheel and source distribution with `SHA256SUMS`. Verify the workflow conclusion, release target, asset names and checksums. Retain a failed run for diagnosis rather than manually publishing unvalidated files.

For local artifact checks, use the external-SSD cache setup, `python -m build --no-isolation` with existing build tools, and `python scripts/prepare_release.py --dist <external-dist-path> --tag vX.Y.Z`. A mismatched tag must fail before generating checksums.

Versioning is pre-1.0: document observable compatibility changes, use minor versions for added behavior, and patch versions for compatible fixes. Each published artifact is tied to a fixed tag; GitHub checksums detect transfer errors but are not an independent signature.
