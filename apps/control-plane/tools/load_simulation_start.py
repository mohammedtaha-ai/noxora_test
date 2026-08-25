#!/usr/bin/env python3
"""Local diagnostic load test for the authenticated simulation-start HTTP path.
Not a production benchmark or SLA. Requires a fixture JSON file produced locally.
"""
import argparse
import concurrent.futures
import json
import os
import statistics
import subprocess
import time
import urllib.error
import urllib.request
import uuid


def uuid7() -> str:
    milliseconds = int(time.time() * 1000)
    rand_a = int.from_bytes(os.urandom(2), 'big') & 0x0FFF
    rand_b = int.from_bytes(os.urandom(8), 'big') & ((1 << 62) - 1)
    value = (milliseconds << 80) | (0x7 << 76) | (rand_a << 64) | (0x2 << 62) | rand_b
    return str(uuid.UUID(int=value))


def percentile(values, fraction):
    if not values:
        return None
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, round((len(ordered) - 1) * fraction)))
    return ordered[index]


def connection_count(args):
    command = [
        'psql', '-h', args.db_host, '-p', str(args.db_port), '-U', args.db_user,
        '-d', args.db_name, '-Atc',
        "SELECT count(*) FROM pg_stat_activity WHERE datname = current_database();",
    ]
    env = os.environ.copy()
    env['PGPASSWORD'] = args.db_password
    return int(subprocess.check_output(command, env=env, text=True).strip())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--fixture', required=True)
    parser.add_argument('--base-url', default='http://127.0.0.1:8000')
    parser.add_argument('--requests', type=int, default=40)
    parser.add_argument('--concurrency', type=int, default=8)
    parser.add_argument('--db-host', default='127.0.0.1')
    parser.add_argument('--db-port', type=int, default=5432)
    parser.add_argument('--db-name', default='nexora_control_plane_test')
    parser.add_argument('--db-user', default='nexora_control')
    parser.add_argument('--db-password', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--same-request-id', action='store_true', help='Send one request id concurrently to verify idempotency.')
    args = parser.parse_args()
    fixture = json.load(open(args.fixture, encoding='utf-8'))

    shared_request_id = uuid7()

    def call(_):
        request_id = shared_request_id if args.same_request_id else uuid7()
        body = json.dumps({'assignment_id': fixture['assignment_id'], 'request_id': request_id}).encode()
        request = urllib.request.Request(
            args.base_url + '/api/v1/simulation-start-requests', data=body, method='POST',
            headers={
                'Authorization': 'Bearer ' + fixture['token'],
                'Content-Type': 'application/json',
                'Accept': 'application/json',
                'X-Tenant-Id': fixture['tenant_id'],
                'X-Request-Id': request_id,
            },
        )
        started = time.perf_counter()
        try:
            with urllib.request.urlopen(request, timeout=15) as response:
                code = response.status
                payload = json.loads(response.read())
        except urllib.error.HTTPError as error:
            code = error.code
            payload = {'error': error.read().decode(errors='replace')}
        except Exception as error:
            code = 0
            payload = {'error': repr(error)}
        return (time.perf_counter() - started) * 1000, code, payload

    initial_connections = connection_count(args)
    started = time.perf_counter()
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.concurrency) as pool:
        results = list(pool.map(call, range(args.requests)))
    elapsed = time.perf_counter() - started
    final_connections = connection_count(args)
    latencies = [round(item[0], 3) for item in results]
    status_counts = {}
    for _, code, _ in results:
        status_counts[str(code)] = status_counts.get(str(code), 0) + 1
    summary = {
        'purpose': 'local diagnostic; not a production SLA',
        'path': 'authenticated HTTP simulation-start request -> authorization -> assignment lookup -> PostgreSQL transaction -> outbox insert -> response',
        'requests': args.requests,
        'concurrency': args.concurrency,
        'elapsed_seconds': round(elapsed, 3),
        'rps': round(args.requests / elapsed, 3),
        'latency_ms': {
            'p50': percentile(latencies, 0.50),
            'p95': percentile(latencies, 0.95),
            'p99': percentile(latencies, 0.99),
            'min': min(latencies),
            'max': max(latencies),
        },
        'status_counts': status_counts,
        'errors': sum(count for code, count in status_counts.items() if code not in ('200', '202')),
        'database_connections': {'before': initial_connections, 'after': final_connections},
        'same_request_id': args.same_request_id,
    }
    with open(args.output, 'w', encoding='utf-8') as output:
        json.dump(summary, output, indent=2)
        output.write('\n')
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    main()
