"""
快速测试脚本 - 验证模型加载和推理
"""
import sys
import torch
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from inference import load_model, build_vocab

DATA_DIR = Path(__file__).parent.parent / "data"
CHECKPOINT_PATH = Path(__file__).parent.parent / "checkpoints" / "TFNet-CE-CSL-CSLDaily-32.46.pth"

# 检查文件是否存在
print(f"检查点文件存在: {CHECKPOINT_PATH.exists()}")
print(f"数据集标签目录存在: {(DATA_DIR / 'label').exists()}")

# 构建词表
train_label = DATA_DIR / "label" / "train.csv"
dev_label = DATA_DIR / "label" / "dev.csv"
test_label = DATA_DIR / "label" / "test.csv"

print(f"\n训练标签存在: {train_label.exists()}")
print(f"验证标签存在: {dev_label.exists()}")
print(f"测试标签存在: {test_label.exists()}")

print("\n=== 构建词表 ===")
word2idx, vocab_size, idx2word = build_vocab(
    [str(train_label), str(dev_label), str(test_label)],
    "CE-CSL"
)
print(f"词表大小: {vocab_size}")
print(f"词表样本: {list(idx2word)[:10]}")

# 加载模型
print("\n=== 加载模型 ===")
device = torch.device("cpu")
model = load_model(str(CHECKPOINT_PATH), 1024, vocab_size, device, "CE-CSL")

# 测试 dummy 输入
print("\n=== 测试推理 ===")
batch_size, T, C, H, W = 1, 32, 3, 224, 224
dummy_input = torch.randn(batch_size, T, C, H, W)
dummy_len = torch.LongTensor([[32]])

with torch.no_grad():
    logProbs1, logProbs2, logProbs3, logProbs4, logProbs5, lgt, x1, x2, x3 = model(dummy_input, dummy_len)
    print(f"logProbs1 shape: {logProbs1.shape}")  # (T', B, vocab)
    print(f"lgt: {lgt}")
    print(f"推理成功!")

print("\n=== 模型加载和测试通过 ===")
