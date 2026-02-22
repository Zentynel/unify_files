# Unify Files — extractor y unificador de documentos

Una utilidad en Python para identificar documentos en una carpeta, extraer su contenido y unificarlos en un único Markdown y un CSV resumen. Está pensada para preparar datos para ingestión por modelos de lenguaje o para conservar trazabilidad básica de metadatos.

## Principales características

- Detecta y procesa ficheros Word (`.docx`, `.docm`, `.doc`, `.dotx`) y ficheros de texto simples (`.txt`, `.md`, `.markdown`, `.log`).
- Soporte opcional para PDF: extracción de texto y extracción de imágenes incrustadas (cuando se solicita exportar a Markdown).
- Guarda imágenes extraídas desde PDFs en una carpeta de assets y las referencia desde el Markdown generado.
- Prioriza fechas internas (metadatos del documento, p. ej. CreationDate/ModDate del PDF) sobre los timestamps del sistema cuando esos metadatos están disponibles y parseables. El CSV y el Markdown indican la procedencia de cada fecha.
- Conversión automática de `.doc` a `.docx` si está disponible Microsoft Word (COM, Windows) o LibreOffice (`soffice`).
- Salida principal: archivo Markdown unificado (opcional) y un CSV de resultados que incluye trazabilidad y estatus por fichero.

## Comportamiento por defecto

Si no se pasa ninguna de las opciones `--include-*`, el script procesará por defecto Word, texto simple y PDF (si las dependencias necesarias están presentes cuando se exporta MD con PDFs). Esto facilita usar el script sin tener que marcar cada tipo explícitamente.

## Instalación y dependencias

Instala las dependencias mínimas según lo que quieras procesar. Todas son opcionales: el script realizará comprobaciones y pedirá las librerías necesarias solo si vas a procesar esos tipos.

- Recomendado (para `.docx`):

```powershell
pip install python-docx
```

- Para conversión de `.doc` en Windows (opcional, si quieres usar Word COM):

```powershell
pip install pywin32
```

- Para procesar PDFs (extracción de texto e imágenes):

```powershell
pip install pymupdf
```

## Uso y opciones principales

Opciones relevantes (resumen):

- `-d, --dir <carpeta>`: carpeta raíz donde buscar ficheros.
- `--include-word`: incluir ficheros Word en el procesamiento.
- `--include-simple-text`: incluir ficheros de texto simple.
- `--include-pdf`: incluir ficheros PDF (extrae texto e imágenes cuando sea posible).
- `--recursive`: buscar recursivamente en subcarpetas.
- `--export-md <ruta>`: generar un único Markdown unificado en la ruta indicada.
- `--soffice-path <ruta>`: ruta al ejecutable `soffice` si quieres forzar/indicar LibreOffice para conversiones `.doc` → `.docx`.

## Salida y trazabilidad

- Markdown: el fichero unificado contiene un índice y el contenido extraído. Las imágenes extraídas de PDFs se guardan en una carpeta de assets junto al Markdown y se referencian con enlaces relativos. Para Word, por ahora el script inserta marcadores (p. ej. [imagen]) donde hay imágenes incrustadas; la extracción física de imágenes desde `.docx` puede habilitarse/implementarse posteriormente.
- CSV: se genera un CSV con una fila por documento (y filas adicionales para imágenes extraídas) con, entre otras, estas columnas:

  - `file`: ruta relativa o absoluta del fichero origen
  - `status`: `ok`, `error` o `image` (si la fila describe una imagen extraída)
  - `message`: texto con información adicional o el error
  - `created_meta`: fecha de creación tomada de metadatos internos (si disponible)
  - `created_fs`: fecha de creación del sistema de ficheros (fallback)
  - `modified_meta`: fecha de modificación tomada de metadatos internos (si disponible)
  - `modified_fs`: fecha de modificación del sistema de ficheros (fallback)

  El CSV ayuda a trazar si las fechas provienen de metadatos del documento o del sistema de ficheros.

## Ejemplos (PowerShell)

Procesar una carpeta y generar Markdown unificado:

```powershell
python unify_files.py -d "C:\ruta\a\carpeta" --export-md unified.md
```

Incluir solo Word y texto simple:

```powershell
python unify_files.py -d "C:\ruta\a\carpeta" --include-word --include-simple-text --export-md unified.md
```

Incluir PDFs (asegúrate de instalar pymupdf si quieres extraer texto/imagenes):

```powershell
python unify_files.py -d "C:\ruta\a\carpeta" --include-pdf --export-md unified.md
```

## Notas y consideraciones

- Extracción de imágenes desde PDFs: las imágenes se escriben en una carpeta de assets con un nombre derivado del Markdown (p. ej. `unified_assets/`) y el Markdown contiene referencias relativas.
- Extracción de imágenes desde `.docx`: actualmente el script inserta marcadores en el Markdown donde había imágenes; se puede mejorar para extraer las imágenes físicamente y unificarlas con el mismo patrón de assets.
- Conversiones `.doc` → `.docx`: el script usará Microsoft Word (COM) en Windows si está disponible, o `soffice` (LibreOffice) si el ejecutable está presente y se indica su ruta/está en PATH.
- Empaquetado en Windows: hay un script `build.ps1` que usa PyInstaller para generar un .exe. Revisa y ajusta el `spec` si añades dependencias nativas.

## Problemas comunes

- Si intentas exportar PDFs a Markdown sin tener `pymupdf` instalado, el script abortará con un mensaje indicando que instales la dependencia o que no incluyas PDFs.
- Si alguna conversión `.doc` falla, revisa que Word/LibreOffice estén presentes y que la ruta proporcionada en `--soffice-path` sea correcta.

## Contribuciones y mejoras previstas

- Extraer y guardar imágenes de `.docx` a la misma carpeta de assets que los PDFs.
- Añadir un flag `--extract-images` para controlar explícitamente la extracción física de imágenes (actualmente las de PDF se extraen cuando se exporta MD).
- Añadir tests unitarios y un pequeño conjunto de fixtures para validar el flujo end-to-end.

## Licencia

Este proyecto es de uso personal/experimental. Si lo quieres usar en producción, revisa y prueba con tus documentos y añade tests según tus necesidades.

---

Si quieres que ajuste el README con instrucciones de build detalladas para PyInstaller o ejemplos más avanzados, dime qué formato prefieres y lo añado.
# Unify Files — extractor y unificador de documentos

Este repositorio contiene una utilidad en Python para identificar documentos en una carpeta, extraer su contenido y unificarlos en un único Markdown para facilitar su ingestión por una IA.

Características actuales:

- Detección recursiva de ficheros Word (`.docx`, `.docm`, `.doc`, `.dotx`).
- Soporte para ficheros de texto simples (`.txt`, `.md`, `.markdown`, `.log`).
- Opción `--include-word` para incluir ficheros Word en el procesamiento.
- Opción `--include-simple-text` para incluir ficheros de texto simple en la exportación Markdown.
- Si no se especifica ninguna de las opciones anteriores, el comportamiento por defecto es procesar todos los tipos soportados (Word + texto simple).
- Opción `--export-md <ruta>` para generar un Markdown unificado con índice, metadatos y contenido extraído.
- Conversión automática de `.doc` a `.docx` si está disponible Microsoft Word (pywin32) o LibreOffice (`soffice`).
- Pre-check al inicio: el script valida que las herramientas necesarias (python-docx, conversores) estén disponibles solo si se van a procesar ficheros Word, y aborta con mensajes claros si falta algo.

Requisitos y dependencias (opcionales según uso):

- `python-docx` — extracción de `.docx` (instálalo si vas a exportar MD con contenido de Word):

```powershell
pip install python-docx
```

- `pywin32` — (opcional en Windows) para usar Microsoft Word COM y convertir `.doc` a `.docx`:

```powershell
python -m pip install -r requirements.txt
```


```powershell
python unify_files.py

3) Ejecutar incluyendo solo Word:

```powershell
python unify_files.py -d C:\ruta\a\carpeta --include-word --export-md unified.md
4) Ejecutar incluyendo solo ficheros de texto simple:

