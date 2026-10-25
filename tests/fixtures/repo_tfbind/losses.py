"""SYNTHETIC FIXTURE: pairwise ranking loss (Eq. 2 in the fixture paper)."""

import torch.nn.functional as F


def pairwise_ranking_loss(scores, targets, tf_index):
    loss = 0.0
    for t in tf_index.unique():
        m = tf_index == t
        s, y = scores[m], targets[m]
        diff = s[:, None] - s[None, :]
        better = (y[:, None] > y[None, :]).float()
        loss = loss + (F.softplus(-diff) * better).sum() / better.sum().clamp(min=1)
    return loss
