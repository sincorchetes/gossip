# CI/CD Pipeline & Release Workflow

Gossip integrates automated continuous testing, coverage enforcement, and multi-platform distribution.

---

## Pipeline Architecture

```mermaid
flowchart LR
    subgraph TestStage ["Stage 1: Test and Quality"]
        T1["pytest --cov=src"] --> T2["100% Coverage Gate (> 90%)"]
        T2 --> T3["Export Cobertura XML and JUnit XML"]
    end

    subgraph BuildStage ["Stage 2: Multi-Platform Build"]
        B1["build:linux (x86_64 tar.gz)"]
        B2["build:windows (x64 zip)"]
        B3["build:macos (universal dmg)"]
    end

    subgraph ReleaseStage ["Stage 3: Publish Release"]
        R1["GitLab Generic Package Registry"]
        R2["release-cli (Automated GitLab Release)"]
    end

    TestStage --> BuildStage
    BuildStage --> ReleaseStage
```

---

## Branching Model: `dev -> pre -> release`

1. **`dev` (Continuous Integration)**:
   - Feature branches merge into `dev`.
   - Runs unit tests and verifies code coverage with a strict 90% threshold.
2. **`pre` (Staging / Release Candidate)**:
   - Code freeze branch for stabilization and integration testing.
   - Triggers preliminary packaging builds across all target operating systems.
3. **`release` / `main` (Production Tags)**:
   - Tagging a commit with SemVer (`vX.Y.Z`) triggers production compilation, uploads binaries to the package registry, and generates the official Release.
