import threading

from django.apps import AppConfig


class SignApiConfig(AppConfig):
    name = 'sign_api'

    def ready(self):
        # 方案三：后台预热 TFNet 模型，避免首次翻译请求时等待加载
        def _warmup():
            try:
                from sign_api.views import _ensure_model

                _ensure_model()
                print("[sign_api] TFNet 模型预热完成")
            except Exception as exc:  # noqa: BLE001
                print(f"[sign_api] TFNet 模型预热失败: {exc}")

        def _seed():
            # 首次启动时预置「手语斩」词库（幂等：已有数据则跳过）
            try:
                from sign_api.views import _seed_words

                _seed_words()
            except Exception as exc:  # noqa: BLE001
                print(f"[sign_api] 手语词库预置失败: {exc}")

        threading.Thread(target=_warmup, daemon=True).start()
        threading.Thread(target=_seed, daemon=True).start()
