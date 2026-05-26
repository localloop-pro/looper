"""Export LOOPER training data to Hugging Face datasets format."""
import json
import os
from datetime import datetime
from models import SessionLocal, TrainingLog


def export_to_jsonl(output_path: str = None, limit: int = None):
    """Export training_log to JSONL format for Hugging Face fine-tuning."""
    db = SessionLocal()
    query = db.query(TrainingLog).order_by(TrainingLog.created_at.desc())
    if limit:
        query = query.limit(limit)
    logs = query.all()

    if not output_path:
        os.makedirs("data/exports", exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = f"data/exports/looper_training_{ts}.jsonl"

    records = []
    for log in logs:
        # Only export helpful responses (negative feedback is excluded)
        if log.feedback == "not_helpful":
            continue

        records.append({
            "instruction": log.query_text,
            "response": log.response_text,
            "intent": log.intent,
            "user_id": log.user_id,
            "timestamp": log.created_at.isoformat() if log.created_at else None,
        })

    with open(output_path, "w") as f:
        for record in records:
            f.write(json.dumps(record) + "\n")

    db.close()
    print(f"✅ Exported {len(records)} training records to {output_path}")
    return len(records), output_path


def export_to_hf_dataset(output_dir: str = "data/hf_dataset"):
    """Export to Hugging Face Dataset format (requires `datasets` library)."""
    try:
        from datasets import Dataset
    except ImportError:
        print("Install `datasets` first: pip install datasets")
        return

    db = SessionLocal()
    logs = db.query(TrainingLog).filter(TrainingLog.feedback != "not_helpful").all()

    data = {
        "instruction": [log.query_text for log in logs],
        "response": [log.response_text or "" for log in logs],
        "intent": [log.intent or "" for log in logs],
    }

    dataset = Dataset.from_dict(data)
    dataset.save_to_disk(output_dir)

    db.close()
    print(f"✅ Saved {len(logs)} records to Hugging Face dataset at {output_dir}")
    return len(logs), output_dir


if __name__ == "__main__":
    export_to_jsonl()