# 部署指南

本指南说明如何从零开始部署并启动手语翻译系统。

---

## 目录

- [环境要求](#环境要求)
- [快速启动（推荐）](#快速启动推荐)
- [分步部署](#分步部署)
  - [1. 创建 Python 虚拟环境](#1-创建-python-虚拟环境)
  - [2. 安装 Python 依赖](#2-安装-python-依赖)
  - [3. 安装前端依赖](#3-安装前端依赖)
  - [4. 下载 TFNet 模型权重](#4-下载-tfnet-模型权重)
  - [5. 可选：部署 GPT-SoVITS 音色克隆](#5-可选部署-gpt-sovits-音色克隆)
  - [6. 启动服务](#6-启动服务)
- [服务结构](#服务结构)
- [常见问题](#常见问题)

---

## 环境要求

| 项目 | 要求 |
|------|------|
| 操作系统 | Windows 10/11 或 Linux（推荐 Windows） |
| Python | 3.12 |
| Node.js | ≥ 18 |
| GPU | NVIDIA GPU, 8GB+ 显存（推荐） |
| CUDA | 12.x（GPU 模式必需） |
| 磁盘空间 | 至少 10GB（含模型文件） |

## 快速启动（推荐）

在项目根目录执行以下命令，然后双击 `run_app.bat`：

```bash
# 1. 创建并激活虚拟环境
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # Linux

# 2. 安装后端依赖
pip install -r requirements.txt

# 3. 配置环境变量
copy .env.example .env   # 然后编辑 .env 填入 DEEPSEEK_API_KEY

# 4. 安装音色克隆依赖
pip install -r voice_clone_server\requirements.txt

# 5. 安装前端依赖
cd sign_language
npm install
cd ..

# 6. 下载 TFNet 模型权重（见下方说明）

# 7. 启动所有服务
.\run_app.bat
```

> **注意：** 首次启动后，服务首次调用可能需要数分钟加载模型（BERT、HuBERT 等会自动下载），属于正常现象。

---

## 分步部署

### 1. 创建 Python 虚拟环境

```bash
python -m venv .venv
```

激活虚拟环境：

```bash
# Windows
.venv\Scripts\activate

# Linux
source .venv/bin/activate
```

### 2. 安装 Python 依赖

```bash
# 核心依赖
pip install -r requirements.txt

# 音色克隆代理服务依赖
pip install -r voice_clone_server\requirements.txt

# 可选：GPT-SoVITS 推理引擎依赖
# 如果不需要音色克隆功能可以跳过
cd voice_clone_server\GPT-SoVITS
pip install -r requirements.txt
cd ..\..
```

> 如果部分依赖安装失败（如 `jieba_fast`），可以忽略，系统会自动使用替代方案。

### 3. 配置环境变量

```bash
# 复制环境变量示例文件
copy .env.example .env
```

打开 `.env` 文件，填入你的 DeepSeek API Key：

```ini
DEEPSEEK_API_KEY=sk-your_key_here
```

> DeepSeek API Key 用于语义核验、文本改写、结果整理等功能。免费注册地址：https://platform.deepseek.com/

### 4. 安装前端依赖

```bash
cd sign_language
npm install
cd ..
```

### 4. 下载 TFNet 模型权重

模型文件需要手动下载，放入 `checkpoints/` 目录：

```bash
# 创建目录
mkdir checkpoints

# 下载 TFNet 预训练权重
# 文件名: TFNet-CE-CSL-CSLDaily-32.46.pth
# 下载链接（百度网盘）: https://pan.baidu.com/s/1KPbDL2nAvBsSsTDwc9og0A
# 提取码: 0000
# 原项目: https://github.com/woshisad159/TFNet
```

权重文件放入 `checkpoints/` 后，目录结构应为：

```
├── checkpoints/
│   └── TFNet-CE-CSL-CSLDaily-32.46.pth
├── src/
│   ├── inference.py
│   └── tfnet/
└── ...
```

### 5. 可选：部署 GPT-SoVITS 音色克隆

如果需要音色克隆功能（用户自录音色合成配音），需额外下载预训练模型：

```bash
# 创建模型目录
mkdir voice_clone_server\GPT-SoVITS\GPT_SoVITS\pretrained_models

# 下载 v2 模型权重，放入 pretrained_models/ 目录
# 需要以下文件:
#   pretrained_models/gsv-v2final-pretrained/s1bert25hz-5kh-longer-epoch=12-step=3698.ckpt
#   pretrained_models/gsv-v2final-pretrained/s2G2333k.pth

# GitHub 发布页面:
# https://github.com/RVC-Boss/GPT-SoVITS/releases
```

首次启动 GPT-SoVITS 引擎时，以下模型会自动从 Hugging Face 下载（建议使用镜像加速）：

```bash
# 使用国内镜像加速
set HF_ENDPOINT=https://hf-mirror.com
```

| 自动下载的模型 | 大小 | 说明 |
|---------------|------|------|
| `chinese-roberta-wwm-ext-large` | ~650MB | BERT 语言模型 |
| `chinese-hubert-base` | ~380MB | 音频特征提取 |
| `nvidia/bigvgan_v2_24khz_100band_256x` | ~400MB | 声码器 |
| `G2PWModel/g2pW.onnx` | ~670MB | 多音字消歧 ONNX 模型 |

### 7. 启动服务

系统由 4 个服务组成：

| 服务 | 端口 | 说明 | 是否必需 |
|------|------|------|---------|
| Django 后端 | 8000 | 核心 API | **必需** |
| Vue 前端 | 5173 | 用户界面 | **必需** |
| GPT-SoVITS 引擎 | 9870 | 音色克隆推理 | 可选 |
| 克隆代理 | 9880 | 克隆 API 代理 | 可选 |

**方式一：一键启动（推荐）**

```bash
.\run_app.bat
```

**方式二：手动逐个启动**

```bash
# 终端 1：Django 后端
.venv\Scripts\python.exe backend\manage.py runserver 0.0.0.0:8000

# 终端 2：Vue 前端
cd sign_language
npm run dev

# 终端 3（可选）：GPT-SoVITS 引擎
cd voice_clone_server\GPT-SoVITS
..\..\.venv\Scripts\python.exe api_v2.py -a 127.0.0.1 -p 9870 -c GPT_SoVITS/configs/tts_infer.yaml

# 终端 4（可选）：克隆代理
.venv\Scripts\python.exe voice_clone_server\api_server.py --port 9880
```

启动后访问 **http://localhost:5173** 即可使用系统。

---

## 服务结构

```
├── backend/                   # Django 后端 API
│   ├── manage.py              # Django 管理入口
│   ├── sign_api/              # 手语识别/生成/配音 API
│   ├── text_to_sign/          # 文本→手语检索
│   ├── records/               # 翻译记录
│   ├── config/                # Django 配置
│   ├── chat/                  # AI 课堂
│   └── users/                 # 用户管理
│
├── sign_language/             # Vue 3 前端
│   ├── package.json           # 前端依赖配置
│   └── vite.config.js         # 开发服务器配置（含 API 代理）
│
├── src/                       # TFNet 手语识别引擎
│   ├── inference.py           # 模型推理接口
│   └── tfnet/                 # TFNet 网络定义
│
├── voice_clone_server/        # 音色克隆服务
│   ├── api_server.py          # Flask 代理（端口 9880）
│   ├── GPT-SoVITS/            # GPT-SoVITS 推理引擎
│   │   ├── api_v2.py          # FastAPI 服务入口（端口 9870）
│   │   └── GPT_SoVITS/        # 模型代码
│   └── requirements.txt       # 克隆代理依赖
│
├── checkpoints/               # TFNet 模型权重（需手动放入）
├── requirements.txt           # 核心依赖
├── run_app.bat                # 一键启动脚本
├── .gitignore
└── DEPLOY.md                  # 本文件
```

---

## 常见问题

### Q：端口被占用

```bash
# 查看端口占用
netstat -ano | findstr :8000
# 或
netstat -ano | findstr :5173

# 强制结束进程
taskkill /F /PID <进程ID>
```

### Q：GPT-SoVITS 启动很慢或报错

首次启动会自动下载 BERT/HuBERT/BigVGAN 模型，视网络情况可能需要 5-30 分钟。

如果不需要音色克隆功能，可以不启动 GPT-SoVITS 引擎，系统会自动回退到 edge-tts 配音。

```bash
# 使用国内镜像加速
set HF_ENDPOINT=https://hf-mirror.com
```

### Q：缺少虚拟环境的 Python

确保在项目根目录下执行了：

```bash
python -m venv .venv
```

且终端已激活虚拟环境（命令行前缀显示 `(.venv)`）。

### Q：Vue 前端报模块找不到

```bash
cd sign_language
npm install
```

### Q：手语识别或检索报错

- 确认 `checkpoints/TFNet-CE-CSL-CSLDaily-32.46.pth` 已正确下载
- 确认 `backend/models/vosk-model-small-cn-0.22/` 目录完整（已包含在源码中）
- 确认 `backend/text_to_sign/index/` 目录存在（已包含在源码中）

### Q：音色克隆总是回退到默认音色

可能原因：
- GPT-SoVITS 引擎未启动（检查 9870 端口）
- 预训练模型文件未正确下载
- 参考音频未上传（在「语音库」页面录制上传）

### Q：如何修改后端端口？

编辑 `run_app.bat` 中的 `runserver` 参数，或直接运行：

```bash
.venv\Scripts\python.exe backend\manage.py runserver 0.0.0.0:端口号
```

同时修改 `sign_language/vite.config.js` 中的代理目标地址。
