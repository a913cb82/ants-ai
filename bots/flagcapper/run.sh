#!/bin/sh
# FlagCapper launcher: rebuild ./MyBot with gcc when sources are newer, then exec it.
# Build mirrors the upstream Makefile (gcc -O3 -funroll-loops; link -O2 -lm).
# See README.md for the one-word deviation from the 2011 sources.
set -eu
cd "$(dirname "$0")"
STALE=0
[ -x ./MyBot ] || STALE=1
if [ "$STALE" -eq 0 ]; then
  for f in MyBot.c YourCode.c ants.c ants.h Exploration.c BattleResolution.c; do
    if [ "$f" -nt ./MyBot ]; then STALE=1; break; fi
  done
fi
if [ "$STALE" -eq 1 ]; then
  gcc -O3 -funroll-loops -c MyBot.c -o MyBot.o
  gcc -O3 -funroll-loops -c YourCode.c -o YourCode.o
  gcc -O3 -funroll-loops -c ants.c -o ants.o
  gcc -O2 MyBot.o YourCode.o ants.o -o MyBot -lm
fi
exec ./MyBot
