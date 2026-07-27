from django.db import models


class TextToSignRecord(models.Model):
    """文本→手语 转换记录"""
    input_text = models.TextField(verbose_name="输入文本")
    matched_text = models.TextField(blank=True, default="", verbose_name="匹配到的原文")
    matched_gloss = models.TextField(blank=True, default="", verbose_name="匹配到的Gloss")
    video_name = models.CharField(max_length=255, blank=True, default="", verbose_name="视频文件名")
    similarity = models.FloatField(default=0.0, verbose_name="相似度")
    method = models.CharField(
        max_length=20, default="retrieval",
        choices=[("retrieval", "向量检索"), ("deepseek", "DeepSeek改写"), ("gloss", "Gloss匹配")],
        verbose_name="匹配方式",
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "文本转手语记录"
        verbose_name_plural = "文本转手语记录"

    def __str__(self):
        return f"[{self.created_at:%Y-%m-%d %H:%M}] {self.input_text[:30]}"
