# Kubernetes manifests (scaffold)

Kustomize layout for future cloud deployment. **Nothing here is production
ready yet** — Phase 0 only scaffolds the structure. Manifests are wired in
Phase 4+ once the services are actually running.

```
deploy/k8s/
├── base/                 # Kustomize base (no cluster-specific values)
│   ├── kustomization.yaml
│   ├── namespace.yaml
│   ├── configmap.yaml
│   ├── postgres/
│   ├── redis/
│   ├── kafka/
│   ├── gateway-service/
│   ├── auth-service/
│   ├── registry-service/
│   ├── metrics-collector/
│   ├── analytics-service/
│   ├── dashboard-service/
│   └── ml-service/
└── overlays/
    ├── local/            # kind / minikube
    ├── staging/
    └── prod/
```

## Apply (once populated)

```bash
kubectl apply -k deploy/k8s/overlays/local
```

## Secrets

Real secret material (JWT keys, DB passwords, Kafka SASL creds) lives in
external secret managers (Vault, cloud KMS, or SealedSecrets). Never commit
`secrets.yaml` — the root `.gitignore` blocks it.
