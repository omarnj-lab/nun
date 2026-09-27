"""Print the GPU / library environment and the GPU tier (SPEC.md §6.4)."""

from __future__ import annotations

import importlib
import os
import shutil


def pick_tier(vram_gb: list[float]) -> str:
    """a80: one GPU ≥ 80 GB · a48: one GPU ≥ 40 GB, or ≥ 2 GPUs totalling ≥ 48 GB (model split
    across devices) · a24: otherwise (Qari-OCR 4B fallback)."""
    if not vram_gb:
        return "none"
    if max(vram_gb) >= 79:
        return "a80"
    if max(vram_gb) >= 39 or (len(vram_gb) >= 2 and sum(vram_gb) >= 48):
        return "a48"
    return "a24"


def main() -> None:
    import torch

    print(f"torch {torch.__version__}  cuda {torch.version.cuda}  available={torch.cuda.is_available()}")
    vram = []
    for i in range(torch.cuda.device_count()):
        p = torch.cuda.get_device_properties(i)
        free, total = torch.cuda.mem_get_info(i)
        vram.append(total / 2**30)
        print(f"  gpu{i} {p.name} sm_{p.major}{p.minor} total={total / 2**30:.1f}G free={free / 2**30:.1f}G")
    for mod in ("transformers", "peft", "accelerate", "bitsandbytes", "unsloth"):
        try:
            m = importlib.import_module(mod)
            print(f"{mod} {getattr(m, '__version__', '?')}")
        except Exception as e:  # noqa: BLE001 — report, don't fail
            print(f"{mod} NOT importable: {type(e).__name__}: {e}")
    hf_home = os.environ.get("HF_HOME", os.path.expanduser("~/.cache/huggingface"))
    print(f"disk free at {hf_home}: {shutil.disk_usage(os.path.dirname(hf_home)).free / 2**30:.0f}G (virtual)")
    env_tier = os.environ.get("GPU_TIER", "auto")
    tier = pick_tier(vram) if env_tier == "auto" else env_tier
    print(f"GPU_TIER={tier} (env={env_tier})")


if __name__ == "__main__":
    main()
