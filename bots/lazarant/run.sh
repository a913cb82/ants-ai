#!/bin/bash
# lazarant runner: compile with javac 17 when build/ is stale, then play.
# The engine runs the bot with this directory as the working directory.
set -e
cd "$(dirname "$0")"

NEED=0
if [ ! -f build/MyBot.class ]; then
    NEED=1
else
    for f in *.java; do
        if [ "$f" -nt build/MyBot.class ]; then
            NEED=1
            break
        fi
    done
fi

if [ "$NEED" -eq 1 ]; then
    mkdir -p build
    javac -d build *.java
fi

exec java -cp build MyBot
