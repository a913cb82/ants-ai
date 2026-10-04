#!/bin/bash
# xathis runner: compile when stale, then run.
# Engine runs each bot from its own dir, so all paths are relative.
set -e
cd "$(dirname "$0")"
STALE=0
if [ ! -d build ]; then
  STALE=1
else
  for f in *.java; do
    if [ "$f" -nt "build" ]; then
      STALE=1
      break
    fi
  done
fi
if [ "$STALE" -eq 1 ]; then
  mkdir -p build
  javac -d build *.java
  # bump build dir mtime past sources so the next run is a no-op
  touch build
fi
exec java -cp build MyBot
