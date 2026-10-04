#!/bin/bash
# runevision bot runner: rebuild MyBot.exe when any .cs source is newer,
# then run it under mono. The engine runs this from the bot's own dir.
set -e
cd "$(dirname "$0")"
if [ ! -f MyBot.exe ] || [ -n "$(find . -maxdepth 2 -name '*.cs' -newer MyBot.exe -print -quit)" ]; then
    mcs -out:MyBot.exe *.cs PowerCollections/*.cs
fi
exec mono MyBot.exe "$@"
