#!/bin/bash
# fourmidable launcher: compile with javac 17 if build/ is stale, then run.
set -e
cd "$(dirname "$0")"
if [ ! -d build ] || [ -n "$(find . -maxdepth 1 -name '*.java' -newer build -print -quit 2>/dev/null)" ]; then
  mkdir -p build
  javac -d build *.java
fi
exec java -cp build MyBot
