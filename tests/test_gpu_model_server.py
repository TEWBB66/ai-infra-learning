from fastapi.testclient import TestClient

from projects.gpu_model_server.main import app


client = TestClient(app)


def test_gpu_model_server_health_check():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "gpu-model-server",
    }


def test_gpu_model_server_generate_success(monkeypatch):
    from projects.gpu_model_server import main

    monkeypatch.setattr(main, "GPU_MODEL_MODE", "template")

    response = client.post(
        "/generate",
        json={
            "model": "qwen2.5-0.5b",
            "tokens_in": 100,
            "tokens_out": 20,
        },
    )

    assert response.status_code == 200

    data = response.json()
    assert data["model"] == "qwen2.5-0.5b"
    assert data["status"] == 200
    assert data["tokens_in"] == 100
    assert data["tokens_out"] == 20
    assert data["latency_ms"] > 0


def test_gpu_model_server_generate_with_forced_status(monkeypatch):
    from projects.gpu_model_server import main

    monkeypatch.setattr(main, "GPU_MODEL_MODE", "template")

    response = client.post(
        "/generate",
        json={
            "model": "qwen2.5-0.5b",
            "tokens_in": 100,
            "tokens_out": 20,
            "force_status": 500,
        },
    )

    assert response.status_code == 200
    assert response.json()["status"] == 500


def test_gpu_model_server_rejects_invalid_force_status(monkeypatch):
    from projects.gpu_model_server import main

    monkeypatch.setattr(main, "GPU_MODEL_MODE", "template")

    response = client.post(
        "/generate",
        json={
            "model": "qwen2.5-0.5b",
            "tokens_in": 100,
            "tokens_out": 20,
            "force_status": 999,
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "force_status must be one of 200, 400, 429, 500"


def test_gpu_model_server_rejects_unsupported_mode(monkeypatch):
    from projects.gpu_model_server import main

    monkeypatch.setattr(main, "GPU_MODEL_MODE", "unsupported")

    response = client.post(
        "/generate",
        json={
            "model": "qwen2.5-0.5b",
            "tokens_in": 100,
            "tokens_out": 20,
        },
    )

    assert response.status_code == 500
    assert response.json()["detail"] == "unsupported GPU_MODEL_MODE: unsupported"

def test_gpu_model_server_load_transformers_model_returns_cached_runtime(monkeypatch):
    from projects.gpu_model_server import main

    cached_tokenizer = object()
    cached_model = object()
    cached_torch = object()

    monkeypatch.setattr(main, "_TRANSFORMERS_TOKENIZER", cached_tokenizer)
    monkeypatch.setattr(main, "_TRANSFORMERS_MODEL", cached_model)
    monkeypatch.setattr(main, "_TRANSFORMERS_TORCH", cached_torch)

    runtime = main.load_transformers_model()

    assert runtime["tokenizer"] is cached_tokenizer
    assert runtime["model"] is cached_model
    assert runtime["torch"] is cached_torch


def test_gpu_model_server_load_transformers_model_loads_and_caches_runtime(monkeypatch):
    from projects.gpu_model_server import main

    class FakeCuda:
        @staticmethod
        def is_available():
            return True

    class FakeTorch:
        cuda = FakeCuda()

    class FakeModel:
        def __init__(self):
            self.device = None
            self.eval_called = False

        def to(self, device):
            self.device = device
            return self

        def eval(self):
            self.eval_called = True

    class FakeAutoTokenizer:
        @staticmethod
        def from_pretrained(model_name):
            return {"tokenizer_for": model_name}

    class FakeAutoModelForCausalLM:
        @staticmethod
        def from_pretrained(model_name):
            return FakeModel()

    class FakeTransformers:
        AutoTokenizer = FakeAutoTokenizer
        AutoModelForCausalLM = FakeAutoModelForCausalLM

    def fake_import_module(module_name):
        if module_name == "torch":
            return FakeTorch
        if module_name == "transformers":
            return FakeTransformers
        raise ImportError(module_name)

    monkeypatch.setattr(main, "_TRANSFORMERS_TOKENIZER", None)
    monkeypatch.setattr(main, "_TRANSFORMERS_MODEL", None)
    monkeypatch.setattr(main, "_TRANSFORMERS_TORCH", None)
    monkeypatch.setattr(main, "GPU_MODEL_NAME", "Qwen/Qwen2.5-0.5B-Instruct")
    monkeypatch.setattr(main.importlib, "import_module", fake_import_module)

    runtime = main.load_transformers_model()

    assert runtime["tokenizer"] == {"tokenizer_for": "Qwen/Qwen2.5-0.5B-Instruct"}
    assert runtime["model"].device == "cuda"
    assert runtime["model"].eval_called is True
    assert runtime["torch"] is FakeTorch

    assert main._TRANSFORMERS_TOKENIZER is runtime["tokenizer"]
    assert main._TRANSFORMERS_MODEL is runtime["model"]
    assert main._TRANSFORMERS_TORCH is FakeTorch

def test_gpu_model_server_detects_missing_transformers_dependencies(monkeypatch):
    from projects.gpu_model_server import main

    def fake_find_spec(package_name):
        if package_name == "torch":
            return None
        if package_name == "transformers":
            return object()
        return object()

    monkeypatch.setattr(main.importlib.util, "find_spec", fake_find_spec)

    assert main.get_missing_transformers_dependencies() == ["torch"]

def test_gpu_model_server_transformers_mode_reports_missing_dependencies(monkeypatch):
    from projects.gpu_model_server import main

    def fake_find_spec(package_name):
        if package_name in {"torch", "transformers"}:
            return None
        return object()

    monkeypatch.setattr(main, "GPU_MODEL_MODE", "transformers")
    monkeypatch.setattr(main.importlib.util, "find_spec", fake_find_spec)

    response = client.post(
        "/generate",
        json={
            "model": "qwen2.5-0.5b",
            "tokens_in": 100,
            "tokens_out": 20,
        },
    )

    assert response.status_code == 500
    assert response.json()["detail"] == (
        "transformers mode requires missing dependencies: torch, transformers"
    )


def test_gpu_model_server_transformers_mode_generates_response(monkeypatch):
    from projects.gpu_model_server import main

    class FakeInputs(dict):
        def to(self, device):
            self["device"] = device
            return self

    class FakeTokenizer:
        def __init__(self):
            self.prompt = None
            self.decoded = False

        def __call__(self, prompt, return_tensors):
            self.prompt = prompt
            return FakeInputs({"input_ids": [1, 2, 3]})

        def decode(self, output_ids, skip_special_tokens):
            self.decoded = True
            return "fake generated text"

    class FakeModel:
        def __init__(self):
            self.generate_kwargs = None

        def generate(self, **kwargs):
            self.generate_kwargs = kwargs
            return [[1, 2, 3, 4]]

    class FakeCuda:
        @staticmethod
        def is_available():
            return True

    class FakeNoGrad:
        def __enter__(self):
            return None

        def __exit__(self, exc_type, exc_value, traceback):
            return None

    class FakeTorch:
        cuda = FakeCuda()

        @staticmethod
        def no_grad():
            return FakeNoGrad()

    fake_tokenizer = FakeTokenizer()
    fake_model = FakeModel()

    monkeypatch.setattr(main, "GPU_MODEL_MODE", "transformers")
    monkeypatch.setattr(main.importlib.util, "find_spec", lambda package_name: object())
    monkeypatch.setattr(
        main,
        "load_transformers_model",
        lambda: {
            "tokenizer": fake_tokenizer,
            "model": fake_model,
            "torch": FakeTorch,
        },
    )

    response = client.post(
        "/generate",
        json={
            "model": "qwen2.5-0.5b",
            "tokens_in": 100,
            "tokens_out": 20,
        },
    )

    assert response.status_code == 200

    data = response.json()
    assert data["model"] == "qwen2.5-0.5b"
    assert data["status"] == 200
    assert data["tokens_in"] == 100
    assert data["tokens_out"] == 20
    assert data["latency_ms"] > 0

    assert fake_tokenizer.prompt is not None
    assert fake_tokenizer.decoded is True
    assert fake_model.generate_kwargs["max_new_tokens"] == 20
    assert fake_model.generate_kwargs["do_sample"] is False
    assert fake_model.generate_kwargs["device"] == "cuda"