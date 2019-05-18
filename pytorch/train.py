import argparse
import os
import time

import numpy as np
import torch
from torch import nn, optim
from torch.functional import F
from torch.utils.data import DataLoader
from torch.utils.tensorboard import SummaryWriter

from data import StereoDataset
from model import Model

learning_rate = 1e-2
half_range = 100

parser = argparse.ArgumentParser()
parser.add_argument("--data", type=str, default='../data/training')
parser.add_argument("--checkpoint", type=str, default='./checkpoint.pkl')
parser.add_argument("--batch_size", type=int, default=128)
parser.add_argument("--epochs", type=int, default=10)
args = parser.parse_args()

batch_size = args.batch_size
epochs = args.epochs
checkpoint = args.checkpoint

torch.manual_seed(42)
device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")


def three_pixel_loss(pred, target, weights):
    error = 0
    for i in range(pred.size(0)):
        pred_compare = pred[i, target[i][0]-2:target[i][0]+2+1]
        loss = torch.mul(pred_compare, weights).sum()
        error = error - loss

    return error / pred.size(0)

def three_pixel_accuracy(pred, target):
    acc = 0
    for i in range(pred.size(0)):
        sc = pred[i, target[i][0]-2:target[i][0]+2+1]
        acc -= sc.sum()

    return 1 - ((acc / pred.size(0)).item() / 100)

writer = SummaryWriter()
model = Model(3, half_range*2+1).to(device)
if os.path.exists(checkpoint):
    model.load_state_dict(torch.load(checkpoint))

optimizer = optim.Adam(model.parameters(), lr=learning_rate)
dataset = StereoDataset(
    util_root='../preprocess/debug_15/',
    data_root=args.data,
    filename='tr_160_18_100.bin',
)

train_data = DataLoader(dataset, batch_size=batch_size, shuffle=True)
class_weights = torch.Tensor([1, 4, 10, 4, 1]).to(device)
samples = len(dataset)

i = 0
for epoch in range(epochs):
    model.train()
    targets = np.tile(half_range, (batch_size, 1))
    target_batch = torch.tensor(targets, dtype=torch.int32)
    losses = np.array([])
    for batch in train_data:
        start_time = time.time()
        i += 1

        left_img = batch['left'].to(device)
        right_img = batch['right'].to(device)
        target = target_batch.to(device)

        _, _, pred = model(left_img, right_img)
        loss = three_pixel_loss(pred, target, class_weights)
        loss.backward()
        optimizer.step()
        optimizer.zero_grad()

        losses = np.append(losses, loss.item())
        writer.add_scalar("train_loss", loss, global_step=i)
        if i % 50 == 0:
            avg_time = ((time.time() - start_time) * 1000) / 50
            print("%d/%d samples, Avg. loss: %f, Time per batch: %fms" % ((batch_size * i), samples, np.mean(losses), avg_time))
            losses = np.array([])

        if i % 500 == 0:
            torch.save(model.state_dict(), checkpoint)
            print("Created checkpoint")


    print("Finished epoch %d" % epoch)
    torch.save(model.state_dict(), checkpoint)
