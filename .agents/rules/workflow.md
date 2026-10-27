# Reglas de flujo de trabajo tras completar cambios

`main` está protegida: no se hace push directo. Cada cambio entra por una rama corta y un pull request, y las publicaciones se hacen con tags `v*`.

Siempre que se terminen de implementar cambios en el proyecto, seguir rigurosamente este ciclo completo:

1. **Rama**:
   - Trabajar en una rama corta creada desde `main` actualizada: `git switch -c <tipo>/<descripcion>` (`feat/`, `fix/`, `ci/`, `docs/`...).
2. **Preformateo**:
   - Ejecutar el formateador y linter: `devenv shell "ruff format && ruff check --fix"`.
3. **Generar tests**:
   - Ejecutar la suite completa y compuerta de cobertura: `devenv test`.
4. **Commit**:
   - Crear el commit con mensaje convencional (`feat:`, `fix:`, `perf:`, `ci:`, etc.).
5. **Push y pull request**:
   - Subir la rama: `git push -u origin <rama>`.
   - Abrir el PR hacia `main` (`gh pr create`) y esperar a que pasen los checks requeridos (`Run Pytest & Coverage Gate`, `CodeQL`, `Secret scan`).
   - Fusionar con *squash* y borrar la rama.
6. **Tag versión n+** (solo cuando haya que publicar):
   - Actualizar `main` y obtener la última versión (`git tag -l "v*" --sort=-v:refname | head -n 1`).
   - Crear el tag siguiente `v0.0.<n+1>` y subirlo a origin: `git tag v0.0.<n+1> && git push origin v0.0.<n+1>`. Los tags `v*` no se pueden mover ni borrar.
   - Para probar el empaquetado sin publicar, lanzar a mano el workflow *Release* (Run workflow) sobre `main`.
