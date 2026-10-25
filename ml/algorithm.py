"""RL updates: policy in, improved policy out.

Knows torch and the REINFORCE estimator. Knows nothing about ants,
replays, or the engine: batches arrive as plain
(window, action_index, discounted_return) tuples, with action indices
in model.ACTIONS order. Masking comes from model.masked_logits so the
learner scores actions under the same distribution the bot acted with.
"""

from __future__ import annotations

import sys
from pathlib import Path

import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "bots" / "alphastarzero"))

import model


def advantages(returns: list[float]) -> list[float]:
    """Mean-centered advantages. Zero-sum batch -> zero gradient."""
    mean = sum(returns) / len(returns)
    return [r - mean for r in returns]


def logprob(policy: model.CNNPolicy, window: torch.Tensor, action: int) -> float:
    logits = model.masked_logits(policy, window)
    return float(torch.log_softmax(logits, dim=0)[action])


def to_batch(
    records: list[dict], returns: list[float]
) -> list[tuple[torch.Tensor, int, float]]:
    """Decision rows + priced returns -> learner batch."""
    return [
        (
            torch.tensor(rec["window"], dtype=torch.float32),
            model.ACTIONS.index(rec["action"]),
            ret,
        )
        for rec, ret in zip(records, returns, strict=True)
    ]


def reinforce_step(
    policy: model.CNNPolicy,
    batch: list[tuple[torch.Tensor, int, float]],
    lr: float = 1e-3,
    device: str = "cpu",
) -> dict[str, float]:
    """One REINFORCE step: loss = -mean(log pi(a|s) * (R - mean R)).

    device is a one-line switch for later ("cuda" when training moves
    to the GPU); inference stays CPU for the engine turn budget.
    """
    policy.to(device)
    windows = torch.stack([w for w, _a, _r in batch]).to(device)
    actions = torch.tensor([a for _w, a, _r in batch], device=device)
    adv = torch.tensor(
        advantages([r for _w, _a, r in batch]), dtype=torch.float32, device=device
    )
    opt = torch.optim.Adam(policy.parameters(), lr=lr)
    opt.zero_grad()
    logits = policy(windows)
    logp = torch.log_softmax(logits, dim=1)
    loss = -(logp[range(len(batch)), actions] * adv).mean()
    loss.backward()
    opt.step()
    return {
        "loss": float(loss.detach()),
        "mean_return": sum(r for _w, _a, r in batch) / len(batch),
    }
