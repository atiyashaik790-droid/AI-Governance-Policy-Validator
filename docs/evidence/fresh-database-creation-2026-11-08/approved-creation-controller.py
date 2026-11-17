"""One approved persistent database. No data-plane, site writes, deletion or PUT retry."""
import argparse
import hashlib
import json
import os
import re
import subprocess
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError

ROOT = Path('/home/sigmoid/AI governance policy validator')
OUT = ROOT / 'docs/evidence/fresh-database-creation-2026-11-08'
SUB = '25ddf5d2-6e0b-4a34-82fc-bfc91415e7a6'
RG = 'rg_techdemo_Atiya_Tabsum_Shaik'
SERVER = 'sql-governance-validator-dev-atiya'
DB = 'sqldb-gpv-demo-v008-20261108'
APP = 'app-governance-validator-atiya-1026'
BASE = f'https://management.azure.com/subscriptions/{SUB}/resourceGroups/{RG}/providers'
SERVER_URL = BASE + '/Microsoft.Sql/servers/' + SERVER
TARGET = SERVER_URL + '/databases/' + DB
SOURCE = SERVER_URL + '/databases/sqldb-governance-validator-dev'
SITE = BASE + '/Microsoft.Web/sites/' + APP
API = '?api-version=2023-08-01'
JOURNAL = OUT / 'result.json'
STATE = {}
TOKEN = None


def now():
    return datetime.now(timezone.utc).isoformat()


def save(event=None, **fields):
    STATE.update(fields)
    if event:
        STATE.setdefault('events', []).append({'utc': now(), 'event': event})
    OUT.mkdir(parents=True, exist_ok=True)
    temp = JOURNAL.with_suffix('.tmp')
    with temp.open('w') as handle:
        json.dump(STATE, handle, indent=2)
        handle.write('\n')
        handle.flush()
        os.fsync(handle.fileno())
    temp.replace(JOURNAL)
    print(json.dumps({'utc': now(), 'event': event, **fields}), flush=True)


def cli(args):
    env = dict(os.environ, AZURE_CONFIG_DIR=str(ROOT / '.azure-sql-cli'))
    result = subprocess.run(['az', *args, '--only-show-errors'], env=env,
                            capture_output=True, text=True, timeout=30)
    if result.returncode:
        raise RuntimeError('AZURE_CLI_FAILED')
    return result.stdout.strip()


def authenticate():
    global TOKEN
    account = json.loads(cli(['account', 'show', '-o', 'json', '--query',
                             '{id:id,name:name,tenantId:tenantId,state:state}']))
    if account != {'id': SUB, 'name': 'Devops_Azure_SV',
                   'tenantId': '4ac50105-0c66-404e-a107-7cbd8a9a6442', 'state': 'Enabled'}:
        raise RuntimeError('SUBSCRIPTION_MISMATCH')
    TOKEN = cli(['account', 'get-access-token', '--subscription', SUB,
                 '--resource', 'https://management.azure.com/', '--query', 'accessToken', '-o', 'tsv'])
    return account


def arm(url, method='GET', payload=None, new_only=False):
    if not url.startswith('https://management.azure.com/subscriptions/' + SUB + '/'):
        raise RuntimeError('WRONG_SUBSCRIPTION_URL')
    if method != 'GET' and url not in {TARGET + API, TARGET + '/backupShortTermRetentionPolicies/default' + API}:
        raise RuntimeError('WRITE_TARGET_NOT_ALLOWED')
    headers = {'Authorization': 'Bearer ' + TOKEN}
    if payload is not None:
        headers['Content-Type'] = 'application/json'
    if new_only:
        headers['If-None-Match'] = '*'
    try:
        with urlopen(Request(url, method=method, headers=headers,
                             data=json.dumps(payload).encode() if payload is not None else None), timeout=25) as response:
            raw = response.read()
            body = json.loads(raw) if raw else {}
            return response.status, body, {'request_id': response.headers.get('x-ms-request-id')}
    except HTTPError as error:
        status = error.code
        code = None
        try:
            candidate = json.loads(error.read()).get('error', {}).get('code', '')
            if re.fullmatch(r'[A-Za-z0-9_.-]{1,100}', candidate):
                code = candidate
        except Exception:
            pass
        error.close()
        return status, {}, {'error_code': code}


def required_get(url):
    status, body, _ = arm(url)
    if status != 200:
        raise RuntimeError('ARM_READ_FAILED_' + str(status))
    return body


def absent():
    status, _, _ = arm(TARGET + API)
    if status != 404:
        raise RuntimeError('TARGET_EXISTS_OR_ABSENCE_UNPROVED_' + str(status))
    inventory = required_get(SERVER_URL + '/databases' + API)
    if inventory.get('nextLink'):
        raise RuntimeError('INVENTORY_PAGINATED')
    if any(row['name'].casefold() == DB.casefold() for row in inventory['value']):
        raise RuntimeError('TARGET_PRESENT_IN_INVENTORY')
    return [row['name'] for row in inventory['value']]


def source_snapshot():
    body = required_get(SOURCE + API)
    props = body['properties']
    return {key: body.get(key) for key in ['id', 'name', 'location', 'sku']} | {
        'properties': {key: props.get(key) for key in [
            'databaseId', 'creationDate', 'status', 'collation', 'maxSizeBytes',
            'currentServiceObjectiveName', 'requestedServiceObjectiveName',
            'currentBackupStorageRedundancy', 'requestedBackupStorageRedundancy',
            'elasticPoolId', 'zoneRedundant', 'readScale']},
        'retention': required_get(SOURCE + '/backupShortTermRetentionPolicies/default' + API)['properties']}


def app_snapshot():
    body = required_get(SITE + '?api-version=2024-11-01')
    config = required_get(SITE + '/config/web?api-version=2024-11-01')
    digest = hashlib.sha256(json.dumps(config['properties'], sort_keys=True).encode()).hexdigest()
    return {'id': body['id'], 'state': body['properties']['state'],
            'identity_principal': body['identity']['principalId'],
            'web_config_sha256': digest}


def health():
    checks = {}
    for path in ['/health', '/ready']:
        with urlopen('https://' + APP + '.azurewebsites.net' + path, timeout=20) as response:
            body = json.load(response)
            if response.status != 200 or body.get('status') != ('ok' if path == '/health' else 'ready'):
                raise RuntimeError('HOSTED_HEALTH_FAILED')
            checks[path] = {'http_status': response.status, 'status': body['status']}
            if path == '/ready':
                version = body.get('release', {}).get('build_version')
                revision = body.get('database_revision')
                if version != '1.2-ca5df7c1dc19e525' or revision != '005':
                    raise RuntimeError('HOSTED_BASELINE_CHANGED')
                checks[path].update(release=version, revision=revision)
    return checks


def preflight():
    if JOURNAL.exists():
        raise RuntimeError('EXISTING_CREATION_JOURNAL_REQUIRES_RECONCILIATION')
    account = authenticate()
    subscription = required_get(f'https://management.azure.com/subscriptions/{SUB}/?api-version=2022-12-01')
    if subscription['subscriptionId'] != SUB or subscription['displayName'] != 'Devops_Azure_SV':
        raise RuntimeError('SUBSCRIPTION_RESOURCE_MISMATCH')
    server = required_get(SERVER_URL + API)
    if (server['id'].casefold() != SERVER_URL.removeprefix('https://management.azure.com').casefold()
            or server['name'] != SERVER or server['location'].replace(' ', '').lower() != 'westus2'
            or server['properties']['fullyQualifiedDomainName'] != SERVER + '.database.windows.net'):
        raise RuntimeError('SQL_SERVER_MISMATCH')
    inventory = absent()
    source, app, hosted = source_snapshot(), app_snapshot(), health()
    if app['identity_principal'] != '600447fe-5fea-4801-9033-ab4aafc474cc':
        raise RuntimeError('APP_IDENTITY_MISMATCH')
    save('PREFLIGHT_PASS', status='PREFLIGHT_PASS', subscription=account, server=SERVER,
         target_database=DB, location=server['location'], inventory_before=inventory,
         source_before=source, app_before=app, hosted_before=hosted,
         target_confirmed_absent=True, preflight_utc=now(),
         authorization='USER_APPROVED_PERSISTENT_EMPTY_DATABASE_CREATION_ONLY',
         sql_data_plane_operations=0, webapp_mutations=0, source_database_mutations=0,
         firewall_permission_mutations=0, provider_calls=0,
         requested={'sku': {'name': 'Standard', 'tier': 'Standard', 'capacity': 10},
                    'service_objective': 'S0', 'backup_redundancy': 'Local', 'retention_days': 7,
                    'create_mode': 'Default', 'persistent': True})


def create():
    STATE.update(json.loads(JOURNAL.read_text()))
    if STATE['status'] != 'PREFLIGHT_PASS':
        raise RuntimeError('CREATION_NOT_RETRYABLE')
    if datetime.now(timezone.utc) - datetime.fromisoformat(STATE['preflight_utc']) > timedelta(minutes=5):
        raise RuntimeError('PREFLIGHT_EXPIRED')
    authenticate()
    if source_snapshot() != STATE['source_before'] or app_snapshot() != STATE['app_before']:
        raise RuntimeError('BASELINE_DRIFT')
    absent()  # Immediately recheck before the only creation request.
    payload = {'location': STATE['location'], 'sku': STATE['requested']['sku'], 'properties': {
        'createMode': 'Default', 'requestedServiceObjectiveName': 'S0',
        'requestedBackupStorageRedundancy': 'Local'}}
    save('CREATION_INTENT_DURABLE', status='CREATE_REQUEST_MAY_HAVE_STARTED',
         creation_request_utc=now(), creation_request_body=payload, creation_requests=1)
    # No retry: a transport error must be reconciled with GET, never another PUT.
    status, _, metadata = arm(TARGET + API, 'PUT', payload, new_only=True)
    save('CREATION_HTTP_RESPONSE', creation_http_status=status, creation_response=metadata)
    if status not in {200, 201, 202}:
        raise RuntimeError('CREATE_NOT_ACCEPTED_' + str(status))
    reconcile()


def reconcile():
    if not STATE:
        STATE.update(json.loads(JOURNAL.read_text()))
        authenticate()
    deadline = time.monotonic() + 900
    while True:
        status, body, metadata = arm(TARGET + API)
        if status == 200:
            props = body['properties']
            actual = {'id': body['id'], 'name': body['name'], 'location': body['location'],
                      'sku': body['sku'], 'status': props.get('status'),
                      'database_id': props.get('databaseId'), 'creation_date': props.get('creationDate'),
                      'service_objective': props.get('currentServiceObjectiveName'),
                      'requested_backup_redundancy': props.get('requestedBackupStorageRedundancy'),
                      'current_backup_redundancy': props.get('currentBackupStorageRedundancy')}
            save('TARGET_OBSERVED', actual=actual)
            if (body['id'].casefold() != TARGET.removeprefix('https://management.azure.com').casefold()
                    or body['name'] != DB or body['location'].replace(' ', '').lower() != 'westus2'
                    or body['sku'].get('tier') != 'Standard' or body['sku'].get('capacity') != 10
                    or props.get('requestedServiceObjectiveName') != 'S0'
                    or props.get('requestedBackupStorageRedundancy') != 'Local'):
                raise RuntimeError('PROVISIONED_CONFIGURATION_MISMATCH_NO_AUTOMATIC_CHANGE')
            if props.get('status') == 'Online' and props.get('currentBackupStorageRedundancy') == 'Local':
                break
            if props.get('status') in {'Failed', 'Inaccessible', 'Suspect'}:
                raise RuntimeError('DATABASE_PROVISIONING_FAILED')
        elif status != 404:
            raise RuntimeError('TARGET_RECONCILIATION_READ_FAILED_' + str(status))
        if time.monotonic() >= deadline:
            raise RuntimeError('PROVISIONING_VERIFICATION_TIMED_OUT')
        time.sleep(10)
    policy_url = TARGET + '/backupShortTermRetentionPolicies/default' + API
    policy = required_get(policy_url)
    if policy['properties'].get('retentionDays') != 7:
        if STATE.get('retention_write_attempted'):
            raise RuntimeError('RETENTION_NOT_VERIFIED_NO_RETRY')
        save('RETENTION_INTENT_DURABLE', retention_write_attempted=True)
        status, _, metadata = arm(policy_url, 'PUT', {'properties': {'retentionDays': 7}})
        save('RETENTION_HTTP_RESPONSE', retention_http_status=status, retention_response=metadata)
        if status not in {200, 201, 202}:
            raise RuntimeError('RETENTION_NOT_ACCEPTED')
        for _ in range(12):
            policy = required_get(policy_url)
            if policy['properties'].get('retentionDays') == 7:
                break
            time.sleep(5)
    if policy['properties'].get('retentionDays') != 7:
        raise RuntimeError('RETENTION_VERIFICATION_FAILED')
    inventory = required_get(SERVER_URL + '/databases' + API)
    names = sorted(row['name'] for row in inventory['value'])
    if inventory.get('nextLink') or names != sorted(STATE['inventory_before'] + [DB]):
        raise RuntimeError('INVENTORY_DRIFT')
    source, app, hosted = source_snapshot(), app_snapshot(), health()
    source_same = source == STATE['source_before']
    app_same = app == STATE['app_before']
    save('POSTCHECKS_RECORDED', retention=policy['properties'], inventory_after=names,
         source_after=source, source_metadata_unchanged=source_same,
         app_after=app, app_config_unchanged=app_same, hosted_after=hosted)
    if not source_same or not app_same:
        raise RuntimeError('POSTCHECK_BASELINE_DRIFT')
    due = datetime.fromisoformat(STATE['creation_request_utc']) + timedelta(days=7)
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    start = due.strftime('%Y%m%dT%H%M%SZ')
    end = (due + timedelta(minutes=15)).strftime('%Y%m%dT%H%M%SZ')
    calendar = '\r\n'.join(['BEGIN:VCALENDAR','VERSION:2.0','PRODID:-//GPV//Owner Review//EN',
        'BEGIN:VEVENT','UID:gpv-fresh-database-owner-review-20261108@local', 'DTSTAMP:' + stamp,
        'DTSTART:' + start, 'DTEND:' + end, 'SUMMARY:Review persistent GPV Azure SQL database cost and retention',
        'DESCRIPTION:Review sqldb-gpv-demo-v008-20261108 on sql-governance-validator-dev-atiya. Persistent billed database. No automatic deletion. Any deletion or configuration change needs separate approval.',
        'BEGIN:VALARM','TRIGGER:-PT15M','ACTION:DISPLAY','DESCRIPTION:Owner review due','END:VALARM',
        'END:VEVENT','END:VCALENDAR',''])
    (OUT / 'owner-review.ics').write_bytes(calendar.encode())
    save('VERIFICATION_PASS', status='PASS', verified_utc=now(),
         owner_review_due_utc=due.isoformat(), owner_review_calendar='owner-review.ics',
         reminder_delivery='NOT_INSTALLED_NO_CONNECTED_CALENDAR_SCHEDULER',
         deletion_scheduled=False, empty_database_basis='Default create mode without source or sample; no SQL connections or schema/data writes',
         backup_restore_proof='NOT_PERFORMED')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('mode', choices=['preflight', 'create', 'reconcile'])
    args = parser.parse_args()
    try:
        {'preflight': preflight, 'create': create, 'reconcile': reconcile}[args.mode]()
    except BaseException as error:
        detail = str(error) if isinstance(error, RuntimeError) and re.fullmatch(r'[A-Z0-9_]+', str(error)) else None
        save('STOPPED', status='BLOCKED', failure_type=type(error).__name__, failure_code=detail,
             no_automatic_deletion=True)
        raise SystemExit(1) from None


if __name__ == '__main__':
    main()
