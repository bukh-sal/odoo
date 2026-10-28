#!/bin/bash
set -euo pipefail
cp /run/secrets/init-db.sh /docker-entrypoint-initdb.d/10-modular-role.sh
exec docker-entrypoint.sh "$@"
