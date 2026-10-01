# Contributing

Camp Leverage All accepts focused bug fixes, tests, and documentation improvements.

1. Open an issue before changing the score definition or repository-selection semantics.
2. Create a branch from `main`.
3. Keep the runtime dependency-free unless a new dependency has a clear operational benefit.
4. Run the checks below.
5. Sign off every commit with `git commit --signoff` to certify the [Developer Certificate of Origin](https://developercertificate.org/).

```sh
python3 -m unittest -v
python3 -m compileall -q camp_leverage_all.py
ruff check .
python3 -m build
docker build -f tests/integration/Dockerfile -t camp-leverage-all-integration .
docker run --rm --network none camp-leverage-all-integration
docker run --rm --network none --entrypoint python camp-leverage-all-integration /app/tests/terminal/render_pty.py
docker build -f tests/release/Dockerfile -t camp-leverage-all-release-test .
docker run --rm --network none camp-leverage-all-release-test
```

A behavior change should include a test for its reachable success or failure path. Tests that create, delete, or rewrite repositories must run in containerized isolation.

Pull requests should explain the user-visible result, the calculation or discovery behavior affected, and the checks that passed.
