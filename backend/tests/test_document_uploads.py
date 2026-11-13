"""Synthetic in-memory documents; all generation and moderation are fixtures."""
import asyncio
import base64
import io
import json
import zipfile
from unittest.mock import AsyncMock
from xml.sax.saxutils import escape

import pytest
from fastapi import HTTPException
from pypdf import PdfWriter
from pypdf.generic import ArrayObject, DecodedStreamObject, DictionaryObject, NameObject, TextStringObject
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app import providers
from app.models import Execution, InferenceUsage
from app.models_multi_policy import Execution006, ExecutionPolicyEvidence
from app.routers import document_uploads as upload
from app.schemas import PolicyDocument
import test_multi_policy_bridge as phase_bridge
import test_multi_policy_phase_b as phase_b
import test_multi_policy_phase_d as phase_d

templates = phase_b.templates
template010 = phase_b.template010
engine006 = phase_b.engine010
bridge = phase_bridge.bridge
TYPES = upload.TYPES


def pdf(text="public document", *, encrypted=False, blank=False, form_value=None, action=False, opening=None, link=None):
    writer = PdfWriter()
    page = writer.add_blank_page(300, 300)
    if not blank:
        font = DictionaryObject({NameObject("/Type"): NameObject("/Font"), NameObject("/Subtype"): NameObject("/Type1"),
                                 NameObject("/BaseFont"): NameObject("/Helvetica")})
        page[NameObject("/Resources")] = DictionaryObject({NameObject("/Font"): DictionaryObject({NameObject("/F1"): writer._add_object(font)})})
        stream = DecodedStreamObject()
        stream.set_data(f"BT /F1 12 Tf 10 200 Td ({text}) Tj ET".encode())
        page[NameObject("/Contents")] = writer._add_object(stream)
    if encrypted:
        writer.encrypt("synthetic-password")
    if opening == "destination":
        writer._root_object[NameObject("/OpenAction")] = ArrayObject([page.indirect_reference, NameObject("/Fit")])
    elif opening == "goto":
        writer._root_object[NameObject("/OpenAction")] = DictionaryObject({NameObject("/S"): NameObject("/GoTo"),
                                                                             NameObject("/D"): ArrayObject([page.indirect_reference, NameObject("/Fit")])})
    elif opening == "action":
        writer._root_object[NameObject("/OpenAction")] = DictionaryObject({NameObject("/S"): NameObject("/JavaScript"),
                                                                             NameObject("/JS"): TextStringObject("alert(1)")})
    if link:
        link_action = DictionaryObject({NameObject("/Type"): NameObject("/Action"),
                                        NameObject("/S"): NameObject("/JavaScript" if link == "script" else "/URI"),
                                        NameObject("/JS" if link == "script" else "/URI"): TextStringObject("alert(1)" if link == "script" else "mailto:test@example.invalid")})
        annotation = DictionaryObject({NameObject("/Subtype"): NameObject("/Link"),
                                       NameObject("/A"): writer._add_object(link_action)})
        page[NameObject("/Annots")] = ArrayObject([writer._add_object(annotation)])
    if form_value is not None:
        field = DictionaryObject({NameObject("/Type"): NameObject("/Annot"), NameObject("/Subtype"): NameObject("/Widget"),
                                  NameObject("/FT"): NameObject("/Tx"), NameObject("/T"): TextStringObject("Notes"),
                                  NameObject("/V"): TextStringObject(form_value)})
        field_ref = writer._add_object(field)
        page[NameObject("/Annots")] = ArrayObject([field_ref])
        writer._root_object[NameObject("/AcroForm")] = DictionaryObject({NameObject("/Fields"): ArrayObject([field_ref])})
        if action:
            field[NameObject("/AA")] = DictionaryObject({NameObject("/K"): DictionaryObject({NameObject("/S"): NameObject("/JavaScript"), NameObject("/JS"): TextStringObject("alert(1)")})})
    output = io.BytesIO()
    writer.write(output)
    return output.getvalue()


def docx(text="public document", *, extra=None):
    parts = {
        "[Content_Types].xml": '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/></Types>',
        "_rels/.rels": '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/></Relationships>',
        "word/document.xml": '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>' + escape(text) + '</w:t></w:r></w:p></w:body></w:document>',
        **(extra or {}),
    }
    result = io.BytesIO()
    with zipfile.ZipFile(result, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, value in parts.items():
            archive.writestr(name, value)
    return result.getvalue()


def payload(kind="txt", text="public document", raw=None, prompt="Summarize"):
    raw = raw if raw is not None else docx(text) if kind == "docx" else pdf(text) if kind == "pdf" else text.encode()
    return {"text": prompt, "filename": f"synthetic.{kind}", "content_type": TYPES.get(kind, "application/octet-stream"),
            "content_base64": base64.b64encode(raw).decode()}


@pytest.mark.parametrize("kind", ["pdf", "docx", "txt"])
async def test_extracts_complete_document_with_boundaries(kind):
    combined, metadata = await upload.extract(upload.DocumentRequest(**payload(kind)))
    assert "USER PROMPT:\nSummarize" in combined.text
    assert "UNTRUSTED DOCUMENT DATA" in combined.text and "public document" in combined.text
    assert metadata["type"] == kind and metadata["extracted_characters"] >= 15
    assert "filename" not in metadata


async def test_extracts_harmless_pdf_form_value_for_governance():
    combined, metadata = await upload.extract(upload.DocumentRequest(**payload("pdf", raw=pdf(form_value="private finance"))))
    assert "public document" in combined.text and "private finance" in combined.text
    assert metadata["type"] == "pdf"
    form_only, _ = await upload.extract(upload.DocumentRequest(**payload("pdf", raw=pdf(blank=True, form_value="form text"))))
    assert "form text" in form_only.text


async def test_rejects_pdf_form_action():
    with pytest.raises(HTTPException, match="PDF form actions are unsupported"):
        await upload.extract(upload.DocumentRequest(**payload("pdf", raw=pdf(form_value="private finance", action=True))))


async def test_accepts_passive_pdf_open_destination():
    combined, _ = await upload.extract(upload.DocumentRequest(**payload("pdf", raw=pdf(opening="destination"))))
    assert "public document" in combined.text


async def test_rejects_pdf_opening_script_with_specific_error():
    with pytest.raises(HTTPException, match="PDF opening actions are unsupported"):
        await upload.extract(upload.DocumentRequest(**payload("pdf", raw=pdf(opening="action"))))


async def test_accepts_internal_navigation_and_ignored_uri_link():
    combined, _ = await upload.extract(upload.DocumentRequest(**payload("pdf", raw=pdf(opening="goto", link="uri"))))
    assert "public document" in combined.text
    assert "test@example.invalid" not in combined.text


async def test_rejects_scripted_pdf_link():
    with pytest.raises(HTTPException, match="PDF annotation actions are unsupported"):
        await upload.extract(upload.DocumentRequest(**payload("pdf", raw=pdf(link="script"))))


@pytest.mark.parametrize("kind,raw", [
    ("pdf", b"%PDF-corrupt%%EOF"), ("pdf", pdf(encrypted=True)), ("pdf", pdf(blank=True)),
    ("docx", b"PK-broken"), ("docx", docx("")), ("txt", b"\xff\x00"), ("txt", b"\x00binary"),
    ("txt", pdf()), ("docx", docx(extra={"word/vbaProject.bin": b"macro"})),
    ("docx", docx(extra={"../escape.xml": "bad"})),
    ("docx", docx(extra={"word/embeddings/oleObject.bin": b"embedded"})),
    ("docx", docx(extra={"word/bomb.xml": "x" * 100000})),
    ("docx", docx(extra={"word/header1.xml": '<!DOCTYPE x [<!ENTITY y "secret">]><x>&y;</x>'})),
    ("docx", docx(extra={"word/_rels/document.xml.rels": '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="x" TargetMode="External" Target="file:///etc/passwd"/></Relationships>'})),
])
async def test_rejects_invalid_unsafe_and_incomplete_documents(kind, raw):
    with pytest.raises(HTTPException) as caught:
        await upload.extract(upload.DocumentRequest(**payload(kind, raw=raw)))
    assert caught.value.status_code == 422
    assert raw.decode(errors="replace") not in str(caught.value.detail)


async def test_type_size_and_full_text_limits():
    for values, code in [
        (payload("exe"), 415), (payload(raw=b""), 413),
        ({**payload(), "content_type": "application/pdf"}, 415),
        ({**payload(), "content_base64": "invalid@@"}, 422),
        (payload(text="a" * 10001), 422),
        (payload(prompt="a" * 2200, text="b" * 10000), 413),
        (payload(raw=b"a" * (upload.MAX_FILE + 1)), 413),
    ]:
        with pytest.raises(HTTPException) as caught:
            await upload.extract(upload.DocumentRequest(**values))
        assert caught.value.status_code == code


async def test_worker_timeout_and_capacity_fail_closed(monkeypatch):
    class Stalled:
        returncode = None
        killed = False
        async def communicate(self, data):
            raise TimeoutError()
        def kill(self):
            self.killed = True
            self.returncode = -9
        async def wait(self):
            return self.returncode
    process = Stalled()
    monkeypatch.setattr(asyncio, "create_subprocess_exec", AsyncMock(return_value=process))
    with pytest.raises(HTTPException, match="timed out"):
        await upload.extract(upload.DocumentRequest(**payload()))
    assert process.killed
    assert upload.SLOTS.acquire(False) and upload.SLOTS.acquire(False)
    try:
        with pytest.raises(HTTPException) as caught:
            await upload.extract(upload.DocumentRequest(**payload()))
        assert caught.value.status_code == 503
    finally:
        upload.SLOTS.release()
        upload.SLOTS.release()


def policy(action):
    return PolicyDocument(name="Attachment policy", rules={"moderation": {"enabled": False}}, custom_categories=[{
        "id": "private", "name": "Private data", "action": action, "detection": "keyword", "values": ["private finance"],
    }])


@pytest.mark.parametrize("action,expected_calls", [("BLOCK", 0), ("REDACT", 1)])
async def test_mixed_synthetic_document_credentials_and_pii(engine006, monkeypatch, action, expected_calls):  # noqa: F811
    synthetic = ("Project Atlas improves audit reporting. Status: on track. Meeting: December first, 2026. "
                 "Objective: reduce manual review.\n"
                 "api_key=sk-test-ABCDEFGHIJKLMNOPQRSTUVWXYZ12345\n"
                 "password=DummyPassword123!\nclient_secret=DummyClientSecret456!\n"
                 "Server=tcp:example.invalid;Password=DummyDbPassword789!\n"
                 "Authorization: Bearer SyntheticBearerToken1234567890\n"
                 "Email: demo@example.com Phone: +1 415 555 0123")
    doc = PolicyDocument(name="Mixed document policy", rules={
        "secret_detection": {"enabled": True, "action": action},
        "pii_detection": {"enabled": True, "action": "REDACT"},
        "moderation": {"enabled": False},
    })
    from app.config import settings
    from app import engine_multi_policy as evaluator
    monkeypatch.setattr(settings, "pii_mode", "regex")
    monkeypatch.setattr(settings, "provider_mode", "fixture")
    async def inline(function, *args):
        return function(*args)
    monkeypatch.setattr(evaluator.asyncio, "to_thread", inline)
    combined, metadata = await upload.extract(upload.DocumentRequest(**payload("txt", synthetic)))
    provider = AsyncMock(return_value="Project Atlas is on track and aims to reduce manual review.")
    monkeypatch.setattr(providers, "generate_ai_response", provider)
    with Session(engine006, expire_on_commit=False) as db:
        phase_d.setup_workspace(db, [doc])
        body = await phase_d.gateway.execute("generate", combined, db, phase_b.ADMIN,
                                             attachment=metadata, original_prompt="Summarize")
        assert body["decision"] == action and provider.await_count == expected_calls
        assert body["attachment"]["extracted_characters"] == len(synthetic)
        metadata_json = db.scalar(select(Execution006.metadata_json))
        stored_evidence = " ".join(db.scalars(select(ExecutionPolicyEvidence.evidence_json)).all())
        sensitive = ("DummyPassword123", "DummyClientSecret456", "DummyDbPassword789", "SyntheticBearerToken1234567890", "demo@example.com", "415 555 0123", "sk-test-ABCDEFGHIJKLMNOPQRSTUVWXYZ12345")
        assert all(secret not in metadata_json + stored_evidence for secret in sensitive)
        if action == "REDACT":
            approved = provider.await_args.args[0]
            for secret in sensitive:
                assert secret not in approved
            for safe in ("Project Atlas", "on track", "December first, 2026", "reduce manual review"):
                assert safe in approved
            assert body["safe_response"] == "Project Atlas is on track and aims to reduce manual review."
            assert body["output"] is not None and body["output"]["decision"] == "ALLOW"
        else:
            assert body["safe_response"] is None
            assert body["output"] is None


@pytest.mark.parametrize("mode", ["LEGACY", "MULTI"])
@pytest.mark.parametrize("kind", ["pdf", "docx", "txt"])
@pytest.mark.parametrize("action,calls", [("BLOCK", 0), ("HUMAN_REVIEW", 0), ("REDACT", 1)])
def test_governed_upload_enforces_custom_rules_before_one_dispatch_and_audits_metadata_only(bridge, engine006, monkeypatch, mode, kind, action, calls):
    doc = policy(action)
    if mode == "MULTI":
        with Session(engine006, expire_on_commit=False) as db:
            phase_d.setup_workspace(db, [doc, phase_d.document(name="Second policy")])
        prefix = "/api/v2"
        headers = {"If-Match": bridge.get("/api/v2/workspace/policy-state").headers["etag"]}
    else:
        row = bridge.post("/api/policies", json=doc.model_dump()).json()
        for operation in ["submit", "approve", "publish", "activate"]:
            assert bridge.post(f"/api/policies/{row['id']}/{operation}").status_code == 200
        prefix, headers = "/api", {}
    generate = AsyncMock(return_value="public response")
    monkeypatch.setattr(providers, "generate_ai_response", generate)
    result = bridge.post(prefix + "/governance/generate-document", json=payload(kind, "private finance"), headers=headers)
    assert result.status_code == 200, result.text
    body = result.json()
    assert body["decision"] == action and generate.await_count == calls
    assert body["attachment"]["type"] == kind
    if calls:
        assert "private finance" not in generate.await_args.args[0]
        assert "[REDACTED]" in generate.await_args.args[0]
        assert body["output"] is not None and body["safe_response"] == "public response"
    else:
        assert body["safe_response"] is None
    model = Execution006 if mode == "MULTI" else Execution
    with Session(engine006) as db:
        row = db.scalar(select(model))
        metadata = json.loads(row.metadata_json)
        assert metadata["attachment"] == body["attachment"]
        assert "private finance" not in row.metadata_json and "synthetic." not in row.metadata_json
        if mode == "MULTI":
            assert db.scalar(select(func.count()).select_from(ExecutionPolicyEvidence)) == 2
    bridge.headers["Authorization"] = "Bearer foreign"
    assert bridge.get("/api/v2/audit/executions/" + body["request_id"]).status_code == 404


def test_invalid_upload_and_permissions_never_dispatch(client, monkeypatch):
    generate = AsyncMock()
    monkeypatch.setattr(providers, "generate_ai_response", generate)
    assert client.post("/api/governance/generate-document", json=payload("pdf", raw=b"corrupt")).status_code == 422
    client.headers["Authorization"] = "Bearer reviewer"
    assert client.post("/api/governance/generate-document", json=payload()).status_code == 403
    client.headers.pop("Authorization")
    assert client.post("/api/governance/generate-document", json=payload()).status_code == 401
    generate.assert_not_awaited()


def test_upload_rate_limit_and_body_limit(client):
    for _ in range(5):
        assert client.post("/api/governance/generate-document", json=payload("pdf", raw=b"bad")).status_code == 422
    assert client.post("/api/governance/generate-document", json=payload("pdf", raw=b"bad")).status_code == 429
    assert client.post("/api/governance/generate-document", content=b"x" * (upload.UPLOAD_BODY_LIMIT + 1)).status_code == 413
    assert client.post("/api/governance/generate", content=b"x" * 64001).status_code == 413


def test_multi_preconditions_before_extraction_or_reservation(bridge, engine006, monkeypatch):
    with Session(engine006, expire_on_commit=False) as db:
        phase_d.setup_workspace(db, [policy("BLOCK")])
    extractor = AsyncMock(side_effect=AssertionError("No extraction"))
    monkeypatch.setattr(upload, "extract", extractor)
    for header, code in [(None, 428), ('"999"', 412), ('W/"2"', 412)]:
        result = bridge.post("/api/v2/governance/generate-document", json=payload(), headers={"If-Match": header} if header else {})
        assert result.status_code == code
    assert bridge.post("/api/governance/generate-document", json=payload()).status_code == 409
    extractor.assert_not_awaited()
    with Session(engine006) as db:
        assert db.scalar(select(func.count()).select_from(InferenceUsage)) == 0


@pytest.mark.parametrize("mode", ["LEGACY", "MULTI"])
@pytest.mark.parametrize("failure", ["output_block", "ambiguous_generation", "fenced"])
def test_output_gate_no_retry_and_reservation_fencing(bridge, engine006, monkeypatch, mode, failure):
    doc = policy("BLOCK")
    if mode == "MULTI":
        with Session(engine006, expire_on_commit=False) as db:
            phase_d.setup_workspace(db, [doc])
        prefix = "/api/v2"
        headers = {"If-Match": bridge.get("/api/v2/workspace/policy-state").headers["etag"]}
    else:
        row = bridge.post("/api/policies", json=doc.model_dump()).json()
        for operation in ["submit", "approve", "publish", "activate"]:
            assert bridge.post(f"/api/policies/{row['id']}/{operation}").status_code == 200
        prefix, headers = "/api", {}

    async def generate(_text):
        if failure == "ambiguous_generation":
            raise providers.ProviderUnavailable("synthetic ambiguous response")
        if failure == "fenced":
            with Session(engine006) as db:
                reservation = db.scalar(select(InferenceUsage).where(InferenceUsage.status == "RESERVED"))
                reservation.expires = "2000-01-01T00:00:00+00:00"
                db.commit()
            return "Unreleasable generated output"
        return "private finance"
    provider = AsyncMock(side_effect=generate)
    monkeypatch.setattr(providers, "generate_ai_response", provider)
    result = bridge.post(prefix + "/governance/generate-document", json=payload(), headers=headers)
    assert provider.await_count == 1
    if failure == "fenced":
        assert result.status_code == 409 and "Unreleasable" not in result.text
    else:
        assert result.status_code == 200 and result.json()["decision"] == "BLOCK"
        assert result.json()["safe_response"] is None


def test_sso_csrf_protects_document_endpoint(bridge, engine006, monkeypatch):
    import httpx
    from urllib.parse import urlsplit, parse_qs
    from app import sso
    from app.config import settings
    from app.models import SsoMembership
    directory = "11111111-1111-4111-8111-111111111111"
    oid = "33333333-3333-4333-8333-333333333333"
    for key, value in {"sso_enabled": True, "demo_browser_login_enabled": False, "entra_tenant_id": directory,
        "entra_client_id": "22222222-2222-4222-8222-222222222222", "entra_client_secret": "synthetic-only", "sso_public_origin": "https://testserver"}.items():
        monkeypatch.setattr(settings, key, value)
    with Session(engine006) as db:
        db.add(SsoMembership(directory_tenant=directory, object_id=oid, tenant="one", actor="admin", role="Admin"))
        db.commit()
    monkeypatch.setattr(sso, "metadata", AsyncMock(return_value={"authorization_endpoint": f"https://login.microsoftonline.com/{directory}/oauth2/v2.0/authorize"}))
    monkeypatch.setattr(sso, "exchange_code", AsyncMock(return_value={"tid": directory, "oid": oid}))
    bridge.headers.pop("Authorization")
    bridge.base_url = httpx.URL("https://testserver")
    login = bridge.get("/api/sso/login", follow_redirects=False)
    state = parse_qs(urlsplit(login.headers["location"]).query)["state"][0]
    assert bridge.get("/api/sso/callback", params={"state": state, "code": "synthetic"}, follow_redirects=False).status_code == 303
    csrf = bridge.get("/api/sso/me").json()["csrf_token"]
    extractor = AsyncMock(side_effect=HTTPException(422, "Synthetic extraction failure"))
    monkeypatch.setattr(upload, "extract", extractor)
    for prefix in ["/api", "/api/v2"]:
        path = prefix + "/governance/generate-document"
        assert bridge.post(path, json=payload()).status_code == 403
        assert bridge.post(path, json=payload(), headers={"X-CSRF-Token": csrf, "Origin": "https://foreign.invalid"}).status_code == 403
    assert bridge.post("/api/governance/generate-document", json=payload(), headers={"X-CSRF-Token": csrf, "Origin": "https://testserver"}).status_code == 422
    extractor.assert_awaited_once()


async def test_docx_headers_are_inspected_and_unknown_text_is_rejected():
    header = '<w:hdr xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:p><w:r><w:t>private finance</w:t></w:r></w:p></w:hdr>'
    text, _ = await upload.extract(upload.DocumentRequest(**payload("docx", raw=docx(extra={"word/header1.xml": header}))))
    assert "private finance" in text.text
    unknown = '<unsupported>private finance</unsupported>'
    with pytest.raises(HTTPException):
        await upload.extract(upload.DocumentRequest(**payload("docx", raw=docx(extra={"word/header1.xml": unknown}))))


async def test_pdf_image_content_and_page_limit_are_rejected():
    writer = PdfWriter()
    page = writer.add_blank_page(300, 300)
    image = DecodedStreamObject()
    image.set_data(b"\x00\x00\x00")
    image.update({NameObject("/Type"): NameObject("/XObject"), NameObject("/Subtype"): NameObject("/Image")})
    page[NameObject("/Resources")] = DictionaryObject({NameObject("/XObject"): DictionaryObject({NameObject("/Im1"): writer._add_object(image)})})
    output = io.BytesIO()
    writer.write(output)
    with pytest.raises(HTTPException, match="image content"):
        await upload.extract(upload.DocumentRequest(**payload("pdf", raw=output.getvalue())))
    writer = PdfWriter()
    for _ in range(21):
        writer.add_blank_page(300, 300)
    output = io.BytesIO()
    writer.write(output)
    with pytest.raises(HTTPException, match="1 to 20 pages"):
        await upload.extract(upload.DocumentRequest(**payload("pdf", raw=output.getvalue())))


async def test_cancelled_extraction_kills_worker_and_releases_capacity(monkeypatch):
    class Cancelled:
        returncode = None
        killed = False
        async def communicate(self, data):
            raise asyncio.CancelledError()
        def kill(self):
            self.killed = True
            self.returncode = -9
        async def wait(self):
            return self.returncode
    process = Cancelled()
    monkeypatch.setattr(asyncio, "create_subprocess_exec", AsyncMock(return_value=process))
    with pytest.raises(asyncio.CancelledError):
        await upload.extract(upload.DocumentRequest(**payload()))
    assert process.killed
    assert upload.SLOTS.acquire(False) and upload.SLOTS.acquire(False)
    upload.SLOTS.release()
    upload.SLOTS.release()
