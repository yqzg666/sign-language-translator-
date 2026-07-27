"""
句向量索引 — 构建与检索
使用 sentence-transformers 对所有训练句子做向量化，支持余弦相似度搜索。
"""
import csv
import math
import os
import pickle
from pathlib import Path

import numpy as np

# 项目根目录
BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = BASE_DIR / "data"
INDEX_DIR = BASE_DIR / "backend" / "text_to_sign" / "index"

# 设置 Hugging Face 国内镜像
os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")

# 模型名称 (轻量中文句向量)
EMBEDDING_MODEL = "shibing624/text2vec-base-chinese"
# EMBEDDING_MODEL = "BAAI/bge-small-zh-v1.5"  # 更快的备选


def _load_records():
    """从 label CSV 加载所有句子 + gloss + 视频路径"""
    records = []
    for subset in ("train", "dev", "test"):
        csv_path = DATA_DIR / "label" / f"{subset}.csv"
        if not csv_path.exists():
            continue
        with open(csv_path, encoding="utf-8") as f:
            reader = csv.reader(f)
            next(reader)  # skip header
            for row in reader:
                if len(row) < 4:
                    continue
                video_id = row[0].strip()  # train-00001
                translator = row[1].strip()  # A-L
                chinese = row[2].strip()
                gloss = row[3].strip()
                # video path 可能是 .mp4 或图片目录
                video_dir = subset
                video_path = DATA_DIR / "video" / video_dir / translator / f"{video_id}.mp4"
                records.append({
                    "video_id": video_id,
                    "video_path": str(video_path),
                    "chinese": chinese,
                    "gloss": gloss,
                    "subset": subset,
                })
    return records


def build_index():
    """对所有训练句子计算向量并保存"""
    # 设置 Hugging Face 国内镜像
    os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")

    print("加载记录...")
    records = _load_records()
    print(f"  共 {len(records)} 条")

    print(f"加载嵌入模型 {EMBEDDING_MODEL}...")
    from sentence_transformers import SentenceTransformer
    model = SentenceTransformer(EMBEDDING_MODEL)
    device = "cuda" if hasattr(model, "to") else "cpu"
    model = model.to(device)
    print(f"  模型就绪 (device={device})")

    texts = [r["chinese"] for r in records]

    print("计算句向量...")
    embeddings = model.encode(
        texts,
        batch_size=64,
        show_progress_bar=True,
        normalize_embeddings=True,  # 归一化后可直接用点积 = 余弦相似度
    )
    embeddings = np.array(embeddings, dtype=np.float32)
    print(f"  向量形状: {embeddings.shape}")

    # 保存
    INDEX_DIR.mkdir(parents=True, exist_ok=True)
    np.save(INDEX_DIR / "embeddings.npy", embeddings)
    with open(INDEX_DIR / "records.pkl", "wb") as f:
        pickle.dump(records, f)
    print(f"索引已保存至 {INDEX_DIR}")


class SentenceSearcher:
    """句向量检索器 — 单例，加载一次即可复用"""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._loaded = False
        return cls._instance

    def load(self):
        if self._loaded:
            return
        index_file = INDEX_DIR / "embeddings.npy"
        records_file = INDEX_DIR / "records.pkl"
        if not index_file.exists():
            raise FileNotFoundError(
                f"索引文件不存在，请先运行 python -m backend.text_to_sign.sentence_index 构建索引"
            )
        self.embeddings = np.load(index_file)
        with open(records_file, "rb") as f:
            self.records = pickle.load(f)

        # 加载句向量模型（一次，后续复用）
        from sentence_transformers import SentenceTransformer
        self._model = SentenceTransformer(EMBEDDING_MODEL)

        self._loaded = True
        print(f"句向量索引已加载: {len(self.records)} 条, 维度 {self.embeddings.shape[1]}")

    def search(self, query, top_k=5):
        """检索最相似的 top_k 条记录，返回 (records, scores)"""
        self.load()

        query_vec = self._model.encode(
            [query],
            normalize_embeddings=True,
        )
        query_vec = np.array(query_vec, dtype=np.float32)

        # 余弦相似度
        scores = np.dot(self.embeddings, query_vec.T).flatten()
        top_indices = np.argsort(-scores)[:top_k]

        results = []
        for idx in top_indices:
            results.append({
                "record": self.records[idx],
                "score": float(scores[idx]),
            })
        return results


def _find_best_match_by_gloss(gloss_text, top_k=5):
    """用 Gloss 序列找最相似的视频 (简单字符级别重叠)"""
    from difflib import SequenceMatcher

    records = _load_records()
    gloss_set = set(g.strip() for g in gloss_text.split("/") if g.strip())

    scored = []
    for r in records:
        r_gloss_set = set(g.strip() for g in r["gloss"].split("/") if g.strip())
        if not gloss_set or not r_gloss_set:
            continue
        # Jaccard 相似度
        intersection = gloss_set & r_gloss_set
        union = gloss_set | r_gloss_set
        score = len(intersection) / len(union) if union else 0
        scored.append((score, r))

    scored.sort(key=lambda x: -x[0])
    results = []
    for score, r in scored[:top_k]:
        results.append({"record": r, "score": score})
    return results


def find_video_by_gloss_word(word, records=None):
    """
    为单个 Gloss 词找到最佳的训练视频
    优先选择: 词在序列中出现早 + 序列总长度短的视频
    """
    if records is None:
        records = _load_records()

    candidates = []
    for r in records:
        gloss_words = [g.strip() for g in r["gloss"].rstrip("。").split("/") if g.strip()]
        if word in gloss_words:
            pos = gloss_words.index(word)
            # 得分：位置早（pos+1 越小越好）* 句长短（num_words 越小越好）
            score = 1.0 / (pos + 1) * (1.0 / len(gloss_words))
            candidates.append((score, r, pos))

    if not candidates:
        return None

    candidates.sort(key=lambda x: -x[0])
    return candidates[0][1]  # 返回最佳匹配记录


if __name__ == "__main__":
    build_index()
