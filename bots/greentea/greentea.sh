#!/bin/bash
# GreenTea runner: compile with javac 17 if build/ is stale, then play.
set -e
cd "$(dirname "$0")"
rebuild=0
if [ ! -d build ] || [ -z "$(ls build/*.class 2>/dev/null)" ]; then
  rebuild=1
else
  for src in *.java; do
    if [ "$src" -nt build ]; then
      rebuild=1
      break
    fi
  done
fi
if [ "$rebuild" = 1 ]; then
  mkdir -p build
  javac -d build *.java
  touch build
fi
exec java -cp build MyBot
