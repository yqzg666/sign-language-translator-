"""检查模型下载链接是否可用"""
import requests

models = {
    "s1a.pth": "https://huggingface.co/lj1995/GPT-SoVITS/resolve/main/pretrained_models/gsv-v2final-pretrained/s1a.pth",
    "s2G2333k.pth": "https://huggingface.co/lj1995/GPT-SoVITS/resolve/main/pretrained_models/gsv-v2final-pretrained/s2G2333k.pth",
    "gsv-v2-final-pretrained-gpt.ckpt": "https://huggingface.co/ChrisYang/gpt-sovits-v2/resolve/main/gsv-v2-final-pretrained-gpt.ckpt",
    "gsv-v2-final-pretrained-sovits.ckpt": "https://huggingface.co/ChrisYang/gpt-sovits-v2/resolve/main/gsv-v2-final-pretrained-sovits.ckpt",
}

for name, url in models.items():
    try:
        r = requests.head(url, timeout=10, allow_redirects=True)
        size = r.headers.get("content-length", "?")
        print(f"[{r.status_code}] {name}: {size} bytes")
        if r.status_code == 200:
            print(f"  URL: {url}")
    except Exception as e:
        print(f"[ERR] {name}: {e}")
