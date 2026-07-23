"""检查国内镜像下载源"""
import requests

# hf-mirror 上的 lj1995/GPT-SoVITS
tests = [
    ("hf-mirror lj1995/GPT-SoVITS", "https://hf-mirror.com/lj1995/GPT-SoVITS/resolve/main/pretrained_models/gsv-v2final-pretrained/s1a.pth"),
    ("hf-mirror lj1995/GPT-SoVITS", "https://hf-mirror.com/lj1995/GPT-SoVITS/resolve/main/pretrained_models/gsv-v2final-pretrained/s2G2333k.pth"),
    ("hf-mirror ChrisYang", "https://hf-mirror.com/ChrisYang/gpt-sovits-v2/resolve/main/gsv-v2-final-pretrained-gpt.ckpt"),
    ("hf-mirror ChrisYang", "https://hf-mirror.com/ChrisYang/gpt-sovits-v2/resolve/main/gsv-v2-final-pretrained-sovits.ckpt"),
    ("modelscope AIDub/GPT-SoVITS", "https://modelscope.cn/api/v1/models/AIDub/GPT-SoVITS/repo?Revision=master&FilePath=GPT_SoVITS/pretrained_models/"),
    ("baidu", "https://www.baidu.com"),
]

for src, url in tests:
    try:
        # Just check if domain is reachable
        r = requests.get(url, timeout=5, allow_redirects=True)
        print(f"[{r.status_code}] {src}: {len(r.content)} bytes")
    except requests.exceptions.ConnectionError:
        print(f"[CONN_ERR] {src}")
    except requests.exceptions.Timeout:
        print(f"[TIMEOUT] {src}")
    except Exception as e:
        print(f"[ERR] {src}: {type(e).__name__}: {str(e)[:60]}")
