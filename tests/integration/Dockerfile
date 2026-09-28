FROM golang:1.25-bookworm AS scc-build

RUN GOBIN=/out go install github.com/boyter/scc/v3@v3.7.0

FROM python:3.11-slim-bookworm

RUN apt-get update \
    && apt-get install --yes --no-install-recommends ca-certificates git \
    && apt-get clean \
    && find /var/lib/apt/lists -mindepth 1 -delete

COPY --from=scc-build /out/scc /usr/local/bin/scc

WORKDIR /app
COPY LICENSE NOTICE README.md campaign_leverage.py pyproject.toml ./
RUN python -m pip install --no-cache-dir --disable-pip-version-check .

COPY tests/integration/run.sh /usr/local/bin/campaign-leverage-integration
RUN chmod +x /usr/local/bin/campaign-leverage-integration

ENTRYPOINT ["campaign-leverage-integration"]
