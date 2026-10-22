"""Validate bounded refusal observations, not whole-state rollback correctness."""
import argparse
import json
from pathlib import Path
import re

COUNTERS = ('metadata_spans', 'metadata_changed', 'pages', 'page_changed',
            'unread_before', 'unread_after', 'os_pages', 'os_changed', 'os_unread')
FIELDS = {'v', 'frame', 'outcome', 'complete', 'holds', 'authoritative', *COUNTERS}


def analyze_auxiliary(lines, native=False, payload=False):
    records, errors = [], []
    label = 'payload' if payload else 'native' if native else 'CB'
    marker = 'FIBER_PAYLOAD_REFUSAL_AUDIT' if payload else 'NATIVE_REFUSAL_AUDIT' if native else 'CB_REFUSAL_AUDIT'
    holds = 'unproven' if native or payload else 'registry_membership_only'
    counts = (('targets', 'observed', 'excluded', 'stacks', 'stack_bytes', 'fls', 'revalidated') if payload else
              ('threads', 'fibers', 'contexts') if native else ('objects',)) + ('spans', 'changed', 'unread_before', 'unread_after')
    expected = {'v', 'frame', 'outcome', 'complete', 'holds', 'authoritative', *counts}
    for number, raw in enumerate(lines, 1):
        if marker not in raw:
            continue
        try:
            prefix = 'r1: ' + marker + ' '
            if not raw.startswith(prefix):
                raise ValueError('invalid CB audit prefix')
            pairs = [token.split('=', 1) for token in raw[len(prefix):].strip().split()]
            if any(len(pair) != 2 for pair in pairs):
                raise ValueError('invalid CB audit field')
            record = dict(pairs)
            if len(record) != len(pairs) or set(record) != expected:
                raise ValueError('missing, duplicate or unknown CB audit fields')
            if record['v'] != '1' or record['holds'] != holds or record['authoritative'] != '0':
                raise ValueError('unsupported CB version or authority claim')
            if record['outcome'] not in ('refused', 'commit_not_checked') or record['complete'] not in ('0', '1'):
                raise ValueError('invalid CB audit outcome/completeness')
            for name in ('frame', 'complete', *counts):
                if not re.fullmatch(r'\d+', record[name]):
                    raise ValueError(f'invalid CB {name}')
                record[name] = int(record[name])
            records.append(record)
            if record['outcome'] != 'refused' or not record['complete']:
                raise ValueError('CB refusal not completely compared')
            if payload:
                if not (0 < record['targets'] == record['observed'] <= 1024 and
                        record['targets'] + record['excluded'] <= 1024 and
                        record['stacks'] <= record['targets'] and record['fls'] <= record['targets'] and
                        record['stacks'] <= record['stack_bytes'] <= 64 * 1024 * 1024 and
                        (record['stacks'] > 0 or record['stack_bytes'] == 0) and record['revalidated'] == 1 and
                        record['spans'] == 2 * record['observed'] + record['stacks'] + record['fls']):
                    raise ValueError('empty or inconsistent payload coverage')
            elif native:
                if not (0 < record['contexts'] <= record['threads'] <= 256 and
                        0 < record['fibers'] <= 1024 and
                        record['spans'] == 3 + 5 * record['threads'] + 11 * record['fibers'] + record['contexts']):
                    raise ValueError('empty or inconsistent native coverage')
            elif not 0 < record['objects'] <= record['spans']:
                raise ValueError('empty or inconsistent CB coverage')
            if any(record[key] for key in ('changed', 'unread_before', 'unread_after')):
                raise ValueError('changed or unread CB state')
        except ValueError as error:
            errors.append({'line': number, 'message': str(error).replace('CB', label)})
    if len(records) > 1:
        errors.append({'line': 0, 'message': f'multiple {label} records for a one-attempt audit'})
    return records, errors


def analyze(lines, require_cb=False, require_native=False, require_payload=False):
    lines = list(lines)
    records, errors = [], []
    for number, raw in enumerate(lines, 1):
        if 'RESTORE_REFUSAL_AUDIT' not in raw:
            continue
        try:
            prefix = 'r1: RESTORE_REFUSAL_AUDIT '
            if not raw.startswith(prefix):
                raise ValueError('invalid audit prefix')
            tokens = raw[len(prefix):].strip().split()
            pairs = [token.split('=', 1) for token in tokens]
            if any(len(pair) != 2 for pair in pairs):
                raise ValueError('invalid audit field')
            record = dict(pairs)
            expected = FIELDS | ({'absent_before', 'absent_after'} if record.get('v') == '2' else set())
            if len(record) != len(pairs) or set(record) != expected:
                raise ValueError('missing, duplicate or unknown audit fields')
            if record['v'] not in ('1', '2') or record['holds'] != 'unproven' or record['authoritative'] != '0':
                raise ValueError('unsupported version or authority claim')
            if record['outcome'] not in ('refused', 'commit_not_checked'):
                raise ValueError('unknown audit outcome')
            if record['complete'] not in ('0', '1'):
                raise ValueError('invalid completeness flag')
            absent_fields = ('absent_before', 'absent_after') if record['v'] == '2' else ()
            for name in ('frame', *COUNTERS, *absent_fields):
                if not re.fullmatch(r'\d+', record[name]):
                    raise ValueError(f'invalid {name}')
                record[name] = int(record[name])
            record['complete'] = int(record['complete'])
            for changed, total in (('metadata_changed', 'metadata_spans'),
                                   ('page_changed', 'pages'), ('os_changed', 'os_pages')):
                if record[changed] > record[total]:
                    raise ValueError(f'{changed} exceeds {total}')
            for unread in ('unread_before', 'unread_after'):
                if record[unread] > record['metadata_spans'] + record['pages']:
                    raise ValueError(f'{unread} exceeds byte-span coverage')
            for absent in absent_fields:
                if record[absent] > record['pages']:
                    raise ValueError(f'{absent} exceeds page coverage')
            for side in ('before', 'after'):
                if record['unread_' + side] + record.get('absent_' + side, 0) > record['metadata_spans'] + record['pages']:
                    raise ValueError('absent and unread counts exceed byte-span coverage')
            records.append(record)
            if record['outcome'] == 'refused':
                if not record['complete']:
                    raise ValueError('incomplete refusal coverage')
                if not record['metadata_spans'] or not record['pages'] or not record['os_pages']:
                    raise ValueError('empty refusal coverage')
                if not record['pages'] <= record['os_pages'] <= 2 * record['pages']:
                    raise ValueError('OS observations do not cover logical destination pages')
                if any(record[key] for key in ('metadata_changed', 'page_changed',
                                              'unread_before', 'unread_after', 'os_changed', 'os_unread')):
                    raise ValueError('changed or unread refusal state')
                if record.get('absent_before', 0) != record.get('absent_after', 0):
                    raise ValueError('reserved-page absence changed')
            elif record['complete']:
                raise ValueError('successful commit is not a refusal comparison')
        except ValueError as error:
            errors.append({'line': number, 'message': str(error)})
    refused = sum(record['outcome'] == 'refused' for record in records)
    if len(records) > 1:
        errors.append({'line': 0, 'message': 'multiple records for a one-attempt audit'})
    if not refused:
        errors.append({'line': 0, 'message': 'no refused attempt audited'})
    cb_records, cb_errors = analyze_auxiliary(lines)
    errors.extend(cb_errors)
    if require_cb and not cb_records:
        errors.append({'line': 0, 'message': 'required CB refusal audit missing'})
    if cb_records and (len(records) != 1 or len(cb_records) != 1 or
                       cb_records[0]['frame'] != records[0]['frame'] or records[0]['outcome'] != 'refused'):
        errors.append({'line': 0, 'message': 'CB and ring refusal attempts do not match'})
    native_records, native_errors = analyze_auxiliary(lines, native=True)
    errors.extend(native_errors)
    if require_native and not native_records:
        errors.append({'line': 0, 'message': 'required native refusal audit missing'})
    if native_records and (len(records) != 1 or len(native_records) != 1 or
                           native_records[0]['frame'] != records[0]['frame'] or records[0]['outcome'] != 'refused'):
        errors.append({'line': 0, 'message': 'native and ring refusal attempts do not match'})
    payload_records, payload_errors = analyze_auxiliary(lines, payload=True)
    errors.extend(payload_errors)
    if require_payload and not payload_records:
        errors.append({'line': 0, 'message': 'required fiber payload refusal audit missing'})
    if payload_records and (len(records) != 1 or len(payload_records) != 1 or
                            payload_records[0]['frame'] != records[0]['frame'] or records[0]['outcome'] != 'refused'):
        errors.append({'line': 0, 'message': 'payload and ring refusal attempts do not match'})
    return {'status': 'failed' if errors else 'bounded_refusal_observation_passed',
            'records': records, 'cb_records': cb_records, 'cb_required': require_cb,
            'native_records': native_records, 'native_required': require_native,
            'payload_records': payload_records, 'payload_required': require_payload,
            'errors': errors, 'refused_attempts': refused,
            'gameplay_certified': False, 'quiescence': 'unproven',
            'scope': 'reported ring metadata and planned destination bytes or verified reservation, plus protections'
                     + ('; recorded live/staging command-buffer identities, metadata and active payloads' if cb_records else '')
                     + ('; selected native bookkeeping and held guest contexts' if native_records else '')
                     + ('; selected suspended fiber payload bytes' if payload_records else '')}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('log', type=Path)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--require-cb', action='store_true', help='Require a complete live/staging CB audit for the same refusal')
    parser.add_argument('--require-native', action='store_true', help='Require a complete native bookkeeping audit for the same refusal')
    parser.add_argument('--require-payload', action='store_true', help='Require a complete suspended fiber payload audit for the same refusal')
    args = parser.parse_args()
    result = analyze(args.log.read_text(encoding='utf-8', errors='replace').splitlines(), require_cb=args.require_cb, require_native=args.require_native, require_payload=args.require_payload)
    payload = json.dumps(result, indent=2) + '\n'
    if args.output:
        args.output.write_text(payload, encoding='utf-8')
    print(payload, end='')
    return int(bool(result['errors']))


if __name__ == '__main__':
    raise SystemExit(main())
