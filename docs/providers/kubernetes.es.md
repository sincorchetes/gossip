# Proveedor Kubernetes Secrets

Implementación de `BaseSecretProvider` para los Secrets de un namespace de un clúster de Kubernetes. Habla con el servidor de la API con la biblioteca estándar de Python y PyYAML, así que no añade ninguna dependencia.

## Conexión

- Los contextos salen de tu kubeconfig: `KUBECONFIG` (varios ficheros se combinan como en `kubectl`) o `~/.kube/config`. Elige contexto y namespace con el botón de la cabecera, o usa `--kube-context` y `--kube-namespace`.
- El diálogo lista los namespaces del contexto elegido para que selecciones uno; si tu usuario no puede listarlos, escribe el nombre.
- Autenticación soportada: token (`token`, `tokenFile`), certificados de cliente y plugins de credenciales (`exec`, usados por EKS, GKE, AKS y ayudantes OIDC). No se admiten `auth-provider` antiguo ni autenticación básica.
- El certificado del clúster siempre se verifica: los contextos con `insecure-skip-tls-verify` se rechazan. Gossip lee las credenciales cuando las necesita y nunca las guarda.

## Cómo se muestran los Secrets

- Un Secret es un mapa de claves. Un objeto JSON de cadenas se guarda como varias claves; cualquier otro texto se guarda bajo `value` y se muestra de vuelta como texto plano. Los valores binarios aparecen como `base64:<datos>` y se escriben de vuelta sin cambios.
- Kubernetes no guarda historial, así que cada Secret tiene una única versión (su `resourceVersion`).
- Crear nunca sobrescribe un Secret existente. Editar conserva su tipo y etiquetas. Borrar elimina el Secret.
- Necesita `get`, `list`, `create`, `update` y `delete` sobre `secrets` en el namespace.

::: src.providers.kubernetes.KubernetesClient
    options:
      show_root_heading: true
      show_source: true
