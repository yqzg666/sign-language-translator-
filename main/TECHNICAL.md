# 手语翻译系统 — 技术文档

## 系统架构

```
┌──────────────┐          ┌──────────────────────────────────────┐
│  浏览器      │◀────────→│     Vue 3 前端 (5173)                 │
│  (Chrome/etc)│          │  Vite 代理 /api → Django             │
│              │          │  Vite 代理 /video → Django           │
│              │          │                                      │
│              │  音色克隆流程（可选）                            │
│              │  前端录制 → Django(8000)                        │
│              │    → 克隆代理(9880) → GPT-SoVITS(9870)          │
└──────────────┘          └──────────────┬───────────────────────┘
                                          │ HTTP / SSE
                                          ▼
┌──────────────────────────────────────────────────────────────┐
│              Django 后端 (8000)                                │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌─────────────┐  │
│  │ sign_api │  │ text_to_ │  │ records  │  │   chat      │  │
│  │ 识别/生成 │  │ sign     │  │ 翻译记录 │  │ AI 课堂    │  │
│  │ 配音/音色 │  │ 三阶段   │  │ CRUD     │  │ + Vosk ASR │  │
│  │ 管理      │  │ 检索+拼接│  │          │  │             │  │
│  └─────┬────┘  └─────┬────┘  └──────────┘  └─────────────┘  │
│        │              │                                       │
│        ▼              ▼                                       │
│  edge-tts       sentence-transformers                         │
│  (TTS 配音)     (句向量检索)                                  │
│                                                               │
│  ┌───────────────────────────────────────────────────────┐   │
│  │  TFNet 推理引擎 (src/inference.py)                     │   │
│  │  ├─ 帧提取 + 预处理                                     │   │
│  │  ├─ 手语识别 → Gloss 序列                               │   │
│  │  └─ 视频词汇定位（拼接用）                              │   │
│  └───────────────────────────────────────────────────────┘   │
├───────────────────────────────────────────────────────────────┤
│  SQLite (db.sqlite3) / 视频文件 (data/video/)                 │
└───────────────────────────────────────────────────────────────┘
```

## API 文档

所有 API 位于 `http://127.0.0.1:8000/api/`。

### 手语→文本

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/sign/recognize` | 识别手语视频/Blob → 文本 |
| POST | `/api/video/translate` | 上传视频识别手语（非流式，multipart） |
| POST | `/api/video/translate-stream` | 上传视频识别（SSE 流式进度推送） |

**POST /api/sign/recognize** 支持两种方式：

- 上传文件（multipart `video` 字段）
- 数据集路径（JSON `{"video_path": "train-00001.mp4"}`）

响应：
```json
{"result": "你好", "gloss_text": "你 / 好"}
```

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

### 文本→手语（三阶段检索 + 视频拼接）

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

当三阶段检索全部失败时，generate-stream 自动触发拼接流程：

| 进度 | 状态文字 | 说明 |
|------|---------|------|
| 30% | 未找到匹配，正在尝试视频拼接... | 进入拼接流程 |
| 50% | 正在剪辑视频... | TFNet 逐帧定位 + 裁剪 |
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

### 视频直出

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/video/<subset>/<translator>/<video_id>` | 返回视频文件 |

支持 HTTP Range 请求（浏览器视频播放、拖动进度条）。

### 配音生成

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/video/dub` | 文本 → edge-tts 配音（多语种） |
| POST | `/api/video/dub-v2` | 文本 → 配音（支持音色克隆） |
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

**POST /api/video/dub-v2** 请求体：
```json
{"text": "你好，今天天气真好", "language": "zh", "voice_name": "马子欣"}
```

- `voice_name` 可选：指定已上传的参考音色名称，使用 GPT-SoVITS 真实克隆
- 不指定或克隆失败时自动回退到 edge-tts

### 音色克隆管理

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/voice/reference` | 上传参考音频 + 文本（multipart） |
| GET | `/api/voice/references` | 列出已保存的参考音色 |
| DELETE | `/api/voice/references/<name>` | 删除指定音色 |
| GET | `/api/voice/audio/<name>/<filename>` | 获取参考音频文件 |

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

### 鉴权

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/auth/login` | 登录 |
| POST | `/api/auth/register` | 注册 |
| POST | `/api/auth/logout` | 退出 |

---

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
        │     └─ 将时间步映射回原始帧序号（步→帧: s*4-6±缓冲15帧）
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

---

## 手语识别流程

```
视频文件 → 提取帧(OpenCV) → 预处理(Resize+CenterCrop+归一化)
    → TFNet 推理 → Gloss 序列 → DeepSeek 整理中文
```

支持 SSE 流式进度（`/api/video/translate-stream`）：分阶段推送 加载模型 → 提取帧 → TFNet 识别（多线程，每 2 秒更新）→ DeepSeek 整理 → 完成。

---

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

多语种配音流程（v2 支持音色克隆）：

```
dub-v2 请求
    │
    ├─ 有 voice_name → 查找本地参考音频
    │   ├─ 找到 → 转发至克隆代理 (9880)
    │   │   ├─ GPT-SoVITS (9870) 可用 → 返回克隆音频
    │   │   └─ 不可用 → edge-tts fallback（按 voice_name 映射发音人）
    │   └─ 未找到 → edge-tts 默认音色
    │
    └─ 无 voice_name → 直接走 edge-tts
```

---

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

---

## 配置文件

### requirements.txt

见项目根目录的 `requirements.txt`，包含 PyTorch、Django、DRF、sentence-transformers、edge-tts、OpenCV、imageio-ffmpeg 等核心依赖。

### run_app.bat

启动脚本依次启动四个服务：

1. **Django 后端** — `python backend/manage.py runserver 0.0.0.0:8000`
2. **Vue 前端** — `cd sign_language && npm run dev`
3. **GPT-SoVITS 推理引擎** — `api_v2.py :9870`（可选，文件不存在时自动跳过）
4. **音色克隆代理** — `api_server.py :9880`（可选，文件不存在时自动跳过）

后两个服务缺失时不影响系统核心功能（配音回退 edge-tts）。

### 视频/音频文件管理

| 类型 | 存储路径 | 说明 |
|------|---------|------|
| 拼接视频 | `data/video/generated/A/` | 每次生成前自动清理旧文件 |
| 配音音频 | `data/video/dub/` | `dub_文本_语言_时间戳.mp3` 命名 |
| 参考音频 | `voice_clone_server/ref_audio/<音色名>/` | 用户上传 |
| 克隆输出 | `voice_clone_server/output/` | 克隆代理合成结果 |

---

## 音色克隆（GPT-SoVITS）

系统支持通过 GPT-SoVITS 实现零样本音色克隆，让配音使用用户自己的声音。

### 架构

```
┌──────────┐    ┌──────────┐    ┌─────────────┐    ┌─────────────┐
│ 前端录制  │ →  │ Django   │ →  │ 克隆代理服务  │ →  │ GPT-SoVITS  │
│VoiceLib  │    │/dub-v2   │    │:9880/clone  │    │:9870/tts    │
│rary.vue  │    │(views.py)│    │api_server.py│    │api_v2.py    │
└──────────┘    └──────────┘    └─────────────┘    └──────┬──────┘
                                                          │
                                              ┌───────────▼──────────┐
                                              │  v2 预训练模型       │
                                              │  (gsv-v2final-       │
                                              │   pretrained/)       │
                                              │  + BERT/HuBERT       │
                                              │  (自动下载)          │
                                              └──────────────────────┘
```

GPT-SoVITS 不可用时，克隆代理自动回退到 edge-tts（按音色名称哈希映射不同发音人）。

### 组件说明

| 组件 | 路径 | 端口 | 说明 |
|------|------|------|------|
| GPT-SoVITS 推理引擎 | `voice_clone_server/GPT-SoVITS/api_v2.py` | 9870 | FastAPI 服务，加载 v2 模型进行零样本推理 |
| 克隆代理服务 | `voice_clone_server/api_server.py` | 9880 | Flask 服务，代理请求并处理 fallback |
| v2 模型文件 | `GPT-SoVITS/GPT_SoVITS/pretrained_models/gsv-v2final-pretrained/` | — | s1bert25hz + s2G2333k.pth |
| BERT 模型 | 首次启动 `api_v2.py` 时自动下载 | — | chinese-roberta-wwm-ext-large |
| HuBERT 模型 | 首次启动 `api_v2.py` 时自动下载 | — | chinese-hubert-base |
| 前端语音库 | `sign_language/src/components/sidebar/VoiceLibrary.vue` | — | 录音 → 上传 → 选音色配音 |

### 用户操作流程

1. 进入侧边栏「语音库」
2. 点击「录制」→ 对着麦克风说话（3-10 秒）
3. 输入刚才说的文本（如"大家好，欢迎使用手语翻译系统"）
4. 点击「上传」→ 参考音频保存到后端
5. 在视频翻译 Tab 中，选择「中文」，系统自动使用该克隆音色合成配音
6. 若 GPT-SoVITS 服务未启动，自动回退 edge-tts（不同音色名映射不同发音人）

### 部署要求

- GPU: 推荐 6GB+ 显存（零样本推理约 4GB）
- 模型文件（~2.5GB）：
  - v2 权重：s1bert25hz (148MB) + s2G2333k (101MB)
  - BERT 模型：chinese-roberta-wwm-ext-large (~500MB)
  - HuBERT 模型：chinese-hubert-base (~400MB)
- 磁盘空间：建议预留 10GB

### 音色克隆部署步骤

```bash
# 1. 进入音色克隆服务目录
cd voice_clone_server

# 2. 安装 Python 依赖
pip install -r requirements.txt

# 3. 一键启动（GPT-SoVITS 引擎 + 代理服务）
run_server.bat

# GPT-SoVITS 首次启动会自动下载 BERT/HuBERT 模型，
# 使用国内镜像可设置环境变量:
# set HF_ENDPOINT=https://hf-mirror.com
```

或直接使用 `main/run_app.bat`，该脚本已包含音色克隆服务的启动逻辑。

### 架构说明

- **GPT-SoVITS API（9870 端口）**：实际推理引擎，加载 v2 模型，接收参考音频 + 文本，返回克隆语音
- **克隆代理（9880 端口）**：中间层，兼容 Django 调用的 API 格式，将请求转换为 GPT-SoVITS 格式，失败时 fallback 至 edge-tts
- **Django `/api/video/dub-v2`**：前端直接调用的接口，处理参考音频查找、跨语言翻译等业务逻辑

### 启动

```bash
# 独立启动
cd voice_clone_server
run_server.bat

# 或随主系统启动（运行 main/run_app.bat 自动包含）
cd main
run_app.bat
```

音色克隆服务作为两个独立进程运行（9870 + 9880 端口）。若 GPT-SoVITS 服务未启动，配音功能自动回退 edge-tts，不影响系统其他功能。

### 已知问题

| 问题 | 解决方案 |
|------|---------|
| `jieba_fast` 编译失败 | 替换为 `jieba` 并修改所有导入 |
| `torchcodec` 缺少 FFmpeg 运行时 | 使用 `soundfile` 补丁（已内置） |
| BERT/HuBERT 模型国内下载慢 | 使用 `hf-mirror.com` 镜像 |
| 端口 9870 被占用 | `taskkill /F /PID <pid>` 后重试 |
| NLTK 资源缺失 | 手动转换 `averaged_perceptron_tagger` 至 JSON 格式 |

---

## TFNet 推理引擎

TFNet 是系统的核心手语识别模型，位于 `src/` 目录。

### 网络结构

- **视觉编码器**：3D ResNet（视频帧序列 → 时空特征）
- **时序建模**：BiLSTM（双向 LSTM 捕获时序依赖）
- **注意力**：SENet（通道注意力增强）
- **输出**：每个时间步对各词汇的预测概率 `logProbs1` shape `(T', 1, vocab_size+1)`

### 推理流程

```
视频 → 帧提取(OpenCV) → Resize(224x224) → CenterCrop → 归一化
    → TFNet 前向 → logProbs1 → argmax → Gloss 序列
    → 去重 → DeepSeek 整理 → 中文文本
```

### 拼接定位原理

拼接时利用 `logProbs1` 中目标词汇在各时间步的置信度曲线：

1. 提取目标词汇在 `logProbs1` 中所有时间步的概率值
2. 计算动态阈值：`mean + 0.5 * std`
3. 找到高于阈值的连续区间
4. 映射回原始帧序号：`时间步 × 4 - 6 ± 15 帧缓冲`
5. 裁剪对应视频段 → H.264 拼接
