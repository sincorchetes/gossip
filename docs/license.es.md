# Licencia y software de terceros

## Gossip

Gossip es software libre bajo la **Licencia Pública General de GNU, versión 3 o (a tu elección) cualquier versión posterior** (SPDX: `GPL-3.0-or-later`). Copyright © 2026 Álvaro Castillo; el asistente de programación con IA que ayudó a escribirlo figura como colaborador en `AUTHORS.md`. El texto completo está en [`LICENSE`](https://github.com/sincorchetes/gossip/blob/main/LICENSE).

## Software de terceros

Gossip se apoya en software de código abierto que sus paquetes incluyen, cada uno bajo su propia licencia:

| Grupo | Ejemplos | Licencias habituales |
|---|---|---|
| Plataforma GNOME | GTK 4, libadwaita, GLib, Pango, GdkPixbuf, librsvg, PyGObject | LGPL-2.1-or-later |
| SDK de nube | boto3, Google Cloud Secret Manager, gRPC, Azure SDK | Apache-2.0, MIT |
| Ansible | `ansible-core`, `ansible-vault` | GPL-3.0-or-later |
| Criptografía y utilidades | cryptography, PyYAML, requests, certifi | Apache-2.0 o BSD, MIT, MPL-2.0 |
| Entorno de ejecución | Python, OpenSSL, el *bootloader* de PyInstaller | PSF-2.0, Apache-2.0, GPL-2.0-or-later con excepción del bootloader |

La lista completa y generada (nombres, versiones fijadas, licencias, URL de cada proyecto y todos los textos de licencia) está en [`THIRD_PARTY_NOTICES.md`](https://github.com/sincorchetes/gossip/blob/main/THIRD_PARTY_NOTICES.md). También se muestra, resumida, en el diálogo **Acerca de** de la aplicación.

## Dónde están las licencias en cada paquete

| Paquete | Ubicación |
|---|---|
| Linux `.tar.gz` | `gossip/LICENSE`, `gossip/THIRD_PARTY_NOTICES.md`, `gossip/licenses/system/` |
| Linux `.deb` / `.rpm` | `/opt/gossip/` (misma estructura), `/usr/share/doc/gossip/copyright`, `/usr/share/licenses/gossip/` |
| Windows `.zip` / `.msi` | junto a `gossip.exe`: `LICENSE`, `THIRD_PARTY_NOTICES.md`, `licenses\msys2\` |
| macOS `.dmg` / `.tar.gz` | `gossip.app/Contents/Resources/` (`LICENSE`, `THIRD_PARTY_NOTICES.md`, `licenses/`) |

`licenses/` contiene los ficheros de licencia de las bibliotecas C que realmente se incluyeron en ese paquete (copiados de los paquetes de Debian, MSYS2 o Homebrew de los que proceden).

## Sustituir bibliotecas LGPL

Las bibliotecas bajo LGPL (GTK, GLib, Pango, ...) se distribuyen como bibliotecas compartidas independientes, no enlazadas estáticamente, así que puedes sustituirlas por tu propia compilación de la misma versión. Su código fuente está disponible en las páginas de proyecto que figuran en los avisos.

## Contribuir

Las contribuciones se aceptan bajo la misma licencia (GPL-3.0-or-later). No añadas código que solo esté disponible bajo GPL-2.0-only ni bajo una licencia que no se pueda combinar con GPL-3.0.

## Regenerar los avisos

`THIRD_PARTY_NOTICES.md` se genera a partir de los locks con hashes mediante `python scripts/generate_third_party_notices.py`; el workflow semanal de dependencias lo hace automáticamente y un test falla si falta algún paquete bloqueado en el archivo.
