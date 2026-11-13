"""Reviewed eight-policy lifecycle operations; caller owns target and transaction guards.

No Azure transport, credentials, grants, memberships or automatic execution.
Use an externally owned transaction with Session(join_transaction_mode='rollback_only')
so lifecycle-owned commits cannot leave a partial seed.
"""
import hashlib
import json
from uuid import NAMESPACE_URL, uuid5
from unittest.mock import AsyncMock, patch

from fastapi import HTTPException
from sqlalchemy import select
from app.models import Policy, Version
from app.models_multi_policy import WorkspacePolicyAssignment, WorkspacePolicyState
from app.repositories import record_audit_event
from app.schemas import PolicyDocument
from app.security import Identity
from app.services.policies import get_policy, transition_policy
from app.services.policy_sets import capture, change_assignment, change_mode

TENANT = 'demo-appservice-4e2dcce8d618'
MANIFEST_SHA256 = 'b5b1aea3889a8a42193f7a5058a427cf8da7ed09fdd41fb0437aa5944c72104b'
ADMIN = Identity('atiya-tabsum-shaik', TENANT, 'Admin')


def documents(path):
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != MANIFEST_SHA256:
        raise RuntimeError('REVIEWED_MANIFEST_CHANGED')
    manifest = json.loads(raw)
    if (manifest['database'], manifest['required_revision'], manifest['tenant'], manifest['policy_mode']) != ('sqldb-gpv-demo-v008-20261108', '008', TENANT, 'MULTI'):
        raise RuntimeError('MANIFEST_TARGET_MISMATCH')
    docs = manifest['policies']
    if len(docs) != 8 or len({d['name'] for d in docs}) != 8:
        raise RuntimeError('MANIFEST_COUNT_MISMATCH')
    return [(str(uuid5(NAMESPACE_URL, manifest['profile']+':'+TENANT+':'+d['name'])), PolicyDocument.model_validate(d).model_dump(mode='json')) for d in docs]


def readback(db, reviewed):
    policies = list(db.scalars(select(Policy)))
    versions = list(db.scalars(select(Version)))
    assignments = list(db.scalars(select(WorkspacePolicyAssignment)))
    state = db.get(WorkspacePolicyState, TENANT, populate_existing=True)
    if len(policies) != 8 or len(versions) != 8 or len(assignments) != 8 or not state or state.mode != 'MULTI':
        raise RuntimeError('POLICY_SET_COUNT_OR_MODE_MISMATCH')
    for identifier, document in reviewed:
        policy = db.get(Policy, identifier)
        version = next((v for v in versions if v.policy_id == identifier), None)
        pin = db.get(WorkspacePolicyAssignment, (TENANT, identifier), populate_existing=True)
        if not policy or policy.tenant != TENANT or policy.name != document['name'] or policy.status != 'PUBLISHED' or not policy.enabled or json.loads(policy.draft) != document:
            raise RuntimeError('POLICY_DOCUMENT_OR_STATE_DRIFT')
        if not version or version.tenant != TENANT or version.number != 1 or json.loads(version.document) != document or not pin or not pin.active or pin.version_id != version.id:
            raise RuntimeError('PUBLISHED_VERSION_OR_PIN_DRIFT')
        try:
            get_policy(db, Identity('foreign', 'unapproved-foreign-tenant', 'Admin'), identifier)
        except HTTPException as denied:
            if denied.status_code != 404:
                raise
        else:
            raise RuntimeError('CROSS_TENANT_POLICY_VISIBLE')
    pins = capture(db, ADMIN, state)
    if len(pins) != 8:
        raise RuntimeError('CAPTURE_COUNT_MISMATCH')
    return pins, state.set_revision


def seed(db, reviewed):
    # Existing complete matching seed is read-only; partial or foreign state stops.
    if db.scalar(select(Policy.id).limit(1)) is not None:
        readback(db, reviewed)
        return 0
    if db.scalar(select(Version.id).limit(1)) is not None or db.scalar(select(WorkspacePolicyState.tenant).limit(1)) is not None or db.scalar(select(WorkspacePolicyAssignment.policy_id).limit(1)) is not None:
        raise RuntimeError('UNEXPECTED_PREEXISTING_POLICY_STATE')
    for identifier, document in reviewed:
        db.add(Policy(id=identifier, tenant=TENANT, name=document['name'], draft=json.dumps(document)))
        record_audit_event(db, ADMIN, 'policy.created', identifier)
        db.flush()
        for operation in ('submit', 'approve', 'publish'):
            transition_policy(identifier, operation, db, ADMIN)
        version = db.scalar(select(Version).where(Version.policy_id == identifier, Version.tenant == TENANT))
        state = db.get(WorkspacePolicyState, TENANT, populate_existing=True)
        if state.mode != 'MULTI':
            change_mode(db, ADMIN, 'MULTI', expected_revision=state.set_revision, seed_legacy_assignment=False)
        state = db.get(WorkspacePolicyState, TENANT, populate_existing=True)
        change_assignment(db, ADMIN, identifier, active=True, version_id=version.id, expected_revision=state.set_revision)
    readback(db, reviewed)
    return 8


async def evaluate(pins):
    """Real local evaluation; synthetic moderation, denied HTTP, no persistence."""
    import httpx
    from app import engine_multi_policy as evaluator

    async def coverage(text, required):
        return {name: name == 'violence' and 'synthetic-moderation-flag' in text for name in required}

    cases = [
        ('safe', 'Explain why governance matters.', 'ALLOW'),
        ('pii', 'Email alex@example.test or call +1 202-555-0147.', 'REDACT'),
        ('secret', 'Synthetic api_key=DEMO1234567890NOTREAL', 'BLOCK'),
        ('card', 'Synthetic credit card 4111 1111 1111 1111', 'BLOCK'),
        ('confidential', 'An internal-only synthetic note', 'BLOCK'),
        ('review', 'review-required synthetic request', 'HUMAN_REVIEW'),
        ('moderation_fixture', 'synthetic-moderation-flag', 'BLOCK'),
        ('block_over_review', 'review-required internal-only', 'BLOCK'),
        ('review_over_redact', 'review-required alex@example.test', 'HUMAN_REVIEW'),
    ]
    results = []
    with patch.object(httpx.Client, 'request', side_effect=RuntimeError('EXTERNAL_HTTP_FORBIDDEN')), patch.object(httpx.AsyncClient, 'request', side_effect=RuntimeError('EXTERNAL_HTTP_FORBIDDEN')):
        for label, prompt, expected in cases:
            moderate = AsyncMock(side_effect=coverage)
            with patch.object(evaluator, 'moderation_evidence', moderate):
                result = await evaluator.evaluate_policy_set(prompt, pins)
                reverse = await evaluator.evaluate_policy_set(prompt, list(reversed(pins)))
            if result != reverse or result['decision'] != expected or result['policy_count'] != 8 or len(result['policies']) != 8 or {p['policy_id'] for p in result['policies']} != {p.policy_id for p in pins}:
                raise RuntimeError('SYNTHETIC_DECISION_OR_ATTRIBUTION_MISMATCH')
            if expected == 'REDACT' and (not result['revalidated'] or 'alex@example.test' in result['safe_text'] or '202-555-0147' in result['safe_text']):
                raise RuntimeError('REDACTION_REINSPECTION_FAILED')
            if label in {'secret', 'card', 'confidential', 'block_over_review'} and moderate.call_count:
                raise RuntimeError('LOCAL_BLOCK_DID_NOT_SHORT_CIRCUIT')
            results.append({'case': label, 'decision': expected, 'order_independent': True, 'attribution_count': 8})
        with patch.object(evaluator, 'moderation_evidence', AsyncMock(side_effect=TimeoutError)):
            result = await evaluator.evaluate_policy_set('Explain governance.', pins)
        if result['decision'] != 'BLOCK' or result['safe_text'] is not None:
            raise RuntimeError('MODERATION_FAILURE_NOT_CLOSED')
        results.append({'case': 'moderation_timeout_fixture', 'decision': 'BLOCK', 'content_withheld': True})
    return results
