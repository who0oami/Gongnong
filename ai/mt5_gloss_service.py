"""Fine-tuned mT5 inference for Korean text to KSL gloss conversion.

The public service interface deliberately stays small:
``convert_to_gloss('오늘 비가 옵니다.') -> ['오늘', '비', '오다']``.
It is used by the backend job worker and does not call an external generative AI API.
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path


GLOSS_SEPARATOR = "<g>"
PROMPT_PREFIX = "한국수어 글로스 변환: "


class GlossModelError(RuntimeError):
    """Raised when the local fine-tuned model cannot be loaded or used."""


def _model_dir() -> Path:
    value = os.environ.get("KSL_MT5_MODEL_DIR", "ai/models/ksl-gloss-mt5")
    return Path(value).expanduser().resolve()


def _parse_glosses(text: str) -> list[str]:
    """Parse the serialization emitted by the fine-tuned model."""
    return [item.strip() for item in text.split(GLOSS_SEPARATOR) if item.strip()]


@lru_cache(maxsize=1)
def _load_model():
    model_dir = _model_dir()
    weight_files = ("model.safetensors", "pytorch_model.bin")
    if not model_dir.is_dir() or not any((model_dir / name).is_file() for name in weight_files):
        raise GlossModelError(
            "학습된 mT5 가중치를 찾을 수 없습니다. "
            f"KSL_MT5_MODEL_DIR={model_dir} 에 model.safetensors 또는 pytorch_model.bin이 필요합니다."
        )
    try:
        import torch
        from transformers import AutoModelForSeq2SeqLM, AutoTokenizer
    except ImportError as error:
        raise GlossModelError("로컬 mT5 추론 패키지가 없습니다. requirements-ai.txt를 설치하세요.") from error

    tokenizer = AutoTokenizer.from_pretrained(model_dir, local_files_only=True)
    model = AutoModelForSeq2SeqLM.from_pretrained(model_dir, local_files_only=True)
    device = "cuda" if torch.cuda.is_available() else "mps" if torch.backends.mps.is_available() else "cpu"
    model.to(device)
    model.eval()
    return tokenizer, model, device, torch


def convert_to_gloss(korean_text: str) -> list[str]:
    """Convert one Korean sentence to a non-empty KSL gloss list using local mT5."""
    text = korean_text.strip()
    if not text:
        return []
    tokenizer, model, device, torch = _load_model()
    encoded = tokenizer(
        PROMPT_PREFIX + text,
        return_tensors="pt",
        truncation=True,
        max_length=96,
    ).to(device)
    with torch.inference_mode():
        generated = model.generate(
            **encoded,
            max_new_tokens=96,
            num_beams=4,
            early_stopping=True,
        )
    glosses = _parse_glosses(tokenizer.decode(generated[0], skip_special_tokens=True))
    if not glosses:
        raise GlossModelError("mT5가 빈 글로스 결과를 반환했습니다. 검증을 통과한 가중치인지 확인하세요.")
    return glosses
