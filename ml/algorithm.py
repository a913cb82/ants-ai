"""RL updates: policy in, improved policy out.

PPO with Monte-Carlo targets (no GAE): clipped surrogate +
shared-trunk value head + per-minibatch standardized
(return - value) advantages. (GAE was omitted deliberately: with dense
per-ant shaping over <=150-turn episodes, Monte-Carlo targets are
already low-bias; see README. Adding GAE is a ~20-line change now
that the value head exists.) Knows torch and the PPO estimator.
Knows nothing about ants, replays, or the engine: batches arrive as
(window, action, return, legal-mask, behavior-logprob) tuples,
action indices in features.ACTIONS order. Masks come from the stored
per-decision legal sets, so the learner scores actions under exactly
the distribution the bot acted with.
"""

from __future__ import annotations

import sys
from pathlib import Path

import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "bots" / "alphaant"))

import model

BatchItem = tuple[torch.Tensor, int, float, list, float]

# NESW are equivalent: the rules never favor a compass direction, so a
# rotated window with the counter-rotated move is an equally valid row.
# One CCW turn sends n->w->s->e->n (stay stays); the mask permutes with
# the actions (mask'[new] = mask[old]). Random k per row quadruples
# the directional coverage of a 6k-param net for free.
ROT_PERM = (3, 0, 1, 2, 4)
ROT_MASK = (1, 2, 3, 0, 4)


def new_policy(
    weights: dict | None = None, arch: str | None = None
) -> model.CNNPolicy:
    """Construct a policy, optionally from stored weight lists.

    The one place ml/ names the bot's network shape: train.py talks to
    new_policy/policy_weights and never imports model directly.
    arch defaults to whatever the weights say (infer_arch), so an
    explicit flag is only needed for fresh random nets.
    """
    if arch is None:
        arch = model.infer_arch(weights) if weights is not None else "base"
    policy = model.CNNPolicy(arch=arch)
    if weights is not None:
        # strict=False: pre-value-head checkpoints lack the value keys
        # (they stay zero-initialized, i.e. no baseline yet).
        policy.load_state_dict(model.lists_to_state_dict(weights), strict=False)
    return policy


def policy_weights(policy: model.CNNPolicy) -> dict:
    """Policy parameters -> JSON-able lists for the archive."""
    return model.state_dict_to_lists(policy)


def to_batch(
    records: list[dict], returns: list[float], logps: list[float]
) -> list[BatchItem]:
    """Decision rows + priced returns + behavior log-probs -> learner batch."""
    return [
        (
            torch.tensor(rec["window"], dtype=torch.float32),
            model.ACTIONS.index(rec["action"]) if "action" in rec else 0,
            ret,
            rec.get("legal", [True] * len(model.ACTIONS)),
            logp,
        )
        for rec, ret, logp in zip(records, returns, logps, strict=True)
    ]


def _rotate_item(item: BatchItem, k: int) -> BatchItem:
    """Rotate a row k quarter-turns CCW (window, action, mask together).

    k = 0 is the identity. The return is untouched: rotation preserves
    game facts, only the viewpoint turns."""
    w, a, r, m, o = item
    for _ in range(k % 4):
        w = torch.rot90(w, 1, [1, 2])
        a = ROT_PERM[a]
        m = [m[i] for i in ROT_MASK]
    return (w, a, r, m, o)


def collect(
    policy: model.CNNPolicy, records: list[dict], returns: list[float]
) -> list[BatchItem]:
    """to_batch + behavior log-probs in one pass: the policy is frozen
    during collection, so these are the on-policy log-probs PPO's ratio
    needs later."""
    items = to_batch(records, returns, [0.0] * len(returns))
    if not items:
        return items
    # Random rotation per row: the behavior log-probs are scored on the
    # rotated pairs, so PPO's ratio stays on-policy by construction.
    ks = torch.randint(0, 4, (len(items),)).tolist()
    items = [_rotate_item(it, k) for it, k in zip(items, ks, strict=True)]
    chosen, _entropy = masked_log_probs(policy, items)
    return [
        (w, a, r, m, float(c))
        for (w, a, r, m, _o), c in zip(items, chosen.tolist(), strict=True)
    ]


def make_optimizer(
    policy: model.CNNPolicy, lr: float = 1e-3
) -> torch.optim.Optimizer:
    """Caller-owned Adam; momentum must survive across PPO epochs.

    NOTE: train.py rebuilds the optimizer per generation, so momentum
    does NOT cross generations today — only epochs. Cross-generation
    persistence needs serialized optimizer state (future work).
    """
    return torch.optim.Adam(policy.parameters(), lr=lr)


def _tensors(policy: model.CNNPolicy, batch: list[BatchItem]):
    device = next(policy.parameters()).device
    windows = torch.stack([w for w, _a, _r, _m, _o in batch]).to(device)
    masks = torch.tensor(
        [m for _w, _a, _r, m, _o in batch], dtype=torch.bool, device=device
    )
    actions = torch.tensor([a for _w, a, _r, _m, _o in batch], device=device)
    returns = torch.tensor(
        [r for _w, _a, r, _m, _o in batch], dtype=torch.float32, device=device
    )
    old = torch.tensor(
        [o for _w, _a, _r, _m, o in batch], dtype=torch.float32, device=device
    )
    return windows, masks, actions, returns, old


def masked_log_probs(
    policy: model.CNNPolicy, batch: list[BatchItem]
) -> tuple[torch.Tensor, torch.Tensor]:
    """(log pi(a|s), entropy) under each row's stored legal mask.

    Empty batch -> empty tensors; the caller skips the update.
    """
    if not batch:
        return torch.empty(0), torch.empty(0)
    windows, masks, actions, _returns, _old = _tensors(policy, batch)
    logp = model.masked_log_softmax(policy, windows, masks)
    chosen = logp[range(len(batch)), actions]
    entropy = -(logp.exp() * logp).sum(dim=1)
    return chosen, entropy


def _advantages(
    returns: torch.Tensor, values: torch.Tensor,
    bmean: torch.Tensor, bstd: torch.Tensor,
) -> torch.Tensor:
    """Batch-scaled advantages: (standardized return) - value.

    No second standardization: a minibatch of pure noise rows keeps
    near-zero advantages while an event minibatch keeps large ones."""
    rz = (returns - bmean) / (bstd + 1e-8)
    return rz - values.detach()


def train_epoch(
    policy: model.CNNPolicy,
    opt: torch.optim.Optimizer,
    batch: list[BatchItem],
    clip: float = 0.2,
    vf_coef: float = 0.5,
    entropy_beta: float = 0.01,
    max_norm: float = 1.0,
    minibatch: int = 64,
) -> dict[str, float]:
    """One PPO pass: clipped surrogate + value loss - beta * entropy.

    Advantages are (return - value) standardized over the WHOLE batch,
    so a minibatch of pure noise rows keeps near-zero advantages while
    an event minibatch keeps large ones. (Per-minibatch standardization
    gave every minibatch unit variance by construction, amplifying noise
    into full-scale gradients.) Empty batch is a no-op (early
    elimination, lost records). Returns losses for the generation log.
    """
    stats = {"loss": 0.0, "mean_return": 0.0, "entropy": 0.0, "kl": 0.0,
             "pg_loss": 0.0, "v_loss": 0.0, "steps": 0}
    if not batch:
        return stats
    stats["mean_return"] = sum(r for _w, _a, r, _m, _o in batch) / len(batch)
    # Batch-level return statistics: every minibatch is scored on the
    # same scale, preserving the event-vs-noise magnitude gap.
    all_ret = torch.tensor(
        [r for _w, _a, r, _m, _o in batch], dtype=torch.float32)
    bmean, bstd = all_ret.mean(), all_ret.std(unbiased=False)
    mb_size = min(minibatch, max(16, len(batch) // 4)) if batch else minibatch
    idx = torch.randperm(len(batch)).tolist()
    n_loss = n_pg = n_v = n_ent = n_kl = 0.0
    n_steps = 0
    for start in range(0, len(batch), mb_size):
        mb = [batch[i] for i in idx[start:start + mb_size]]
        windows, masks, actions, returns, old = _tensors(policy, mb)
        logp = model.masked_log_softmax(policy, windows, masks)
        chosen = logp[range(len(mb)), actions]
        entropy = -(logp.exp() * logp).sum(dim=1)
        values = policy.values(windows)
        # Critic fits batch-standardized returns; advantages keep the
        # batch scale (no second standardization: noise minibatches must
        # stay small next to event minibatches).
        adv = _advantages(returns, values, bmean, bstd)
        rz = (returns - bmean) / (bstd + 1e-8)  # value target (same scale)
        ratio = torch.exp(chosen - old)
        pg = -torch.min(ratio * adv, torch.clamp(ratio, 1 - clip, 1 + clip) * adv).mean()
        v = ((values - rz) ** 2).mean()
        loss = pg + vf_coef * v - entropy_beta * entropy.mean()
        opt.zero_grad()
        loss.backward()
        torch.nn.utils.clip_grad_norm_(policy.parameters(), max_norm)
        opt.step()
        kl = ((ratio - 1) - (chosen - old)).mean()
        n_loss += float(loss.detach())
        n_pg += float(pg.detach())
        n_v += float(v.detach())
        n_ent += float(entropy.mean().detach())
        n_kl += float(kl.detach())
        n_steps += 1
    stats.update({
        "loss": n_loss / n_steps, "pg_loss": n_pg / n_steps,
        "v_loss": n_v / n_steps, "entropy": n_ent / n_steps,
        "kl": n_kl / n_steps, "steps": n_steps,
    })
    return stats
