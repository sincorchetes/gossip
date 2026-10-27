# Gossip Multi-Cloud Secret Manager

Welcome to the official developer documentation for **Gossip**, a modern cross-platform desktop application built with **Python 3.14**, **GTK4**, and **Libadwaita** to explore, inspect, and manage the full lifecycle of secrets across multiple cloud providers and local environments.

---

## Why "Gossip"?

The name is a nod to *Gossip Girl*, the TV series (2007–2012, based on the novels by Cecily von Ziegesar) about an anonymous blogger who knew everyone's secrets and could not keep quiet about them.

This application is the opposite: it also lives among secrets, but it never tells. Values stay hidden until you reveal them, they are dropped from memory after a short while, they are never written to logs or to the state file, and nothing leaves your machine except the request to the provider you chose.

---

## Supported Secret Providers

Gossip implements an extensible **Strategy Pattern** enabling on-the-fly switching between seven secret backends without restarting the application:

| Provider | Backend Service | Context / Scope | Key Capabilities |
| :--- | :--- | :--- | :--- |
| **Google Cloud** | GCP Secret Manager | Project ID (ADC / `gcloud`) | Full versioning, version enabling/disabling, version destroying, replication policy inspection |
| **Amazon Web Services** | AWS Secrets Manager | Profile & Target Region | Version inspection, staging labels (`AWSCURRENT`, `AWSPREVIOUS`), cross-region replication |
| **Microsoft Azure** | Azure Key Vault | Vault URL / Vault Name | Secret lifecycle, version enabling/disabling, content-type descriptions |
| **Ansible Vault** | Encrypted YAML files (AES-256) | Vault file path & password | Local file encryption, automatic `.bak` version snapshots, in-memory variable mutations |
| **AWS Parameter Store** | Systems Manager Parameter Store | Profile & Target Region | Hierarchical parameters, SecureString, version history with labels |
| **HashiCorp Vault / OpenBao** | KV v2 secrets engine (HTTP API) | Server address, mount & token | Path tree, full version history, soft-delete/undelete and destroy of versions, check-and-set creation |
| **Kubernetes** | Secrets of a namespace (API server) | kubeconfig context & namespace | Token, certificate and `exec` plugin authentication, keys as JSON, optimistic update |

---

## Architectural Principles

Gossip is built following senior **Clean Code** and **Clean Architecture** guidelines:

1. **Strategy Pattern & Open-Closed Principle (OCP)**:
   - All secret backend clients inherit from [`BaseSecretProvider`](providers/base.md).
   - Adding a new provider (e.g., 1Password or Bitwarden) requires zero modifications to the UI controllers or window layout.
2. **Single Responsibility Principle (SRP)**:
   - UI dialogs are decoupled into dedicated modules under [`src/ui/dialogs/`](ui/dialogs.md).
   - Domain models are pure dataclasses decoupled from network libraries.
3. **Non-Blocking Asynchronous Concurrency**:
   - Every network and encryption operation is executed in background worker threads, reporting results to the GTK main loop via `GLib.idle_add()`.
4. **Test Coverage Gate**:
   - The codebase is verified by an automated test suite (about 780 tests, about 98% statement and branch coverage) and CI fails below **95%**.

---

## Quick Navigation

- [Installation Guide](getting-started/installation.md)
- [Quickstart & Configuration](getting-started/quickstart.md)
- [Graphical UI Guide](getting-started/gui-guide.md)
- [Security & Privacy](security.md)
- [Architecture & Design Patterns](architecture.md)
- [Providers Reference](providers/index.md)
- [Data Models](api/models.md)
- [Exception Hierarchy](api/exceptions.md)
- [User Interface & Windowing](ui/window.md)
- [Dialogs Subsystem](ui/dialogs.md)
- [Internationalization (i18n)](i18n.md)
- [CI/CD & Releases](cicd.md)
