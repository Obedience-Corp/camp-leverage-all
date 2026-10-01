# Releasing Camp Leverage All

## Public repository readiness

The repository can be made public after all checks below pass:

- [x] Apache-2.0 license and copyright notice are present.
- [x] Installation, privacy, score semantics, and failure behavior are documented.
- [x] The package builds a wheel and installs the `camp-leverage-all` plugin executable, avoiding Camp's native `camp leverage` namespace.
- [x] Unit tests and package smoke checks run in GitHub Actions on macOS and Linux.
- [x] A containerized integration fixture verifies that two Camps sharing one remote score it once.
- [x] Public fixtures and runtime defaults contain no user-specific author, Camp, or filesystem assumptions.
- [x] Timeline output identifies its allocation method, explains its current-code allocation, and ends at the headline score.
- [ ] Change repository visibility, then enable GitHub private vulnerability reporting before announcing it.
- [x] The tracked files contain no machine-specific paths, private Camp names, or real author addresses.
- [x] Version `0.3.0` supports source installation for contributors; PyPI publishing is deferred.

The containerized fixture proves repository discovery, Git history, `scc`, packaging, and remote deduplication together without mutating the host filesystem.

## Marketplace readiness

The supported user installation path is the Festival TUI: **Browse catalog**, select `obedience-corp/camp-leverage-all`, and install. A Python wheel or source-install command alone does not make this path available.

- [ ] Publish versioned release archives with an executable `camp-leverage-all` and SHA-256 checksums for each supported platform.
- [ ] Verify bundled Python and `scc`, external Git/Camp requirements, and packaged execution on supported systems.
- [ ] Add the plugin to the official marketplace through its metadata-signing PR workflow.
- [ ] Verify the signed official catalog in a fresh Festival home: TUI installation, saved receipt, and `camp leverage-all --version`.
- [ ] Replace the README's local-catalog preview with a VHS recording of the official marketplace install, then remove the release-pending notice.

The local-catalog walkthrough proves the TUI can install the plugin archive and Camp can dispatch it. Its unsigned fixture is deliberately labeled as a preview; it does not establish public release availability or official metadata trust.

## Version release

1. Update `VERSION` in `camp_leverage_all.py` and `version` in `pyproject.toml`.
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
   camp leverage-all --version
   camp leverage-all --help
   ```

6. Add release notes at `docs/releases/X.Y.Z.md`. Tag the verified commit as `vX.Y.Z` and push the tag. The `Release packages` workflow builds all four native archives, verifies Linux installation through Festival, and publishes archives, Python distributions, and `checksums.txt` after all jobs pass.
7. If PyPI publishing is enabled, use a trusted publisher from the GitHub release workflow rather than a long-lived API token.

## Native Festival packages

The release workflow runs on PRs to verify the same build before tagging. It builds
Linux x86_64/arm64 (glibc 2.36+) and macOS x86_64/arm64 (macOS 15+) archives.
Python 3.11 and `scc` 3.7 are bundled with the executable. Git and Camp remain
external prerequisites. Wheels and source installs use external Python and `scc`.

Each archive contains `camp-leverage-all`, the project license/readme, and an
`assets/` directory with dependency notices and build metadata. Festival installs
those assets into `~/.obey/plugins/camp-leverage-all/`.

Run the complete packaged-installer test locally in Docker:

```sh
docker build -f tests/release/Dockerfile -t camp-leverage-all-release-test .
docker run --rm --network none camp-leverage-all-release-test
```

This test installs from a disposable local catalog, dispatches through real Camp,
checks defaults and deduplication from two registered Camps, verifies missing
prerequisite errors, uninstalls, and rejects a corrupted archive. The local catalog
uses explicit unsigned-content consent solely for the fixture. Official catalog
trust and TUI installation remain separate marketplace launch checks.
