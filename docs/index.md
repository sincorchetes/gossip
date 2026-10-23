# Gossip Multi-Cloud Secret Manager

Welcome to the official developer documentation for **Gossip**, a modern cross-platform desktop application built with **Python 3.13**, **GTK4**, and **Libadwaita** to explore, inspect, and manage the full lifecycle of secrets across multiple cloud providers and local environments.

---

## Supported Secret Providers

Gossip implements an extensible **Strategy Pattern** enabling on-the-fly switching between four major secret backends without restarting the application:

| Provider | Backend Service | Context / Scope | Key Capabilities |
| :--- | :--- | :--- | :--- |
| **Google Cloud** | GCP Secret Manager | Project ID (ADC / `gcloud`) | Full versioning, version enabling/disabling, version destroying, replication policy inspection |
| **Amazon Web Services** | AWS Secrets Manager | Profile & Target Region | Version inspection, staging labels (`AWSCURRENT`, `AWSPREVIOUS`), cross-region replication |
| **Microsoft Azure** | Azure Key Vault | Vault URL / Vault Name | Secret lifecycle, version enabling/disabling, content-type descriptions |
| **Ansible Vault** | Encrypted YAML files (AES-256) | Vault file path & password | Local file encryption, automatic `.bak` version snapshots, in-memory variable mutations |

---

## Architectural Principles

Gossip is built following senior **Clean Code** and **Clean Architecture** guidelines:

1. **Strategy Pattern & Open-Closed Principle (OCP)**:
   - All secret backend clients inherit from [`BaseSecretProvider`](providers/base.md).
   - Adding a new provider (e.g., HashiCorp Vault, Kubernetes Secrets) requires zero modifications to the UI controllers or window layout.
2. **Single Responsibility Principle (SRP)**:
   - UI dialogs are decoupled into dedicated modules under [`src/ui/dialogs/`](ui/dialogs.md).
   - Domain models are pure dataclasses decoupled from network libraries.
3. **Non-Blocking Asynchronous Concurrency**:
   - Every network and encryption operation is executed in background worker threads, reporting results to the GTK main loop via `GLib.idle_add()`. The UI maintains 60 FPS under all circumstances.
4. **100% Test Coverage Gate**:
   - The entire codebase is verified by 187 automated tests maintaining **100.00% statement and branch coverage**.

---

## Quick Navigation

- [Installation Guide](getting-started/installation.md)
- [Quickstart & Configuration](getting-started/quickstart.md)
- [Graphical UI Guide](getting-started/gui-guide.md)
- [Architecture & Design Patterns](architecture.md)
- [Providers Reference](providers/index.md)
- [Data Models](api/models.md)
- [Exception Hierarchy](api/exceptions.md)
- [User Interface & Windowing](ui/window.md)
- [Dialogs Subsystem](ui/dialogs.md)
- [Internationalization (i18n)](i18n.md)
- [CI/CD & Releases](cicd.md)
