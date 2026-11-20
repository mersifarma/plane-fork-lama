#!/usr/bin/env bash
# Deploy Plane on a server from this checkout. Images are built from source, so this branch's changes ship.
# All settings live in one file, plane.env.
#
#   bash deploy.sh    first run: creates plane.env with fresh secrets and stops so you can edit it
#                     next runs: git pull, build images, (re)start everything, smoke-test
#   bash deploy.sh db start only the database (deployments/db, settings in db.env) on this host
set -euo pipefail
cd "$(dirname "$0")"

ENV_FILE=plane.env
DIR=deployments/cli/community
getenv() { grep -E "^$1=" "$ENV_FILE" | cut -d= -f2- || true; }
setenv() { sed -i "s|^$1=.*|$1=$2|" "$ENV_FILE"; }
rand() { LC_ALL=C tr -dc 'a-z0-9' < /dev/urandom | head -c "$1" || true; }
compose() {
  local files=(-f "$DIR/docker-compose.yml" -f "$DIR/build.yml")
  case "$(getenv PGHOST)" in "" | plane-db) ;; *) files+=(-f "$DIR/external-db.yml") ;; esac
  docker compose -p plane-server --env-file "$ENV_FILE" "${files[@]}" "$@"
}

docker compose version > /dev/null 2>&1 || { echo "Docker with the compose plugin is required." >&2; exit 1; }

if [ "${1:-}" = db ]; then
  if [ ! -f db.env ]; then
    printf '%s\n' "POSTGRES_USER=plane" "POSTGRES_PASSWORD=$(rand 32)" "POSTGRES_DB=plane" "POSTGRES_PORT=5432" \
      "# address to listen on; a private IP keeps the database off the public internet" "DB_BIND=0.0.0.0" > db.env
    echo "Created db.env with a fresh password."
  fi
  docker compose --env-file db.env -f deployments/db/docker-compose.yml up -d
  echo "Database is up. On the app server, set these in plane.env:"
  echo "  PGHOST=$(hostname -I 2> /dev/null | awk '{print $1}')   <- this host's IP, reachable from the app server"
  grep -E '^POSTGRES_(USER|PASSWORD|DB|PORT)=' db.env | sed 's/^/  /'
  exit 0
fi

if [ ! -f "$ENV_FILE" ]; then
  cp "$DIR/variables.env" "$ENV_FILE"
  setenv SECRET_KEY "$(rand 50)"
  setenv LIVE_SERVER_SECRET_KEY "$(rand 50)"
  setenv AWS_ACCESS_KEY_ID "$(rand 20)"
  setenv AWS_SECRET_ACCESS_KEY "$(rand 40)"
  setenv LISTEN_HTTP_PORT 2028
  # browsers drop :80 from Origin, so if LISTEN_HTTP_PORT becomes 80, drop the :port from these two
  setenv WEB_URL 'http://${APP_DOMAIN}:${LISTEN_HTTP_PORT}'
  setenv CORS_ALLOWED_ORIGINS 'http://${APP_DOMAIN}:${LISTEN_HTTP_PORT}'
  cat << EOF
Created $ENV_FILE with fresh secrets. Edit it, then run 'bash deploy.sh' again:
  APP_DOMAIN          domain or IP users open in the browser, without port
  LISTEN_HTTP_PORT    host port for the web UI (set to 2028)
  Own MinIO / S3:     USE_MINIO=0, AWS_S3_ENDPOINT_URL, AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_S3_BUCKET_NAME
                      (the endpoint must be reachable from this server AND from users' browsers)
  Separate database:  run 'bash deploy.sh db' on the DB host, then copy PGHOST and POSTGRES_* here
EOF
  exit 1
fi

git pull --ff-only
compose build
compose up -d --remove-orphans

PORT=$(getenv LISTEN_HTTP_PORT)
URL="http://localhost:${PORT:-80}/api/instances/"
echo "Waiting for Plane (migrations can take a few minutes)..."
for _ in $(seq 1 60); do curl -fs -o /dev/null "$URL" && break; sleep 5; done
curl -fs -o /dev/null "$URL" || { echo "Plane did not come up. Check: docker compose -p plane-server logs api" >&2; exit 1; }

echo "Object storage check:"
compose exec -T api python manage.py create_bucket
echo "Plane is up: http://$(getenv APP_DOMAIN):${PORT:-80}  (first time: open /god-mode/ to create the admin)"
