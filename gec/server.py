"""Local GECToR server for the diary's second error detector (backend/app/services/gec_client.py).

    gec/.venv/bin/python gec/server.py            # http://127.0.0.1:8010
    POST /correct {"sentences": [...]} -> {"corrected": [...]}   GET /health

Model: gotutiyan/gector-roberta-base-5k (CPU, ~0.8 s per essay on the Mac in the 2026-11-24 benchmark).
Settings match that benchmark and the blind check that decided to use it.
verb-form-vocab.txt is from grammarly/gector (Apache-2.0).
"""
import json
import logging
import os
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import torch
from gector import GECToR, load_verb_dict, predict
from transformers import AutoTokenizer

MODEL_ID = os.getenv("GEC_MODEL", "gotutiyan/gector-roberta-base-5k")
PORT = int(os.getenv("GEC_PORT", "8010"))
MAX_SENTENCES = 400

logging.basicConfig(level=logging.INFO, format="%(asctime)s gec %(message)s")
log = logging.getLogger("gec")

t0 = time.perf_counter()
model = GECToR.from_pretrained(MODEL_ID, low_cpu_mem_usage=False).eval()
tokenizer = AutoTokenizer.from_pretrained(MODEL_ID)
encode, decode = load_verb_dict(str(Path(__file__).with_name("verb-form-vocab.txt")))
lock = threading.Lock()  # one prediction at a time; the model is not shared safely across threads
log.info(f"loaded {MODEL_ID} in {time.perf_counter() - t0:.1f}s")


def correct(sentences):
    with lock, torch.no_grad():
        return predict(model, tokenizer, sentences, encode, decode, keep_confidence=0.0, min_error_prob=0.0,
                       batch_size=32, n_iteration=3)


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, body):
        data = json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        self._send(200, {"ok": True, "model": MODEL_ID}) if self.path == "/health" else self._send(404, {})

    def do_POST(self):
        if self.path != "/correct":
            return self._send(404, {})
        try:
            body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))))
            sentences = body["sentences"]
            if not isinstance(sentences, list) or not all(isinstance(s, str) for s in sentences) \
                    or len(sentences) > MAX_SENTENCES:
                raise ValueError("sentences must be a list of at most 400 strings")
        except Exception as e:
            return self._send(400, {"error": str(e)})
        started = time.perf_counter()
        out = correct(sentences) if sentences else []
        log.info(f"{len(sentences)} sentences in {(time.perf_counter() - started) * 1000:.0f} ms")
        self._send(200, {"corrected": out})

    def log_message(self, *args):
        pass


if __name__ == "__main__":
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
