from django.db import models


class SignWord(models.Model):
    """手语词汇表：用于「手语斩」背词模块。

    首次学习某词时，前端调用 generate 接口触发后端生成：
    - video_url   : 该词的手语动作视频（复用 text-to-sign/拼接，缓存在此）
    - description : 该词的手语动作文字要领（复用 DeepSeek / 杏云同学生成，缓存在此）
    """
    word = models.CharField(max_length=50, unique=True, verbose_name="中文词")
    pinyin = models.CharField(max_length=100, blank=True, default="", verbose_name="拼音")
    description = models.TextField(blank=True, default="", verbose_name="手语动作说明")
    video_url = models.CharField(max_length=255, blank=True, default="", verbose_name="手语动作视频 URL")
    generated = models.BooleanField(default=False, verbose_name="是否已生成视频与说明")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")

    class Meta:
        ordering = ["id"]
        verbose_name = "手语词"
        verbose_name_plural = "手语词"

    def __str__(self):
        return self.word
