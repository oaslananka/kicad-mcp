FROM python:3.13.12-alpine3.22@sha256:41351b07080ccfaa27bf38dde20de79ee6a0ac74a58c00c6d7a7d96ac4e69716 AS builder

ARG UV_VERSION=0.11.16
ENV UV_NO_CACHE=1
WORKDIR /build

RUN python -m pip install --no-cache-dir --disable-pip-version-check --root-user-action=ignore "uv==${UV_VERSION}"
COPY pyproject.toml uv.lock README.md LICENSE ./
COPY src/ src/
RUN uv build --wheel --out-dir /dist \
  && uv export --frozen --no-dev --no-emit-project \
    --no-hashes \
    --format requirements.txt \
    --output-file /dist/requirements.txt

FROM python:3.13.12-alpine3.22@sha256:41351b07080ccfaa27bf38dde20de79ee6a0ac74a58c00c6d7a7d96ac4e69716 AS runtime

ARG KICAD_MCP_VERSION=0.0.0
ARG VCS_REF=unknown
ARG KICAD_CLI_APK_PACKAGE=

ENV PYTHONDONTWRITEBYTECODE=1 \
  PYTHONUNBUFFERED=1 \
  KICAD_MCP_TRANSPORT=streamable-http \
  KICAD_MCP_HOST=0.0.0.0
WORKDIR /app

LABEL io.modelcontextprotocol.server.name="io.github.oaslananka/kicad-mcp-pro" \
  org.opencontainers.image.title="kicad-mcp-pro" \
  org.opencontainers.image.description="Professional MCP server for KiCad automation" \
  org.opencontainers.image.source="https://github.com/oaslananka/kicad-mcp" \
  org.opencontainers.image.version="${KICAD_MCP_VERSION}" \
  org.opencontainers.image.revision="${VCS_REF}" \
  org.opencontainers.image.licenses="MIT"

RUN apk upgrade --no-cache \
  && if [ -n "${KICAD_CLI_APK_PACKAGE}" ]; then apk add --no-cache "${KICAD_CLI_APK_PACKAGE}"; fi \
  && addgroup -S kicadmcp \
  && adduser -S -G kicadmcp -h /app -s /sbin/nologin kicadmcp

COPY --from=builder /dist/ /tmp/dist/
COPY docker-entrypoint.sh /usr/local/bin/kicad-mcp-pro-entrypoint
RUN python -m pip install --no-cache-dir --disable-pip-version-check --root-user-action=ignore \
    --requirement /tmp/dist/requirements.txt \
    /tmp/dist/*.whl \
  && rm -rf /tmp/dist \
  && chmod 0755 /usr/local/bin/kicad-mcp-pro-entrypoint

USER kicadmcp
EXPOSE 3334
ENTRYPOINT ["kicad-mcp-pro-entrypoint"]
CMD ["--transport", "streamable-http"]
