# Placement Match Spec

## Goal
Select game sizes and opponents to lower placement error.

## Ratings
Use OpenSkill BradleyTerryFull.
Start each bot at mu=25 and sigma=8.33.
Update all players after each game with league/ratings.py.

## New Bots
Sample mu_true from Uniform[-50,100] for each new bot.
Add 1000 bots in fixed order.

## Budget
Give each new bot 30 slots.
Count all players in each game.
Select size from 2 to 10.
A 2-player game costs 2 slots.
A 10-player game costs 10 slots.
Use smaller games until the pool allows the selected size.

## Outcome
Sample performance from Normal(mu_true, 4.17) for each player.
Rank players by performance.
Rank 1 wins the game.

## Policy
Select opponents only from placed bots.
Reuse opponents as needed.
Use only mu, sigma, and game count for selection.
Do not use mu_true for selection.
Select each next game after the last result.

## Error
Record mu at the end of placement.
Later games do not change the recorded value.

## Evaluation
Score the run as corr(recorded mu, mu_true) across all 1000 bots.
Repeat for 5 seeds.
Report the mean correlation. Higher wins.

## Running the agent
Start your coding agent in this repo.
Give the agent full permissions.
Then prompt:

```
Read placement/docs/PROGRAM.md. Do the setup. Start the loop.
```

The agent works alone after that.
It commits, evaluates, measures, and repeats.
`docs/PROGRAM.md` is the skill.
