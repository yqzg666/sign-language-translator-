"""
手语翻译 Web 应用 - Gradio 界面
功能:
  1. 手语→文本: 上传/录制视频 → TFNet 识别 → DeepSeek 整理中文
  2. 文本→手语: 输入文本 → 句向量检索 → 返回匹配手语视频（不匹配时自动拼接）
"""
import os
import sys
import json
import torch
import gradio as gr
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import URLError

sys.path.insert(0, str(Path(__file__).parent))
from inference import (
    load_model, build_vocab, recognize_frames,
    extract_frames_from_video,
)

# ============ 全局配置 ============

DATA_DIR = Path(__file__).parent.parent / "data"
CHECKPOINT_DIR = Path(__file__).parent.parent / "checkpoints"
CHECKPOINT_PATH = CHECKPOINT_DIR / "TFNet-CE-CSL-CSLDaily-32.46.pth"
HIDDEN_SIZE = 1024
DEVICE = "cuda"

# DeepSeek
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"

# Django 后端地址
API_BASE_URL = "http://127.0.0.1:8000/api"
DJANGO_BASE = "http://127.0.0.1:8000"

# 全局变量
model = None
idx2word = None
word2idx = None


# ============ 后端 API 交互 ============

def _api_request(method, path, data=None):
    """向 Django 后端发送请求"""
    url = f"{API_BASE_URL}{path}"
    payload = json.dumps(data).encode("utf-8") if data else None
    req = Request(url, data=payload, method=method)
    req.add_header("Content-Type", "application/json")
    try:
        with urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        return None


def save_record(video_name, gloss_text, chinese_text):
    return _api_request("POST", "/records/", {
        "video_name": video_name,
        "gloss_text": gloss_text,
        "chinese_text": chinese_text,
    })


# ============ 历史记录 API ============

def fetch_records(page=1, page_size=20):
    """分页获取翻译记录"""
    data = _api_request("GET", f"/records/?page={page}&page_size={page_size}")
    if isinstance(data, dict) and "results" in data:
        return data
    return None


def fetch_single_record(record_id):
    """单条查询（不加载全部记录）"""
    data = _api_request("GET", f"/records/?id={record_id}")
    return data if isinstance(data, dict) and "id" in data else None


def delete_record(record_id):
    """按复合 ID（如 stt:5, tts:3）删除记录"""
    _api_request("DELETE", f"/records/{record_id}/")


def delete_all_records():
    """一键删除所有记录"""
    return _api_request("DELETE", "/records/", {"action": "delete_all"})


# ============ 文本→手语 API ============

def text_to_sign_api(text):
    """调用文本→手语 API，失败时返回含 error 的 dict"""
    from urllib.error import HTTPError

    url = f"{API_BASE_URL}/text-to-sign/"
    payload = json.dumps({"text": text}).encode("utf-8")
    req = Request(url, data=payload, method="POST")
    req.add_header("Content-Type", "application/json")
    try:
        with urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except HTTPError as e:
        body = e.read().decode("utf-8")
        try:
            return json.loads(body)
        except json.JSONDecodeError:
            return {"error": f"后端错误: {e.code}"}
    except Exception as e:
        return {"error": f"后端服务不可用: {str(e)}"}


def text_to_sign_stitch_api(text):
    """调用视频拼接 API"""
    from urllib.error import HTTPError

    url = f"{API_BASE_URL}/text-to-sign/stitch/"
    payload = json.dumps({"text": text}).encode("utf-8")
    req = Request(url, data=payload, method="POST")
    req.add_header("Content-Type", "application/json")
    try:
        with urlopen(req, timeout=60) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except HTTPError as e:
        body = e.read().decode("utf-8")
        try:
            return json.loads(body)
        except json.JSONDecodeError:
            return {"error": f"拼接后端错误: {e.code}"}
    except Exception as e:
        return {"error": f"拼接服务不可用: {str(e)}"}


# ============ 模型 + 推理 ============

def init_model():
    global model, idx2word, word2idx
    train_label = DATA_DIR / "label" / "train.csv"
    dev_label = DATA_DIR / "label" / "dev.csv"
    test_label = DATA_DIR / "label" / "test.csv"
    print("正在构建词表...")
    word2idx, vocab_size, idx2word = build_vocab(
        [str(train_label), str(dev_label), str(test_label)], "CE-CSL"
    )
    print(f"词表大小: {vocab_size}")
    print("正在加载模型...")
    model = load_model(str(CHECKPOINT_PATH), HIDDEN_SIZE, vocab_size, torch.device(DEVICE), "CE-CSL")
    return model, idx2word


def translate_gloss_with_deepseek(gloss_text):
    """调用 DeepSeek API 将 Gloss 序列翻译为通顺中文"""
    if not gloss_text or gloss_text in ("(未识别到手语词汇)", ""):
        return "请先识别手语视频，获取 Gloss 序列后再调用翻译。"

    prompt = f"""你是一个专业的手语翻译助手。将手语 Gloss 序列翻译成地道的中文口语。

规则：
1. 调整手语语序为中文语序
2. 补全省略的虚词（的、了、吗、把、被等）
3. 用最自然的中文口语表达，不要逐词硬译
4. 注意问句的合理措辞（"多少"问时间→"几点"，"什么 时间"→"什么时候"，"啥"→"什么"）
5. 输出只有翻译结果，不要加任何解释

示例：
手语 Gloss：你 / 叫 / 什么 / 名字
翻译结果：你叫什么名字？

手语 Gloss：他 / 去 / 商店 / 买 / 东西
翻译结果：他去商店买东西。

手语 Gloss：你 / 边 / 时间 / 多少 / ？
翻译结果：你那边时间是几点？

手语 Gloss：我 / 今天 / 不 / 舒服
翻译结果：我今天不舒服。

手语 Gloss：你 / 星期几 / 有空
翻译结果：你星期几有空？

现在翻译：
手语 Gloss：{gloss_text}
翻译结果："""

    payload = json.dumps({
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": "你是一个专业的手语翻译助手，将手语 Gloss 序列翻译为地道的中文口语。不要逐词硬译，用最自然的日常表达。"},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.3,
        "max_tokens": 256,
    }).encode("utf-8")

    req = Request(DEEPSEEK_API_URL, data=payload, method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("Authorization", f"Bearer {DEEPSEEK_API_KEY}")

    try:
        with urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            return result["choices"][0]["message"]["content"].strip()
    except URLError as e:
        return f"[DeepSeek API 请求失败] {e.reason}"
    except Exception as e:
        return f"[翻译出错] {str(e)}"


def recognize_video_wrapper(video_path, progress=gr.Progress()):
    """识别视频并保存记录"""
    global model, idx2word

    if model is None or idx2word is None:
        progress(0, desc="正在初始化模型...")
        init_model()

    if video_path is None:
        return None, "请上传或录制视频", ""

    progress(0.15, desc="正在提取视频帧...")
    frames = extract_frames_from_video(video_path, sample_rate=1)
    if len(frames) == 0:
        return None, "无法读取视频，请检查视频格式", ""

    progress(0.3, desc="正在识别手语 (TFNet)...")
    gloss_list, raw_text = recognize_frames(model, frames, idx2word, torch.device(DEVICE))

    if gloss_list:
        gloss_words = [g[0] for g in gloss_list]
        gloss_result = " / ".join(gloss_words)
    else:
        gloss_result = "(未识别到手语词汇)"

    progress(0.6, desc="正在调用 DeepSeek 翻译...")
    chinese_text = translate_gloss_with_deepseek(gloss_result)

    video_name = Path(video_path).name
    save_record(video_name, gloss_result, chinese_text)

    progress(1.0, desc="完成!")
    return video_path, gloss_result, chinese_text


# ============ 历史记录逻辑 ============

def refresh_history(page=1, page_size=20):
    """获取分页数据并返回表格行"""
    data = fetch_records(page, page_size)
    if not data or not data.get("results"):
        return (
            gr.update(value=[["暂无记录", "", "", "", ""]], label="翻译历史记录（共 0 条）"),
            gr.update(value=""),
            f"第 0/0 页",
        )
    rows = [[r["id"], r["type"], r["input"], r["detail"], r["created_at"]] for r in data["results"]]
    return (
        gr.update(value=rows, label=f"翻译历史记录（共 {data['count']} 条）"),
        gr.update(value=""),
        f"第 {data['page']}/{data['total_pages']} 页",
    )


def go_to_page(direction, current_page, total_pages):
    """翻页"""
    if not current_page or not total_pages:
        return 1
    new_page = current_page + (1 if direction == "next" else -1)
    new_page = max(1, min(new_page, total_pages))
    return new_page


def delete_selected(delete_id):
    if delete_id:
        delete_record(delete_id)
    return refresh_history()


def delete_all_and_refresh():
    delete_all_records()
    return refresh_history()


def show_history_video(selected_id):
    """单条查询，不加载全部记录"""
    if not selected_id:
        return None, "请输入记录 ID"
    record = fetch_single_record(selected_id)
    if not record or "error" in record:
        return None, f"未找到 ID 为 {selected_id} 的记录"
    url = record.get("video_url", "")
    if url:
        return DJANGO_BASE + url, f"视频: {record['type']} - {record['input']}"
    return None, "该记录没有关联的视频文件"


# ============ 文本 → 手语 ============

def text_to_sign_wrapper(input_text, progress=gr.Progress()):
    """调用后端 API 获取匹配的手语视频，检索不到时自动拼接"""
    if not input_text or not input_text.strip():
        return ""

    progress(0.15, desc="正在检索手语视频库...")
    result = text_to_sign_api(input_text.strip())

    if result and "error" not in result:
        video_url = f"http://127.0.0.1:8000{result['video_url']}" if result.get("video_url") else None
        method_map = {
            "retrieval": "句向量直接匹配",
            "deepseek": "DeepSeek 改写后匹配",
            "gloss": "Gloss 序列匹配兜底",
        }
        method_cn = method_map.get(result.get("method", ""), result.get("method", ""))
        video_html = f'<video width="100%" height="380" controls style="border-radius:8px;"><source src="{video_url}" type="video/mp4"></video>' if video_url else ""
        progress(1.0)
        return f"""
        {video_html}
        <div style="padding:12px 0;">
            <div style="font-size:15px;margin-bottom:6px;">
                <span style="color:#555;">匹配句子：</span>
                <span style="font-weight:600;">{result.get("chinese_text", "")}</span>
            </div>
            <div style="font-size:13px;color:#777;margin-bottom:6px;">
                <span>对应序列：</span>
                <span>{result.get("gloss_text", "")}</span>
            </div>
            <div style="font-size:13px;color:#888;">
                <span>相似度 {result.get("similarity", 0):.2f} ｜ {method_cn}</span>
            </div>
        </div>
        """

    progress(0.3, desc="未找到匹配，正在尝试视频拼接...")
    stitch_result = text_to_sign_stitch_api(input_text.strip())

    if stitch_result and "error" not in stitch_result:
        video_url = f"http://127.0.0.1:8000{stitch_result['video_url']}"
        video_html = f'<video width="100%" height="380" controls style="border-radius:8px;"><source src="{video_url}" type="video/mp4"></video>' if video_url else ""
        note = stitch_result.get("note", "")
        progress(1.0)
        return f"""
        <div style="padding:8px 12px;background:#fff3cd;border-radius:6px;margin-bottom:10px;font-size:13px;color:#856404;">
            未找到整句匹配的完整视频，已改为<strong>逐词拼接</strong>模式：{note}
        </div>
        {video_html}
        <div style="padding:12px 0;">
            <div style="font-size:15px;margin-bottom:6px;">
                <span style="color:#555;">输入文本：</span>
                <span style="font-weight:600;">{stitch_result.get("chinese_text", "")}</span>
            </div>
            <div style="font-size:13px;color:#777;margin-bottom:6px;">
                <span>对应序列：</span>
                <span>{stitch_result.get("gloss_text", "")}</span>
            </div>
            <div style="font-size:13px;color:#888;">
                <span>视频拼接生成</span>
            </div>
        </div>
        """

    err = result.get("error", "未知错误") if result else "后端服务不可用"
    hint = result.get("hint", "") if result else ""
    msg = f'<div style="color:#e74c3c;font-size:14px;padding:10px 0;"><b>{err}</b></div>'
    if hint:
        msg += f'<div style="color:#888;font-size:13px;">{hint}</div>'
    progress(1.0)
    return msg


# ============ Gradio 界面 ============

CSS = """
.app-header h1 { font-size: 1.8rem; margin-bottom: 0; }
.app-header p { color: #666; margin-top: 0.2rem; }
"""

with gr.Blocks(title="手语翻译系统") as demo:

    gr.HTML("""
    <div class="app-header">
        <h1>手语翻译系统</h1>
        <p>上传手语视频 → 识别文本 ｜ 输入中文文本 → 生成手语视频</p>
    </div>
    """)

    with gr.Tabs():
        # ===== Tab 1: 手语→文本 =====
        with gr.TabItem("手语→文本"):
            with gr.Row():
                with gr.Column(scale=1):
                    gr.Markdown("### 输入")
                    video_input = gr.Video(
                        label="上传或录制手语视频",
                        sources=["upload", "webcam"],
                        height=400,
                    )
                    with gr.Row():
                        submit_btn = gr.Button("开始识别", variant="primary", size="lg")
                        clear_btn = gr.Button("清除", size="lg")

                with gr.Column(scale=1):
                    gr.Markdown("### 识别结果")
                    with gr.Group():
                        gloss_output = gr.Textbox(
                            label="识别结果",
                            placeholder="识别到的手语词汇将显示在这里...",
                            lines=3,
                        )
                        text_output = gr.Textbox(
                            label="中文翻译",
                            placeholder="经过 DeepSeek 整理后的中文文本...",
                            lines=3,
                        )

                    gr.Markdown("""
                    **说明:**
                    - 支持上传 mp4、avi 等常见视频格式
                    - 支持使用摄像头录制
                    - 视频长度建议 2-10 秒
                    """)

            submit_btn.click(
                fn=lambda: ("", ""),
                outputs=[gloss_output, text_output],
            ).then(
                fn=recognize_video_wrapper,
                inputs=[video_input],
                outputs=[video_input, gloss_output, text_output],
            )
            clear_btn.click(
                fn=lambda: (None, "", ""),
                outputs=[video_input, gloss_output, text_output],
            )

            with gr.Row():
                deepseek_btn = gr.Button("重新翻译 (DeepSeek)", variant="secondary")
            deepseek_btn.click(
                fn=lambda: "",
                outputs=[text_output],
            ).then(
                fn=translate_gloss_with_deepseek,
                inputs=[gloss_output],
                outputs=[text_output],
            )

        # ===== Tab 2: 文本→手语 =====
        with gr.TabItem("文本→手语"):
            with gr.Row():
                with gr.Column(scale=1):
                    gr.Markdown("### 输入")
                    tts_input = gr.Textbox(
                        label="请输入中文",
                        placeholder="例如：你家住在哪里？",
                        lines=3,
                    )
                    with gr.Row():
                        tts_submit = gr.Button("生成手语视频", variant="primary", size="lg")
                        tts_clear = gr.Button("清除", size="lg")

                with gr.Column(scale=1):
                    gr.Markdown("### 结果")
                    tts_output = gr.HTML()

            tts_submit.click(
                fn=lambda: "",
                outputs=[tts_output],
            ).then(
                fn=text_to_sign_wrapper,
                inputs=[tts_input],
                outputs=[tts_output],
            )
            tts_clear.click(
                fn=lambda: ("", ""),
                outputs=[tts_output, tts_input],
            )

        # ===== Tab 3: 历史记录（分页 + 视频播放 + 一键删除） =====
        with gr.TabItem("历史记录"):
            history_state = gr.State({"page": 1, "total_pages": 0})

            with gr.Row():
                refresh_btn = gr.Button("刷新", variant="primary", size="lg")

            history_table = gr.Dataframe(
                headers=["ID", "类型", "输入内容", "详情", "创建时间"],
                row_count=10,
                column_count=(5, "fixed"),
                interactive=False,
            )

            with gr.Row():
                prev_btn = gr.Button("◀ 上一页", size="sm")
                page_info = gr.Textbox(label="", value="第 1/1 页", scale=0, min_width=160, interactive=False)
                next_btn = gr.Button("下一页 ▶", size="sm")

            with gr.Row():
                view_id = gr.Textbox(label="输入记录 ID 查看视频", scale=2, placeholder="例如 stt:5 或 tts:3")
                view_btn = gr.Button("查看视频", variant="primary", scale=1)
                delete_btn = gr.Button("删除单条", variant="stop", scale=1)

            with gr.Row():
                delete_all_btn = gr.Button("🗑 一键删除全部记录", variant="stop", size="sm")

            with gr.Row():
                history_video = gr.Video(label="历史视频", height=360)
                history_video_info = gr.Textbox(label="视频信息", interactive=False)

            # 加载 / 刷新
            def load_page(state):
                data = fetch_records(state["page"])
                if not data or not data.get("results"):
                    return (
                        gr.update(value=[["暂无记录", "", "", "", ""]], label="翻译历史记录（共 0 条）"),
                        f"第 0/0 页",
                        {"page": 1, "total_pages": 0},
                    )
                rows = [[r["id"], r["type"], r["input"], r["detail"], r["created_at"]] for r in data["results"]]
                return (
                    gr.update(value=rows, label=f"翻译历史记录（共 {data['count']} 条）"),
                    f"第 {data['page']}/{data['total_pages']} 页",
                    {"page": data["page"], "total_pages": data["total_pages"]},
                )

            def prev_page(state):
                if state["page"] > 1:
                    state["page"] -= 1
                return load_page(state)

            def next_page(state):
                if state["page"] < state["total_pages"]:
                    state["page"] += 1
                return load_page(state)

            refresh_btn.click(
                fn=load_page,
                inputs=[history_state],
                outputs=[history_table, page_info, history_state],
            )

            prev_btn.click(
                fn=prev_page,
                inputs=[history_state],
                outputs=[history_table, page_info, history_state],
            )

            next_btn.click(
                fn=next_page,
                inputs=[history_state],
                outputs=[history_table, page_info, history_state],
            )

            view_btn.click(
                fn=show_history_video,
                inputs=[view_id],
                outputs=[history_video, history_video_info],
            )

            delete_btn.click(
                fn=delete_selected,
                inputs=[view_id],
                outputs=[history_table, view_id, page_info],
            ).then(
                fn=lambda state: load_page(state),
                inputs=[history_state],
                outputs=[history_table, page_info, history_state],
            )

            delete_all_btn.click(
                fn=delete_all_and_refresh,
                outputs=[history_table, view_id, page_info],
            ).then(
                fn=lambda: {"page": 1, "total_pages": 0},
                outputs=[history_state],
            )

            demo.load(
                fn=load_page,
                inputs=[history_state],
                outputs=[history_table, page_info, history_state],
            )


def main():
    print("正在初始化模型...")
    init_model()
    print("模型初始化完成!")

    demo.launch(
        server_name="127.0.0.1",
        server_port=7860,
        share=False,
        theme=gr.themes.Soft(),
        css=CSS,
    )


if __name__ == "__main__":
    main()
