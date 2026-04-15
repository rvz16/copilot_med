import argparse
import json
import os
import sys
from pathlib import Path

import httpx

# Example usage on Windows:
# ..\.venv\Scripts\python.exe scripts\smoke_test_api.py --base-url http://localhost:8080 --chunk-count 2
# ..\.venv\Scripts\python.exe scripts\smoke_test_api.py --help
# ..\.venv\Scripts\python.exe scripts\smoke_test_api.py --audio-file path\to\sample.webm


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Smoke-test the Session Manager API with sample requests.",
    )
    parser.add_argument(
        "--base-url",
        default=os.getenv("SESSION_MANAGER_URL", "http://localhost:8080"),
        help="Session Manager base URL.",
    )
    parser.add_argument("--doctor-id", default="doc_001", help="Doctor identifier.")
    parser.add_argument("--patient-id", default="pat_001", help="Patient identifier.")
    parser.add_argument(
        "--chunk-count",
        type=int,
        default=2,
        help="Number of sequential mock chunks to upload.",
    )
    parser.add_argument(
        "--mime-type",
        default="audio/webm",
        help="MIME type to submit with each upload.",
    )
    parser.add_argument(
        "--audio-file",
        type=Path,
        default=None,
        help="Optional path to a real audio file. If omitted, fake bytes are used.",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=20.0,
        help="HTTP timeout in seconds.",
    )
    return parser.parse_args()


def print_response(label: str, response: httpx.Response) -> dict | list | str | None:
    print(f"\n### {label}")
    print(f"{response.request.method} {response.request.url}")
    print(f"Status: {response.status_code}")

    try:
        body = response.json()
        print(json.dumps(body, indent=2))
    except ValueError:
        body = response.text
        print(body)

    response.raise_for_status()
    return body


def chunk_bytes(args: argparse.Namespace, seq: int) -> bytes:
    if args.audio_file is not None:
        return args.audio_file.read_bytes()
    return f"mock-audio-chunk-{seq}".encode("utf-8")


def main() -> int:
    args = parse_args()
    if args.chunk_count < 1:
        print("--chunk-count must be at least 1.", file=sys.stderr)
        return 2
    if args.audio_file is not None and not args.audio_file.exists():
        print(f"Audio file not found: {args.audio_file}", file=sys.stderr)
        return 2

    base_url = args.base_url.rstrip("/")

    try:
        with httpx.Client(timeout=args.timeout) as client:
            print_response("Health", client.get(f"{base_url}/health"))

            created = print_response(
                "Create Session",
                client.post(
                    f"{base_url}/api/v1/sessions",
                    json={
                        "doctor_id": args.doctor_id,
                        "patient_id": args.patient_id,
                    },
                ),
            )
            assert isinstance(created, dict)
            session_id = created["session_id"]

            for seq in range(1, args.chunk_count + 1):
                is_final = seq == args.chunk_count
                data = {
                    "seq": str(seq),
                    "duration_ms": "4000",
                    "mime_type": args.mime_type,
                    "is_final": str(is_final).lower(),
                }
                files = {
                    "file": (
                        f"chunk-{seq:03d}.webm",
                        chunk_bytes(args, seq),
                        args.mime_type,
                    )
                }
                print_response(
                    f"Upload Chunk {seq}",
                    client.post(
                        f"{base_url}/api/v1/sessions/{session_id}/audio-chunks",
                        data=data,
                        files=files,
                    ),
                )

            print_response(
                "Stop Recording",
                client.post(
                    f"{base_url}/api/v1/sessions/{session_id}/stop",
                    json={"reason": "user_stopped_recording"},
                ),
            )

            print_response(
                "Close Session",
                client.post(
                    f"{base_url}/api/v1/sessions/{session_id}/close",
                    json={"trigger_post_session_analytics": True},
                ),
            )

            print_response(
                "Get Session", client.get(f"{base_url}/api/v1/sessions/{session_id}")
            )
            print_response(
                "List Sessions",
                client.get(
                    f"{base_url}/api/v1/sessions",
                    params={
                        "doctor_id": args.doctor_id,
                        "patient_id": args.patient_id,
                        "limit": 10,
                        "offset": 0,
                    },
                ),
            )
            print_response(
                "Get Transcript",
                client.get(f"{base_url}/api/v1/sessions/{session_id}/transcript"),
            )
            print_response(
                "Get Hints",
                client.get(f"{base_url}/api/v1/sessions/{session_id}/hints"),
            )
            print_response(
                "Get Extractions",
                client.get(f"{base_url}/api/v1/sessions/{session_id}/extractions"),
            )

    except httpx.HTTPError as exc:
        print(f"\nRequest failed: {exc}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
