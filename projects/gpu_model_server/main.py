import importlib
import importlib.util
import os
import time
from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field


app = FastAPI(title="GPU Model Server")

ALLOWED_STATUS_CODES = {200, 400, 429, 500}
GPU_MODEL_MODE = os.getenv("GPU_MODEL_MODE", "template")
GPU_MODEL_NAME = os.getenv("GPU_MODEL_NAME", "Qwen/Qwen2.5-0.5B-Instruct")
_TRANSFORMERS_TOKENIZER = None
_TRANSFORMERS_MODEL = None
_TRANSFORMERS_TORCH = None

class GenerateRequest(BaseModel):
    model: str
    tokens_in: int = Field(ge=0)
    tokens_out: int = Field(ge=0)
    force_status: Optional[int] = None


class GenerateResponse(BaseModel):
    model: str
    status: int
    latency_ms: int
    tokens_in: int
    tokens_out: int


def estimate_gpu_latency_ms(model: str, tokens_in: int, tokens_out: int) -> int:
    total_tokens = tokens_in + tokens_out

    if model == "qwen2.5-1.5b":
        return 70 + int(total_tokens * 0.18)

    if model == "qwen2.5-0.5b":
        return 45 + int(total_tokens * 0.12)

    return 90 + int(total_tokens * 0.2)


@app.get("/health")
def health_check():
    return {
        "status": "ok",
        "service": "gpu-model-server",
    }


def generate_with_template(request: GenerateRequest) -> dict:
    start_time = time.perf_counter()

    status = request.force_status or 200
    estimated_latency_ms = estimate_gpu_latency_ms(
        request.model,
        request.tokens_in,
        request.tokens_out,
    )

    elapsed_ms = int((time.perf_counter() - start_time) * 1000)
    latency_ms = max(estimated_latency_ms, elapsed_ms)

    return {
        "model": request.model,
        "status": status,
        "latency_ms": latency_ms,
        "tokens_in": request.tokens_in,
        "tokens_out": request.tokens_out,
    }

def get_missing_transformers_dependencies() -> list[str]:
    missing_dependencies = []

    if importlib.util.find_spec("torch") is None:
        missing_dependencies.append("torch")

    if importlib.util.find_spec("transformers") is None:
        missing_dependencies.append("transformers")

    return missing_dependencies

def load_transformers_model() -> dict:
    global _TRANSFORMERS_TOKENIZER
    global _TRANSFORMERS_MODEL
    global _TRANSFORMERS_TORCH

    if (
        _TRANSFORMERS_TOKENIZER is not None
        and _TRANSFORMERS_MODEL is not None
        and _TRANSFORMERS_TORCH is not None
    ):
        return {
            "tokenizer": _TRANSFORMERS_TOKENIZER,
            "model": _TRANSFORMERS_MODEL,
            "torch": _TRANSFORMERS_TORCH,
        }

    torch = importlib.import_module("torch")
    transformers = importlib.import_module("transformers")

    tokenizer = transformers.AutoTokenizer.from_pretrained(GPU_MODEL_NAME)
    model = transformers.AutoModelForCausalLM.from_pretrained(GPU_MODEL_NAME)

    if torch.cuda.is_available():
        model = model.to("cuda")

    model.eval()

    _TRANSFORMERS_TOKENIZER = tokenizer
    _TRANSFORMERS_MODEL = model
    _TRANSFORMERS_TORCH = torch

    return {
        "tokenizer": tokenizer,
        "model": model,
        "torch": torch,
    }


def generate_with_transformers(request: GenerateRequest) -> dict:
    missing_dependencies = get_missing_transformers_dependencies()

    if missing_dependencies:
        raise HTTPException(
            status_code=500,
            detail=(
                "transformers mode requires missing dependencies: "
                + ", ".join(missing_dependencies)
            ),
        )

    runtime = load_transformers_model()
    tokenizer = runtime["tokenizer"]
    model = runtime["model"]
    torch = runtime["torch"]

    prompt = (
        "You are a model backend used for an AI inference observability test. "
        f"Generate a short response for model={request.model}, "
        f"tokens_in={request.tokens_in}, tokens_out={request.tokens_out}."
    )

    start_time = time.perf_counter()

    inputs = tokenizer(prompt, return_tensors="pt")
    if torch.cuda.is_available() and hasattr(inputs, "to"):
        inputs = inputs.to("cuda")

    max_new_tokens = max(request.tokens_out, 1)

    with torch.no_grad():
        output_ids = model.generate(
            **inputs,
            max_new_tokens=max_new_tokens,
            do_sample=False,
        )

    tokenizer.decode(output_ids[0], skip_special_tokens=True)

    elapsed_ms = int((time.perf_counter() - start_time) * 1000)
    latency_ms = max(elapsed_ms, 1)

    return {
        "model": request.model,
        "status": request.force_status or 200,
        "latency_ms": latency_ms,
        "tokens_in": request.tokens_in,
        "tokens_out": request.tokens_out,
    }

@app.post("/generate", response_model=GenerateResponse)
def generate(request: GenerateRequest):
    if request.force_status is not None and request.force_status not in ALLOWED_STATUS_CODES:
        raise HTTPException(
            status_code=400,
            detail="force_status must be one of 200, 400, 429, 500",
        )

    if GPU_MODEL_MODE == "template":
        return generate_with_template(request)

    if GPU_MODEL_MODE == "transformers":
        return generate_with_transformers(request)

    raise HTTPException(
        status_code=500,
        detail=f"unsupported GPU_MODEL_MODE: {GPU_MODEL_MODE}",
    )

