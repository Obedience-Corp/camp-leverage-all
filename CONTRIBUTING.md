# Contributing

Campaign Leverage accepts focused bug fixes, tests, and documentation improvements.

1. Open an issue before changing the score definition or repository-selection semantics.
2. Create a branch from `main`.
3. Keep the runtime dependency-free unless a new dependency has a clear operational benefit.
4. Run the checks below.
5. Sign off every commit with `git commit --signoff` to certify the [Developer Certificate of Origin](https://developercertificate.org/).

```sh
python3 -m unittest -v
python3 -m compileall -q campaign_leverage.py
ruff check .
python3 -m build
docker build -f tests/integration/Dockerfile -t campaign-leverage-integration .
docker run --rm --network none campaign-leverage-integration
```

A behavior change should include a test for its reachable success or failure path. Tests that create, delete, or rewrite repositories must run in containerized isolation.

Pull requests should explain the user-visible result, the calculation or discovery behavior affected, and the checks that passed.
