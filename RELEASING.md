# Releasing Campaign Leverage

## Public repository readiness

The repository can be made public after all checks below pass:

- [x] Apache-2.0 license and copyright notice are present.
- [x] Installation, privacy, score semantics, and failure behavior are documented.
- [x] The package builds a wheel and installs both `leverage` and `campaign-leverage`.
- [x] Unit tests and package smoke checks run in GitHub Actions on macOS and Linux.
- [x] A containerized integration fixture verifies that two campaigns sharing one remote score it once.
- [ ] Change repository visibility, then enable GitHub private vulnerability reporting before announcing it.
- [x] The tracked files contain no machine-specific paths, private campaign names, or real author addresses.
- [x] Version `0.1.0` will install directly from GitHub; PyPI publishing is deferred.

The containerized fixture proves repository discovery, Git history, `scc`, packaging, and remote deduplication together without mutating the host filesystem.

## Version release

1. Update `VERSION` in `campaign_leverage.py` and `version` in `pyproject.toml`.
2. Update any user-visible behavior in `README.md` and `SPEC.md`.
3. Run the development checks from `CONTRIBUTING.md`.
4. Build and inspect the distributions:

   ```sh
   rm -rf build dist
   python3 -m build
   python3 -m zipfile --list dist/*.whl
   ```

5. Install the wheel into a clean virtual environment and run:

   ```sh
   leverage --version
   leverage --help
   ```

6. Tag the verified commit as `vX.Y.Z` and create a GitHub release.
7. If PyPI publishing is enabled, use a trusted publisher from the GitHub release workflow rather than a long-lived API token.
