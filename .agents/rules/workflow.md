# Reglas de flujo de trabajo tras completar cambios

Siempre que se terminen de implementar cambios en el proyecto, seguir rigurosamente este ciclo completo:

1. **Preformateo**:
   - Ejecutar el formateador y linter: `devenv shell "ruff format && ruff check --fix"`.
2. **Generar tests**:
   - Ejecutar la suite completa y compuerta de cobertura: `devenv test`.
3. **Commit**:
   - Crear el commit con mensaje convencional (`feat:`, `fix:`, `perf:`, `ci:`, etc.).
4. **Push**:
   - Subir los commits a la rama remota: `git push origin <branch>`.
5. **Tag versión n+**:
   - Obtener la última versión (`git tag -l "v*" --sort=-v:refname | head -n 1`).
   - Crear el tag siguiente `v0.3.<n+1>` y subirlo a origin: `git tag v0.3.<n+1> && git push origin v0.3.<n+1>`.
