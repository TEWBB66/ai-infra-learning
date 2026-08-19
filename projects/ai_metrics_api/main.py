from datetime import datetime, timezone
from threading import Condition, Lock
from typing import Optional
from uuid import uuid4
import time


from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel, Field
from fastapi.responses import PlainTextResponse

from projects.log_analyzer.analyze_logs import analyze_logs, parse_log_line
from projects.ai_metrics_api.model_client import call_model_server

from projects.ai_metrics_api.config import (
    ALLOWED_FORCE_STATUS_CODES,
    DEFAULT_SLOW_THRESHOLD_MS,
    LOG_PATH,
    MAX_IN_FLIGHT_REQUESTS,
    QUEUE_TIMEOUT_MS,
    MAX_QUEUE_SIZE,
    ADMISSION_MODE,
    API_KEY,
    REQUIRE_API_KEY,
    MODEL_BACKEND,
    MODEL_SERVER_URL,
    VLLM_BASE_URL,
    VLLM_MODEL,
    MODEL_ERROR_RATE_CRITICAL_THRESHOLD,
    MODEL_ERROR_RATE_WARNING_THRESHOLD,
    MODEL_P95_LATENCY_CRITICAL_MS,
    MODEL_P95_LATENCY_WARNING_MS,
    SERVICE_ERROR_RATE_CRITICAL_THRESHOLD,
    SERVICE_ERROR_RATE_WARNING_THRESHOLD,
    SERVICE_P95_LATENCY_CRITICAL_MS,
    SERVICE_P95_LATENCY_WARNING_MS,
    SERVICE_SLOW_REQUEST_CRITICAL_COUNT,
    SERVICE_SLOW_REQUEST_WARNING_COUNT,
)
from projects.ai_metrics_api.prometheus_histogram import build_latency_histogram_prometheus

app = FastAPI()

class InferenceGate:
    def __init__(
        self,
        max_in_flight: int,
        admission_mode: str = "reject",
        max_queue_size: int = 0,
        queue_timeout_ms: int = 0,
    ):
        self.max_in_flight = max_in_flight
        self.admission_mode = admission_mode
        self.max_queue_size = max_queue_size
        self.queue_timeout_ms = queue_timeout_ms
        self.current_in_flight = 0
        self.current_queued = 0
        self.queue_rejected_total = 0
        self.queue_timeout_total = 0
        self._condition = Condition(Lock())

    def try_acquire(self) -> bool:
        if self.admission_mode == "queue":
            return self._try_acquire_with_queue()
        return self._try_acquire_reject()

    def _try_acquire_reject(self) -> bool:
        with self._condition:
            if self.current_in_flight >= self.max_in_flight:
                return False

            self.current_in_flight += 1
            return True

    def _try_acquire_with_queue(self) -> bool:
        deadline = time.perf_counter() + (self.queue_timeout_ms / 1000)

        with self._condition:
            if self.current_in_flight < self.max_in_flight:
                self.current_in_flight += 1
                return True

            if self.current_queued >= self.max_queue_size:
                self.queue_rejected_total += 1
                return False

            self.current_queued += 1
            try:
                while self.current_in_flight >= self.max_in_flight:
                    remaining_seconds = deadline - time.perf_counter()
                    if remaining_seconds <= 0:
                        self.queue_timeout_total += 1
                        return False
                    self._condition.wait(timeout=remaining_seconds)

                self.current_in_flight += 1
                return True
            finally:
                self.current_queued -= 1

    def release(self) -> None:
        with self._condition:
            if self.current_in_flight > 0:
                self.current_in_flight -= 1
            self._condition.notify()

    def snapshot(self) -> dict:
        with self._condition:
            return {
                "admission_mode": self.admission_mode,
                "max_in_flight": self.max_in_flight,
                "current_in_flight": self.current_in_flight,
                "max_queue_size": self.max_queue_size,
                "current_queued": self.current_queued,
                "queue_rejected_total": self.queue_rejected_total,
                "queue_timeout_total": self.queue_timeout_total,
            }


INFERENCE_GATE = InferenceGate(
    MAX_IN_FLIGHT_REQUESTS,
    admission_mode=ADMISSION_MODE,
    max_queue_size=MAX_QUEUE_SIZE,
    queue_timeout_ms=QUEUE_TIMEOUT_MS,
)

def format_log_line(
    request_id: str,
    model: str,
    endpoint: str,
    status: int,
    latency_ms: int,
    tokens_in: int,
    tokens_out: int,
) -> str:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return (
        f"{now} "
        f"request_id={request_id} "
        f"model={model} "
        f"endpoint={endpoint} "
        f"status={status} "
        f"latency_ms={latency_ms} "
        f"tokens_in={tokens_in} "
        f"tokens_out={tokens_out}"
    )


def append_log_line(log_line: str) -> None:
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(log_line + "\n")
        

def add_alert(alerts, level, scope, metric, message, actual, threshold):
    alerts.append({
        "level": level,
        "scope": scope,
        "metric": metric,
        "message": message,
        "actual": actual,
        "threshold": threshold,
    })


def build_alerts(metrics):
    alerts = []

    error_rate = metrics["error_rate"]
    p95_latency_ms = metrics["p95_latency_ms"]
    slow_request_count = metrics["slow_request_count"]

    if error_rate >= SERVICE_ERROR_RATE_CRITICAL_THRESHOLD:
        add_alert(alerts,"critical","service","error_rate","service error rate is too high",error_rate,SERVICE_ERROR_RATE_CRITICAL_THRESHOLD)
    elif error_rate >= SERVICE_ERROR_RATE_WARNING_THRESHOLD:
        add_alert(alerts,"warning","service","error_rate","service error rate is elevated", error_rate,SERVICE_ERROR_RATE_WARNING_THRESHOLD)

    if p95_latency_ms >= SERVICE_P95_LATENCY_CRITICAL_MS:
        add_alert(alerts, "critical", "service", "p95_latency_ms", "service P95 latency is too high", p95_latency_ms, SERVICE_P95_LATENCY_CRITICAL_MS)
    elif p95_latency_ms >= SERVICE_P95_LATENCY_WARNING_MS:
        add_alert(alerts, "warning", "service", "p95_latency_ms", "service P95 latency is elevated", p95_latency_ms, SERVICE_P95_LATENCY_WARNING_MS)

    if slow_request_count >= SERVICE_SLOW_REQUEST_CRITICAL_COUNT:
        add_alert(alerts, "critical", "service", "slow_request_count", "too many slow requests", slow_request_count, SERVICE_SLOW_REQUEST_CRITICAL_COUNT)
    elif slow_request_count >= SERVICE_SLOW_REQUEST_WARNING_COUNT:
        add_alert(alerts, "warning", "service", "slow_request_count", "slow requests are increasing", slow_request_count, SERVICE_SLOW_REQUEST_WARNING_COUNT)

    for model_name, model_metrics in metrics["metrics_by_model"].items():
        model_error_rate = model_metrics["error_rate"]
        model_p95_latency_ms = model_metrics["p95_latency_ms"]

        if model_error_rate >= MODEL_ERROR_RATE_CRITICAL_THRESHOLD:
            add_alert(alerts, "critical", model_name, "error_rate", "model error rate is too high", model_error_rate, MODEL_ERROR_RATE_CRITICAL_THRESHOLD)
        elif model_error_rate >= MODEL_ERROR_RATE_WARNING_THRESHOLD:
            add_alert(alerts, "warning", model_name, "error_rate", "model error rate is elevated", model_error_rate, MODEL_ERROR_RATE_WARNING_THRESHOLD)

        if model_p95_latency_ms >= MODEL_P95_LATENCY_CRITICAL_MS:
            add_alert(alerts, "critical", model_name, "p95_latency_ms", "model P95 latency is too high", model_p95_latency_ms, MODEL_P95_LATENCY_CRITICAL_MS)
        elif model_p95_latency_ms >= MODEL_P95_LATENCY_WARNING_MS:
            add_alert(alerts, "warning", model_name, "p95_latency_ms", "model P95 latency is elevated", model_p95_latency_ms, MODEL_P95_LATENCY_WARNING_MS)

    service_status = "healthy"
    if any(alert["level"] == "critical" for alert in alerts):
        service_status = "critical"
    elif alerts:
        service_status = "warning"

    return {
        "service_status": service_status,
        "alert_count": len(alerts),
        "alerts": alerts,
    }



def _extract_bearer_token(authorization: Optional[str]) -> Optional[str]:
    if not authorization:
        return None

    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        return None
    return token


def require_api_key(
    authorization: Optional[str] = Header(default=None),
    x_api_key: Optional[str] = Header(default=None, alias="X-API-Key"),
) -> None:
    if not REQUIRE_API_KEY:
        return

    if not API_KEY:
        raise HTTPException(
            status_code=500,
            detail="API key authentication is enabled but API_KEY is not configured",
        )

    presented_key = _extract_bearer_token(authorization) or x_api_key
    if not presented_key:
        raise HTTPException(status_code=401, detail="missing API key")

    if presented_key != API_KEY:
        raise HTTPException(status_code=403, detail="invalid API key")

class InferRequest(BaseModel):
    model: str = "qwen2.5-7b"
    endpoint: str = "/v1/infer"
    tokens_in: int = Field(default=256, ge=0)
    tokens_out: int = Field(default=80, ge=0)
    prompt: Optional[str] = None
    max_tokens: Optional[int] = Field(default=None, ge=1)
    temperature: float = Field(default=0.0, ge=0.0)
    force_status: Optional[int] = None

def load_records():
    records = []

    with open(LOG_PATH, "r", encoding="utf-8") as f:
        for line in f:
            record = parse_log_line(line)
            records.append(record)

    return records

@app.get("/health")
def health_check():
    return {
        "status": "ok",
        "service": "ai-metrics-api",
    }

@app.get("/ready")
def readiness_check():
    if MODEL_BACKEND in {"mock", "remote_http"}:
        return {
            "status": "ready",
            "service": "ai-metrics-api",
            "backend": MODEL_BACKEND,
            "model_server_url": MODEL_SERVER_URL,
        }

    if MODEL_BACKEND == "vllm":
        return {
            "status": "ready",
            "service": "ai-metrics-api",
            "backend": MODEL_BACKEND,
            "vllm_base_url": VLLM_BASE_URL,
            "vllm_model": VLLM_MODEL,
        }

    raise HTTPException(
        status_code=503,
        detail=f"unsupported MODEL_BACKEND: {MODEL_BACKEND}",
    )

def handle_infer(request: InferRequest, endpoint: str):
    if (
        request.force_status is not None
        and request.force_status not in ALLOWED_FORCE_STATUS_CODES
    ):
        raise HTTPException(
            status_code=400,
            detail="force_status must be one of 200, 400, 429, 500",
        )

    request_id = f"req-{uuid4().hex[:8]}"
    start_time = time.perf_counter()

    if not INFERENCE_GATE.try_acquire():
        latency_ms = max(1, int((time.perf_counter() - start_time) * 1000))
        log_line = format_log_line(
            request_id=request_id,
            model=request.model,
            endpoint=endpoint,
            status=429,
            latency_ms=latency_ms,
            tokens_in=request.tokens_in,
            tokens_out=0,
        )
        append_log_line(log_line)
        raise HTTPException(
            status_code=429,
            detail="too many in-flight inference requests",
        )

    try:
        payload = {
            "model": request.model,
            "tokens_in": request.tokens_in,
            "tokens_out": request.tokens_out,
            "prompt": request.prompt,
            "max_tokens": request.max_tokens,
            "temperature": request.temperature,
            "force_status": request.force_status,
        }

        try:
            result = call_model_server(payload)
        except HTTPException as exc:
            latency_ms = max(1, int((time.perf_counter() - start_time) * 1000))
            log_line = format_log_line(
                request_id=request_id,
                model=request.model,
                endpoint=endpoint,
                status=exc.status_code,
                latency_ms=latency_ms,
                tokens_in=request.tokens_in,
                tokens_out=0,
            )
            append_log_line(log_line)
            raise exc

        log_line = format_log_line(
            request_id=request_id,
            model=result["model"],
            endpoint=endpoint,
            status=result["status"],
            latency_ms=result["latency_ms"],
            tokens_in=result["tokens_in"],
            tokens_out=result["tokens_out"],
        )
        append_log_line(log_line)

        return {
            "request_id": request_id,
            **result,
        }
    finally:
        INFERENCE_GATE.release()

@app.post("/v1/infer", dependencies=[Depends(require_api_key)])
def infer(request: InferRequest):
    return handle_infer(request, endpoint="/v1/infer")


@app.post("/v1/mock-infer", dependencies=[Depends(require_api_key)])
def mock_infer(request: InferRequest):
    return handle_infer(request, endpoint="/v1/mock-infer")

@app.get("/metrics/logs")
def get_log_metrics():
    return analyze_logs(LOG_PATH)

@app.get("/metrics/models")
def get_model_metrics(model_name: Optional[str] = None):
    metrics = analyze_logs(LOG_PATH)
    metrics_by_model = metrics["metrics_by_model"]
    if model_name is None:
        return {
            "metrics_by_model": metrics_by_model,
        }
        
    if model_name not in metrics_by_model:
        raise HTTPException(status_code=404, detail="model not found")

    return {
    "model_name": model_name,
    "metrics": metrics_by_model[model_name],
}

@app.get("/metrics/slow")
def get_slow_requests(threshold_ms: int = DEFAULT_SLOW_THRESHOLD_MS):
    records = load_records()

    slow_records = []
    for record in records:
        latency = int(record["latency_ms"])
        if latency > threshold_ms:
            slow_records.append({
                "request_id": record["request_id"],
                "model": record["model"],
                "status": int(record["status"]),
                "latency_ms": latency,
            })

    return {
        "threshold_ms": threshold_ms,
        "slow_request_count": len(slow_records),
        "slow_requests": slow_records,
    }


@app.get("/metrics/errors")
def get_error_requests(status_code: Optional[int] = None):
    records = load_records()

    error_records = []
    for record in records:
        status = int(record["status"])

        if status_code is not None:
            is_error = status == status_code
        else:
            is_error = status >= 400

        if is_error:
            error_records.append({
                "request_id": record["request_id"],
                "model": record["model"],
                "status": status,
                "latency_ms": int(record["latency_ms"]),
            })

    return {
        "status_code": status_code,
        "error_request_count": len(error_records),
        "error_requests": error_records,
    }

@app.get("/metrics/alerts")
def get_alerts():
    metrics = analyze_logs(LOG_PATH)
    return build_alerts(metrics)

def build_incident_report(metrics, alerts_response):
    alerts = alerts_response.get("alerts", [])
    service_status = alerts_response.get("service_status", "healthy")

    possible_causes = []
    suggested_actions = []

    for alert in alerts:
        scope = alert.get("scope")
        metric = alert.get("metric")
        level = alert.get("level")

        if scope == "service" and metric == "error_rate":
            possible_causes.append("overall inference service error rate is elevated")
            suggested_actions.append("check recent failed requests and model server logs")

        elif scope == "service" and metric == "p95_latency_ms":
            possible_causes.append("overall inference latency is elevated")
            suggested_actions.append("inspect top slow requests and high-latency models")

        elif scope == "service" and metric == "slow_request_count":
            possible_causes.append("slow requests are accumulating")
            suggested_actions.append("check whether recent traffic contains long prompts or slow models")

        elif scope != "service" and metric == "error_rate":
            possible_causes.append(f"{scope} has elevated error rate")
            suggested_actions.append(f"consider reducing traffic to {scope} or checking its backend health")

        elif scope != "service" and metric == "p95_latency_ms":
            possible_causes.append(f"{scope} has elevated P95 latency")
            suggested_actions.append(f"inspect slow requests for {scope}")

        if level == "critical":
            suggested_actions.append("treat this as an incident and prioritize immediate investigation")

    if not alerts:
        summary = "service is healthy; no active incident detected"
    elif service_status == "critical":
        summary = "critical incident detected in inference service"
    else:
        summary = "warning-level service degradation detected"

    return {
        "service_status": service_status,
        "summary": summary,
        "total_requests": metrics.get("total_requests"),
        "error_rate": metrics.get("error_rate"),
        "p95_latency_ms": metrics.get("p95_latency_ms"),
        "slow_request_count": metrics.get("slow_request_count"),
        "alert_count": len(alerts),
        "possible_causes": list(dict.fromkeys(possible_causes)),
        "suggested_actions": list(dict.fromkeys(suggested_actions)),
    }


@app.get("/metrics/incidents")
def get_incident_report():
    metrics = analyze_logs(LOG_PATH)
    alerts_response = get_alerts()
    return build_incident_report(metrics, alerts_response)

def _escape_prometheus_label(value: str) -> str:
    return str(value).replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def _snapshot_inference_gate(gate) -> dict:
    if hasattr(gate, "snapshot"):
        return gate.snapshot()

    return {
        "admission_mode": "reject",
        "max_in_flight": getattr(gate, "max_in_flight", 0),
        "current_in_flight": getattr(gate, "current_in_flight", 0),
        "max_queue_size": 0,
        "current_queued": 0,
        "queue_rejected_total": 0,
        "queue_timeout_total": 0,
    }


@app.get("/metrics/prometheus", response_class=PlainTextResponse)
def get_prometheus_metrics():
    metrics = analyze_logs(LOG_PATH)
    gate_metrics = _snapshot_inference_gate(INFERENCE_GATE)
    admission_mode_label = _escape_prometheus_label(gate_metrics["admission_mode"])

    lines = [
        "# HELP ai_inference_total_requests Total number of inference requests",
        "# TYPE ai_inference_total_requests gauge",
        f"ai_inference_total_requests {metrics['total_requests']}",
        "# HELP ai_inference_success_requests Total number of successful inference requests",
        "# TYPE ai_inference_success_requests gauge",
        f"ai_inference_success_requests {metrics['success_requests']}",
        "# HELP ai_inference_failed_requests Total number of failed inference requests",
        "# TYPE ai_inference_failed_requests gauge",
        f"ai_inference_failed_requests {metrics['failed_requests']}",
        "# HELP ai_inference_error_rate Inference request error rate",
        "# TYPE ai_inference_error_rate gauge",
        f"ai_inference_error_rate {metrics['error_rate']}",
        "# HELP ai_inference_p95_latency_ms P95 inference latency in milliseconds",
        "# TYPE ai_inference_p95_latency_ms gauge",
        f"ai_inference_p95_latency_ms {metrics['p95_latency_ms']}",
        "# HELP ai_inference_p99_latency_ms P99 inference latency in milliseconds",
        "# TYPE ai_inference_p99_latency_ms gauge",
        f"ai_inference_p99_latency_ms {metrics['p99_latency_ms']}",
        "# HELP ai_inference_slow_request_count Number of slow inference requests",
        "# TYPE ai_inference_slow_request_count gauge",
        f"ai_inference_slow_request_count {metrics['slow_request_count']}",
        "# HELP ai_inference_current_in_flight_requests Current in-flight inference requests",
        "# TYPE ai_inference_current_in_flight_requests gauge",
        f"ai_inference_current_in_flight_requests {gate_metrics['current_in_flight']}",
        "# HELP ai_inference_queue_depth Current queued inference requests",
        "# TYPE ai_inference_queue_depth gauge",
        f"ai_inference_queue_depth {gate_metrics['current_queued']}",
        "# HELP ai_inference_queue_rejected_total Total inference requests rejected because the queue was full",
        "# TYPE ai_inference_queue_rejected_total counter",
        f"ai_inference_queue_rejected_total {gate_metrics['queue_rejected_total']}",
        "# HELP ai_inference_queue_timeout_total Total inference requests rejected after queue timeout",
        "# TYPE ai_inference_queue_timeout_total counter",
        f"ai_inference_queue_timeout_total {gate_metrics['queue_timeout_total']}",
        "# HELP ai_inference_admission_mode Active inference admission mode",
        "# TYPE ai_inference_admission_mode gauge",
        f'ai_inference_admission_mode{{mode="{admission_mode_label}"}} 1',
        "# HELP ai_inference_status_requests Number of inference requests by status code",
        "# TYPE ai_inference_status_requests gauge",
        "# HELP ai_inference_model_requests Number of inference requests by model",
        "# TYPE ai_inference_model_requests gauge",
    ]

    for status, request_count in metrics.get("requests_by_status", {}).items():
        status_label = _escape_prometheus_label(status)
        lines.append(
            f'ai_inference_status_requests{{status="{status_label}"}} {request_count}'
        )

    for model_name, model_metrics in metrics["metrics_by_model"].items():
        model_label = _escape_prometheus_label(model_name)
        lines.append(
            f'ai_inference_model_requests{{model="{model_label}"}} {model_metrics["request_count"]}'
        )

    lines.extend(
        [
            "# HELP ai_inference_model_errors Number of failed inference requests by model",
            "# TYPE ai_inference_model_errors gauge",
        ]
    )

    for model_name, model_metrics in metrics["metrics_by_model"].items():
        model_label = _escape_prometheus_label(model_name)
        lines.append(
            f'ai_inference_model_errors{{model="{model_label}"}} {model_metrics["error_count"]}'
        )

    lines.extend(
        [
            "# HELP ai_inference_model_error_rate Error rate by model",
            "# TYPE ai_inference_model_error_rate gauge",
        ]
    )

    for model_name, model_metrics in metrics["metrics_by_model"].items():
        model_label = _escape_prometheus_label(model_name)
        lines.append(
            f'ai_inference_model_error_rate{{model="{model_label}"}} {model_metrics["error_rate"]}'
        )

    lines.extend(
        [
            "# HELP ai_inference_model_p95_latency_ms P95 inference latency by model in milliseconds",
            "# TYPE ai_inference_model_p95_latency_ms gauge",
        ]
    )

    for model_name, model_metrics in metrics["metrics_by_model"].items():
        model_label = _escape_prometheus_label(model_name)
        lines.append(
            f'ai_inference_model_p95_latency_ms{{model="{model_label}"}} {model_metrics["p95_latency_ms"]}'
        )

    lines.extend(build_latency_histogram_prometheus(LOG_PATH))
    return "\n".join(lines) + "\n"