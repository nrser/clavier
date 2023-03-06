#!/usr/bin/env bash
poetry run \
  -- python -m clavier.srv.entrypoint build \
    --name clavex \
    --install-dir ./bin \
    --start-env CLAVIER_SRV=1 \
    -- poetry run clavex
