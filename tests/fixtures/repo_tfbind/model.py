"""SYNTHETIC FIXTURE repository for CDRI tests (never executed by CDRI; parsed statically)."""

import torch
from torch import nn


class FiLM(nn.Module):
    def __init__(self, z_dim, channels):
        super().__init__()
        self.gamma = nn.Linear(z_dim, channels)
        self.beta = nn.Linear(z_dim, channels)

    def forward(self, h, z):
        return self.gamma(z)[:, :, None] * h + self.beta(z)[:, :, None]


class TFBindModel(nn.Module):
    def __init__(self, z_dim=1280, channels=128, kernel=15):
        super().__init__()
        self.conv = nn.Conv1d(4, channels, kernel)
        self.film = FiLM(z_dim, channels)
        self.head = nn.Linear(channels, 1)

    def forward(self, x, z):
        h = torch.relu(self.conv(x))
        h = self.film(h, z)
        # NOTE: mean pooling here, while the paper (Eq. 1) describes global max pooling
        pooled = h.mean(dim=-1)
        return self.head(pooled).squeeze(-1)
