# AWS Systems Manager Parameter Store Provider

Implementation of `BaseSecretProvider` for AWS Systems Manager Parameter Store using `boto3`. It shares the AWS profile and region selection with the [Secrets Manager provider](aws.md).

- Parameters are listed with their full path (`/app/prod/db`) and type (`String`, `StringList`, `SecureString`).
- New parameters are created as encrypted `SecureString` and never overwrite an existing one.
- Writing to an existing parameter creates a new version and keeps its type. The history shows every version with its labels; the latest is marked as current.
- Values of `SecureString` parameters are decrypted on demand. Deleting a parameter removes its whole history.
- Requires `ssm:DescribeParameters`, `ssm:GetParameter`, `ssm:GetParameterHistory`, `ssm:PutParameter`, `ssm:DeleteParameter` (and `kms:Decrypt` for custom keys).

::: src.providers.ssm.SSMClient
    options:
      show_root_heading: true
      show_source: true
