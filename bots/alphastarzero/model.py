"""Policy heads for the AlphaStarZero bot.

LinearPolicy is the v0 cue baseline. CNNPolicy is the minimum feasible
self-play policy: two convolutions over the 6-channel local window,
global pooling, one linear layer to 5 action logits. Both run through
torch so the trainer differentiates the exact code the bot runs.
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


ACTION_OFFSETS = {
    "n": (-1, 0),
    "e": (0, 1),
    "s": (1, 0),
    "w": (0, -1),
    "stay": (0, 0),
}

# Water channel index in features.CHANNELS.
WATER_CHANNEL = 0


class CNNPolicy(torch.nn.Module):
    """Small convnet: (6, H, W) window -> 5 action logits.

    Adaptive pooling keeps it radius-agnostic: any odd-sized window in,
    5 logits out. ~6k params; microseconds per forward on CPU.
    """

    def __init__(self, channels: int = 6) -> None:
        super().__init__()
        self.conv1 = torch.nn.Conv2d(channels, 16, kernel_size=3, padding=1)
        self.conv2 = torch.nn.Conv2d(16, 32, kernel_size=3, padding=1)
        self.pool = torch.nn.AdaptiveAvgPool2d((2, 2))
        self.head = torch.nn.Linear(32 * 4, len(ACTIONS))

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """x: (B, 6, H, W) -> logits (B, 5)."""
        x = torch.relu(self.conv1(x))
        x = torch.relu(self.conv2(x))
        x = self.pool(x).flatten(start_dim=1)
        return self.head(x)


def _legal_mask(window: torch.Tensor, blocked: frozenset = frozenset()) -> torch.Tensor:
    """True for actions that are water-free and not blocked.

    Dest offsets read straight off the window: the ant is the center.
    blocked carries the live reservation set as action names, so two
    ants never take the same tile."""
    radius = (window.shape[-2] - 1) // 2
    ok = []
    for action in ACTIONS:
        dr, dc = ACTION_OFFSETS[action]
        water_free = window[WATER_CHANNEL, radius + dr, radius + dc] <= 0
        ok.append(bool(water_free) and action not in blocked)
    return torch.tensor(ok, dtype=torch.bool)


def masked_logits(
    policy: CNNPolicy, window: torch.Tensor, blocked: frozenset = frozenset()
) -> torch.Tensor:
    """Logits with illegal destinations sent to -inf. Nothing legal
    falls back to stay: the mask keeps stay legal and kills the rest."""
    with torch.no_grad():
        logits = policy(window.unsqueeze(0)).flatten()
    mask = _legal_mask(window, blocked)
    if not bool(mask.any()):
        mask = torch.tensor([a == "stay" for a in ACTIONS], dtype=torch.bool)
    return torch.where(mask, logits, torch.tensor(-1e9))


def act_ranked(
    policy: CNNPolicy, window: torch.Tensor, blocked: frozenset = frozenset()
) -> list:
    """All actions, best first by masked logit."""
    order = torch.argsort(masked_logits(policy, window, blocked), descending=True)
    return [ACTIONS[int(i)] for i in order]


def act_probs(
    policy: CNNPolicy,
    window: torch.Tensor,
    temperature: float = 1.0,
    blocked: frozenset = frozenset(),
) -> dict[str, float]:
    p = torch.softmax(
        masked_logits(policy, window, blocked) / temperature, dim=0
    )
    return {a: float(v) for a, v in zip(ACTIONS, p.tolist(), strict=True)}


def act_greedy(
    policy: CNNPolicy, window: torch.Tensor, blocked: frozenset = frozenset()
) -> str:
    return ACTIONS[int(torch.argmax(masked_logits(policy, window, blocked)))]


def sample(
    policy: CNNPolicy,
    window: torch.Tensor,
    temperature: float,
    blocked: frozenset = frozenset(),
) -> str:
    p = torch.softmax(
        masked_logits(policy, window, blocked) / temperature, dim=0
    )
    return ACTIONS[int(torch.multinomial(p, 1))]


def state_dict_to_lists(policy: CNNPolicy) -> dict:
    return {k: v.detach().tolist() for k, v in policy.state_dict().items()}


def lists_to_state_dict(lists: dict) -> dict:
    return {k: torch.tensor(v, dtype=torch.float32) for k, v in lists.items()}
