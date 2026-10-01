# Native Linux builds use glibc 2.36 (Debian 12) as their compatibility floor.
FROM golang:1.25-bookworm AS helper
WORKDIR /src
COPY scripts/release/build-scc.sh scripts/release/build-scc.sh
RUN bash scripts/release/build-scc.sh

FROM python:3.11-slim-bookworm AS package
RUN apt-get update && apt-get install --yes --no-install-recommends binutils \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /src
COPY scripts/release/requirements.txt scripts/release/requirements.txt
RUN python -m pip install --no-cache-dir -r scripts/release/requirements.txt
COPY --from=helper /src/build/release-input build/release-input
COPY LICENSE NOTICE README.md camp_leverage_all.py pyproject.toml ./
COPY scripts/release/build.py scripts/release/build.py
ARG GITHUB_SHA=local
RUN GITHUB_SHA="$GITHUB_SHA" python scripts/release/build.py

FROM scratch AS export
COPY --from=package /src/dist/release/ /

FROM python:3.11-slim-bookworm AS test
RUN apt-get update && apt-get install --yes --no-install-recommends git ca-certificates \
    && rm -rf /var/lib/apt/lists/*
COPY --from=package /src/dist/release /artifacts
COPY tests/release/fetch-festival.py /test/fetch-festival.py
RUN python /test/fetch-festival.py
COPY tests/release/verify.py /test/verify.py
ENTRYPOINT ["python", "/test/verify.py"]
