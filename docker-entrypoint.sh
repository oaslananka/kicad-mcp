#!/bin/sh
set -eu

if [ "$#" -gt 0 ] && [ "$1" = "kicad-mcp-pro" ]; then
  exec "$@"
fi

exec kicad-mcp-pro "$@"
