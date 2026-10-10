"""PostgreSQL foundation and source-preserving synthetic CSV importer."""
import argparse
import csv
import hashlib
import io
import json
import os
import re
from collections import Counter
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

FIELDS = ['Session_ID', 'Timestamp', 'Vehicle_Model', 'Region', 'Trim_Package',
          'Option_Codes_Viewed', 'Option_Codes_Selected', 'Configurator_Dropoff_Point',
          'Package_Attach_Success', 'Causality_Score']
MARKETS = {'Europe_DE': 'DE', 'Europe_UK': 'GB', 'North_America_US': 'US', 'Asia_CN': 'CN'}
PARSER_VERSION = '1.0.0'
GAPS = {'generator': None, 'prompt': None, 'sampling_method': None,
        'score_definition': None, 'timestamp_meaning': None, 'package_attachment_rule': None}


def validate(path):
    content = Path(path).read_bytes()
    reader = csv.DictReader(io.StringIO(content.decode('utf-8-sig'), newline=''))
    if reader.fieldnames != FIELDS:
        raise ValueError('CSV header must match the documented ten columns in order')
    rows = []
    for number, raw in enumerate(reader, 2):
        issues = []
        parsed = {}
        if None in raw or any(v is None or v == '' for v in raw.values()):
            issues.append('missing or extra cells')
        try:
            ts = datetime.fromisoformat(raw['Timestamp'].replace('Z', '+00:00'))
            if ts.tzinfo is None or ts.utcoffset() is None:
                raise ValueError('timestamp has no timezone')
            parsed['timestamp'] = ts
        except (ValueError, AttributeError):
            issues.append('invalid timezone-aware timestamp')
        for name in ['Option_Codes_Viewed', 'Option_Codes_Selected']:
            try:
                codes = json.loads(raw[name])
                if not isinstance(codes, list) or any(not isinstance(x, str) or not re.fullmatch(r'SA[A-Za-z0-9]+', x) for x in codes):
                    raise ValueError('invalid option array')
                if len(set(codes)) != len(codes):
                    raise ValueError('repeated option code')
                parsed[name] = codes
            except (TypeError, ValueError):
                issues.append('invalid JSON option array: ' + name)
        if all(k in parsed for k in ['Option_Codes_Selected', 'Option_Codes_Viewed']):
            if not set(parsed['Option_Codes_Selected']) <= set(parsed['Option_Codes_Viewed']):
                issues.append('selected option absent from viewed list')
        if raw['Package_Attach_Success'] not in ('True', 'False'):
            issues.append('invalid boolean; expected True or False')
        try:
            score = Decimal(raw['Causality_Score'])
            if not score.is_finite():
                raise ValueError('non-finite score')
            parsed['score'] = score
        except (InvalidOperation, ValueError, TypeError):
            issues.append('invalid finite numeric score')
        if raw['Vehicle_Model'] not in ('F70', 'G60', 'G70'):
            issues.append('unsupported model; review mapping')
        if raw['Region'] not in MARKETS:
            issues.append('unreviewed market alias')
        if raw['Trim_Package'] not in ('Base', 'M_Sport', 'M_Performance'):
            issues.append('unknown source trim label')
        rows.append({'row': number, 'raw': raw, 'parsed': parsed, 'issues': issues})
    ids = Counter(r['raw']['Session_ID'] for r in rows)
    for row in rows:
        if ids[row['raw']['Session_ID']] > 1:
            row['issues'].append('duplicate external ID within dataset version')
    valid = [r for r in rows if not r['issues']]
    report = {'sha256': hashlib.sha256(content).hexdigest(), 'data_origin': 'synthetic',
              'parser_version': PARSER_VERSION, 'rows': len(rows), 'valid_sessions': len(valid),
              'quarantined_rows': len(rows)-len(valid), 'unknown_definitions': GAPS,
              'models': dict(Counter(r['raw']['Vehicle_Model'] for r in valid)),
              'final_stages': dict(Counter(r['raw']['Configurator_Dropoff_Point'] for r in valid)),
              'option_views': sum(len(r['parsed']['Option_Codes_Viewed']) for r in valid),
              'option_selections': sum(len(r['parsed']['Option_Codes_Selected']) for r in valid),
              'issues': [{'row': r['row'], 'reasons': r['issues']} for r in rows if r['issues']]}
    scores = [r['parsed']['score'] for r in valid]
    times = [r['parsed']['timestamp'] for r in valid]
    report.update({'distinct_option_codes': len({c for r in valid for c in r['parsed']['Option_Codes_Viewed']}),
                   'package_attach': dict(Counter(r['raw']['Package_Attach_Success'] for r in valid)),
                   'score_min': str(min(scores)) if scores else None,
                   'score_max': str(max(scores)) if scores else None,
                   'scores_above_30': sum(s > 30 for s in scores),
                   'timestamp_min': min(times).isoformat() if times else None,
                   'timestamp_max': max(times).isoformat() if times else None})
    return rows, report


def connect():
    import psycopg
    dsn = os.environ.get('BMW_DATABASE_URL')
    if not dsn:
        raise ValueError('Set BMW_DATABASE_URL to an isolated development database')
    return psycopg.connect(dsn)


def migrate(conn):
    with conn.transaction(), conn.cursor() as cur:
        cur.execute("SELECT pg_advisory_xact_lock(709102026)")
        cur.execute('CREATE TABLE IF NOT EXISTS schema_migrations (name text PRIMARY KEY, sha256 text NOT NULL, applied_at timestamptz NOT NULL DEFAULT now())')
        for path in sorted((Path(__file__).parent / 'database/migrations').glob('*.sql')):
            raw = path.read_bytes()
            canonical = raw.replace(b'\r\n', b'\n')
            digest = hashlib.sha256(canonical).hexdigest()
            # Older ledgers used raw bytes. Accept only the same SQL with Git's
            # LF/CRLF conversion; preserve historical ledger values unchanged.
            compatible = {hashlib.sha256(x).hexdigest() for x in
                          (raw, canonical, canonical.replace(b'\n', b'\r\n'))}
            cur.execute('SELECT sha256 FROM schema_migrations WHERE name=%s', (path.name,))
            previous = cur.fetchone()
            if previous:
                if previous[0] not in compatible:
                    raise ValueError('Previously applied migration changed: ' + path.name)
                continue
            cur.execute(path.read_text(encoding='utf-8'))
            cur.execute('INSERT INTO schema_migrations(name,sha256) VALUES (%s,%s)', (path.name, digest))


def import_csv(conn, path, namespace='bmw.synthetic.configurator'):
    from psycopg.types.json import Jsonb
    rows, report = validate(path)
    # Keep a content-addressed original outside PostgreSQL; hash again to detect
    # concurrent source edits between validation and archival.
    content = Path(path).read_bytes()
    if hashlib.sha256(content).hexdigest() != report['sha256']:
        raise ValueError('Source changed during validation')
    archive = Path(__file__).parent / 'data/assets' / report['sha256']
    archive.parent.mkdir(parents=True, exist_ok=True)
    try:
        with archive.open('xb') as dest:
            dest.write(content)
    except FileExistsError:
        if archive.read_bytes() != content:
            raise ValueError('Archived asset does not match source hash')
    with conn.transaction(), conn.cursor() as cur:
        cur.execute('SELECT pg_advisory_xact_lock(709102027)')
        cur.execute("INSERT INTO datasets(namespace,evidence_kind) VALUES (%s,'configurator_session') ON CONFLICT(namespace) DO NOTHING", (namespace,))
        cur.execute('SELECT id,evidence_kind FROM datasets WHERE namespace=%s', (namespace,))
        dataset, kind = cur.fetchone()
        if kind != 'configurator_session':
            raise ValueError('Dataset namespace has incompatible evidence kind')
        cur.execute('INSERT INTO source_assets(sha256,original_filename,original_location,storage_path) VALUES (%s,%s,%s,%s) ON CONFLICT(sha256) DO NOTHING', (report['sha256'], Path(path).name, str(Path(path).resolve()),str(archive.resolve())))
        cur.execute('SELECT id FROM source_assets WHERE sha256=%s', (report['sha256'],))
        asset = cur.fetchone()[0]
        cur.execute("INSERT INTO dataset_versions(dataset_id,asset_id,data_origin) VALUES (%s,%s,'synthetic') ON CONFLICT(dataset_id,asset_id) DO NOTHING RETURNING id", (dataset, asset))
        created = cur.fetchone()
        if not created:
            cur.execute('SELECT id,data_origin FROM dataset_versions WHERE dataset_id=%s AND asset_id=%s', (dataset, asset))
            version, origin = cur.fetchone()
            if origin != 'synthetic':
                raise ValueError('Existing dataset version has incompatible origin')
            return {**report, 'version_id': version, 'reimport': True}
        version = created[0]
        cur.execute('INSERT INTO scenarios(version_id,assumptions) VALUES (%s,%s) RETURNING id', (version, Jsonb(GAPS)))
        scenario = cur.fetchone()[0]
        cur.execute("INSERT INTO ingestion_runs(asset_id,version_id,parser_version,status) VALUES (%s,%s,%s,'running') RETURNING id", (asset, version, PARSER_VERSION))
        run = cur.fetchone()[0]
        duplicate_ids = Counter(r['raw']['Session_ID'] for r in rows)
        for row in rows:
            raw, parsed = row['raw'], row['parsed']
            external = raw['Session_ID'] if duplicate_ids[raw['Session_ID']] == 1 else None
            cur.execute('INSERT INTO source_records(version_id,record_number,external_id,raw_payload) VALUES (%s,%s,%s,%s) RETURNING id', (version, row['row'], external, Jsonb(raw)))
            record = cur.fetchone()[0]
            cur.execute('INSERT INTO evidence_locations(record_id,row_number) VALUES (%s,%s)', (record,row['row']))
            for reason in row['issues']:
                cur.execute('INSERT INTO validation_issues(run_id,record_id,code,reason) VALUES (%s,%s,%s,%s)', (run,record,'csv_validation',reason))
            if row['issues']:
                continue
            cur.execute('SELECT market_code FROM market_aliases WHERE alias=%s', (raw['Region'],))
            market = cur.fetchone()[0]
            cur.execute('''INSERT INTO configurator_sessions(version_id,source_record_id,scenario_id,external_id,source_timestamp,raw_timestamp,model_code,market_code,raw_region,trim_label,final_stage,package_attach_success,raw_synthetic_score,raw_viewed,raw_selected)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id''',
                (version, record, scenario, raw['Session_ID'], parsed['timestamp'], raw['Timestamp'], raw['Vehicle_Model'], market, raw['Region'], raw['Trim_Package'], raw['Configurator_Dropoff_Point'], raw['Package_Attach_Success']=='True', parsed['score'], Jsonb(parsed['Option_Codes_Viewed']), Jsonb(parsed['Option_Codes_Selected'])))
            session = cur.fetchone()[0]
            cur.executemany('INSERT INTO configurator_session_options(session_id,option_code,selected) VALUES (%s,%s,%s)', [(session,code,code in parsed['Option_Codes_Selected']) for code in parsed['Option_Codes_Viewed']])
        cur.execute('UPDATE ingestion_runs SET status=%s,finished_at=now(),report=%s WHERE id=%s', ('quarantined' if report['issues'] else 'succeeded', Jsonb(report), run))
    return {**report, 'version_id': version, 'reimport': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['migrate','validate','import'])
    parser.add_argument('path', nargs='?')
    parser.add_argument('--report', type=Path)
    args = parser.parse_args()
    if args.command != 'migrate' and not args.path:
        parser.error('CSV path required')
    if args.command == 'validate':
        result = validate(args.path)[1]
    else:
        with connect() as conn:
            result = migrate(conn) if args.command == 'migrate' else import_csv(conn,args.path)
    output = json.dumps(result, indent=2)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(output+'\n',encoding='utf-8')
    print(output)
    if isinstance(result,dict) and result.get('issues'):
        raise SystemExit(2)


if __name__ == '__main__':
    main()
