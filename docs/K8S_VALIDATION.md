# Kubernetes Validation

This document records a local Kubernetes validation workflow for the example manifests in `k8s/`.

The validation uses minikube with the mock backend. It verifies that the API Deployment, Service, PVC, runtime environment overrides, mock backend Service, port-forwarding, and smoke test path work together. It is not production cluster evidence.

## Environment

Recorded validation environment:

- Kubernetes environment: minikube
- minikube version: v1.38.1
- Kubernetes client: v1.35.2
- Docker server: 29.0.1
- Default API image: `ghcr.io/tewbb66/ai-metrics-api:latest`
- Local validation image override: locally built `ai-metrics-api:ci`
- API backend mode: `mock`
- API replicas: 1

## Start minikube

    minikube start --driver=docker
    kubectl cluster-info
    kubectl get nodes

## Build and Load the API Image

    docker build -t ai-metrics-api:ci .
    minikube image load ai-metrics-api:ci

## Apply API Manifests

    kubectl create namespace ai-infra-learning --dry-run=client -o yaml | kubectl apply -f -

    kubectl apply -n ai-infra-learning -f k8s/configmap.yaml
    kubectl apply -n ai-infra-learning -f k8s/secret.example.yaml
    kubectl apply -n ai-infra-learning -f k8s/persistent-volume-claim.yaml
    kubectl apply -n ai-infra-learning -f k8s/deployment.yaml
    kubectl apply -n ai-infra-learning -f k8s/service.yaml

    kubectl set image -n ai-infra-learning deployment/ai-metrics-api ai-metrics-api=ai-metrics-api:ci

The committed Deployment points at the GHCR image. This local workflow overrides it with the image loaded into minikube so the validation remains self-contained.

## Add a Mock Backend for Local Cluster Smoke Tests

The example ConfigMap defaults to a vLLM backend endpoint. For a local minikube smoke test without a vLLM service, run a mock backend Deployment and Service in the same namespace.

    kubectl create deployment mock-model-server \
      -n ai-infra-learning \
      --image=ai-metrics-api:ci \
      --dry-run=client -o yaml \
      -- python -m uvicorn projects.mock_model_server.main:app --host 0.0.0.0 --port 8001 \
      | kubectl apply -f -

    kubectl expose deployment mock-model-server \
      -n ai-infra-learning \
      --port=8001 \
      --target-port=8001 \
      --dry-run=client -o yaml \
      | kubectl apply -f -

    kubectl set env -n ai-infra-learning deployment/ai-metrics-api \
      MODEL_BACKEND=mock \
      MOCK_MODEL_SERVER_URL=http://mock-model-server:8001/generate \
      READINESS_CHECK_BACKEND=false \
      REQUIRE_API_KEY=false \
      LOG_BACKEND=file \
      INFERENCE_LOG_PATH=/app/data/day02/k8s-smoke.log

## Wait for Rollout

    kubectl rollout status -n ai-infra-learning deployment/mock-model-server --timeout=120s
    kubectl rollout status -n ai-infra-learning deployment/ai-metrics-api --timeout=120s

    kubectl get pods -n ai-infra-learning -o wide
    kubectl get svc -n ai-infra-learning

## Run the Smoke Test

    kubectl port-forward -n ai-infra-learning svc/ai-metrics-api 18000:8000 >/tmp/ai-metrics-api-port-forward.log 2>&1 &
    PF_PID=$!

    sleep 3

    python scripts/local_smoke_test.py --base-url http://127.0.0.1:18000
    SMOKE_EXIT=$?

    kill "$PF_PID" 2>/dev/null || true

    echo "smoke exit code: $SMOKE_EXIT"

Expected smoke test output:

    OK /health
    OK /ready backend=mock
    OK /v1/infer request_id=...
    OK /metrics/logs
    OK /metrics/prometheus
    Local smoke test passed
    smoke exit code: 0

## Cleanup

    kubectl delete namespace ai-infra-learning

## Boundary

This workflow validates the example Kubernetes manifests in a local minikube cluster with a mock backend. It does not validate a production Kubernetes cluster, GPU scheduling, a vLLM in-cluster Deployment, autoscaling, ServiceMonitor integration, or external durable storage.
