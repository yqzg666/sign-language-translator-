import sys
import os
import torch
import warnings

sys.path.append(f"{os.getcwd()}/GPT_SoVITS/eres2net")
sv_path = "GPT_SoVITS/pretrained_models/sv/pretrained_eres2netv2w24s4ep4.ckpt"

# ERes2NetV2 is only needed for v2Pro/v2ProPlus models.
# v2 base model does not use speaker verification.
try:
    from ERes2NetV2 import ERes2NetV2
    _ERES2NET_AVAILABLE = True
except ModuleNotFoundError:
    ERes2NetV2 = None
    _ERES2NET_AVAILABLE = False
    warnings.warn("ERes2NetV2 not available; SV module (v2Pro) will be disabled.")

try:
    import kaldi as Kaldi
    _KALDI_AVAILABLE = True
except ModuleNotFoundError:
    Kaldi = None
    _KALDI_AVAILABLE = False
    warnings.warn("kaldi not available; SV module (v2Pro) will be disabled.")


class SV:
    def __init__(self, device, is_half):
        if not _ERES2NET_AVAILABLE or not _KALDI_AVAILABLE:
            raise RuntimeError(
                "SV module requires ERes2NetV2 and kaldi packages, "
                "which are missing. This module is only needed for "
                "GPT-SoVITS v2Pro/v2ProPlus models."
            )
        pretrained_state = torch.load(sv_path, map_location="cpu", weights_only=False)
        embedding_model = ERes2NetV2(baseWidth=24, scale=4, expansion=4)
        embedding_model.load_state_dict(pretrained_state)
        embedding_model.eval()
        self.embedding_model = embedding_model
        if is_half == False:
            self.embedding_model = self.embedding_model.to(device)
        else:
            self.embedding_model = self.embedding_model.half().to(device)
        self.is_half = is_half

    def compute_embedding3(self, wav):
        with torch.no_grad():
            if self.is_half == True:
                wav = wav.half()
            feat = torch.stack(
                [Kaldi.fbank(wav0.unsqueeze(0), num_mel_bins=80, sample_frequency=16000, dither=0) for wav0 in wav]
            )
            sv_emb = self.embedding_model.forward3(feat)
        return sv_emb
