# Autoresearch tree

Coders work in parallel. Exams run serial (one at a time).
The tree records every entry. The frontier is the unevaluated
leaves. Each exam takes the next leaf per the rule below.

## Rule

Group leaves by line (one line per approach). Cycle the lines
round-robin. Take the oldest leaf of the next line. New lines
join the cycle at once. No line jumps the queue.

## Worktrees

The coordinator owns a pool of 6 paths: /tmp/cbt-0 to /tmp/cbt-5.
One path per active coder. Spawn recreates the path fresh,
detached, at the leaf parent. The report carries parent and
child sha. The coordinator records the edge, then removes
the path. No path is reused without recreate.

## Frontier

| Leaf | Line | Parent | State |
|---|---|---|---|
| Xathis5 | xathis | Xathis4 | coded, queued |
| Dirichlet5 | dirichlet | Dirichlet4 | coded, queued |
| Influence4 | influence | Influence3 | coded, queued |
| Greedy3 | greedy | Greedy2 | coded, queued |
| Softmax2 | softmax | Softmax | picked, queued |
| Tables | tables | Crowd | EXAM RUNNING |
| Fixing2 | fixing | Fixing | picked, queued |
| TwoStage impl | twostage | Crowd | unpicked |
