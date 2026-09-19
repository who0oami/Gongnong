"""Low-memory fine-tuning and mandatory saved-model reload verification.

Input JSONL rows must contain ``input_text`` and ``target_glosses`` (a string list).
The script saves a complete Transformers checkpoint, reloads it from disk, then writes
only predictions produced by that reloaded checkpoint to ``verification_predictions.json``.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

GLOSS_SEPARATOR = "<g>"
PROMPT_PREFIX = "한국수어 글로스 변환: "


def serialize_glosses(items: list[str]) -> str:
    return f" {GLOSS_SEPARATOR} ".join(item.strip() for item in items if item.strip())


def parse_glosses(text: str) -> list[str]:
    return [item.strip() for item in text.split(GLOSS_SEPARATOR) if item.strip()]


def gloss_f1(prediction: list[str], reference: list[str]) -> float:
    """Token F1 used as a small, readable release gate."""
    from collections import Counter
    overlap = sum((Counter(prediction) & Counter(reference)).values())
    if not prediction or not reference:
        return 0.0
    precision = overlap / len(prediction)
    recall = overlap / len(reference)
    return 2 * precision * recall / (precision + recall) if precision + recall else 0.0


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--train", type=Path, required=True)
    parser.add_argument("--validation", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=Path("ai/models/ksl-gloss-mt5"))
    parser.add_argument("--smoke", action="store_true", help="Use 256 train rows and 20 steps only.")
    parser.add_argument("--epochs", type=float, default=3.0)
    parser.add_argument("--min-verification-f1", type=float, default=0.30,
                        help="Minimum mean gloss-token F1 before a model is accepted.")
    args = parser.parse_args()

    import torch
    from datasets import load_dataset
    from transformers import (AutoModelForSeq2SeqLM, AutoTokenizer, DataCollatorForSeq2Seq,
                              Seq2SeqTrainer, Seq2SeqTrainingArguments, set_seed)

    set_seed(42)
    model_name = "google/mt5-small"
    dataset = load_dataset("json", data_files={"train": str(args.train), "validation": str(args.validation)})
    if args.smoke:
        dataset["train"] = dataset["train"].shuffle(seed=42).select(range(min(256, len(dataset["train"]))))
        dataset["validation"] = dataset["validation"].select(range(min(32, len(dataset["validation"]))))

    tokenizer = AutoTokenizer.from_pretrained(model_name)
    added = tokenizer.add_special_tokens({"additional_special_tokens": [GLOSS_SEPARATOR]})
    model = AutoModelForSeq2SeqLM.from_pretrained(model_name)
    if added:
        model.resize_token_embeddings(len(tokenizer))
    model.config.use_cache = False

    def preprocess(batch):
        sources = [PROMPT_PREFIX + text for text in batch["input_text"]]
        targets = [serialize_glosses(row) for row in batch["target_glosses"]]
        encoded = tokenizer(sources, max_length=96, truncation=True)
        encoded["labels"] = tokenizer(text_target=targets, max_length=96, truncation=True)["input_ids"]
        return encoded

    tokenized = dataset.map(preprocess, batched=True, remove_columns=dataset["train"].column_names)
    arguments = Seq2SeqTrainingArguments(
        output_dir=str(args.output_dir.parent / "training-checkpoints"),
        per_device_train_batch_size=1,
        per_device_eval_batch_size=1,
        gradient_accumulation_steps=4,
        gradient_checkpointing=torch.cuda.is_available(),
        learning_rate=1e-4,
        num_train_epochs=args.epochs,
        max_steps=20 if args.smoke else -1,
        optim="adafactor",
        fp16=False,
        bf16=False,
        eval_strategy="no",
        save_strategy="no",
        report_to="none",
    )
    trainer = Seq2SeqTrainer(
        model=model, args=arguments, train_dataset=tokenized["train"],
        tokenizer=tokenizer, data_collator=DataCollatorForSeq2Seq(tokenizer, model=model),
    )
    trainer.train()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    trainer.save_model(str(args.output_dir))
    tokenizer.save_pretrained(str(args.output_dir))

    # This is intentionally a new model object loaded solely from saved files.
    reloaded_tokenizer = AutoTokenizer.from_pretrained(args.output_dir, local_files_only=True)
    reloaded_model = AutoModelForSeq2SeqLM.from_pretrained(args.output_dir, local_files_only=True)
    device = "cuda" if torch.cuda.is_available() else "mps" if torch.backends.mps.is_available() else "cpu"
    reloaded_model.to(device).eval()
    predictions = []
    for row in dataset["validation"].select(range(min(10, len(dataset["validation"])))):
        encoded = reloaded_tokenizer(PROMPT_PREFIX + row["input_text"], return_tensors="pt", truncation=True, max_length=96).to(device)
        with torch.inference_mode():
            ids = reloaded_model.generate(**encoded, max_new_tokens=96, num_beams=4, early_stopping=True)
        prediction = parse_glosses(reloaded_tokenizer.decode(ids[0], skip_special_tokens=True))
        contains_special_token = any("<extra_id_" in item or "<unk>" in item for item in prediction)
        if not prediction or contains_special_token:
            raise RuntimeError(
                "저장 후 재로딩한 모델이 비어 있거나 특수 토큰을 반환했습니다. 가중치를 배포하지 마세요."
            )
        predictions.append({
            "source": row["input_text"], "reference": row["target_glosses"],
            "prediction": prediction, "gloss_f1": gloss_f1(prediction, row["target_glosses"]),
        })
    mean_f1 = sum(row["gloss_f1"] for row in predictions) / len(predictions)
    if mean_f1 < args.min_verification_f1:
        raise RuntimeError(
            f"재로딩 검증 gloss F1={mean_f1:.3f}; 기준 {args.min_verification_f1:.3f} 미만입니다. "
            "가중치를 배포하지 마세요."
        )
    (args.output_dir / "verification_predictions.json").write_text(json.dumps(predictions, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"verified model saved to: {args.output_dir} (mean gloss F1={mean_f1:.3f})")


if __name__ == "__main__":
    main()
