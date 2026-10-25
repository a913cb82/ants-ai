"""Linear policy head for the AlphaStarZero bot.

Forward pass runs through torch (single Linear layer today), so the
self-play trainer differentiates the exact code the bot runs. choose()
is the greedy inference path used inside the 1000 ms turn budget:
mask water, argmax, deterministic order tiebreak.
"""

from __future__ import annotations

import torch

from features import ACTIONS

FEATURE_KEYS = ("passable", "food", "threat", "crowd")

# Extra penalty applied to already-crowded destinations when the caller
# reports live reservations the features were not built with. The normal
# path bakes reservations into features; this is a second line of defense.
STALE_CROWD_PENALTY = 2.0


class LinearPolicy(torch.nn.Module):
    """One shared linear layer: score(action) = w . features(action)."""

    def __init__(self, weights: dict[str, float] | None = None) -> None:
        super().__init__()
        self.linear = torch.nn.Linear(len(FEATURE_KEYS), 1, bias=False)
        if weights is not None:
            self.load_weights(weights)

    def load_weights(self, weights: dict[str, float]) -> None:
        with torch.no_grad():
            row = torch.tensor(
                [[weights[k] for k in FEATURE_KEYS]], dtype=torch.float32
            )
            self.linear.weight.copy_(row)

    def export_weights(self) -> dict[str, float]:
        with torch.no_grad():
            row = self.linear.weight.detach().flatten().tolist()
        return {k: float(v) for k, v in zip(FEATURE_KEYS, row, strict=True)}

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """x: (n_actions, n_features) -> scores (n_actions,)."""
        return self.linear(x).flatten()

    def probs(
        self, feats: dict[str, dict[str, float]], temperature: float = 1.0
    ) -> dict[str, float]:
        x = torch.tensor(
            [[feats[a][k] for k in FEATURE_KEYS] for a in ACTIONS],
            dtype=torch.float32,
        )
        mask = torch.tensor(
            [feats[a]["passable"] > 0 for a in ACTIONS], dtype=torch.bool
        )
        scores = self.forward(x)
        if not bool(mask.any()):
            return {a: 1.0 / len(ACTIONS) for a in ACTIONS}
        scores = torch.where(
            mask, scores, torch.tensor(-1e9, dtype=torch.float32)
        )
        p = torch.softmax(scores / temperature, dim=0)
        return {a: float(v) for a, v in zip(ACTIONS, p.tolist(), strict=True)}


def choose(
    feats: dict[str, dict[str, float]],
    weights: dict[str, float],
    occupied: set[tuple[int, int]] | frozenset[tuple[int, int]] = frozenset(),
) -> str:
    """Greedy legal action. Water is masked, never chosen if any land
    move exists. occupied only strengthens the baked-in crowd cue."""
    policy = LinearPolicy(weights)
    with torch.no_grad():
        x = torch.tensor(
            [[feats[a][k] for k in FEATURE_KEYS] for a in ACTIONS],
            dtype=torch.float32,
        )
        scores = policy.forward(x)
        if occupied:
            crowd = torch.tensor(
                [feats[a]["crowd"] for a in ACTIONS], dtype=torch.float32
            )
            scores = scores - STALE_CROWD_PENALTY * crowd
        mask = torch.tensor(
            [feats[a]["passable"] > 0 for a in ACTIONS], dtype=torch.bool
        )
        if not bool(mask.any()):
            return "stay"
        scores = torch.where(
            mask, scores, torch.tensor(-1e9, dtype=torch.float32)
        )
        best = int(torch.argmax(scores))
    return ACTIONS[best]
