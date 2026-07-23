# 手语翻译系统

基于深度学习的中文手语（CSL）翻译系统，支持**手语→文本**和**文本→手语视频**双向翻译。

## 功能

| 功能 | 说明 |
|------|------|
| **手语→文本** | 上传/录制手语视频 → TFNet 识别 → DeepSeek 整理为中文 |
| **文本→手语** | 输入中文 → 句向量检索匹配手语视频（不匹配时自动拼接） |
| **视频翻译配音** | 上传视频识别手语 → 多语种 TTS 配音（中文/英文/粤语/四川方言/日语） |
| **音色克隆** | 录制自己的声音 → GPT-SoVITS 零样本克隆 → 用克隆音色合成配音 |
| **AI 课堂（杏云同学）** | AI 对话教学，回复可生成手语视频，🎤 语音输入 |
| **手语实时识别** | 摄像头实时捕获 → 逐帧识别 → DeepSeek 组织语句 |
| **历史记录** | 查看所有翻译记录，支持删除 |

## 文本→手语策略（三级检索 + 拼接兜底）

```
用户输入中文句子
    │
    ├─ ① 句向量检索 + DeepSeek 语义确认 → ✅ 返回完整视频
    ├─ ② DeepSeek 改写后再次检索       → ✅ 返回完整视频
    ├─ ③ Gloss 序列匹配兜底            → ✅ 返回完整视频
    └─ ④ 视频拼接（以上均失败时）
          ├─ Gloss 分词 → 找训练视频
          ├─ TFNet 逐帧扫描定位该词出现的时间段
          └─ 精确裁剪各段 → 拼接 → H.264 输出
```

第四级拼接不使用固定取前 1 秒，而是调用 TFNet 识别模型扫描视频每一帧的置信度，**精确定位词汇的手势在视频中出现的时间段**后再裁剪。

## 快速开始

### 环境要求

- Python 3.12
- CUDA 12+（GPU 加速，非必需但强烈推荐）
- Node.js ≥ 18（前端构建）
- Windows / Linux

### 安装

```bash
# 1. 创建 Python 虚拟环境
python -m venv .venv
.venv\Scripts\activate      # Windows
source .venv/bin/activate    # Linux

# 2. 安装 Python 依赖
pip install -r requirements.txt

# 3. 下载模型权重
# 将 TFNet-CE-CSL-CSLDaily-32.46.pth 放入 checkpoints/ 目录

# 4. 安装前端依赖
cd sign_language
npm install
cd ..
```

### 启动

双击 `run_app.bat`，或手动分两步执行：

```bash
# 终端 1: 启动 Django 后端（端口 8000）
python backend/manage.py runserver 0.0.0.0:8000

# 终端 2: 启动 Vue 前端（端口 5173）
cd sign_language
npm run dev
```

访问 **http://localhost:5173** 使用系统。

## 项目结构

```
main/
├── backend/               # Django 后端（API 服务）
│   ├── config/            # 项目配置、根路由
│   ├── records/           # 翻译记录 CRUD
│   ├── sign_api/          # 手语识别/生成/配音/翻译 API
│   └── text_to_sign/      # 文本→手语核心逻辑（三级检索 + 拼接）
├── src/                   # 推理引擎
│   ├── inference.py       # TFNet 模型推理 + 视频词汇定位
│   └── tfnet/             # TFNet 网络定义
├── sign_language/         # Vue 3 前端
│   ├── src/
│   │   ├── api/           # 后端接口契约
│   │   ├── components/    # UI 组件（Tab 页、侧边栏、素材）
│   │   ├── store/         # 状态管理
│   │   └── views/         # 页面视图
│   ├── package.json
│   └── vite.config.js
├── checkpoints/           # 模型权重
├── data/
│   ├── label/             # CSV 标注文件
│   └── video/             # 手语视频 + 拼接/配音生成视频
│       ├── generated/A/   # 拼接输出视频
│       └── dub/           # 配音音频文件
├── requirements.txt
└── run_app.bat
```

## 核心流程

### 手语→文本

```
视频文件 → 提取帧 → TFNet 推理 → Gloss 序列 → DeepSeek 整理中文
                                                   ↓
                                           实时流式进度推送
```

### 文本→手语（三级检索 + 拼接兜底）

```
用户输入 → 句向量检索 → DeepSeek 核验 → 命中返回
         → DeepSeek 改写检索         → 命中返回
         → Gloss 序列匹配            → 命中返回
         → 视频拼接（TFNet 精确定位裁剪）
```

### 视频翻译配音

```
上传视频 → 流式翻译（实时进度） → 译文展示
                                   ↓
                         选择语言 → edge-tts TTS → 独立播放条播放
```

## API 概览

所有 API 位于 `http://127.0.0.1:8000/api/`。

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/sign/recognize` | 手语→文本识别 |
| POST | `/api/sign/generate` | 文本→手语视频匹配 |
| POST | `/api/sign/generate-stream` | 文本→手语（SSE 流式进度） |
| POST | `/api/video/translate` | 上传视频翻译手语 |
| POST | `/api/video/translate-stream` | 上传视频翻译（SSE 流式进度） |
| POST | `/api/video/dub` | 文本→TTS 配音音频 |
| GET  | `/api/video/dub-audio/<filename>` | 获取配音音频文件 |
| POST | `/api/chat/message` | AI 课堂对话 |
| POST | `/api/chat/extract-sign` | 从 AI 回复中提取手语关键词 |
| POST | `/api/chat/speech-to-text` | 语音转文字（Vosk 离线 ASR） |
| POST | `/api/auth/login` | 用户登录 |
| POST | `/api/auth/register` | 用户注册 |
| GET  | `/api/records/` | 翻译记录列表 |

## 技术栈

- **前端**：Vue 3 + Vite 5
- **后端**：Django 5 + DRF
- **模型**：TFNet（3D ResNet + BiLSTM + SENet）
- **语义检索**：sentence-transformers（text2vec-base-chinese）
- **LLM**：DeepSeek API
- **TTS**：edge-tts（微软 Edge 在线语音）
- **ASR**：Vosk（离线中文语音识别）
- **视频处理**：OpenCV + imageio-ffmpeg（H.264）
- **深度学习**：PyTorch 2 + CUDA

## 详细文档

- [技术文档](TECHNICAL.md) — 完整 API 文档、三阶段检索策略、TFNet 精确定位原理
