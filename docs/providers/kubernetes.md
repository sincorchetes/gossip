# Kubernetes Secrets Provider

Implementation of `BaseSecretProvider` for the Secrets of one namespace of a Kubernetes cluster. It talks to the API server with the Python standard library and PyYAML, so it adds no dependency.

## Connecting

- Contexts come from your kubeconfig: `KUBECONFIG` (several files are merged like `kubectl`) or `~/.kube/config`. Choose the context and namespace with the header button, or use `--kube-context` and `--kube-namespace`.
- The dialog lists the namespaces of the chosen context so you can pick one; if your user may not list namespaces, type the name instead.
- Supported authentication: bearer token (`token`, `tokenFile`), client certificates and credential plugins (`exec`, used by EKS, GKE, AKS and OIDC helpers). Legacy `auth-provider` and basic authentication are not supported.
- The cluster certificate is always verified: contexts with `insecure-skip-tls-verify` are refused. Credentials are read when needed and never stored by Gossip.

## How Secrets map to the interface

- A Secret is a map of keys. A JSON object of strings is stored as several keys; any other text is stored under `value` and shown back as plain text. Binary values appear as `base64:<data>` and are written back unchanged.
- Kubernetes keeps no history, so each Secret has a single version (its `resourceVersion`).
- Creating never overwrites an existing Secret. Editing keeps its type and labels. Deleting removes the Secret.
- Needs `get`, `list`, `create`, `update` and `delete` on `secrets` in the namespace.

::: src.providers.kubernetes.KubernetesClient
    options:
      show_root_heading: true
      show_source: true
