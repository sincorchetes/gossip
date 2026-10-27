# Proveedor Ansible Vault

Implementación de `BaseSecretProvider` para archivos YAML locales cifrados con Ansible Vault utilizando `ansible-vault` y `PyYAML`.

## Notas de comportamiento

- **El historial de versiones conserva los últimos 5 guardados.** Un archivo de vault no tiene historial nativo. Antes de cada guardado Gossip rota copias junto al vault: `<vault>.bak` (el estado previo al último guardado), `<vault>.bak.2`, ... hasta `<vault>.bak.5`; las más antiguas se descartan. La lista de versiones muestra *Actual* y *Anterior* y *Copia 2*-*5* de las copias en las que la variable ya existía. Si necesitas más historial, mantén el vault bajo control de versiones (por ejemplo git).
- **Tipos de valor.** Los diccionarios y las listas se conservan como YAML estructurado; los valores escalares se leen como texto. Un valor con forma de JSON (`{...}` o `[...]`) se guarda como estructura. Los archivos de exportación llevan diccionarios, listas, números y booleanos como valores JSON nativos, y la importación restaura su tipo.
- **Contraseñas.** La contraseña se escribe en el diálogo de desbloqueo o se lee de un archivo privado que declares (`--ansible-password-file` o `ANSIBLE_VAULT_PASSWORD_FILE`). Nunca se lee del entorno, y se elimina de la memoria cuando salta el bloqueo por inactividad.

::: src.providers.ansible.AnsibleVaultClient
    options:
      show_root_heading: true
      show_source: true
