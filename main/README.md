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
| **手部骨架实时描线** | 录制视频时，用 MediaPipe 实时检测手部 21 个关键点并叠加骨架线（趣味预览，不进录制视频） |
| **手语斩（背词模块）** | 百词斩式卡片记手语：词库自动从数据集 Gloss 提取，用 TFNet 预加载裁剪出单词手语视频并打标签；看词学动作 / 看手语猜词双向翻转，AI 动作要领，四选一答题，错题集，每日打卡与连续天数 |
| **历史记录** | 查看所有翻译记录，支持删除管理 |
| **我的素材** | 可持久化的素材库：文件夹 + 文本/图片/视频素材，存入后端数据库（SQLite），刷新后数据保留 |
| **界面美化** | 每个 Tab 配卡通角色背景图；底部导航、顶部按钮、麦克风等均使用角色插画；卡片统一透明毛玻璃（glassmorphism）风格 |

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
# 将 TFNet-CE-CSL-CSLDaily-32.46.pth 放入 checkpoints/ 目录

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
# cd ../voice_clone_server/GPT-SoVITS
# python api_v2.py -a 127.0.0.1 -p 9870 -c GPT_SoVITS/configs/tts_infer.yaml

# 终端4（可选）: 音色克隆代理服务（端口 9880）
# cd ../voice_clone_server
# python api_server.py --port 9880
```

`run_app.bat` 会自动启动全部 4 个服务（后两个可选，缺失时自动 fallback 至 edge-tts）。
访问 **http://localhost:5173** 即可使用系统。

### 手语斩词库预加载（可选）

「手语斩」词库自动从 `data/label/*.csv` 的 Gloss 序列提取，并可用 TFNet 从整句数据集视频中**裁剪出每个词的独立演示视频**并打标签（预加载后前端秒开，无需等检索生成）。运行一次即可，量大时可分批：

```bash
# 处理全部未生成词（第一次建议先小批验证）
python backend/manage.py preload_vocab --limit 80

# 全部预加载（会裁剪几百个词，耗时较长、占存储）
python backend/manage.py preload_vocab
```

未预加载的词在打开词卡时，后端 `generate` 接口仍会自动兜底（检索或拼接）。

> 前端「手语斩」页也提供「扩充词库」按钮，点击即触发下一批 80 词的后台预加载并实时显示进度。

## 音色克隆部署（可选）

```bash
cd ../voice_clone_server

# 安装依赖
pip install -r requirements.txt

# 一键启动 GPT-SoVITS 引擎 + 代理服务
run_server.bat
```

详细部署步骤见 [技术文档](TECHNICAL.md#音色克隆GPT-SoVITS)。

## 项目结构

```
csl/
├── main/                          # 主项目目录
│   ├── backend/                   # Django 后端
│   │   ├── config/                # Django 配置、根路由
│   │   ├── records/               # 翻译记录 + 素材库 CRUD（MaterialFolder/Material）
│   │   ├── sign_api/              # 手语识别/生成/配音 API + 手语斩词库（SignWord）
│   │   ├── text_to_sign/          # 文本→手语（三阶段检索 + 拼接）
│   │   ├── chat/                  # AI 课堂 API（含 Vosk ASR）
│   │   └── users/                 # 用户鉴权（登录/注册）
│   ├── sign_language/             # Vue 3 前端
│   │   ├── public/
│   │   │   └── bg/                # 界面角色插画与背景图（Tab 背景 / 导航图标 / 按钮图标）
│   │   └── src/
│   │       ├── api/               # 后端接口契约
│   │       ├── components/        # 组件（Tab 页、侧边栏、历史记录、素材库）
│   │       ├── store/             # 状态管理（含素材 store，对接后端）
│   │       ├── styles/            # global.css（毛玻璃变量、主题色、深浅色主题）
│   │       └── views/             # 页面视图
│   ├── src/                       # 推理引擎
│   │   ├── inference.py           # TFNet 模型推理 + 视频词汇定位
│   │   └── tfnet/                 # TFNet 网络定义
│   ├── checkpoints/               # TFNet 模型权重（需手动下载）
│   ├── data/                      # 手语视频 + 生成产物
│   │   ├── label/                 # CSV 标注文件
│   │   ├── video/train/           # 训练集手语视频
│   │   ├── video/generated/       # 拼接输出视频
│   │   └── video/dub/             # 配音音频文件
│   ├── requirements.txt
│   ├── README.md
│   ├── TECHNICAL.md
│   └── run_app.bat
│
└── voice_clone_server/            # 音色克隆服务（独立目录）
    ├── api_server.py              # 克隆代理 API（Flask, 端口 9880）
    ├── GPT-SoVITS/                # GPT-SoVITS 推理引擎
    │   ├── api_v2.py              # 推理 API 服务（FastAPI, 端口 9870）
    │   └── GPT_SoVITS/            # 模型代码 + 预训练权重
    ├── ref_audio/                 # 用户上传的参考音频
    ├── output/                    # 合成音频输出
    ├── requirements.txt
    └── run_server.bat
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
| GET | `/api/records/` | 翻译记录列表（分页/单条/一键清空，含删除） |
| POST | `/api/materials/folders` | 新建素材文件夹 |
| GET | `/api/materials/folders` | 列出素材文件夹 |
| POST | `/api/materials/` | 新建素材 |
| GET | `/api/materials/?folderId=<id>` | 列出某文件夹素材 |
| POST | `/api/materials/upload` | 上传图片/视频素材 |
| POST | `/api/materials/move` | 批量移动素材 |
| GET | `/api/vocab/list` | 手语词库列表（手语斩） |
| POST | `/api/vocab/<pk>/generate` | 生成单个词的手语视频+说明 |
| POST | `/api/vocab/preload` | 批量预加载单词语视频 |

## 技术栈

| 层级 | 技术 | 用途 |
|------|------|------|
| **前端** | Vue 3 + Vite 5 | 用户界面 |
| **手部检测** | MediaPipe HandLandmarker（前端 WASM） | 录制预览实时描骨架线 |
| **后端** | Django 5 + DRF | REST API |
| **模型** | TFNet（3D ResNet + BiLSTM + SENet） | 手语识别 |
| **语义检索** | sentence-transformers（text2vec-base-chinese） | 文本→手语匹配 |
| **LLM** | DeepSeek API | 语义核验、文本改写、结果整理 |
| **TTS** | edge-tts（微软 Edge 在线语音） | 多语种配音 |
| **音色克隆** | GPT-SoVITS v2 | 零样本声音克隆 |
| **ASR** | Vosk | 离线中文语音识别 |
| **视频处理** | OpenCV + imageio-ffmpeg（H.264） | 帧提取、裁剪、拼接 |
| **深度学习** | PyTorch 2 + CUDA | GPU 加速推理 |

## 界面主题与视觉资源

前端采用「卡通角色 + 毛玻璃」的清新风格，视觉资源集中在 `sign_language/public/bg/`：

- **Tab 背景图**：每个 Tab 一张整图背景（`tab-sign.jpg` / `tab-video.jpg` / `tab-vocab.jpg` / `tab-classroom.jpg`），在 `MainView.vue` 的 `tabBgMap` 中按 Tab 切换，并叠一层半透明白色蒙版降低底图浓度。
- **导航与按钮图标**：底部 Tab、顶部侧边栏/素材入口、麦克风、上传/录制按钮等均使用角色插画（`tab-sign.png`、`tab-video.png`、`tab-vocab-icon.jpg`、`tab-classroom.png`、`avatar.png`、`mic.png`、`btn-upload.png`、`btn-record.png`、`upload-hero.jpg`、`folder-empty.png`）。
- **毛玻璃风格**：卡片统一使用 `.glass` 类，底色与模糊由 `styles/global.css` 中的 `--glass-bg` / `--glass-bg-strong` / `--glass-blur` 控制，可在该文件统一调整透明度；同时支持柔和/明亮/深色三套主题。
- **图标缓存**：图标 URL 带 `?v=N` 版本参数，替换图片后递增版本号即可强制浏览器刷新。

## 详细文档

- [技术文档](TECHNICAL.md) — 完整 API 文档、三阶段检索策略、TFNet 精确定位原理、音色克隆部署指南
