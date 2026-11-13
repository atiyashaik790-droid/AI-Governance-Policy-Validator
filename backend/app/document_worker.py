"""Isolated, stdin-only text extraction. Run by document_uploads; never a server."""
import io
import json
import logging
import resource
import sys
import zipfile
import xml.etree.ElementTree as ET

MAX_TEXT = 10000
MAX_EXPANDED = 2 * 1024 * 1024
W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


class Rejected(Exception):
    pass


def checked_text(value):
    if len(value) > MAX_TEXT:
        raise Rejected("Document exceeds 10000 extracted characters")
    if not value.strip():
        raise Rejected("Document has no extractable text; OCR is unavailable")
    if any(ord(char) < 32 and char not in "\n\r\t\f" for char in value):
        raise Rejected("Document contains unsupported binary or control data")
    return value


def xml(data):
    text = data.decode("utf-8-sig")
    if "<!DOCTYPE" in text.upper() or "<!ENTITY" in text.upper():
        raise Rejected("Document XML declarations are unsupported")
    return ET.fromstring(text)


def docx(data):
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        entries = archive.infolist()
        names = [entry.filename for entry in entries]
        if len(entries) > 128 or len(set(names)) != len(names) or sum(e.file_size for e in entries) > MAX_EXPANDED:
            raise Rejected("DOCX archive exceeds safe expansion limits")
        required = {"[Content_Types].xml", "_rels/.rels", "word/document.xml"}
        if not required <= set(names):
            raise Rejected("Invalid DOCX package")
        parts = {}
        for entry in entries:
            name = entry.filename
            if (name.startswith("/") or "\\" in name or ".." in name.split("/") or entry.flag_bits & 1
                    or (entry.external_attr >> 16) & 0o170000 == 0o120000
                    or entry.compress_type not in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED)
                    or entry.file_size > 512 * 1024 or entry.file_size > max(1, entry.compress_size) * 100):
                raise Rejected("Unsafe DOCX archive entry")
            if entry.is_dir():
                continue
            if not name.endswith((".xml", ".rels")) and name != "docProps/thumbnail.jpeg":
                raise Rejected("DOCX embedded or binary content is unsupported")
            with archive.open(entry) as stream:
                content = stream.read(512 * 1024 + 1)
            if len(content) != entry.file_size:
                raise Rejected("Incomplete DOCX archive entry")
            if name.endswith((".xml", ".rels")):
                parts[name] = xml(content)
        main_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"
        if not any(node.get("PartName") == "/word/document.xml" and node.get("ContentType") == main_type
                   for node in parts["[Content_Types].xml"]):
            raise Rejected("DOCX document type is unsupported")
        if parts["word/document.xml"].tag != W + "document":
            raise Rejected("Invalid Word document structure")
        package_rel = "http://schemas.openxmlformats.org/package/2006/relationships"
        office_rel = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument"
        if not any(node.get("Type") == office_rel and node.get("Target") == "word/document.xml"
                   for node in parts["_rels/.rels"]):
            raise Rejected("Invalid Word document relationship")
        for root in parts.values():
            for node in root.iter():
                if node.tag == "{" + package_rel + "}Relationship" and node.get("TargetMode") == "External":
                    raise Rejected("Externally linked DOCX content is unsupported")
                if node.tag.startswith(W) and node.tag[len(W):] in {
                    "altChunk", "object", "drawing", "pict", "instrText", "fldChar", "fldSimple", "subDoc", "sym",
                }:
                    raise Rejected("DOCX contains content that cannot be fully extracted")
        chunks = []
        for name in ["word/document.xml"] + sorted(n for n in parts if n.startswith("word/") and n != "word/document.xml"):
            root = parts[name]
            for node in root.iter():
                if node.tag in {W + "t", W + "delText", "{http://schemas.openxmlformats.org/officeDocument/2006/math}t"}:
                    chunks.append(node.text or "")
                elif node.tag in {W + "p", W + "br", W + "cr"}:
                    chunks.append("\n")
                elif node.tag == W + "tab":
                    chunks.append("\t")
                elif node.tag in {W + "noBreakHyphen", W + "softHyphen"}:
                    chunks.append("-")
                elif node.text and node.text.strip():
                    raise Rejected("DOCX contains unsupported textual content")
                if node.tail and node.tail.strip():
                    raise Rejected("DOCX contains unsupported textual content")
        return checked_text("".join(chunks))


def pdf(data):
    from pypdf import PdfReader
    from pypdf.generic import ArrayObject, DictionaryObject, FloatObject, NameObject, NullObject, NumberObject
    from urllib.parse import urlsplit
    if not data.startswith(b"%PDF-") or not data.rstrip().endswith(b"%%EOF"):
        raise Rejected("Invalid or incomplete PDF structure")
    reader = PdfReader(io.BytesIO(data), strict=True)
    if reader.is_encrypted:
        raise Rejected("Encrypted PDF documents are unsupported")
    if not 1 <= len(reader.pages) <= 20:
        raise Rejected("PDF must contain 1 to 20 pages")
    root = reader.trailer["/Root"]
    def safe_destination(destination):
        destination = destination.get_object()
        return (isinstance(destination, ArrayObject) and len(destination) >= 2
                and isinstance(destination[0].get_object(), DictionaryObject)
                and destination[0].get_object().get("/Type") == "/Page"
                and isinstance(destination[1], NameObject)
                and destination[1] in ("/XYZ", "/Fit", "/FitH", "/FitV", "/FitR", "/FitB", "/FitBH", "/FitBV")
                and all(isinstance(item, (NumberObject, FloatObject, NullObject)) for item in destination[2:]))

    opening = root.get("/OpenAction")
    if opening is not None:
        opening = opening.get_object()
        if isinstance(opening, DictionaryObject):
            safe_opening = set(opening) == {"/S", "/D"} and opening.get("/S") == "/GoTo" and safe_destination(opening["/D"])
        else:
            safe_opening = safe_destination(opening)
        if not safe_opening:
            raise Rejected("PDF opening actions are unsupported")
    if "/AA" in root:
        raise Rejected("PDF catalog actions are unsupported")
    if "/Collection" in root:
        raise Rejected("PDF portfolio collections are unsupported")
    if reader.attachments:
        raise Rejected("PDF embedded files are unsupported")
    names = root.get("/Names")
    if names and any(key in names.get_object() for key in ("/JavaScript", "/EmbeddedFiles")):
        raise Rejected("PDF scripts or embedded files are unsupported")
    form_values = []
    seen_fields = set()
    form = root.get("/AcroForm")
    if form:
        form = form.get_object()
        if any(key in form for key in ("/XFA", "/AA", "/A", "/JS")):
            raise Rejected("PDF active forms are unsupported")
        def inspect_field(reference, inherited_type=None):
            field = reference.get_object()
            identity = id(field)
            if identity in seen_fields or len(seen_fields) >= 256:
                raise Rejected("PDF form structure is unsupported")
            seen_fields.add(identity)
            if any(key in field for key in ("/A", "/AA", "/JS", "/JavaScript", "/RichMedia")):
                raise Rejected("PDF form actions are unsupported")
            field_type = field.get("/FT", inherited_type)
            if field_type and field_type not in ("/Tx", "/Btn", "/Ch"):
                raise Rejected("PDF form field type is unsupported")
            value = field.get("/V")
            if value is not None and str(value) not in ("", "/Off"):
                if field_type not in ("/Tx", "/Btn", "/Ch") or not isinstance(value, (str, list)):
                    raise Rejected("PDF form value is unsupported")
                values = value if isinstance(value, list) else [value]
                if any(not isinstance(item, str) for item in values):
                    raise Rejected("PDF form value is unsupported")
                form_values.extend(str(item).lstrip("/") for item in values)
            for child in field.get("/Kids", []):
                inspect_field(child, field_type)

        for field in form.get("/Fields", []):
            inspect_field(field)
    def reject_images(resources, visited):
        resources = resources.get_object() if resources else {}
        objects = resources.get("/XObject", {})
        objects = objects.get_object() if objects else {}
        for reference in objects.values():
            obj = reference.get_object()
            identity = id(obj)
            if identity in visited:
                continue
            visited.add(identity)
            if len(visited) > 256 or obj.get("/Subtype") == "/Image":
                raise Rejected("PDF image content requires OCR and is unsupported")
            if obj.get("/Resources"):
                reject_images(obj["/Resources"], visited)

    chunks, expanded = [], 0
    for page in reader.pages:
        if "/AA" in page:
            raise Rejected("PDF page actions are unsupported")
        for reference in page.get("/Annots", []):
            annotation = reference.get_object()
            if annotation.get("/Subtype") == "/Link" and "/AA" not in annotation:
                action = annotation.get("/A")
                action = action.get_object() if action else None
                if (isinstance(action, DictionaryObject) and {"/S", "/URI"} <= set(action)
                        and set(action) <= {"/S", "/URI", "/Type"}
                        and action.get("/Type", "/Action") == "/Action"
                        and action.get("/S") == "/URI" and isinstance(action.get("/URI"), str)
                        and len(action["/URI"]) <= 2048
                        and urlsplit(action["/URI"]).scheme.lower() in ("https", "http", "mailto", "tel")
                        and not any(ord(char) < 32 for char in action["/URI"])):
                    continue  # A link target is never fetched, executed, or sent to governance.
            if (annotation.get("/Subtype") != "/Widget" or id(annotation) not in seen_fields
                    or any(key in annotation for key in ("/A", "/AA", "/JS", "/JavaScript", "/RichMedia"))):
                raise Rejected("PDF annotation actions are unsupported")
        reject_images(page.get("/Resources"), set())
        contents = page.get_contents()
        expanded += len(contents.get_data()) if contents else 0
        if expanded > MAX_EXPANDED:
            raise Rejected("PDF content exceeds safe expansion limits")
        value = page.extract_text()
        # A blank or scanned page is rejected rather than silently omitted.
        if not value.strip() and not form_values:
            checked_text(value)
        chunks.append(value)
        if len("\n".join(chunks)) + sum(len(item) + 1 for item in form_values) > MAX_TEXT:
            raise Rejected("Document exceeds 10000 extracted characters")
    return checked_text("\n".join(chunks + form_values))


def main():
    resource.setrlimit(resource.RLIMIT_AS, (256 * 1024 * 1024,) * 2)
    resource.setrlimit(resource.RLIMIT_CPU, (3, 3))
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    resource.setrlimit(resource.RLIMIT_FSIZE, (0, 0))
    warnings = []

    class Capture(logging.Handler):
        def emit(self, record):
            if record.levelno >= logging.WARNING:
                warnings.append(True)
    logging.getLogger().handlers = [Capture()]
    try:
        data = sys.stdin.buffer.read(256 * 1024 + 1)
        if not data or len(data) > 256 * 1024:
            raise Rejected("File must contain 1 to 262144 bytes")
        kind = sys.argv[1]
        if kind == "txt" and data.startswith((b"%PDF-", b"PK", b"\xd0\xcf", b"\x89PNG", b"GIF8")):
            raise Rejected("Attachment structure does not match TXT")
        text = checked_text(data.decode("utf-8-sig")) if kind == "txt" else docx(data) if kind == "docx" else pdf(data)
        if warnings:
            raise Rejected("Document could not be completely extracted")
        print(json.dumps({"text": text}))
    except Rejected as error:
        print(json.dumps({"error": str(error)}))
    except Exception:
        print(json.dumps({"error": "Corrupt or unsupported document; nothing released"}))


if __name__ == "__main__":
    main()
