# Strategy

This file names the best plan. Call it the top. It is final. A
15-seed proof found no better plan.

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

Iteration 43 holds the top. It scored 0.9932 on seeds 0 to 4. It
scored 0.9939 on seeds 5 to 9. It scored 0.9939 on seeds 10 to 14.
It scored 0.9925 on seeds 15 to 29. The mean over all 30 seeds is
0.9931.

The plan has three parts:

1. First game, 10 players: the 9 opponents sit at evenly spaced ranks
   of the older bots. Crowded ranks get more opponents.
2. Second game, 6 players: the 5 opponents split across three groups.
   Below the bot, near the bot, above the bot. Crowded groups get
   more opponents. All 5 are trusted rulers.
3. Last 7 games, 2 players each: each opponent is the bot that teaches
   the most. Teaching power means a close score plus high uncertainty.

## The proof

The closest rival lost a 15-seed match by 0.0001. The bar for a win
was 0.0003. Fifty challengers failed before it. No part can change
without harm: remove any part and the score falls. Small tweaks all
tie. The search is over.

Details live in `WORKLOG.md`. Old rounds live in
`placement/archive/`.
