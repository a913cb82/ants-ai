"""RL updates: policy in, improved policy out.

Knows torch and the REINFORCE estimator. Knows nothing about ants,
replays, or the engine: batches arrive as (window, action, return,
legal-mask) tuples, action indices in features.ACTIONS order. Masks come
from the stored per-decision legal sets, so the learner scores actions
under exactly the distribution the bot acted with.
"""

from __future__ import annotations

import sys
from pathlib import Path

import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "bots" / "alphastarzero"))

import model

BatchItem = tuple[torch.Tensor, int, float, list]


def advantages(returns: list[float]) -> list[float]:
    """Standardized advantages: zero mean, unit variance.

    Still a constant baseline (unbiased), but now late-game and
    early-game returns share one scale instead of letting turn order
    dominate the gradient.
    """
    mean = sum(returns) / len(returns)
    var = sum((r - mean) ** 2 for r in returns) / len(returns)
    std = var**0.5 if var > 0 else 1.0
    return [(r - mean) / std for r in returns]


def to_batch(records: list[dict], returns: list[float]) -> list[BatchItem]:
    """Decision rows + priced returns -> learner batch."""
    return [
        (
            torch.tensor(rec["window"], dtype=torch.float32),
            model.ACTIONS.index(rec["action"]) if "action" in rec else 0,
            ret,
            rec.get("legal", [True] * len(model.ACTIONS)),
        )
        for rec, ret in zip(records, returns, strict=True)
    ]


def make_optimizer(
    policy: model.CNNPolicy, lr: float = 1e-3
) -> torch.optim.Optimizer:
    """Caller-owned optimizer: momentum must survive across epochs."""
    return torch.optim.Adam(policy.parameters(), lr=lr)


def masked_log_probs(
    policy: model.CNNPolicy, batch: list[BatchItem]
) -> tuple[torch.Tensor, torch.Tensor]:
    """(log pi(a|s), entropy) under each row's stored legal mask.

    Empty batch -> empty tensors; the caller skips the update.
    """
    if not batch:
        return torch.empty(0), torch.empty(0)
    device = next(policy.parameters()).device
    windows = torch.stack([w for w, _a, _r, _m in batch]).to(device)
    masks = torch.tensor(
        [m for _w, _a, _r, m in batch], dtype=torch.bool, device=device
    )
    logp = model.masked_log_softmax(policy, windows, masks)
    actions = torch.tensor([a for _w, a, _r, _m in batch], device=device)
    chosen = logp[range(len(batch)), actions]
    entropy = -(logp.exp() * logp).sum(dim=1)
    return chosen, entropy


def train_epoch(
    policy: model.CNNPolicy,
    opt: torch.optim.Optimizer,
    batch: list[BatchItem],
    entropy_beta: float = 0.01,
    max_norm: float = 1.0,
) -> dict[str, float]:
    """One REINFORCE epoch: -mean(log pi * adv) - beta * entropy.

    Returns loss, mean return, and mean entropy for the generation log.
    Empty batch is a no-op (early elimination, lost records).
    """
    mean_return = sum(r for _w, _a, r, _m in batch) / len(batch) if batch else 0.0
    stats = {"loss": 0.0, "mean_return": mean_return, "entropy": 0.0}
    if not batch:
        return stats
    adv = torch.tensor(
        advantages([r for _w, _a, r, _m in batch]),
        dtype=torch.float32,
        device=next(policy.parameters()).device,
    )
    opt.zero_grad()
    chosen, entropy = masked_log_probs(policy, batch)
    loss = -(chosen * adv).mean() - entropy_beta * entropy.mean()
    loss.backward()
    torch.nn.utils.clip_grad_norm_(policy.parameters(), max_norm)
    opt.step()
    stats.update(
        {"loss": float(loss.detach()), "entropy": float(entropy.mean().detach())}
    )
    return stats
