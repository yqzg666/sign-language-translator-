"""
SEN.py stub - SE-Net module, not used by TFNet (moduleChoice=TFNet uses ResNet34MAM)
"""
import torch.nn as nn


class Identity(nn.Module):
    def __init__(self):
        super().__init__()

    def forward(self, x):
        return x


def resnet18():
    """Stub - TFNet doesn't use SEN module"""
    return nn.Sequential()
