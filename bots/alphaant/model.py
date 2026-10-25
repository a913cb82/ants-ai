"""Policy: network shape, masking, act, save. No game, no training."""

from __future__ import annotations

import torch

import features
from features import ACTIONS

# Dihedral action permutations (mirror ml/algorithm.py ROT_PERM, which
# maps a CCW-rotated frame back: n->w->s->e). UNROT[k] gathers logits
# from the k-turns-CCW frame into the canonical frame. UNFLIP mirrors
# a left-right flip (e<->w) back. Both are their own bookkeeping:
# the game is symmetric, the network need not learn to be.
ROT_PERM = (3, 0, 1, 2, 4)
UNFLIP = (0, 3, 2, 1, 4)


def _unrot(k: int) -> tuple:
    # r_k is k CCW turns of x; canonical-a is r_k-ROT_PERM^k[a]
    # (matches algorithm._rotate_item: (R(w), ROT_PERM[a]) is one
    # decision). Gather canonical out of the rotated logits with it.
    perm = tuple(range(5))
    for _ in range(k % 4):
        perm = tuple(ROT_PERM[i] for i in perm)
    return perm


UNROT = {k: _unrot(k) for k in range(4)}


class CNNPolicy(torch.nn.Module):
    """Small convnet: (6, H, W) window -> 5 action logits + 1 value.

    arch="base": 2 conv layers (16/32ch), 5x5 receptive field, 2x2
    pool -> 128 dims, ~6.3k params. The periphery reaches the heads
    only as pooled smear.
    arch="deep": 4 narrow conv layers (8/12/16/16ch), 9x9 receptive
    field covering the whole window, 3x3 pool -> 144 dims, ~6.3k
    params. Same budget, strictly more expressive; the A/B challenger.

    Adaptive pooling keeps both radius-agnostic: any odd-sized window
    in, 5 logits out. The critic owns a SEPARATE conv stack (same tiny
    shapes, vconv* keys) with the value head on it; values() runs the
    value trunk, so actor gradients never fight critic gradients and
    vice versa. The value head is zero-initialized so early value
    estimates start at 0. Fully ant-local: no global inputs, no
    memory, no communication.
    """

    def __init__(
        self, channels: int | None = None, arch: str = "base"
    ) -> None:
        super().__init__()
        assert arch in ("base", "deep"), arch
        self.arch = arch
        channels = len(features.CHANNELS) if channels is None else channels
        if arch == "base":
            self.conv1 = torch.nn.Conv2d(channels, 16, kernel_size=3, padding=1)
            self.conv2 = torch.nn.Conv2d(16, 32, kernel_size=3, padding=1)
            self.vconv1 = torch.nn.Conv2d(channels, 16, kernel_size=3, padding=1)
            self.vconv2 = torch.nn.Conv2d(16, 32, kernel_size=3, padding=1)
            self.pool = torch.nn.AdaptiveAvgPool2d((2, 2))
            trunk_dim = 32 * 4
        else:
            self.conv1 = torch.nn.Conv2d(channels, 8, kernel_size=3, padding=1)
            self.conv2 = torch.nn.Conv2d(8, 12, kernel_size=3, padding=1)
            self.conv3 = torch.nn.Conv2d(12, 16, kernel_size=3, padding=1)
            self.conv4 = torch.nn.Conv2d(16, 16, kernel_size=3, padding=1)
            self.vconv1 = torch.nn.Conv2d(channels, 8, kernel_size=3, padding=1)
            self.vconv2 = torch.nn.Conv2d(8, 12, kernel_size=3, padding=1)
            self.vconv3 = torch.nn.Conv2d(12, 16, kernel_size=3, padding=1)
            self.vconv4 = torch.nn.Conv2d(16, 16, kernel_size=3, padding=1)
            self.pool = torch.nn.AdaptiveAvgPool2d((3, 3))
            trunk_dim = 16 * 9
        self.head = torch.nn.Linear(trunk_dim, len(ACTIONS))
        self.value = torch.nn.Linear(trunk_dim, 1)
        torch.nn.init.zeros_(self.value.weight)
        torch.nn.init.zeros_(self.value.bias)

    def trunk(self, x: torch.Tensor) -> torch.Tensor:
        """x: (B, C, H, W) -> actor features (B, trunk_dim)."""
        x = torch.relu(self.conv1(x))
        x = torch.relu(self.conv2(x))
        if self.arch == "deep":
            x = torch.relu(self.conv3(x))
            x = torch.relu(self.conv4(x))
        return self.pool(x).flatten(start_dim=1)

    def vtrunk(self, x: torch.Tensor) -> torch.Tensor:
        """x: (B, C, H, W) -> critic features (B, trunk_dim)."""
        x = torch.relu(self.vconv1(x))
        x = torch.relu(self.vconv2(x))
        if self.arch == "deep":
            x = torch.relu(self.vconv3(x))
            x = torch.relu(self.vconv4(x))
        return self.pool(x).flatten(start_dim=1)

    def _d4_logits(self, x: torch.Tensor) -> torch.Tensor:
        """Mean logits over the 8 dihedral orientations, mapped back.

        Each orientation is a legal view of the same position (rotations
        and mirrors preserve the game), so their mapped-back logits are
        8 estimates of one distribution. The mean is exactly equivariant
        by group closure: no orientation is privileged, including at
        act time. Costs 8x the forward; the net is tiny."""
        rots = [x]
        for _ in range(3):
            rots.append(torch.rot90(rots[-1], 1, (2, 3)))
        total = None
        count = 0
        for k, r in enumerate(rots):
            for flipped, t in ((False, r), (True, torch.flip(r, (3,)))):
                out = self.head(self.trunk(t))
                if flipped:
                    out = out[:, list(UNFLIP)]
                out = out[:, list(UNROT[k])]
                total = out if total is None else total + out
                count += 1
        return total / count

    def _d4_values(self, x: torch.Tensor) -> torch.Tensor:
        """Mean value over orientations: invariant by construction."""
        rots = [x]
        for _ in range(3):
            rots.append(torch.rot90(rots[-1], 1, (2, 3)))
        total = None
        count = 0
        for r in rots:
            for t in (r, torch.flip(r, (3,))):
                out = self.value(self.vtrunk(t))
                total = out if total is None else total + out
                count += 1
        return total / count

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """x: (B, 6, H, W) -> logits (B, 5). D4-symmetrized."""
        return self._d4_logits(x)

    def values(self, x: torch.Tensor) -> torch.Tensor:
        """x: (B, 6, H, W) -> state values (B,). D4-invariant."""
        return self._d4_values(x).squeeze(-1)


CRITIC_PREFIXES = ("value.", "vconv")


def is_critic_key(key: str) -> bool:
    """True for value-trunk/head keys (training apparatus, not the agent).

    The critic persists across generations (archive/critic.json) while
    the actor restarts from the champion. After the trunk split the
    critic owns vconv* as well as value.* — banking must include both,
    or continuity silently degrades to head-only (random trunk, v ~1.0
    every gen start)."""
    return key.startswith(CRITIC_PREFIXES)


def infer_arch(weights: dict) -> str:
    """Which arch a weight dict belongs to, by key presence.

    The bot and the trainer never share an arch flag: weights carry
    their own shape, so a deep checkpoint can never load into a base
    net (or vice versa) by mistake."""
    return "deep" if "conv3.weight" in weights else "base"


_action_index: dict[int, tuple[torch.Tensor, torch.Tensor]] = {}


def pad_in_channels(state: dict[str, torch.Tensor],
                    policy: CNNPolicy) -> dict[str, torch.Tensor]:
    """Zero-pad narrow input channels so old checkpoints keep working.

    Widening the window adds input channels (own_sight); archived
    weights predate them. Padding with zeros keeps every old output
    bit-identical (the new channels contribute 0) and lets training
    grow them from a live lineage instead of a reset. No-op when the
    shapes already match."""
    own_shapes = dict(policy.named_parameters())
    own_shapes.update(dict(policy.named_buffers()))
    for key, ref in own_shapes.items():
        if (key in state and state[key].shape != ref.shape
                and len(ref.shape) == 4
                and state[key].shape[0] == ref.shape[0]
                and state[key].shape[2:] == ref.shape[2:]):
            missing = ref.shape[1] - state[key].shape[1]
            if missing > 0:
                pad = torch.zeros(ref.shape[0], missing, *ref.shape[2:])
                state[key] = torch.cat([state[key], pad], dim=1)
    return state


def legal_mask(
    window: torch.Tensor, blocked: frozenset = frozenset()
) -> torch.Tensor:
    """True for enterable destinations.

    Dest offsets read straight off the window: the ant is the center.
    A tile is enterable when it holds neither water nor visible food
    (the engine ignores moves into both: tools/ants.py validate_orders).
    blocked carries the live reservation set as action names, so two
    ants never take the same tile.

    The five dest cells are gathered with one advanced-index op instead
    of a python loop with scalar tensor indexing (the old hot spot).
    """
    radius = (window.shape[-2] - 1) // 2
    if radius not in _action_index:
        rows, cols = zip(
            *[
                (radius + features.OFFSETS[a][0], radius + features.OFFSETS[a][1])
                for a in ACTIONS
            ]
        )
        _action_index[radius] = (
            torch.tensor(rows, dtype=torch.long),
            torch.tensor(cols, dtype=torch.long),
        )
    rows, cols = _action_index[radius]
    clear = (window[features.WATER_CHANNEL][rows, cols] <= 0) & (
        window[features.FOOD_CHANNEL][rows, cols] <= 0
    )
    for name in blocked:
        clear[ACTIONS.index(name)] = False
    return clear


def masked_logits_batch(
    policy: CNNPolicy, windows: torch.Tensor, blocked: list
) -> torch.Tensor:
    """Batched masked_logits: one forward for B ants, same math.

    The legal mask vectorizes: water/food clearance reads straight off
    the window channels per action offset, blocked action names become
    a (B, 5) mask. Nothing legal falls back to stay per row."""
    with torch.no_grad():
        if windows.shape[0] == 0:
            return torch.zeros((0, len(ACTIONS)))
        logits = policy(windows)
        radius = (windows.shape[-2] - 1) // 2
        clear = torch.ones((windows.shape[0], len(ACTIONS)), dtype=torch.bool)
        for k, action in enumerate(ACTIONS):
            dr, dc = features.OFFSETS[action]
            clear[:, k] = (
                windows[:, features.WATER_CHANNEL, radius + dr, radius + dc]
                <= 0
            ) & (
                windows[:, features.FOOD_CHANNEL, radius + dr, radius + dc]
                <= 0
            )
        for i, names in enumerate(blocked):
            for name in names:
                clear[i, ACTIONS.index(name)] = False
        return torch.where(
            _with_stay(clear), logits, torch.tensor(-1e9)
        )


def act_greedy_batch(logits: torch.Tensor) -> list:
    """Argmax per row; same answers as act_greedy on each row."""
    return [ACTIONS[int(i)] for i in torch.argmax(logits, dim=1).tolist()]


def sample_batch(logits: torch.Tensor, temperature: float) -> list:
    """One multinomial call for B rows; same distribution as sample."""
    probs = torch.softmax(logits / temperature, dim=1)
    return [
        ACTIONS[int(i)] for i in torch.multinomial(probs, 1).flatten().tolist()
    ]


def mask_logits(
    logits: torch.Tensor,
    window: torch.Tensor,
    blocked: frozenset,
    legal: torch.Tensor | None = None,
) -> torch.Tensor:
    """Apply the legal mask to precomputed logits (batched forward path).

    Same result as masked_logits without the forward: the bot runs one
    forward for all ants, then masks each row as its reservation set
    evolves through the turn. Pass legal= to reuse an already-computed
    mask instead of recomputing it."""
    if legal is None:
        legal = legal_mask(window, blocked)
    use = _with_stay(legal.unsqueeze(0)).flatten()
    return torch.where(use, logits, torch.tensor(-1e9))


def masked_logits(
    policy: CNNPolicy, window: torch.Tensor, blocked: frozenset = frozenset()
) -> torch.Tensor:
    """No-grad masked logits for acting. Nothing legal falls back to
    stay: the mask keeps stay legal and kills the rest."""
    with torch.no_grad():
        return mask_logits(policy(window.unsqueeze(0)).flatten(), window, blocked)


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
