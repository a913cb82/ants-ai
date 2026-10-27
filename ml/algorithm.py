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
        # pad_in_channels: pre-widening checkpoints lack the new input
        # channels (they load zero-padded: identical outputs, lineage
        # continues instead of resetting).
        state = model.pad_in_channels(model.lists_to_state_dict(weights),
                                      policy)
        policy.load_state_dict(state, strict=False)
    return policy


def policy_weights(policy: model.CNNPolicy) -> dict:
    """Policy parameters -> JSON-able lists for the archive."""
    return model.state_dict_to_lists(policy)


def compact_records(records: list[dict]) -> list[dict]:
    """Nested-list windows -> float32 tensors, in place.

    Records arrive from disk as nested python lists (~60KB/row for a
    7x15x15 window); the learner only ever stacks them into tensors
    (~6.3KB/row). Compacting at production keeps a single residency
    instead of lists + tensors side by side. Values are bit-exact:
    float32 -> python float -> float32 round-trips losslessly.
    Non-window keys (action/legal) are untouched; tensor windows pass
    through unchanged.
    """
    for rec in records:
        w = rec.get("window")
        if isinstance(w, list):
            rec["window"] = torch.as_tensor(w, dtype=torch.float32)
    return records


def to_batch(
    records: list[dict], returns: list[float], logps: list[float]
) -> list[BatchItem]:
    """Decision rows + priced returns + behavior log-probs -> learner batch."""
    return [
        (
            # as_tensor: zero-copy when compact_records already
            # tensorized the window; bit-identical otherwise.
            torch.as_tensor(rec["window"], dtype=torch.float32),
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
    """Caller-owned Adam; momentum must survive across PPO epochs."""
    return torch.optim.Adam(policy.parameters(), lr=lr)


def serialize_opt(opt: torch.optim.Optimizer) -> dict:
    """Adam state as JSON-safe lists (tensors don't survive json)."""
    raw = opt.state_dict()
    state = {}
    for idx, vals in raw["state"].items():
        item = {}
        for k, v in vals.items():
            item[k] = v.tolist() if torch.is_tensor(v) else v
        state[str(idx)] = item
    groups = []
    for g in raw["param_groups"]:
        groups.append({k: v for k, v in g.items() if k != "params"})
    return {"state": state, "param_groups": groups}


def load_opt_state(opt: torch.optim.Optimizer, blob: dict | None) -> None:
    """Restore serialized Adam state; drops reshaped params.

    Momentum buffers are shape-bound: after a widening (6ch -> 7ch)
    the old conv1/vconv1 exp_avg no longer fits and must not load
    (round 18 crashed its first opt.step on exactly this). Matching
    params keep their history; reshaped ones restart fresh."""
    if not blob:
        return
    try:
        cur = opt.state_dict()
        if not cur["param_groups"]:
            return
        live = [p for g in opt.param_groups for p in g["params"]]
        state = {}
        for idx, vals in blob.get("state", {}).items():
            try:
                i = int(idx)
            except (ValueError, TypeError):
                continue
            if i >= len(live):
                continue
            want = tuple(live[i].shape)
            item = {}
            ok = True
            for k, v in vals.items():
                t = torch.tensor(v) if isinstance(v, list) else v
                # Scalars (step counters) always fit; every buffer
                # must match exactly or the whole param restarts fresh.
                if (torch.is_tensor(t) and t.shape != torch.Size(())
                        and tuple(t.shape) != want):
                    ok = False
                    break
                item[k] = t
            if ok:
                state[i] = item
        groups = []
        for cur_g, saved_g in zip(cur["param_groups"],
                                  blob.get("param_groups", [])):
            g = dict(cur_g)  # live params kept; saved hypers win.
            g.update({k: v for k, v in saved_g.items() if k != "params"})
            groups.append(g)
        if not groups:
            return
        opt.load_state_dict({"state": state, "param_groups": groups})
    except (ValueError, KeyError, IndexError, TypeError, RuntimeError):
        return


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


# Values-forward chunk: the D4-symmetrized critic runs 8 orientations
# per row, so a full-batch stack scales activations with the generation
# size (85k rows x conv1 16ch = 1.2GB per feature map). Chunking keeps
# the peak per-chunk; conv/relu/pool/linear have no batch coupling
# (no norms), so per-row values are bit-identical at any chunk size.
_VALUE_CHUNK = 1024


def frozen_advantages(
    policy: model.CNNPolicy, batch: list[BatchItem]
) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    """One-shot advantages with the PRE-UPDATE value net (per generation).

    Returns (adv, bmean, bstd) in batch order: adv[i] belongs to
    batch[i]. The caller passes the triple into every train_epoch call
    so all minibatches of all epochs share one frozen baseline instead
    of recomputing (return - value) from the current critic — which
    evaporated advantages as the critic fit. Batch scale (bmean/bstd)
    is per-generation, exactly as train_epoch computed it before."""
    if not batch:
        return (torch.zeros(0), torch.tensor(0.0), torch.tensor(1.0))
    device = next(policy.parameters()).device
    with torch.no_grad():
        vals = []
        for start in range(0, len(batch), _VALUE_CHUNK):
            windows = torch.stack(
                [w for w, _a, _r, _m, _o
                 in batch[start:start + _VALUE_CHUNK]]).to(device)
            vals.append(policy.values(windows).detach().cpu())
        values = torch.cat(vals)
    all_ret = torch.tensor(
        [r for _w, _a, r, _m, _o in batch], dtype=torch.float32)
    bmean, bstd = all_ret.mean(), all_ret.std(unbiased=False)
    return _advantages(all_ret, values, bmean, bstd).detach(), bmean, bstd


def train_epoch(
    policy: model.CNNPolicy,
    opt: torch.optim.Optimizer,
    batch: list[BatchItem],
    clip: float = 0.2,
    vf_coef: float = 0.5,
    entropy_beta: float = 0.01,
    max_norm: float = 1.0,
    minibatch: int = 64,
    anchor: model.CNNPolicy | None = None,
    kl_anchor_beta: float = 0.0,
    advantages: torch.Tensor | None = None,
    bmean: torch.Tensor | None = None,
    bstd: torch.Tensor | None = None,
) -> dict[str, float]:
    """One PPO pass: clipped surrogate + value loss - beta * entropy.

    Advantages are (return - value) standardized over the WHOLE batch,
    so a minibatch of pure noise rows keeps near-zero advantages while
    an event minibatch keeps large ones. (Per-minibatch standardization
    gave every minibatch unit variance by construction, amplifying noise
    into full-scale gradients.) Empty batch is a no-op (early
    elimination, lost records). Returns losses for the generation log.

    Frozen-baseline mode: pass the (adv, bmean, bstd) triple from
    frozen_advantages (computed once per generation with the pre-update
    value net) and every minibatch of this epoch reuses it instead of
    recomputing from the current critic. None (default) recomputes
    exactly as before.
    """
    stats = {"loss": 0.0, "mean_return": 0.0, "entropy": 0.0, "kl": 0.0,
             "pg_loss": 0.0, "v_loss": 0.0, "steps": 0, "kl_anchor": 0.0,
             "pg_abs": 0.0}
    if not batch:
        return stats
    stats["mean_return"] = sum(r for _w, _a, r, _m, _o in batch) / len(batch)
    # Batch-level return statistics: every minibatch is scored on the
    # same scale, preserving the event-vs-noise magnitude gap. A frozen
    # triple from frozen_advantages (one baseline per generation)
    # overrides the recompute: the critic still fits every minibatch,
    # but the policy gradient keeps the pre-update advantages.
    all_ret = torch.tensor(
        [r for _w, _a, r, _m, _o in batch], dtype=torch.float32)
    if advantages is None or bmean is None or bstd is None:
        bmean, bstd = all_ret.mean(), all_ret.std(unbiased=False)
        frozen = None
    else:
        frozen = torch.as_tensor(advantages).detach().flatten()
        assert len(frozen) == len(batch), (
            f"frozen advantages {len(frozen)} != batch {len(batch)}")
    mb_size = min(minibatch, max(16, len(batch) // 4)) if batch else minibatch
    idx = torch.randperm(len(batch)).tolist()
    n_loss = n_pg = n_v = n_ent = n_kl = n_anch = n_pga = 0.0
    n_steps = 0
    for start in range(0, len(batch), mb_size):
        mb_idx = idx[start:start + mb_size]
        mb = [batch[i] for i in mb_idx]
        windows, masks, actions, returns, old = _tensors(policy, mb)
        logp = model.masked_log_softmax(policy, windows, masks)
        chosen = logp[range(len(mb)), actions]
        entropy = -(logp.exp() * logp).sum(dim=1)
        values = policy.values(windows)
        # Critic fits batch-standardized returns; advantages keep the
        # batch scale (no second standardization: noise minibatches must
        # stay small next to event minibatches).
        if frozen is None:
            adv = _advantages(returns, values, bmean, bstd)
        else:
            adv = frozen[mb_idx].to(returns.device)
        rz = (returns - bmean) / (bstd + 1e-8)  # value target (same scale)
        ratio = torch.exp(chosen - old)
        pg_rows = -torch.min(ratio * adv,
                             torch.clamp(ratio, 1 - clip, 1 + clip) * adv)
        pg = pg_rows.mean()
        pg_abs = pg_rows.abs().mean()
        v = ((values - rz) ** 2).mean()
        loss = pg + vf_coef * v - entropy_beta * entropy.mean()
        if anchor is not None and kl_anchor_beta:
            with torch.no_grad():
                alogp = model.masked_log_softmax(anchor, windows, masks)
            kl_anchor = (logp.exp() * (logp - alogp)).sum(dim=1).mean()
            loss = loss + kl_anchor_beta * kl_anchor
        else:
            kl_anchor = torch.zeros((), device=logp.device)
        opt.zero_grad()
        loss.backward()
        torch.nn.utils.clip_grad_norm_(policy.parameters(), max_norm)
        opt.step()
        kl = ((ratio - 1) - (chosen - old)).mean()
        n_loss += float(loss.detach())
        n_anch += float(kl_anchor.detach())
        n_pga += float(pg_abs.detach())
        n_pg += float(pg.detach())
        n_v += float(v.detach())
        n_ent += float(entropy.mean().detach())
        n_kl += float(kl.detach())
        n_steps += 1
    stats.update({
        "loss": n_loss / n_steps, "pg_loss": n_pg / n_steps,
        "v_loss": n_v / n_steps, "entropy": n_ent / n_steps,
        "kl": n_kl / n_steps, "steps": n_steps,
        "kl_anchor": n_anch / n_steps,
        "pg_abs": n_pga / n_steps,
    })
    return stats
