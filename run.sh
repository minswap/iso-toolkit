#!/usr/bin/env bash

set -euo pipefail

docker compose down --volumes --remove-orphans

docker compose --env-file .env up --build
