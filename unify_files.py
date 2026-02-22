
"""Unify-files - script inicial

Este archivo es el punto de partida. Hace un "Hola mundo" y pide
por consola (o por argumento) un directorio a inspeccionar. Más adelante
añadiremos el procesamiento de ficheros dentro de la carpeta y subcarpetas.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys
from typing import Optional, Tuple
from datetime import datetime
import os
import shutil
import subprocess
import tempfile
from typing import Optional

# Si el usuario provee una ruta a soffice vía flag o variable de entorno, la almacenamos aquí
SOFFICE_PATH_OVERRIDE: Optional[str] = None

try:
	from docx import Document  # type: ignore
except Exception:  # pragma: no cover - docx optional at import time
	Document = None

try:
    import fitz  # PyMuPDF for PDF text and image extraction
except Exception:  # pragma: no cover - optional dependency
    fitz = None


def slugify(text: str) -> str:
	"""Crear un slug seguro para anchors Markdown/HTML."""
	import re

	s = text.strip().lower()
	# reemplazar espacios por guiones
	s = re.sub(r"\s+", "-", s)
	# eliminar caracteres que no sean alfanuméricos, guion o underscore
	s = re.sub(r"[^a-z0-9\-_]", "", s)
	# evitar slug vacío
	return s or "section"


def convert_doc_to_docx(doc_path: Path) -> Path | None:
	"""Intenta convertir un .doc (binario) a .docx usando Word COM (Windows) o LibreOffice.

	Retorna la Path del .docx convertido dentro de un directorio temporal, o None si la conversión no es posible.
	"""
	# On Windows, prefer using Word via COM automation (if available)
	if os.name == "nt":
		try:
			import win32com.client  # type: ignore
		except Exception:
			win32com = None
		else:
			win32com = win32com.client

		if win32com is not None:
			tmpdir = Path(tempfile.mkdtemp(prefix="doc_convert_"))
			out_path = tmpdir / (doc_path.stem + ".docx")
			app = None
			try:
				app = win32com.Dispatch("Word.Application")
				app.Visible = False
				app.DisplayAlerts = 0
				doc = app.Documents.Open(str(doc_path))
				# FileFormat=12 corresponde a wdFormatXMLDocument (.docx)
				doc.SaveAs(str(out_path), FileFormat=12)
				doc.Close()
				return out_path
			except Exception:
				try:
					if app is not None:
						app.Quit()
				except Exception:
					pass
				try:
					shutil.rmtree(tmpdir)
				except Exception:
					pass
				# Fall through to LibreOffice option

	# Determinar ruta a soffice: prioridad (1) override CLI/env, (2) PATH, (3) rutas comunes de instalación
	soffice = None
	if SOFFICE_PATH_OVERRIDE:
		candidate = Path(SOFFICE_PATH_OVERRIDE)
		if candidate.is_file():
			soffice = str(candidate)

	if not soffice:
		soffice = shutil.which("soffice") or shutil.which("soffice.exe")

	if not soffice:
		# Comprobar rutas típicas en Windows
		common = [
			r"C:\Program Files\LibreOffice\program\soffice.exe",
			r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
			r"C:\Program Files\LibreOffice 7\program\soffice.exe",
		]
		for c in common:
			if Path(c).is_file():
				soffice = c
				break

	if not soffice:
		return None

	tmpdir = Path(tempfile.mkdtemp(prefix="doc_convert_"))
	try:
		# LibreOffice convierte a la carpeta de salida especificada
		cmd = [soffice, "--headless", "--convert-to", "docx", str(doc_path), "--outdir", str(tmpdir)]
		proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
		if proc.returncode != 0:
			try:
				shutil.rmtree(tmpdir)
			except Exception:
				pass
			return None

		# Buscar el fichero .docx generado
		converted = None
		for f in tmpdir.iterdir():
			if f.suffix.lower() == ".docx":
				converted = f
				break
		return converted
	except Exception:
		try:
			shutil.rmtree(tmpdir)
		except Exception:
			pass
		return None


def check_word_com_available() -> bool:
	"""Comprueba si la automatización COM de Microsoft Word está disponible."""
	if os.name != "nt":
		return False
	try:
		import win32com.client  # type: ignore
		return True
	except Exception:
		return False


def find_soffice_executable() -> Optional[str]:
	"""Devuelve la ruta a soffice si está disponible (override, PATH o rutas comunes)."""
	if SOFFICE_PATH_OVERRIDE:
		candidate = Path(SOFFICE_PATH_OVERRIDE)
		if candidate.is_file():
			return str(candidate)

	soffice = shutil.which("soffice") or shutil.which("soffice.exe")
	if soffice:
		return soffice

	common = [
		r"C:\Program Files\LibreOffice\program\soffice.exe",
		r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
		r"C:\Program Files\LibreOffice 7\program\soffice.exe",
	]
	for c in common:
		if Path(c).is_file():
			return c
	return None


def pre_check(directory: Path, args, include_word: bool, include_text: bool, include_pdf: bool, recursive: bool) -> tuple[bool, str]:
	"""Comprueba que las herramientas necesarias están disponibles antes de procesar.

	Retorna (ok: bool, message: str).
	Solo valida herramientas relacionadas con Word si include_word es True.
	"""
	msgs: list[str] = []

	# Si se pedirá procesamiento de Word y se pidió exportar a MD, python-docx es necesario
	if include_word and args.export_md and Document is None:
		msgs.append("Falta 'python-docx' (necesario para extraer contenido de .docx). Instálalo con: pip install python-docx")

	# Buscar ficheros Word/PDF solo si vamos a procesarlos
	def is_word_file(p: Path) -> bool:
		return p.suffix.lower() in {".docx", ".docm", ".doc", ".dotx"}

	def is_pdf_file(p: Path) -> bool:
		return p.suffix.lower() == ".pdf"

	glob_func = directory.rglob if recursive else directory.glob
	word_files = [p for p in glob_func("*") if p.is_file() and is_word_file(p)] if include_word else []
	pdf_files = [p for p in glob_func("*") if p.is_file() and is_pdf_file(p)] if include_pdf else []

	# Si hay .doc, confirmar que tenemos un convertidor disponible
	has_doc = any(p.suffix.lower() == ".doc" for p in word_files)
	has_docx = any(p.suffix.lower() == ".docx" for p in word_files)

	# Si hay PDFs y se va a exportar a MD, comprobar que PyMuPDF está disponible
	has_pdf = any(p.suffix.lower() == ".pdf" for p in pdf_files)

	if include_word and has_doc:
		soffice = find_soffice_executable()
		word_com = check_word_com_available()
		# Si encontramos soffice, comprobar que es ejecutable y responde a --version
		if soffice:
			try:
				proc = subprocess.run([soffice, "--version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False, text=True, timeout=8)
				if proc.returncode != 0:
					# soffice existe pero falló al ejecutarse
					msgs.append(f"Se encontró 'soffice' en '{soffice}' pero al ejecutar 'soffice --version' devolvió código {proc.returncode}. Asegúrate de que LibreOffice esté correctamente instalado o pasa su ruta con --soffice-path.")
					# marcar como no disponible para forzar fallback o mensaje
					soffice = None
			except Exception as e:
				msgs.append(f"Error al ejecutar '{soffice} --version': {e}. Comprueba la instalación de LibreOffice o pasa la ruta con --soffice-path.")
				soffice = None

		if not (soffice or word_com):
			msgs.append("Se detectaron ficheros .doc pero no se encontró un convertidor (.doc -> .docx).")
			msgs.append("Opciones: instalar LibreOffice y asegurarte de que 'soffice' está en PATH, o instalar pywin32 y usar Microsoft Word en Windows.")
			msgs.append("Puedes pasar la ruta a soffice con --soffice-path o establecer la variable de entorno SOFFICE_PATH.")

	# If export requested and there are docx but python-docx missing, error
	if include_word and args.export_md and has_docx and Document is None:
		msgs.append("Se detectaron .docx pero falta 'python-docx' para extraer su contenido. Instálalo con: pip install python-docx")

	# If export requested and there are pdfs but PyMuPDF missing, error
	if include_pdf and args.export_md and has_pdf and fitz is None:
		msgs.append("Se detectaron ficheros .pdf pero falta 'PyMuPDF' (fitz) para extraer su contenido/imagenes. Instálalo con: pip install PyMuPDF")

	if msgs:
		return False, "\n".join(msgs)
	return True, "Pre-check OK: herramientas disponibles o no necesarias."


def count_entries(directory: Path, recursive: bool = True) -> Tuple[int, int]:
	"""Cuenta archivos y subcarpetas en `directory`.

	Si recursive=True cuenta en todo el árbol, si es False sólo en el directorio raíz.

	Retorna (num_files, num_dirs)
	"""
	num_files = 0
	num_dirs = 0
	try:
		if recursive:
			iterator = directory.rglob("*")
		else:
			iterator = directory.iterdir()

		for p in iterator:
			try:
				if p.is_file():
					num_files += 1
				elif p.is_dir():
					num_dirs += 1
			except (PermissionError, OSError):
				# Saltar elementos a los que no tenemos permiso
				continue
	except Exception:
		# En caso de error al iterar, devolvemos ceros
		return 0, 0

	return num_files, num_dirs


def get_directory_from_args_or_input(arg_dir: Optional[str]) -> Path:
	"""Devuelve un Path válido; si arg_dir es None pide por consola.

	Lanza SystemExit si el usuario escribe 'exit' o si se alcanza EOF.
	"""
	if arg_dir:
		candidate = Path(arg_dir).expanduser().resolve()
		if not candidate.exists() or not candidate.is_dir():
			raise SystemExit(f"El directorio especificado no existe o no es una carpeta: {candidate}")
		return candidate

	# Pedimos por consola si no se proporcionó argumento
	while True:
		try:
			raw = input("Introduce el directorio a inspeccionar (deja vacío para usar el directorio actual): ").strip()
		except EOFError:
			raise SystemExit("Entrada interrumpida. Saliendo.")

		if raw.lower() in {"exit", "salir", "quit"}:
			raise SystemExit("Usuario canceló la operación.")

		if raw == "":
			candidate = Path.cwd()
		else:
			candidate = Path(raw).expanduser().resolve()

		if candidate.exists() and candidate.is_dir():
			return candidate
		print(f"Ruta inválida o no es carpeta: {candidate}\nInténtalo de nuevo, o escribe 'exit' para salir.")


def main(argv: Optional[list[str]] = None) -> int:
	argv = argv if argv is not None else sys.argv[1:]
	parser = argparse.ArgumentParser(description="Unify files - primer script: pide un directorio y resume su contenido.")
	parser.add_argument("-d", "--dir", dest="directory", help="Ruta del directorio a inspeccionar. Si no se proporciona, se pide por consola.")
	parser.add_argument("--include-word", dest="include_word", action="store_true",
						help="Incluir ficheros Word en el procesamiento (extensiones .docx, .docm, .doc, .dotx).")
	parser.add_argument("--export-md", dest="export_md", help="Ruta del fichero Markdown de salida. Si existe se añadirá (append).")
	parser.add_argument("--include-simple-text", dest="include_simple_text", action="store_true",
						help="Incluir ficheros de texto simples (.txt, .md, .markdown, .log) en la exportación Markdown (cuando se use --export-md).")
	parser.add_argument("--include-pdf", dest="include_pdf", action="store_true",
				help="Incluir ficheros PDF en el procesamiento (extrae texto e imágenes).")
	parser.add_argument("--recursive", dest="recursive", action="store_true",
					help="Incluir subdirectorios de forma recursiva. Por defecto solo se procesa el directorio indicado.")
	parser.add_argument("--soffice-path", dest="soffice_path", help="Ruta completa a soffice.exe (opcional). Si no se proporciona, se intentará buscar en PATH o en rutas comunes de instalación.")
	args = parser.parse_args(argv)

	# Aplicar override global si se pasó por CLI o por variable de entorno
	global SOFFICE_PATH_OVERRIDE
	if args.soffice_path:
		SOFFICE_PATH_OVERRIDE = args.soffice_path
	else:
		SOFFICE_PATH_OVERRIDE = os.environ.get("SOFFICE_PATH")

	try:
		directory = get_directory_from_args_or_input(args.directory)
	except SystemExit as exc:
		print(exc)
		return 1

	# Determinar qué tipos procesaremos: si ningún flag de inclusión se pasó,
	# por defecto incluimos todos los tipos soportados (Word y texto simple).
	include_word = bool(getattr(args, "include_word", False))
	include_text = bool(getattr(args, "include_simple_text", False))
	include_pdf = bool(getattr(args, "include_pdf", False))
	# Si el usuario no pasó ningún flag de inclusión, incluir todos los tipos soportados (Word, texto y PDF)
	if not include_word and not include_text and not include_pdf:
		include_word = True
		include_text = True
		include_pdf = True

	# Pre-check: validar herramientas necesarias antes de procesar ficheros
	pre_ok, pre_msg = pre_check(directory, args, include_word, include_text, include_pdf, bool(getattr(args, "recursive", False)))
	if not pre_ok:
		print("Error en pre-check:")
		print(pre_msg)
		return 2


	print(f"\nInspeccionando: {directory}")

	# Construir la lista de ficheros a procesar según flags (o por defecto todos)
	def is_word_file(p: Path) -> bool:
		return p.suffix.lower() in {".docx", ".docm", ".doc", ".dotx"}

	def is_text_file(p: Path) -> bool:
		return p.suffix.lower() in {".txt", ".md", ".markdown", ".log"}

	glob_func = directory.rglob if bool(getattr(args, "recursive", False)) else directory.glob
	word_files = [p for p in glob_func("*") if p.is_file() and is_word_file(p)] if include_word else []
	pdf_files = [p for p in glob_func("*") if p.is_file() and p.suffix.lower() == ".pdf"] if include_pdf else []
	text_files = [p for p in glob_func("*") if p.is_file() and is_text_file(p)] if include_text else []

	combined = []
	if include_word:
		combined.extend(word_files)
	if include_pdf:
		for pf in pdf_files:
			if pf not in combined:
				combined.append(pf)
	if include_text:
		for tp in text_files:
			if tp not in combined:
				combined.append(tp)

	# Feedback
	mode_label = "recursivo" if bool(getattr(args, "recursive", False)) else "no recursivo"
	if include_word:
		print("Resumen (ficheros Word):")
		print(f"  Ficheros Word encontrados ({mode_label}): {len(word_files)}")
	if include_pdf:
		print("Resumen (ficheros PDF):")
		print(f"  Ficheros PDF encontrados ({mode_label}): {len(pdf_files)}")
	if include_text:
		print("Resumen (ficheros de texto simple):")
		print(f"  Ficheros de texto encontrados ({mode_label}): {len(text_files)}")

	if combined:
		print("\nListado de ficheros a procesar (hasta 50):")
		for i, p in enumerate(combined[:50], start=1):
			print(f"  {i}. {p.relative_to(directory)}")

	# Si se pidió exportar a MD, procesamos cada fichero seleccionado y añadimos su contenido
	if args.export_md:
		md_path = Path(args.export_md).expanduser().resolve()
		# assets dir para imágenes extraídas (PDFs u otros)
		assets_dir = md_path.parent / f"{md_path.stem}_assets"
		if not assets_dir.exists():
			try:
				assets_dir.mkdir(parents=True, exist_ok=True)
			except Exception:
				pass
	# Recolectar entradas y resultados, construiremos un MD completo con índice al inicio
		# entries: (path, md_text, slug, meta_dict)
		entries: list[tuple[Path, str, str, dict]] = []
		# results rows will include metadata provenance columns
		# (file, status, message, created_meta, created_fs, modified_meta, modified_fs)
		results: list[tuple[str, str, str, str, str, str, str]] = []

		for p in combined:
			try:
				to_process = p
				cleanup_dir = None
				# Si es un .doc antiguo, intentar convertir a .docx
				if p.suffix.lower() == ".doc":
					converted = convert_doc_to_docx(p)
					if converted is None:
						raise RuntimeError("No se pudo convertir .doc a .docx: falta conversor (.doc -> .docx)")
					to_process = converted
					# si convert_doc_to_docx usó un tempdir, devolver su ruta para limpiarlo después
					cleanup_dir = converted.parent if converted.is_file() else None

				# Elegir render según tipo de fichero y desempaquetar meta
				md_text = ""
				meta: dict = {}
				img_paths: list[str] = []

				if p.suffix.lower() in {".docx", ".docm", ".dotx", ".doc"}:
					rendered = render_docx_as_markdown(to_process, directory)
					if isinstance(rendered, tuple):
						md_text, meta = rendered
					else:
						md_text = str(rendered)
				elif p.suffix.lower() == ".pdf":
					rendered = render_pdf_as_markdown(to_process, directory, assets_dir)
					# expected (md_text, meta_dict, image_rel_paths)
					if isinstance(rendered, tuple) and len(rendered) == 3:
						md_text, meta, img_paths = rendered
					elif isinstance(rendered, tuple) and len(rendered) == 2:
						md_text, meta = rendered
					else:
						md_text = str(rendered)
				else:
					# ficheros de texto
					rendered = render_text_as_markdown(p, directory)
					if isinstance(rendered, tuple):
						md_text, meta = rendered
					else:
						md_text = str(rendered)

				s = slugify(p.name)
				entries.append((p, md_text, s, meta))

				# Añadir fila de fichero principal con columnas de trazabilidad
				results.append((str(p.relative_to(directory)), "ok", "",
								meta.get("created_meta", ""), meta.get("created_fs", ""),
								meta.get("modified_meta", ""), meta.get("modified_fs", "")))

				# por cada imagen extraída añadimos una fila en el CSV indicando su ruta y heredando metadatos del padre
				for ip in img_paths:
					results.append((str(p.relative_to(directory)), "image", str(ip),
									meta.get("created_meta", ""), meta.get("created_fs", ""),
									meta.get("modified_meta", ""), meta.get("modified_fs", "")))

				# limpiar temporales si hace falta
				if cleanup_dir and cleanup_dir.exists():
					try:
						shutil.rmtree(cleanup_dir)
					except Exception:
						pass
			except Exception as e:
				# registrar error con columnas de metadatos vacías
				results.append((str(p.relative_to(directory)), "error", str(e), "", "", "", ""))

		# Escribir fichero MD completo (sobrescribir) con índice
		with md_path.open("w", encoding="utf-8") as md_file:
			# Índice
			md_file.write("# Índice\n\n")
			for p, md, s, meta in entries:
				md_file.write(f"- [{p.name}](#{s})\n")
			md_file.write("\n---\n\n")

			# Secciones por fichero
			for p, md, s, meta in entries:
				md_file.write(f'<a id="{s}"></a>\n')
				md_file.write(md)
				md_file.write("\n\n")

		# Escribir fichero de resultados (CSV simple)
		results_path = md_path.parent / f"{md_path.stem}_results.csv"
		import csv

		with results_path.open("w", encoding="utf-8", newline="") as rf:
			writer = csv.writer(rf)
			writer.writerow(["file", "status", "message", "created_meta", "created_fs", "modified_meta", "modified_fs"])
			for row in results:
				writer.writerow(row)

		print(f"MD generado en: {md_path}")
		print(f"Fichero de resultados: {results_path}")

	# Si no hay ficheros seleccionados, mostrar resumen general
	if not combined:
		num_files, num_dirs = count_entries(directory, recursive=bool(getattr(args, "recursive", False)))
		print(f"Resumen:")
		print(f"  Archivos ({mode_label}): {num_files}")
		print(f"  Directorios ({mode_label}): {num_dirs}")

		# Mostrar algunos ejemplos (máx. 10) para dar feedback inmediato
		print("\nEjemplos de ficheros encontrados (hasta 10):")
		shown = 0
		glob_func = directory.rglob if bool(getattr(args, "recursive", False)) else directory.glob
		for p in glob_func("*"):
			if p.is_file():
				print(f"  - {p.relative_to(directory)}")
				shown += 1
				if shown >= 10:
					break


def _format_dt(dt: Optional[datetime]) -> str:
	if dt is None:
		return "Desconocida"
	if isinstance(dt, datetime):
		return dt.isoformat(sep=" ", timespec="seconds")
	# try to parse string
	try:
		return str(dt)
	except Exception:
		return "Desconocida"


def render_docx_as_markdown(doc_path: Path, base_dir: Path) -> tuple[str, dict]:
	"""Extrae metadatos y contenido de un .docx y devuelve un bloque Markdown.

	Estructura producida:
	# filename.ext
	## Metadatos
	- Creación: ...
	- Última modificación: ...
	## Contenido
	(contenido con mapeo de headings: Heading 1 -> ###, Heading 2 -> ####, ...)
	"""
	title = doc_path.name

	# Preferir metadatos internos de docx cuando sea posible
	created_meta = None
	modified_meta = None
	doc = None
	if Document is not None:
		try:
			doc = Document(doc_path)
			props = doc.core_properties
			created_meta = getattr(props, "created", None)
			modified_meta = getattr(props, "modified", None)
		except Exception:
			doc = None

	# Fallback a timestamps del sistema de ficheros (en Windows st_ctime = creación)
	try:
		st = doc_path.stat()
		fs_created = datetime.fromtimestamp(st.st_ctime)
		fs_modified = datetime.fromtimestamp(st.st_mtime)
	except Exception:
		fs_created = fs_modified = None

	created_fs = fs_created
	modified_fs = fs_modified

	# Decide preferencia: si existe metadato interno lo usamos como 'meta',
	# pero conservamos siempre el valor del sistema para referencia.
	created_val = created_meta or created_fs
	modified_val = modified_meta or modified_fs

	lines: list[str] = []
	# Título (H1)
	lines.append(f"# {title}")
	lines.append("")
	# Metadatos (H2)
	lines.append("## Metadatos")
	lines.append("")
	# Mostrar ambas fuentes cuando estén disponibles
	if created_meta is not None:
		lines.append(f"- Creación (metadato): {_format_dt(created_meta)}")
	else:
		lines.append(f"- Creación (metadato): (no disponible)")
	lines.append(f"- Creación (sistema): {_format_dt(created_fs)}")

	if modified_meta is not None:
		lines.append(f"- Última modificación (metadato): {_format_dt(modified_meta)}")
	else:
		lines.append(f"- Última modificación (metadato): (no disponible)")
	lines.append(f"- Última modificación (sistema): {_format_dt(modified_fs)}")
	lines.append("")
	# Contenido (H2)
	lines.append("## Contenido")
	lines.append("")

	if doc is None:
		lines.append("(No se pudo extraer contenido con `python-docx`)")
		meta = {
			"created_meta": created_meta.isoformat() if isinstance(created_meta, datetime) else (str(created_meta) if created_meta else ""),
			"created_fs": created_fs.isoformat() if isinstance(created_fs, datetime) else (str(created_fs) if created_fs else ""),
			"modified_meta": modified_meta.isoformat() if isinstance(modified_meta, datetime) else (str(modified_meta) if modified_meta else ""),
			"modified_fs": modified_fs.isoformat() if isinstance(modified_fs, datetime) else (str(modified_fs) if modified_fs else ""),
		}
		return "\n".join(lines), meta



	for para in doc.paragraphs:

		# Detectar si el párrafo contiene imágenes dentro de sus runs. Algunos runs
		# no contienen texto pero sí elementos <pic:pic> o <a:blip> en XML.
		def run_contains_image(r) -> bool:
			try:
				el = r._element
				# Namespaces típicos usados para imágenes en docx
				ns = {
					"a": "http://schemas.openxmlformats.org/drawingml/2006/main",
					"pic": "http://schemas.openxmlformats.org/drawingml/2006/picture",
					"wp": "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing",
					"v": "urn:schemas-microsoft-com:vml",
				}
				# Buscar elementos picture o blip (referencias a imágenes)
				if el.xpath('.//pic:pic', namespaces=ns):
					return True
				if el.xpath('.//a:blip', namespaces=ns):
					return True
				if el.xpath('.//v:imagedata', namespaces=ns):
					return True
			except Exception:
				pass
			return False

		style_name = ""
		try:
			style_name = para.style.name if para.style is not None else ""
		except Exception:
			style_name = ""

		heading_level = None
		if style_name:
			# Estilos comunes: 'Heading 1', 'Heading 2', etc.
			import re

			m = re.search(r"heading\s*(\d+)", style_name.lower())
			if m:
				heading_level = int(m.group(1))

		# Reconstruir el párrafo analizando los runs para detectar imágenes
		parts: list[str] = []
		for r in para.runs:
			text_run = (r.text or "").strip()
			if text_run:
				parts.append(text_run)
			elif run_contains_image(r):
				# Insertar etiqueta simple para indicar imagen
				parts.append("[imagen]")

		text = "\n".join(part for part in parts).strip()
		if not text:
			lines.append("")
			continue

		if heading_level is not None:
			# Mapear: document title is H1, content section H2, so Heading 1 -> H3
			md_level = 2 + heading_level
			lines.append("#" * md_level + " " + text)
			lines.append("")
		else:
			# Texto normal, preservar párrafos
			lines.append(text)
			lines.append("")

	meta = {
		"created_meta": created_meta.isoformat() if isinstance(created_meta, datetime) else (str(created_meta) if created_meta else ""),
		"created_fs": created_fs.isoformat() if isinstance(created_fs, datetime) else (str(created_fs) if created_fs else ""),
		"modified_meta": modified_meta.isoformat() if isinstance(modified_meta, datetime) else (str(modified_meta) if modified_meta else ""),
		"modified_fs": modified_fs.isoformat() if isinstance(modified_fs, datetime) else (str(modified_fs) if modified_fs else ""),
	}
	return "\n".join(lines), meta


def render_text_as_markdown(txt_path: Path, base_dir: Path) -> tuple[str, dict]:
	"""Convierte un fichero de texto plano o Markdown a un bloque Markdown con metadatos.

	Para ficheros Markdown (.md, .markdown) se desplazan los niveles de heading aumentando 2 niveles
	para conservar la jerarquía dentro del documento unificado (por ejemplo, '#' -> '###').
	"""
	title = txt_path.name
	# timestamps
	try:
		st = txt_path.stat()
		fs_created = datetime.fromtimestamp(st.st_ctime)
		fs_modified = datetime.fromtimestamp(st.st_mtime)
	except Exception:
		fs_created = fs_modified = None

	created_fs = fs_created
	modified_fs = fs_modified

	lines: list[str] = []
	lines.append(f"# {title}")
	lines.append("")
	lines.append("## Metadatos")
	lines.append("")
	lines.append(f"- Creación (metadato): (no disponible)")
	lines.append(f"- Creación (sistema): {_format_dt(created_fs)}")
	lines.append("")
	lines.append(f"- Última modificación (metadato): (no disponible)")
	lines.append(f"- Última modificación (sistema): {_format_dt(modified_fs)}")
	lines.append("")
	lines.append("## Contenido")
	lines.append("")

	try:
		with txt_path.open("r", encoding="utf-8", errors="replace") as fh:
			for raw in fh:
				line = raw.rstrip("\n")
				if txt_path.suffix.lower() in {".md", ".markdown"}:
					# Shift markdown headings by two levels: '#' -> '###'
					import re
					m = re.match(r'^(\s*)(#+)(\s*)(.*)$', line)
					if m:
						leading, hashes, space, rest = m.groups()
						new_hashes = "#" * (len(hashes) + 2)
						lines.append(f"{leading}{new_hashes}{space}{rest}".rstrip())
					else:
						lines.append(line)
				else:
					lines.append(line)
	except Exception:
		lines.append("(No se pudo leer el fichero de texto.)")

	meta = {
		"created_meta": "",
		"created_fs": created_fs.isoformat() if isinstance(created_fs, datetime) else (str(created_fs) if created_fs else ""),
		"modified_meta": "",
		"modified_fs": modified_fs.isoformat() if isinstance(modified_fs, datetime) else (str(modified_fs) if modified_fs else ""),
	}
	return "\n".join(lines), meta


def render_pdf_as_markdown(pdf_path: Path, base_dir: Path, assets_dir: Path) -> tuple[str, list[str]]:
	"""Extrae texto e imágenes de un PDF y devuelve Markdown + lista de rutas relativas a las imágenes extraídas.

	Retorna (md_text, [image_rel_path, ...]) donde image_rel_path es relativo al directorio del MD (assets_dir nombre/archivo).
	"""
	title = pdf_path.name
	# timestamps (por defecto tomamos los del sistema de ficheros)
	try:
		st = pdf_path.stat()
		fs_created = datetime.fromtimestamp(st.st_ctime)
		fs_modified = datetime.fromtimestamp(st.st_mtime)
	except Exception:
		fs_created = fs_modified = None

	# Por defecto mostramos las fechas del sistema. Si PyMuPDF está disponible
	# intentaremos leer metadatos internos del PDF (CreationDate / ModDate)
	created_val = fs_created
	modified_val = fs_modified

	lines: list[str] = []
	lines.append(f"# {title}")
	lines.append("")
	lines.append("## Metadatos")
	lines.append("")
	lines.append(f"- Creación: {_format_dt(created_val)}")
	lines.append(f"- Última modificación: {_format_dt(modified_val)}")
	lines.append("")
	lines.append("## Contenido")
	lines.append("")

	image_rel_paths: list[str] = []

	if fitz is None:
		lines.append("(No se pudo extraer contenido de PDF: falta PyMuPDF (fitz).)")
		return "\n".join(lines), image_rel_paths

	try:
		doc = fitz.open(str(pdf_path))
	except Exception:
		lines.append("(Error al abrir el PDF con PyMuPDF.)")
		return "\n".join(lines), image_rel_paths


	# Intentar obtener CreationDate / ModDate desde metadatos internos del PDF
	try:
		meta = doc.metadata or {}
		# keys can be 'creationDate', 'CreationDate', 'modDate', etc. Normalize
		cands = {}
		for k, v in meta.items():
			if v is None:
				continue
			cands[k.lower()] = v

		def _parse_pdf_date(s: str) -> Optional[datetime]:
			# PDF dates often look like: D:YYYYMMDDHHmmSSOHH'mm' or variations.
			if not s or not isinstance(s, str):
				return None
			s = s.strip()
			if s.startswith("D:"):
				s = s[2:]
			# Extract digits for YYYY MM DD HH MM SS
			import re

			m = re.match(r"(\d{4})(\d{2})?(\d{2})?(\d{2})?(\d{2})?(\d{2})?", s)
			if not m:
				# Try ISO-like parse
				try:
					return datetime.fromisoformat(s)
				except Exception:
					return None
			parts = m.groups()
			try:
				year = int(parts[0])
				month = int(parts[1]) if parts[1] else 1
				day = int(parts[2]) if parts[2] else 1
				hour = int(parts[3]) if parts[3] else 0
				minute = int(parts[4]) if parts[4] else 0
				second = int(parts[5]) if parts[5] else 0
				return datetime(year, month, day, hour, minute, second)
			except Exception:
				return None

		# Prefer internal metadata if present
		created_meta = None
		modified_meta = None
		if "creationdate" in cands:
			parsed = _parse_pdf_date(cands.get("creationdate"))
			if parsed:
				created_meta = parsed
		elif "creation_date" in cands:
			parsed = _parse_pdf_date(cands.get("creation_date"))
			if parsed:
				created_meta = parsed

		if "moddate" in cands:
			parsedm = _parse_pdf_date(cands.get("moddate"))
			if parsedm:
				modified_meta = parsedm
		elif "mod_date" in cands:
			parsedm = _parse_pdf_date(cands.get("mod_date"))
			if parsedm:
				modified_meta = parsedm

		# If we have parsed meta dates, prefer them for display
		if created_meta:
			created_val = created_meta
		if modified_meta:
			modified_val = modified_meta
	except Exception:
		# no tenemos metadatos o fallo al parsear -> usar filesystem timestamps
		pass

	# Iterar páginas y extraer texto e imágenes
	for pno, page in enumerate(doc, start=1):
		try:
			p_text = page.get_text("text") or ""
			if p_text.strip():
				for pline in p_text.splitlines():
					lines.append(pline)
				lines.append("")
			# extraer imágenes de la página
			images = page.get_images(full=True)
			if images:
				for idx, img in enumerate(images, start=1):
					xref = img[0]
					try:
						imgdict = doc.extract_image(xref)
						imgbytes = imgdict.get("image")
						ext = imgdict.get("ext", "png")
						# Nombre único para la imagen
						fname = f"{slugify(pdf_path.stem)}_p{pno}_img{idx}.{ext}"
						out_path = assets_dir / fname
						# asegurar no sobrescribir: si existe, añadir sufijo numérico
						if out_path.exists():
							base = out_path.stem
							extn = out_path.suffix
							i = 1
							while out_path.exists():
								out_path = assets_dir / f"{base}-{i}{extn}"
								i += 1
						try:
							with out_path.open("wb") as outf:
								outf.write(imgbytes)
						except Exception:
							# no podemos escribir la imagen; insertar placeholder
							lines.append("[imagen]")
							continue
						# ruta relativa que irá al MD (assets_dir nombre / fichero)
						relref = f"{assets_dir.name}/{out_path.name}"
						lines.append("")
						lines.append(f"![imagen]({relref})")
						lines.append("")
						image_rel_paths.append(relref)
					except Exception:
						# problema extrayendo imagen concreta
						lines.append("[imagen]")
		except Exception:
			# ignorar problemas en la página y continuar
			continue

	meta = {
		"created_meta": created_meta.isoformat() if isinstance(created_meta, datetime) else (str(created_meta) if created_meta else ""),
		"created_fs": fs_created.isoformat() if isinstance(fs_created, datetime) else (str(fs_created) if fs_created else ""),
		"modified_meta": modified_meta.isoformat() if isinstance(modified_meta, datetime) else (str(modified_meta) if modified_meta else ""),
		"modified_fs": fs_modified.isoformat() if isinstance(fs_modified, datetime) else (str(fs_modified) if fs_modified else ""),
	}

	return "\n".join(lines), meta, image_rel_paths


if __name__ == "__main__":
	raise SystemExit(main())
