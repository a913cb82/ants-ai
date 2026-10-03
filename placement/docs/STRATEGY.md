# Strategy

This file names the best plan so far. Call it the top.

## The game

Each new bot plays 30 game slots. The plan picks the opponents for
those slots. Opponents are older bots with known scores.

## The score

After 1000 bots play, rank them by their final scores. Rank them also
by their true hidden scores. The correlation measures how well the
two ranks match. Higher is better. A value of 1.0 is perfect.

A trusted ruler is an older bot with low uncertainty. Uncertainty
falls as a bot plays more games.

## The top plan

Iteration 34 holds the top. It scored 0.9930 on seeds 0 to 4. It
scored 0.9932 on seeds 5 to 9. It scored 0.9935 on seeds 10 to 14.
The mean over all 15 seeds is 0.9932.

The plan has three parts:

1. First game, 10 players: the 9 opponents sit at evenly spaced ranks
   of the older bots. Crowded ranks get more opponents.
2. Second game, 6 players: the 5 opponents sit near the bot. All 5
   are trusted rulers.
3. Last 7 games, 2 players each: each opponent is the bot that teaches
   the most. Teaching power means a close score plus high uncertainty.

## What we learned

Duels first fail. Three tries lost much ground. Targeting the most
instructive opponent hurts at the start but helps at the end.

Details live in `WORKLOG.md`. Old rounds live in
`placement/archive/`. Update this file when the top moves.
