#!/usr/bin/env python3
"""
Firestore Chat Sessions Export Script
======================================
Exports the entire `chat_sessions` collection from Firestore to a JSON file.

Usage:
    python scripts/export_firestore_chat_sessions.py

Requirements:
    - Firebase Admin SDK: pip install firebase-admin
    - Service account key file (JSON)

Configuration:
    Set the path to your service account key via:
    1. Environment variable: GOOGLE_APPLICATION_CREDENTIALS=/path/to/key.json
    2. Or place the key as: serviceAccountKey.json in the project root

Output:
    outputs/chat_sessions_raw.json
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path

try:
    import firebase_admin
    from firebase_admin import credentials, firestore
except ImportError:
    print("ERROR: firebase-admin package not installed.")
    print("Install it with: pip install firebase-admin")
    sys.exit(1)


def find_service_account_key():
    """
    Locate the Firebase service account key file.

    Priority:
    1. GOOGLE_APPLICATION_CREDENTIALS environment variable
    2. serviceAccountKey.json in project root
    3. firebase-service-account.json in project root
    """
    # Check environment variable first
    env_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    if env_path and os.path.isfile(env_path):
        return env_path

    # Check common locations in project root
    project_root = Path(__file__).parent.parent
    candidates = [
        project_root / "serviceAccountKey.json",
        project_root / "firebase-service-account.json",
        project_root / "service-account.json",
        Path("serviceAccountKey.json"),
        Path("firebase-service-account.json"),
    ]

    for candidate in candidates:
        if candidate.is_file():
            return str(candidate)

    return None


def serialize_firestore_doc(doc_dict):
    """
    Convert Firestore document data to JSON-serializable format.
    Handles Firestore-specific types like Timestamp, GeoPoint, etc.
    """
    def convert_value(val):
        if val is None:
            return None
        if isinstance(val, datetime):
            return val.isoformat()
        if hasattr(val, 'isoformat'):  # Other datetime-like objects
            return val.isoformat()
        if hasattr(val, '_seconds'):  # Firestore Timestamp
            return datetime.fromtimestamp(val._seconds).isoformat()
        if isinstance(val, dict):
            return {k: convert_value(v) for k, v in val.items()}
        if isinstance(val, list):
            return [convert_value(item) for item in val]
        if isinstance(val, (int, float, str, bool)):
            return val
        # Fallback: convert to string
        return str(val)

    return {k: convert_value(v) for k, v in doc_dict.items()}


def export_chat_sessions(output_path=None):
    """
    Export all chat_sessions documents from Firestore.

    Args:
        output_path: Path to output JSON file. Defaults to outputs/chat_sessions_raw.json

    Returns:
        List of session dictionaries
    """
    # Determine output path
    if output_path is None:
        project_root = Path(__file__).parent.parent
        output_dir = project_root / "outputs"
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / "chat_sessions_raw.json"
    else:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

    # Find and validate service account key
    key_path = find_service_account_key()
    if not key_path:
        print("ERROR: Firebase service account key not found.")
        print()
        print("Please do one of the following:")
        print("1. Set GOOGLE_APPLICATION_CREDENTIALS environment variable:")
        print("   export GOOGLE_APPLICATION_CREDENTIALS=/path/to/your-key.json")
        print()
        print("2. Place your service account key file as:")
        print("   serviceAccountKey.json (in project root)")
        print()
        print("To get a service account key:")
        print("1. Go to Firebase Console > Project Settings > Service Accounts")
        print("2. Click 'Generate new private key'")
        print("3. Save the downloaded JSON file")
        sys.exit(1)

    print(f"Using service account key: {key_path}")

    # Initialize Firebase Admin SDK
    if not firebase_admin._apps:
        cred = credentials.Certificate(key_path)
        firebase_admin.initialize_app(cred)

    # Get Firestore client
    db = firestore.client()

    # Fetch all documents from chat_sessions collection
    print("Fetching chat_sessions collection from Firestore...")
    collection_ref = db.collection("chat_sessions")
    docs = collection_ref.stream()

    sessions = []
    for doc in docs:
        doc_data = doc.to_dict()
        # Add document ID for reference
        doc_data["_document_id"] = doc.id
        # Serialize to JSON-compatible format
        sessions.append(serialize_firestore_doc(doc_data))

    print(f"Retrieved {len(sessions)} session documents")

    # Sort by start_time (newest first)
    sessions.sort(
        key=lambda x: x.get("start_time", "1970-01-01T00:00:00"),
        reverse=True
    )

    # Write to JSON file
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(sessions, f, indent=2, ensure_ascii=False)

    print(f"Exported to: {output_path}")

    # Print summary statistics
    print("\n=== Export Summary ===")
    print(f"Total sessions: {len(sessions)}")

    if sessions:
        # Date range
        dates = [s.get("start_time", "")[:10] for s in sessions if s.get("start_time")]
        if dates:
            print(f"Date range: {min(dates)} to {max(dates)}")

        # Unique users
        users = set(s.get("user_id", "unknown") for s in sessions)
        print(f"Unique users: {len(users)}")

        # Total messages
        total_msgs = sum(s.get("total_message_count", 0) for s in sessions)
        print(f"Total messages: {total_msgs}")

    return sessions


if __name__ == "__main__":
    # Allow custom output path via command line argument
    output_path = sys.argv[1] if len(sys.argv) > 1 else None
    export_chat_sessions(output_path)
