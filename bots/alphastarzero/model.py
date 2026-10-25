"""Policy: network shape, masking, act, save. No game, no training."""

from __future__ import annotations

import torch

import features
from features import ACTIONS


class CNNPolicy(torch.nn.Module):
    """Small convnet: (6, H, W) window -> 5 action logits + 1 value.

    Adaptive pooling keeps it radius-agnostic: any odd-sized window in,
    5 logits out. ~6k params; microseconds per forward on CPU.
    The value head shares the trunk (+129 params, zero-initialized so
    early value estimates start at 0).
    """

    def __init__(self, channels: int | None = None) -> None:
        super().__init__()
        channels = len(features.CHANNELS) if channels is None else channels
        self.conv1 = torch.nn.Conv2d(channels, 16, kernel_size=3, padding=1)
        self.conv2 = torch.nn.Conv2d(16, 32, kernel_size=3, padding=1)
        self.pool = torch.nn.AdaptiveAvgPool2d((2, 2))
        self.head = torch.nn.Linear(32 * 4, len(ACTIONS))
        self.value = torch.nn.Linear(32 * 4, 1)
        torch.nn.init.zeros_(self.value.weight)
        torch.nn.init.zeros_(self.value.bias)

    def trunk(self, x: torch.Tensor) -> torch.Tensor:
        """x: (B, C, H, W) -> shared features (B, 128)."""
        x = torch.relu(self.conv1(x))
        x = torch.relu(self.conv2(x))
        return self.pool(x).flatten(start_dim=1)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """x: (B, 6, H, W) -> logits (B, 5)."""
        return self.head(self.trunk(x))

    def values(self, x: torch.Tensor) -> torch.Tensor:
        """x: (B, 6, H, W) -> state values (B,)."""
        return self.value(self.trunk(x)).squeeze(-1)


def legal_mask(
    window: torch.Tensor, blocked: frozenset = frozenset()
) -> torch.Tensor:
    """True for enterable destinations.

    Dest offsets read straight off the window: the ant is the center.
    A tile is enterable when it holds neither water nor visible food
    (the engine ignores moves into both: tools/ants.py validate_orders).
    blocked carries the live reservation set as action names, so two
    ants never take the same tile.
    """
    radius = (window.shape[-2] - 1) // 2
    ok = []
    for action in ACTIONS:
        dr, dc = features.OFFSETS[action]
        cell = (radius + dr, radius + dc)
        clear = (
            window[features.WATER_CHANNEL, cell[0], cell[1]] <= 0
            and window[features.FOOD_CHANNEL, cell[0], cell[1]] <= 0
        )
        ok.append(bool(clear) and action not in blocked)
    return torch.tensor(ok, dtype=torch.bool)


def masked_logits(
    policy: CNNPolicy, window: torch.Tensor, blocked: frozenset = frozenset()
) -> torch.Tensor:
    """No-grad masked logits for acting. Nothing legal falls back to
    stay: the mask keeps stay legal and kills the rest."""
    with torch.no_grad():
        return _apply_mask(policy(window.unsqueeze(0)).flatten(), window, blocked)


def _with_stay(masks: torch.Tensor) -> torch.Tensor:
    """Empty rows (nothing legal) fall back to stay instead of NaN."""
    fallback = torch.zeros_like(masks)
    fallback[..., ACTIONS.index("stay")] = True
    return torch.where(masks.any(dim=-1, keepdim=True), masks, fallback)


def masked_log_softmax(
    policy: CNNPolicy,
    windows: torch.Tensor,
    masks: torch.Tensor,
) -> torch.Tensor:
    """Grad-enabled masked log-probs for training: (B, 5).

    Masks come from the stored per-decision legal sets, so the learner
    scores actions under exactly the distribution the bot acted with.
    """
    logits = policy(windows)
    return torch.log_softmax(
        torch.where(_with_stay(masks), logits, torch.tensor(-1e9)), dim=1
    )


def _apply_mask(
    logits: torch.Tensor, window: torch.Tensor, blocked: frozenset
) -> torch.Tensor:
    use = _with_stay(legal_mask(window, blocked).unsqueeze(0)).flatten()
    return torch.where(use, logits, torch.tensor(-1e9))


def act_ranked(
    policy: CNNPolicy, window: torch.Tensor, blocked: frozenset = frozenset()
) -> list:
    """All actions, best first by masked logit."""
    order = torch.argsort(masked_logits(policy, window, blocked), descending=True)
    return [ACTIONS[int(i)] for i in order]


def _probs_tensor(
    policy: CNNPolicy,
    window: torch.Tensor,
    temperature: float,
    blocked: frozenset = frozenset(),
) -> torch.Tensor:
    return torch.softmax(
        masked_logits(policy, window, blocked) / temperature, dim=0
    )


def act_probs(
    policy: CNNPolicy,
    window: torch.Tensor,
    temperature: float = 1.0,
    blocked: frozenset = frozenset(),
) -> dict[str, float]:
    p = _probs_tensor(policy, window, temperature, blocked)
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
    return ACTIONS[int(torch.multinomial(_probs_tensor(policy, window, temperature, blocked), 1))]


def state_dict_to_lists(policy: CNNPolicy) -> dict:
    return {k: v.detach().tolist() for k, v in policy.state_dict().items()}


def lists_to_state_dict(lists: dict) -> dict:
    return {k: torch.tensor(v, dtype=torch.float32) for k, v in lists.items()}
