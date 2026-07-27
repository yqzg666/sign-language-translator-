# 手语翻译系统

基于深度学习的中文手语（CSL）翻译系统，支持 **手语→文本** 和 **文本→手语视频** 双向翻译，集成AI课堂、多语种配音、音色克隆等功能。

## 功能

| 功能 | 说明 |
|------|------|
| **手语→文本** | 上传/录制手语视频 → TFNet 识别 → DeepSeek 整理为中文 |
| **文本→手语** | 输入中文 → 三阶段检索匹配手语视频（不匹配时自动视频拼接兜底） |
| **视频翻译配音** | 手语识别 → 多语种 TTS 配音（中/英/粤/川/日），支持 GPT-SoVITS 音色克隆 |
| **音色克隆** | 录制自己的声音 → GPT-SoVITS 零样本克隆 → 用克隆音色合成配音 |
| **AI 课堂（杏云同学）** | AI 对话教学，回复可生成手语视频，支持语音输入 |
| **手语实时识别** | 上传视频/Blob → TFNet 逐帧识别 → DeepSeek 组织语句 |
| **历史记录** | 查看所有翻译记录，支持删除管理 |

## 文本→手语策略（三阶段混合检索 + 视频拼接兜底）

```
用户输入中文句子
    │
    ├─ 阶段1: 句向量检索 + DeepSeek 语义确认 → ✅ 返回完整视频
    ├─ 阶段2: DeepSeek 改写后再次检索       → ✅ 返回完整视频
    ├─ 阶段3: Gloss 序列匹配兜底            → ✅ 返回完整视频
    └─ 全部未命中 → 视频拼接
          ├─ Gloss 分词 → 训练集中找含该词的视频
          ├─ TFNet 逐帧扫描精确定位手势出现时间段
          └─ 裁剪各段 → H.264 拼接输出
```

阶段4 使用 TFNet 模型输出的置信度曲线，动态阈值定位每个词汇在视频帧中的准确位置，而非固定取前 N 秒。

## 快速开始

### 环境要求

- Python 3.12
- CUDA 12+（GPU 加速，强烈推荐）
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
# 下载 TFNet-CE-CSL-CSLDaily-32.46.pth 放入 checkpoints/ 目录
# 百度网盘: https://pan.baidu.com/s/1KPbDL2nAvBsSsTDwc9og0A  提取码: 0000

# 4. 安装前端依赖
cd sign_language
npm install
cd ..
```

### 启动

双击 `run_app.bat`（推荐），或手动启动各服务：

```bash
# 终端1: Django 后端（端口 8000）
python backend/manage.py runserver 0.0.0.0:8000

# 终端2: Vue 前端（端口 5173）
cd sign_language
npm run dev

# 终端3（可选）: GPT-SoVITS 推理引擎（端口 9870）
# cd voice_clone_server/GPT-SoVITS
# python api_v2.py -a 127.0.0.1 -p 9870 -c GPT_SoVITS/configs/tts_infer.yaml

# 终端4（可选）: 音色克隆代理服务（端口 9880）
# cd voice_clone_server
# python api_server.py --port 9880
```

`run_app.bat` 会自动启动全部 4 个服务（后两个可选，缺失时自动 fallback 至 edge-tts）。
访问 **http://localhost:5173** 即可使用系统。

## 音色克隆部署（可选）

```bash
cd voice_clone_server

# 安装依赖
pip install -r requirements.txt

# 一键启动 GPT-SoVITS 引擎 + 代理服务
run_server.bat
```

详细部署步骤见 [技术文档](TECHNICAL.md#音色克隆GPT-SoVITS)。

## 项目结构

```
main/                          # 项目根目录
├── backend/                   # Django 后端
│   ├── config/                # Django 配置、根路由
│   ├── records/               # 翻译记录 CRUD
│   ├── sign_api/              # 手语识别/生成/配音 API
│   ├── text_to_sign/          # 文本→手语（三阶段检索 + 拼接）
│   ├── chat/                  # AI 课堂 API（含 Vosk ASR）
│   └── users/                 # 用户鉴权（登录/注册）
├── sign_language/             # Vue 3 前端
│   └── src/
│       ├── api/               # 后端接口契约
│       ├── components/        # 组件（Tab 页、侧边栏、素材库）
│       ├── store/             # 状态管理
│       └── views/             # 页面视图
├── src/                       # 推理引擎
│   ├── inference.py           # TFNet 模型推理 + 视频词汇定位
│   └── tfnet/                 # TFNet 网络定义
├── voice_clone_server/        # 音色克隆服务
│   ├── api_server.py          # 克隆代理 API（Flask, 端口 9880）
│   ├── GPT-SoVITS/            # GPT-SoVITS 推理引擎
│   │   ├── api_v2.py          # 推理 API 服务（FastAPI, 端口 9870）
│   │   └── GPT_SoVITS/        # 模型代码
│   ├── requirements.txt
│   └── run_server.bat
├── checkpoints/               # TFNet 模型权重（需手动下载）
├── data/                      # 手语视频 + 生成产物
│   ├── label/                 # CSV 标注文件
│   ├── video/train/           # 训练集手语视频
│   ├── video/generated/       # 拼接输出视频
│   └── video/dub/             # 配音音频文件
├── requirements.txt
├── README.md
├── TECHNICAL.md
├── DEPLOY.md
└── run_app.bat
```

## API 概览

所有 API 位于 `http://127.0.0.1:8000/api/`。完整文档见 [TECHNICAL.md](TECHNICAL.md#API-文档)。

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/sign/recognize` | 手语→文本识别 |
| POST | `/api/sign/generate` | 文本→手语视频匹配 |
| POST | `/api/sign/generate-stream` | 文本→手语（SSE 流式进度） |
| POST | `/api/video/translate` | 上传视频识别手语 |
| POST | `/api/video/translate-stream` | 上传视频识别（SSE 流式进度） |
| POST | `/api/video/dub` | 文本→TTS 配音（edge-tts） |
| POST | `/api/video/dub-v2` | 文本→配音（支持音色克隆） |
| GET | `/api/video/dub-audio/<filename>` | 获取配音音频文件 |
| POST | `/api/voice/reference` | 上传参考音频用于音色克隆 |
| GET | `/api/voice/references` | 列出已保存的参考音色 |
| DELETE | `/api/voice/references/<name>` | 删除指定音色 |
| POST | `/api/chat/message` | AI 课堂对话 |
| POST | `/api/chat/extract-sign` | 从 AI 回复中提取手语关键词 |
| POST | `/api/chat/speech-to-text` | 语音转文字（Vosk 离线 ASR） |
| POST | `/api/auth/login` | 用户登录 |
| POST | `/api/auth/register` | 用户注册 |
| POST | `/api/auth/logout` | 退出登录 |
| GET | `/api/records/` | 翻译记录列表 |

## 技术栈

| 层级 | 技术 | 用途 |
|------|------|------|
| **前端** | Vue 3 + Vite 5 | 用户界面 |
| **后端** | Django 5 + DRF | REST API |
| **模型** | TFNet（3D ResNet + BiLSTM + SENet） | 手语识别 |
| **语义检索** | sentence-transformers（text2vec-base-chinese） | 文本→手语匹配 |
| **LLM** | DeepSeek API | 语义核验、文本改写、结果整理 |
| **TTS** | edge-tts（微软 Edge 在线语音） | 多语种配音 |
| **音色克隆** | GPT-SoVITS v2 | 零样本声音克隆 |
| **ASR** | Vosk | 离线中文语音识别 |
| **视频处理** | OpenCV + imageio-ffmpeg（H.264） | 帧提取、裁剪、拼接 |
| **深度学习** | PyTorch 2 + CUDA | GPU 加速推理 |

## 致谢

本项目基于以下开源工作，特此致谢：

| 项目 | 引用 |
|------|------|
| [TFNet](https://github.com/woshisad159/TFNet) — 连续手语识别网络 | Zhu et al., [Continuous Sign Language Recognition via Temporal Super-Resolution Network](https://arxiv.org/pdf/2207.00928.pdf), arXiv 2022 |
| [GPT-SoVITS](https://github.com/RVC-Boss/GPT-SoVITS) — 零样本语音克隆 | 开源语音克隆框架 |
| [CE-CSL Dataset](https://pan.baidu.com/s/1OHJLRfLFPWqkxvLBr4KAQg) — 手语数据集 | 中国连续手语数据集 |

## 详细文档

- [技术文档](TECHNICAL.md) — 完整 API 文档、三阶段检索策略、TFNet 精确定位原理、音色克隆部署指南
