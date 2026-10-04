#!/usr/bin/env bash
# a1k0n: rebuild the bot if sources are newer, then run it.
# Safe to invoke from any cwd: the engine runs each bot from its own dir,
# but playgame may also be given a repo-root-relative path (run.sh cds here).
set -e
cd "$(dirname "$0")"
# make is a no-op when the binary is up to date; keep its chatter on
# stderr so the engine protocol on stdout stays clean.
make >&2
exec ./MyBot
