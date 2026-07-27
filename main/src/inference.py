"""
手语视频识别推理模块
输入: 视频/图片序列 → TFNet → Gloss 序列 → 中文文本
"""
import os
import sys
import cv2
import torch
import numpy as np
from pathlib import Path

# 添加 TFNet 源码路径
sys.path.insert(0, str(Path(__file__).parent / "tfnet"))

from Net import moduleNet
from DataProcessMoudle import Word2Id


def optimize_cuda():
    """配置 CUDA 以获得最佳推理性能"""
    if torch.cuda.is_available():
        torch.backends.cudnn.benchmark = True
        torch.backends.cudnn.deterministic = False
        torch.backends.cuda.matmul.allow_tf32 = True
        torch.backends.cudnn.allow_tf32 = True
        torch.set_num_threads(1)  # GPU 模式不需要多 CPU 线程
        print(f"CUDA 优化已启用: {torch.cuda.get_device_name(0)}")


# 启动时自动配置
optimize_cuda()


def build_vocab(label_paths, data_set_name="CE-CSL"):
    """从数据集标注文件构建词表"""
    word2idx, vocab_size, idx2word = Word2Id(*label_paths, data_set_name)
    return word2idx, vocab_size, idx2word


def load_model(checkpoint_path, hidden_size, vocab_size, device, data_set_name="CE-CSL"):
    """加载 TFNet 模型和权重"""
    model = moduleNet(
        hiddenSize=hidden_size,
        wordSetNum=vocab_size + 1,  # +1 for blank
        moduleChoice="TFNet",
        device=device,
        dataSetName=data_set_name,
    )
    # 信任来自 GitHub 的预训练 checkpoint
    checkpoint = torch.load(checkpoint_path, map_location=device, weights_only=False)
    model.load_state_dict(checkpoint["moduleNet_state_dict"])
    model.to(device)
    model.eval()
    print(f"模型加载完成: {checkpoint_path}")
    print(f"  训练 epoch: {checkpoint.get('epoch', 'N/A')}")
    print(f"  最佳 WER: {checkpoint.get('bestWerScore', 'N/A')}")
    return model


def preprocess_frames(frames, target_size=(256, 256), crop_size=224):
    """
    预处理视频帧
    
    Args:
        frames: list of numpy arrays (H, W, 3), RGB
        target_size: resize to this size first
        crop_size: center crop to this size
        
    Returns:
        tensor: (T, 3, crop_size, crop_size), normalized to [-1, 1]
    """
    processed = []
    for frame in frames:
        # Resize
        img = cv2.resize(frame, target_size)
        # Center crop
        h, w = img.shape[:2]
        sh = (h - crop_size) // 2
        sw = (w - crop_size) // 2
        img = img[sh:sh + crop_size, sw:sw + crop_size]
        # HWC -> CHW
        img = img.transpose(2, 0, 1)
        # Normalize to [-1, 1]
        img = img.astype(np.float32) / 127.5 - 1.0
        processed.append(img)
    
    return torch.from_numpy(np.stack(processed)).float()


def pad_sequence(frames_tensor, left_pad=6, total_stride=4):
    """
    对帧序列进行 padding
    
    Args:
        frames_tensor: (T, C, H, W)
        left_pad: 左侧填充帧数
        total_stride: 总下采样率
        
    Returns:
        padded: (1, T_padded, C, H, W)
        length: 原始长度
    """
    T = frames_tensor.shape[0]
    right_pad = int(np.ceil(T / total_stride)) * total_stride - T + left_pad
    
    # Left pad: repeat first frame
    left_repeat = frames_tensor[:1].expand(left_pad, -1, -1, -1)
    # Right pad: repeat last frame
    right_repeat = frames_tensor[-1:].expand(right_pad, -1, -1, -1)
    
    padded = torch.cat([left_repeat, frames_tensor, right_repeat], dim=0)
    # Add batch dimension: (1, T_padded, C, H, W)
    padded = padded.unsqueeze(0)
    
    # Length after padding adjustment
    feat_len = torch.LongTensor([[int(np.ceil(T / total_stride) * total_stride + 2 * left_pad)]])
    
    return padded, feat_len


def extract_frames_from_video(video_path, sample_rate=1):
    """从视频文件中提取帧"""
    cap = cv2.VideoCapture(video_path)
    frames = []
    frame_idx = 0
    
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        if frame_idx % sample_rate == 0:
            # BGR -> RGB
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            frames.append(frame_rgb)
        frame_idx += 1
    
    cap.release()
    return frames


def extract_frames_from_image_dir(image_dir):
    """从图片目录中提取帧 (按文件名排序)"""
    image_exts = ('.jpg', '.jpeg', '.png', '.bmp')
    image_files = sorted([
        f for f in os.listdir(image_dir)
        if f.lower().endswith(image_exts)
    ])
    
    frames = []
    for fname in image_files:
        img_path = os.path.join(image_dir, fname)
        img = cv2.imread(img_path)
        img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        frames.append(img_rgb)
    
    return frames


@torch.inference_mode()
def inference(model, frames_tensor, feat_len, idx2word, device):
    """
    执行推理
    
    Args:
        model: TFNet model
        frames_tensor: (1, T, C, H, W)
        feat_len: (1, 1) tensor
        idx2word: list, index to gloss word mapping
        device: torch device
        
    Returns:
        gloss_list: list of (gloss_word, position)
        raw_text: gloss sequence string
    """
    data = frames_tensor.to(device, non_blocking=True)
    
    # 使用 FP16 混合精度推理加速
    with torch.amp.autocast(device_type="cuda" if "cuda" in str(device) else "cpu"):
        # Forward pass
        logProbs1, logProbs2, logProbs3, logProbs4, logProbs5, lgt, x1, x2, x3 = model(data, feat_len)
        
        # Use LogSoftmax
        log_softmax = torch.nn.LogSoftmax(dim=-1)
        probs = log_softmax(logProbs1)
    
    # Argmax decoding (non-CTC, simple max)
    indices = torch.argmax(probs, dim=-1)  # (T, B)
    indices = indices.squeeze(1)  # (T,)
    
    # Get actual length
    actual_len = lgt[0].item() if isinstance(lgt, list) else lgt.item()
    actual_len = min(actual_len, indices.shape[0])
    
    # Collapse repeated and remove blanks (blank_id=0)
    result_indices = []
    prev = -1
    for i in range(actual_len):
        idx = indices[i].item()
        if idx != 0 and idx != prev:
            result_indices.append(idx)
        prev = idx
    
    # Map to gloss words
    gloss_list = []
    for pos, idx in enumerate(result_indices):
        if idx < len(idx2word):
            gloss_list.append((idx2word[idx], pos))
    
    # Build raw text
    gloss_words = [g[0] for g in gloss_list]
    raw_text = "/".join(gloss_words)
    
    return gloss_list, raw_text, probs


def recognize_video(model, video_path, idx2word, device, sample_rate=1):
    """识别视频文件"""
    print(f"正在处理视频: {video_path}")
    frames = extract_frames_from_video(video_path, sample_rate)
    print(f"  提取了 {len(frames)} 帧")
    
    if len(frames) == 0:
        return [], "ERROR: 未能从视频中提取帧"
    
    return recognize_frames(model, frames, idx2word, device)


def recognize_frames(model, frames, idx2word, device):
    """识别帧序列"""
    # 预处理
    frames_tensor = preprocess_frames(frames)
    # Padding
    padded, feat_len = pad_sequence(frames_tensor)
    # 推理
    gloss_list, raw_text, probs = inference(model, padded, feat_len, idx2word, device)
    
    return gloss_list, raw_text


def _find_contiguous_regions(arr):
    """找到数组中连续的 True 区域"""
    regions = []
    in_region = False
    start = 0
    for i, val in enumerate(arr):
        if val and not in_region:
            start = i
            in_region = True
        elif not val and in_region:
            regions.append((start, i - 1))
            in_region = False
    if in_region:
        regions.append((start, len(arr) - 1))
    return regions


def _step_to_frame_range(start_step, end_step, total_frames, left_pad=6, stride=4, buffer_frames=15):
    """将模型输出的时间步映射回原始视频的帧区间"""
    start_frame = max(0, start_step * stride - left_pad - buffer_frames)
    end_frame = min(total_frames, (end_step + 1) * stride - left_pad + buffer_frames)
    return int(start_frame), int(end_frame)


@torch.inference_mode()
def locate_gloss_in_video(model, video_path, target_word, word2idx, device, frames=None):
    """
    在视频中定位指定手语词汇出现的帧区间

    Args:
        model: TFNet 模型
        video_path: 视频文件路径
        target_word: 要定位的 Gloss 词（如 "现在"）
        word2idx: 词到索引的映射
        device: torch device
        frames: 可选，预提取的 RGB 帧列表（避免重复读取）

    Returns:
        dict with start_frame, end_frame, start_time, end_time, confidence
        或 None（未找到）
    """
    # 1. 提取帧（或使用外部传入）
    if frames is None:
        frames = extract_frames_from_video(video_path)
    if not frames:
        return None
    total_frames = len(frames)
    fps = 30.0

    # 2. 预处理
    frames_tensor = preprocess_frames(frames)
    padded, feat_len = pad_sequence(frames_tensor)

    # 3. 推理
    data = padded.to(device, non_blocking=True)
    with torch.amp.autocast(device_type="cuda" if "cuda" in str(device) else "cpu"):
        logProbs1, _, _, _, _, lgt, _, _, _ = model(data, feat_len)
        log_softmax = torch.nn.LogSoftmax(dim=-1)
        probs = log_softmax(logProbs1)

    # 4. 目标词索引
    word_idx = word2idx.get(target_word)
    if word_idx is None:
        return None

    # 5. 提取目标词在每个时间步的概率
    actual_len = lgt[0].item() if isinstance(lgt, list) else lgt.item()
    target_log_probs = probs[:actual_len, 0, word_idx]  # (T',)
    target_probs = torch.exp(target_log_probs).cpu().numpy()

    # 6. 动态阈值（mean + 0.5*std，至少保留 top 10% 的步）
    mean = target_probs.mean()
    std = target_probs.std()
    threshold = max(mean + 0.5 * std, np.percentile(target_probs, 90))

    # 7. 找到连续的置信区域
    high_conf = target_probs > threshold
    regions = _find_contiguous_regions(high_conf)

    if not regions:
        # 兜底：取置信度最高的单步
        best_step = int(np.argmax(target_probs))
        start_f, end_f = _step_to_frame_range(best_step, best_step, total_frames)
        return {
            "start_frame": start_f,
            "end_frame": end_f,
            "start_time": start_f / fps,
            "end_time": end_f / fps,
            "confidence": float(target_probs[best_step]),
        }

    # 8. 选平均置信度最高的区域
    best_region = None
    best_score = -1.0
    for start_step, end_step in regions:
        avg_conf = float(target_probs[start_step:end_step + 1].mean())
        if avg_conf > best_score:
            best_score = avg_conf
            best_region = (start_step, end_step)

    if best_region is None:
        return None

    start_step, end_step = best_region
    start_f, end_f = _step_to_frame_range(start_step, end_step, total_frames)

    return {
        "start_frame": start_f,
        "end_frame": end_f,
        "start_time": start_f / fps,
        "end_time": end_f / fps,
        "confidence": best_score,
    }
