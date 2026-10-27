# Proveedor HashiCorp Vault / OpenBao

Implementación de `BaseSecretProvider` para servidores [HashiCorp Vault](https://www.vaultproject.io/) y [OpenBao](https://openbao.org/) con el motor de secretos **KV versión 2**. Usa la API HTTP con la biblioteca estándar de Python, así que no añade ninguna dependencia.

## Conexión

| Ajuste | Campo del diálogo | Entorno | CLI |
| :--- | :--- | :--- | :--- |
| Dirección del servidor | Dirección del servidor | `VAULT_ADDR` / `BAO_ADDR` | `--vault-addr` |
| Montaje KV v2 (por defecto `secret`) | Montaje KV v2 | | `--vault-mount` |
| Namespace | Namespace | `VAULT_NAMESPACE` / `BAO_NAMESPACE` | |
| Token | Token | `VAULT_TOKEN` / `BAO_TOKEN`, luego `~/.vault-token` | |
| CA personalizada | | `VAULT_CACERT` / `BAO_CACERT` | |

- El token escrito en el diálogo solo vive en memoria y se descarta cuando salta el bloqueo por inactividad.
- El token viaja en una cabecera, por eso se rechazan las direcciones `http://` salvo `localhost`. No se puede desactivar la verificación del certificado.

## Cómo se muestran los secretos

- Los secretos se listan de forma recursiva (hasta 8 carpetas de profundidad y 5000 secretos); el nombre es su ruta, por ejemplo `app/prod/db`.
- Un secreto KV es un mapa de claves. Un objeto JSON escrito en el editor se guarda como varias claves; cualquier otro texto se guarda bajo la clave `value` y se muestra de vuelta como texto plano.
- Cada escritura crea una versión nueva. Las versiones anteriores se pueden leer, comparar, deshabilitar (borrado lógico, reversible) y destruir de forma permanente.
- Crear un secreto nunca sobrescribe uno existente (check-and-set).
- Borrar un secreto elimina sus metadatos y todas sus versiones.

::: src.providers.vault.VaultClient
    options:
      show_root_heading: true
      show_source: true
