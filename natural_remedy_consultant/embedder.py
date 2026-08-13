import shutil
from pathlib import Path

import numpy as np
import onnxruntime as ort
from tokenizers import Tokenizer

MODEL_REPO = "Xenova/all-MiniLM-L6-v2"
DEFAULT_MODEL_DIR = Path(__file__).resolve().parent / "models" / MODEL_REPO


def ensure_model(model_dir=DEFAULT_MODEL_DIR, repo=MODEL_REPO):
    """Download the tokenizer and ONNX model if they are not present yet."""
    model_dir = Path(model_dir)

    wanted = {
        "tokenizer.json": model_dir / "tokenizer.json",
        "onnx/model.onnx": model_dir / "model.onnx",
    }

    if all(path.exists() for path in wanted.values()):
        return model_dir

    from huggingface_hub import hf_hub_download

    model_dir.mkdir(parents=True, exist_ok=True)

    for remote, local in wanted.items():
        if not local.exists():
            src = hf_hub_download(repo_id=repo, filename=remote)
            shutil.copy2(src, local)

    return model_dir


class Embedder:
    def __init__(self, path=None):
        path = ensure_model() if path is None else Path(path)
        self.tokenizer = Tokenizer.from_file(str(path / "tokenizer.json"))
        self.session = ort.InferenceSession(
            str(path / "model.onnx"), providers=["CPUExecutionProvider"]
        )
        self.input_names = {inp.name for inp in self.session.get_inputs()}

    def encode(self, text, normalize=True):
        return self.encode_batch([text], normalize=normalize)[0]

    def encode_batch(self, texts, normalize=True):
        self.tokenizer.enable_padding()
        encoded = self.tokenizer.encode_batch(texts)
        feed = {}
        if "input_ids" in self.input_names:
            feed["input_ids"] = np.array([e.ids for e in encoded], dtype=np.int64)
        if "attention_mask" in self.input_names:
            feed["attention_mask"] = np.array(
                [e.attention_mask for e in encoded], dtype=np.int64
            )
        if "token_type_ids" in self.input_names:
            feed["token_type_ids"] = np.array(
                [e.type_ids for e in encoded], dtype=np.int64
            )
        hidden = self.session.run(None, feed)[0]
        mask = feed["attention_mask"][..., None]
        pooled = (hidden * mask).sum(axis=1) / mask.sum(axis=1)
        if normalize:
            pooled = pooled / np.linalg.norm(pooled, axis=1, keepdims=True)
        return pooled
