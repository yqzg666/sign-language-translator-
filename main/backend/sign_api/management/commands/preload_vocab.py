"""预加载「手语斩」词库：从数据集提取词汇 + 用 TFNet 裁剪单词语视频打标签。

用法:
    python backend/manage.py preload_vocab                 # 处理全部未生成词
    python backend/manage.py preload_vocab --limit 80      # 只处理前 80 个未生成词
"""
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "预加载手语斩词库：从数据集提取词汇并裁剪单词语视频"

    def add_arguments(self, parser):
        parser.add_argument(
            "--limit",
            type=int,
            default=0,
            help="最多预加载的视频词数（0=全部）",
        )

    def handle(self, *args, **options):
        from sign_api.views import _seed_words, _preload_vocab

        self.stdout.write("正在从数据集提取手语词库...")
        _seed_words()

        limit = options.get("limit") or 0
        if limit:
            self.stdout.write(f"开始用 TFNet 裁剪单词语视频（最多 {limit} 词）...")
        else:
            self.stdout.write("开始用 TFNet 裁剪单词语视频...")
        done = _preload_vocab(limit)
        self.stdout.write(self.style.SUCCESS(f"完成！共生成 {done} 个单词语视频"))
