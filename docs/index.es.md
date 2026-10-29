# Gossip: Gestor Multi-Cloud de Secretos

Bienvenido a la documentación oficial para desarrolladores de **Gossip**, una aplicación de escritorio moderna desarrollada con **Python 3.14**, **GTK4** y **Libadwaita** para explorar, inspeccionar y administrar el ciclo de vida completo de secretos en múltiples proveedores de nube y entornos locales.

---

## ¿Por qué «Gossip»?

El nombre es un guiño a *Gossip Girl*, la serie de televisión (2007–2012, basada en las novelas de Cecily von Ziegesar) sobre una bloguera anónima que conocía los secretos de todo el mundo y no sabía guardárselos.

Esta aplicación es lo contrario: también vive entre secretos, pero nunca los cuenta. Los valores permanecen ocultos hasta que los reveles, desaparecen de la memoria pasado un rato, no se escriben jamás en los registros ni en el archivo de estado, y nada sale de tu equipo salvo la petición al proveedor que elegiste.

---

## Proveedores de Secretos Soportados

Gossip implementa un **Patrón Estrategia (Strategy Pattern)** extensible que permite alternar en caliente entre siete backends de secretos sin necesidad de reiniciar la aplicación:

| Proveedor | Servicio Backend | Contexto / Ámbito | Capacidades Clave |
| :--- | :--- | :--- | :--- |
| **Google Cloud** | GCP Secret Manager | ID de Proyecto (ADC / `gcloud`) | Versionado completo, activación/desactivación de versiones, destrucción permanente, inspección de políticas de replicación |
| **Amazon Web Services** | AWS Secrets Manager | Perfil y Región Destino | Inspección de versiones, etiquetas de rotación (`AWSCURRENT`, `AWSPREVIOUS`), replicación multi-región |
| **Microsoft Azure** | Azure Key Vault | URL / Nombre del Almacén | Ciclo de vida del secreto, activación/desactivación de versiones, descripción y tipos de contenido |
| **Ansible Vault** | Archivos YAML cifrados (AES-256) | Ruta del archivo y contraseña | Cifrado de archivos locales, copias de seguridad automáticas (`.bak`), mutaciones en memoria de variables |
| **AWS Parameter Store** | Systems Manager Parameter Store | Perfil y región | Parámetros jerárquicos, SecureString, historial de versiones con etiquetas |
| **HashiCorp Vault / OpenBao** | Motor de secretos KV v2 (API HTTP) | Dirección, montaje y token | Árbol de rutas, historial completo de versiones, deshabilitar/rehabilitar y destruir versiones, creación con check-and-set |
| **Kubernetes** | Secrets de un namespace (servidor de la API) | Contexto de kubeconfig y namespace | Autenticación por token, certificado y plugin `exec`, claves en JSON, actualización optimista |

---

## Principios de Arquitectura

Gossip se ha construido siguiendo directrices de **Clean Code** y **Clean Architecture**:

1. **Patrón Estrategia y Principio Abierto-Cerrado (OCP)**:
   - Todos los clientes de proveedores heredan de [`BaseSecretProvider`](providers/base.md).
   - Añadir un nuevo proveedor (ej. 1Password o Bitwarden) requiere cero modificaciones en los controladores de interfaz o la ventana.
2. **Principio de Responsabilidad Única (SRP)**:
   - Los diálogos están desacoplados en módulos especializados dentro de [`src/ui/dialogs/`](ui/dialogs.md).
   - Los modelos de dominio son dataclasses puros desacoplados de librerías de red.
3. **Concurrencia Asíncrona No Bloqueante**:
   - Cada operación de red y criptografía se ejecuta en hilos secundarios en segundo plano mediante `threading.Thread(daemon=True)`, comunicando los resultados al hilo principal de GTK a través de `GLib.idle_add()`.
4. **Puerta de Cobertura de Tests**:
   - La base de código cuenta con una batería de tests automatizados (más de 800, con cobertura completa de declaraciones y ramas) y la CI falla por debajo del **100%**.

---

## Navegación Rápida

- [Guía de Instalación](getting-started/installation.md)
- [Guía Rápida y Configuración](getting-started/quickstart.md)
- [Guía de la Interfaz Gráfica](getting-started/gui-guide.md)
- [Seguridad y Privacidad](security.md)
- [Arquitectura y Patrones de Diseño](architecture.md)
- [Referencia de Proveedores](providers/index.md)
- [Modelos de Datos](api/models.md)
- [Jerarquía de Excepciones](api/exceptions.md)
- [Interfaz de Usuario y Ventana Principal](ui/window.md)
- [Subsistema de Diálogos](ui/dialogs.md)
- [Internacionalización (i18n)](i18n.md)
- [CI/CD y Publicaciones](cicd.md)
