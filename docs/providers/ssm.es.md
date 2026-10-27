# Proveedor AWS Systems Manager Parameter Store

Implementación de `BaseSecretProvider` para AWS Systems Manager Parameter Store con `boto3`. Comparte la selección de perfil y región de AWS con el [proveedor de Secrets Manager](aws.md).

- Los parámetros se listan con su ruta completa (`/app/prod/db`) y su tipo (`String`, `StringList`, `SecureString`).
- Los parámetros nuevos se crean como `SecureString` cifrado y nunca sobrescriben uno existente.
- Escribir en un parámetro existente crea una versión nueva y conserva su tipo. El historial muestra cada versión con sus etiquetas; la última aparece como actual.
- Los valores `SecureString` se descifran bajo demanda. Borrar un parámetro elimina todo su historial.
- Requiere `ssm:DescribeParameters`, `ssm:GetParameter`, `ssm:GetParameterHistory`, `ssm:PutParameter`, `ssm:DeleteParameter` (y `kms:Decrypt` con claves propias).

::: src.providers.ssm.SSMClient
    options:
      show_root_heading: true
      show_source: true
