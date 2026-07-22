# 手语翻译系统 — 技术文档

## 系统架构

```
┌──────────────┐          ┌─────────────────────────────────┐
│  浏览器      │◀────────→│      Vue 3 前端 (5173)           │
│  (Chrome/etc)│          │  Vite 代理 /api → Django         │
│              │          │  Vite 代理 /video → Django        │
└──────────────┘          └──────────────┬──────────────────┘
                                          │ HTTP / SSE
                                          ▼
┌──────────────────────────────────────────────────────────────┐
│              Django 后端 (8000)                               │
│  ┌─────────────┐  ┌─────────────┐  ┌──────────────────┐    │
│  │  sign_api/   │  │ text_to_sign/│  │  records/        │    │
│  │  识别/生成/  │  │  三级检索    │  │  翻译记录 CRUD   │    │
│  │  配音/翻译   │  │  + 视频拼接  │  │                  │    │
│  └──────┬──────┘  └──────┬──────┘  └──────────────────┘    │
│         │                │                                   │
│         ▼                ▼                                   │
│  edge-tts        sentence-transformers                       │
│  (TTS 配音)      (句向量检索)                                │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  TFNet 推理引擎 (src/inference.py)                    │   │
│  │  ├─ 帧提取 + 预处理                                    │   │
│  │  ├─ 手语识别 → Gloss 序列                              │   │
│  │  └─ 视频词汇定位（拼接用）                              │   │
│  └──────────────────────────────────────────────────────┘   │
├──────────────────────────────────────────────────────────────┤
│  SQLite (db.sqlite3) / 视频文件 (data/video/)                │
└──────────────────────────────────────────────────────────────┘
```

## API 文档

所有 API 位于 `http://127.0.0.1:8000/api/`。

### AI 课堂（杏云同学）

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/chat/message` | 发送消息获取 DeepSeek 回复 |
| POST | `/api/chat/extract-sign` | 从 AI 回复中提取手语关键词 |
| POST | `/api/chat/speech-to-text` | 语音转文字（Vosk 离线 ASR，multipart WAV） |

**POST /api/chat/extract-sign** 请求体：
```json
{"reply": "手语"你好"是右手五指并拢..."}
```
响应：
```json
{"keyword": "你好"}
```

**POST /api/chat/speech-to-text** （multipart 上传 audio.wav）：
响应：
```json
{"text": "你好"}
```

### 翻译记录

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/records/` | 获取所有翻译记录 |
| POST | `/api/records/` | 创建翻译记录 |
| DELETE | `/api/records/:id/` | 删除指定记录 |

**POST /api/records/** 请求体：
```json
{
  "video_name": "train-00001.mp4",
  "gloss_text": "你 / 好 / 。",
  "chinese_text": "你好。"
}
```

### 文本→手语（三级检索）

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/sign/generate` | 文本匹配手语视频（非流式） |
| POST | `/api/sign/generate-stream` | 文本匹配（SSE 流式进度推送） |

**POST /api/sign/generate** 请求体：
```json
{"text": "你家住在哪里？"}
```

成功响应：
```json
{
  "video_id": "train-00608",
  "video_url": "/video/train/B/train-00608.mp4",
  "chinese_text": "你住在哪？",
  "gloss_text": "你 / 住 / 哪 / ？",
  "similarity": 0.78,
  "method": "retrieval",
  "note": "DeepSeek确认通过"
}
```

**POST /api/sign/generate-stream** 返回 SSE 事件流，每行一个 JSON：
```json
{"progress": 5, "status": "正在检索手语视频库..."}
{"progress": 20, "status": "正在匹配语义..."}
{"progress": 100, "status": "完成!", "type": "result", "video_id": "train-00608", "video_url": "/video/train/B/train-00608.mp4", ...}
```

### 视频拼接（兜底）

自动在 generate-stream 中触发，当三级检索全部失败时：

| 阶段 | 状态文字 | 说明 |
|------|---------|------|
| 30% | 未找到匹配，正在尝试视频拼接... | 进入拼接流程 |
| 50% | 正在剪辑视频... | TFNet 逐帧定位+裁剪 |
| 100% | 完成! | 返回拼接视频 URL |

拼接响应示例：
```json
{
  "progress": 100,
  "type": "result",
  "video_url": "/video/generated/A/stitch_现在几点了_1700000000.mp4",
  "chinese_text": "现在几点了",
  "gloss_text": "现在 / 几 / 点了",
  "method": "stitch",
  "note": "已拼接 2 个手语词汇片段"
}
```

### 视频翻译（手语→文本）

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/video/translate` | 上传视频识别手语（非流式，multipart） |
| POST | `/api/video/translate-stream` | 上传视频识别（SSE 流式进度推送） |

**POST /api/video/translate-stream** 流式推送阶段：

| 进度 | 状态文字 | 说明 |
|------|---------|------|
| 5% | 正在加载模型... | TFNet 模型初始化 |
| 20% | 正在提取视频帧... | OpenCV 逐帧读取 |
| 35% | TFNet 识别手语中（X 帧）... | 后台线程推理，每 2 秒更新 |
| 75% | DeepSeek 整理结果中... | LLM 整理 Gloss 为中文 |
| 95% | 即将完成... | — |

成功结果：
```json
{
  "progress": 100,
  "status": "完成!",
  "type": "result",
  "translation": "你好，今天天气真好。",
  "gloss_text": "你 / 好 / 今天 / 天气 / 真 / 好 / 。"
}
```

### 配音生成

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/video/dub` | 文本 → edge-tts 配音音频 |
| GET | `/api/video/dub-audio/<filename>` | 获取配音 MP3 文件 |

**POST /api/video/dub** 请求体：
```json
{"text": "你好，今天天气真好", "language": "zh"}
```

`language` 支持：`zh`（中文）、`en`（英文）、`yue`（粤语）、`sc`（四川方言）、`ja`（日语）。跨语言时自动调用 DeepSeek 翻译。

响应：
```json
{
  "audio_url": "/api/video/dub-audio/dub_你好_zh_1700000000.mp3",
  "duration": 3.5,
  "language": "zh"
}
```

### 视频直出

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/video/<subset>/<translator>/<video_id>` | 返回视频文件 |

支持 HTTP Range 请求（浏览器视频播放、拖动进度条）。

### 手语实时识别

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/sign/recognize` | 识别视频/Blob 中的手语 |

支持两种方式：
- 上传文件（multipart `video` 字段）
- 数据集路径（JSON `{"video_path": "train-00001.mp4"}`）

### AI 课堂

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/chat/message` | 发送消息获取 DeepSeek 回复 |
| POST | `/api/chat/extract-sign` | 从 AI 回复中提取手语关键词 |
| POST | `/api/chat/speech-to-text` | 语音转文字（Vosk 离线 ASR） |

### 鉴权

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/auth/login` | 登录 |
| POST | `/api/auth/register` | 注册 |
| POST | `/api/auth/logout` | 退出 |

## 三阶段混合检索 + 拼接兜底

```
输入文本
    │
    ├─ 阶段1: 句向量检索（相似度 ≥ 0.75）
    │   └─ DeepSeek 语义确认 → ✅ 返回匹配视频
    │
    ├─ 阶段2: DeepSeek 改写后检索
    │   └─ 改写用户输入再次检索 → ✅ 返回匹配视频
    │
    ├─ 阶段3: Gloss 序列匹配兜底
    │   └─ 用户输入→Gloss→找训练集中 Gloss 最相似 → ✅ 返回匹配视频
    │
    └─ 全部未命中 → 视频拼接
        │
        ├─ ① 清理旧拼接视频
        ├─ ② Gloss 分词 → ["现在", "几", "点了"]
        ├─ ③ 对每个词，从训练集中找包含该词的视频
        ├─ ④ TFNet 逐帧定位（核心创新）
        │     ├─ 读取视频所有帧
        │     ├─ 送入 TFNet，获取每个时间步对各词汇的置信度
        │     ├─ 提取目标词汇在各时间步的置信度曲线
        │     ├─ 动态阈值（mean+0.5*std）找到高置信连续区间
        │     └─ 将时间步映射回原始帧序号（步→帧: s*4−6±缓冲15帧）
        ├─ ⑤ 裁剪每个词的片段（H.264）
        └─ ⑥ 拼接 → 输出完整视频
```

阶段 4 的定位流程利用了 TFNet 模型输出 `logProbs1` 的 shape `(T', 1, vocab_size+1)`——每个时间步都包含对所有词汇的预测概率，无需额外训练。

### 关键决策

| 决策点 | 选型 | 理由 |
|--------|------|------|
| 检索为主 | 不直接走拼接 | 真人整句视频手势连贯、质量最高 |
| DeepSeek 核验 | 每个命中都要过 | 避免句向量语义偏差 |
| 拼接作为兜底 | 不尝试做数字人 | 复现真人手势，比 3D 数字人准确 |
| TFNet 逐帧定位 | 替代固定取前 1 秒 | 精确定位词汇出现的时间段 |
| 动态阈值 | mean+0.5*std | 自适应不同视频的置信度分布 |
| 近似不返回 | 不匹配则报"暂无" | 翻译需严谨，不让用户困惑 |

## 手语识别流程

```
视频文件 → 提取帧(OpenCV) → 预处理(Resize+CenterCrop+归一化)
    → TFNet 推理 → Gloss 序列 → DeepSeek 整理中文
```

支持 SSE 流式进度（`/api/video/translate-stream`）：分阶段推送 加载模型 → 提取帧 → TFNet 识别（多线程，每 2 秒更新）→ DeepSeek 整理 → 完成。

## 配音生成流程

```
文本 + 语言选择
    │
    ├─ 跨语言（如 zh→ja）→ DeepSeek 翻译
    └─ 中文直接使用原文
          │
          edge-tts 生成 MP3
          │
          保存至 data/video/dub/ → 返回音频 URL
```

## 句向量索引

使用 `shibing624/text2vec-base-chinese` 对所有训练集句子进行向量化：

- 索引维度：768
- 索引规模：~5988 条
- 检索速度：< 100ms/次（GPU 模式）
- 余弦相似度匹配

构建索引：
```bash
python -m backend.text_to_sign.sentence_index
```

## 配置文件说明

### requirements.txt

| 依赖 | 版本 | 用途 |
|------|------|------|
| torch | ≥2.0.0 | 深度学习框架 |
| torchvision | ≥0.15.0 | 图像处理 |
| opencv-python-headless | ≥4.8.0 | 视频/图像处理 |
| django | ≥5.0 | Web 框架 |
| djangorestframework | ≥3.15 | REST API |
| django-cors-headers | ≥4.0 | 跨域支持 |
| sentence-transformers | ≥3.0 | 语义检索 |
| imageio | ≥2.35.0 | 视频帧处理 |
| imageio-ffmpeg | ≥0.6.0 | H.264 编码 |
| edge-tts | ≥6.0 | 微软 Edge TTS 配音 |
| mutagen | ≥1.47 | 音频元数据（获取时长） |
| vosk | ≥0.3.45 | 离线中文语音识别（ASR） |

### run_app.bat

启动脚本依次启动两个服务：

1. `Django` — `python backend/manage.py runserver 0.0.0.0:8000`（新窗口）
2. `Vue 前端` — `cd sign_language && npm run dev`（新窗口）

### 视频自动清理

拼接生成的视频存储在 `data/video/generated/A/`。每次生成新视频前，系统自动删除该目录下所有旧文件，只保留最新一份。

配音音频存储在 `data/video/dub/`，以 `dub_文本_语言_时间戳.mp3` 格式命名。

### 数据集

项目原始数据 `ce_csl/` 与 `main/data/` 完全重复。系统仅使用 `main/data/` 作为唯一数据源。
