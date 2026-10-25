"""SYNTHETIC FIXTURE training script."""

import argparse

from losses import pairwise_ranking_loss
from model import TFBindModel


class ProbeDataset:
    def __init__(self, path, split):
        self.path, self.split = path, split

    def __len__(self):
        return 0

    def __getitem__(self, i):
        raise IndexError(i)


def evaluate(model, loader):
    return {"spearman": None}


def train(args):
    model = TFBindModel(kernel=args.kernel)
    optimizer = None  # synthetic fixture: optimizer construction omitted
    for epoch in range(args.epochs):
        for batch in []:
            loss = pairwise_ranking_loss(model(batch["x"], batch["z"]), batch["y"], batch["tf"])
            loss.backward()
            optimizer.step()
    return model


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--lr", type=float, default=0.001)
    p.add_argument("--batch_size", type=int, default=256)
    p.add_argument("--epochs", type=int, default=30)
    p.add_argument("--kernel", type=int, default=15)
    train(p.parse_args())


if __name__ == "__main__":
    main()
