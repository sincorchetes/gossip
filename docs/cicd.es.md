# Pipeline CI/CD y Ciclo de Publicaciones

Gossip cuenta con una infraestructura automatizada de testing continuo, control estricto de cobertura y empaquetado multiplataforma.

---

## Arquitectura de la Pipeline

```mermaid
flowchart LR
    subgraph TestStage ["Etapa 1: Tests y Calidad"]
        T1["pytest --cov=src"] --> T2["Puerta de Cobertura > 90%"]
        T2 --> T3["Exportación Cobertura XML y JUnit XML"]
    end

    subgraph BuildStage ["Etapa 2: Compilación Multiplataforma"]
        B1["build:linux (x86_64 tar.gz)"]
        B2["build:windows (x64 zip)"]
        B3["build:macos (universal dmg)"]
    end

    subgraph ReleaseStage ["Etapa 3: Publicación"]
        R1["GitLab Generic Package Registry"]
        R2["release-cli (Release Oficial en GitLab)"]
    end

    TestStage --> BuildStage
    BuildStage --> ReleaseStage
```

---

## Modelo de Ramas: `dev -> pre -> release`

1. **`dev` (Integración Continua)**:
   - Se integran las ramas de desarrollo y Merge Requests.
   - Pasan todos los tests unitarios y se exige el cumplimiento de la cobertura mínima del 90%.
2. **`pre` (Staging / Release Candidate)**:
   - Rama de congelación de código para estabilización y pruebas de regresión.
   - Dispara la compilación preliminar de ejecutables en todas las plataformas soportadas.
3. **`release` / `main` (Tags de Producción)**:
   - Al etiquetar con versión SemVer (`vX.Y.Z`), compila los binarios finales, los sube al registro de paquetes y genera la release oficial en GitLab.
