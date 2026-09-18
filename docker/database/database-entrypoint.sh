#!/bin/sh
set -eu

profile='cardchemy-pg16-alpine3.24-vector0.8.6-icu-en-US-v1'
task_pgdata="${PGDATA:-/var/lib/postgresql/data}"
if [ -s "$task_pgdata/PG_VERSION" ]; then
    if [ ! -f "$task_pgdata/.cardchemy-runtime-profile" ] \
        || [ "$(cat "$task_pgdata/.cardchemy-runtime-profile")" != "$profile" ]; then
        printf '%s\n' 'Cardchemy database prerequisite: legacy or incompatible data requires logical backup/restore into a separate reviewed ICU target. PostgreSQL was not started on the original data directory; its database files were not modified.' >&2
        exit 1
    fi
fi
exec /usr/local/bin/docker-entrypoint.sh "$@"
