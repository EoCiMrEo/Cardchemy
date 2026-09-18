#!/bin/sh
set -eu

task_profile_ready="$(psql --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
    --no-psqlrc -v ON_ERROR_STOP=1 -tAX -c "
    SELECT current_setting('server_version_num')::integer BETWEEN 160000 AND 169999
      AND datlocprovider = 'i' AND daticulocale = 'en-US'
      AND pg_encoding_to_char(encoding) = 'UTF8'
    FROM pg_database WHERE datname = current_database();
")"
if [ "$task_profile_ready" != 't' ]; then
    printf '%s\n' 'Cardchemy fresh database requires PostgreSQL16, UTF8 and ICU en-US; initialization profile was not marked.' >&2
    exit 1
fi
printf '%s\n' 'cardchemy-pg16-alpine3.24-vector0.8.6-icu-en-US-v1' > "$PGDATA/.cardchemy-runtime-profile"
chmod 600 "$PGDATA/.cardchemy-runtime-profile"
