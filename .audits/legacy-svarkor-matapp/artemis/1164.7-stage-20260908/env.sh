#!/usr/bin/env bash
# env.sh — T9 (MC 1164.7) local staged-serve environment.
# The staged gate user is a THROWAWAY local-sqlite user (never a real account);
# its name+password are composed here at runtime, not stored anywhere.
export MATAPP_ACCEPT_USER=gate$(date -u +%%Y%%m%%d)
export MATAPP_ACCEPT_PASS=$(tr -dc A-Za-z0-9 < /dev/urandom | head -c 24)
echo "MATAPP_ACCEPT_USER=$MATAPP_ACCEPT_USER (pass generated, held in this shell only)"
