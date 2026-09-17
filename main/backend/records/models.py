from django.db import models


class TranslationRecord(models.Model):
    """手语翻译记录"""
    video_name = models.CharField(max_length=255, verbose_name="视频文件名")
    gloss_text = models.TextField(blank=True, default="", verbose_name="手语 Gloss 序列")
    chinese_text = models.TextField(blank=True, default="", verbose_name="中文翻译结果")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "翻译记录"
        verbose_name_plural = "翻译记录"

    def __str__(self):
        return f"[{self.created_at:%Y-%m-%d %H:%M}] {self.video_name}"




class MaterialFolder(models.Model):
    name = models.CharField(max_length=120)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "素材文件夹"
        verbose_name_plural = "素材文件夹"

    def __str__(self):
        return self.name


class Material(models.Model):
    folder = models.ForeignKey("MaterialFolder", related_name="materials", on_delete=models.CASCADE)
    type = models.CharField(max_length=30, blank=True, default="text")
    name = models.CharField(max_length=200)
    content = models.TextField(blank=True, default="")
    url = models.CharField(max_length=500, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "素材"
        verbose_name_plural = "素材"

    def __str__(self):
        return self.name