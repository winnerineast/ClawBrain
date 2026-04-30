#!/usr/bin/env python3
"""
ClawBrain CLI — Universal Memory Hub Access
===========================================
Usage:
  clawbrain ingest "fact" [--session my-project]
  clawbrain query "topic" [--session my-project] [--budget 2000]
  clawbrain status
"""

import argparse
import httpx
import sys
import os

DEFAULT_URL = "http://localhost:11435"

def get_base_url():
    return os.getenv("CLAWBRAIN_URL", DEFAULT_URL)

def cmd_ingest(args):
    """Save verbatim content into memory."""
    url = f"{get_base_url()}/v1/ingest"
    payload = {
        "content": args.content,
        "session_id": args.session,
        "sync_distill": args.sync
    }
    try:
        resp = httpx.post(url, json=payload, timeout=30.0)
        if resp.status_code == 200:
            data = resp.json()
            print(f"✅ Fact archived (Trace: {data['trace_id'][:8]}...)")
        else:
            print(f"❌ Error {resp.status_code}: {resp.text}")
            sys.exit(1)
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        sys.exit(1)

def cmd_query(args):
    """Retrieve optimized context from all memory layers."""
    url = f"{get_base_url()}/v1/query"
    payload = {
        "query": args.text,
        "session_id": args.session,
        "budget": args.budget
    }
    try:
        resp = httpx.post(url, json=payload, timeout=30.0)
        if resp.status_code == 200:
            data = resp.json()
            context = data.get("context", "")
            if context:
                print(context)
            else:
                print("(No relevant memory found)")
        else:
            print(f"❌ Error {resp.status_code}: {resp.text}")
            sys.exit(1)
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        sys.exit(1)

def cmd_status(args):
    """Show system health, database stats, and active sessions."""
    base = get_base_url()
    try:
        h_resp = httpx.get(f"{base}/health")
        s_resp = httpx.get(f"{base}/v1/status")
        
        if h_resp.status_code == 200 and s_resp.status_code == 200:
            health = h_resp.json()
            stats = s_resp.json()
            
            print("\n🦞 ClawBrain Neural Status")
            print("=" * 40)
            print(f"  Engine:   {health['engine']}")
            print(f"  Status:   {stats['status'].upper()}")
            print(f"  DB Dir:   {stats['db_dir']}")
            print(f"  Vault:    {'Active' if stats['vault_enabled'] else 'Inactive'}")
            if stats['vault_enabled']:
                print(f"  Vault:    {stats['vault_path']}")
            
            sessions = stats['active_sessions']
            print(f"  Sessions: {len(sessions)}")
            if sessions:
                print(f"  Recent:   {', '.join(sessions[:5])}")
            print("=" * 40 + "\n")
        else:
            print(f"❌ System unhealthy (HTTP {h_resp.status_code}/{s_resp.status_code})")
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        sys.exit(1)

def main():
    parser = argparse.ArgumentParser(
        description="ClawBrain CLI - Universal Memory Hub Access",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    
    sub = parser.add_subparsers(dest="command")

    # Ingest
    p_ingest = sub.add_parser("ingest", help="Save a fact to memory")
    p_ingest.add_argument("content", help="The text to remember")
    p_ingest.add_argument("--session", default="default", help="Session ID (default: 'default')")
    p_ingest.add_argument("--sync", action="store_true", help="Perform synchronous extraction (blocks until done)")

    # Query
    p_query = sub.add_parser("query", help="Query memory for context")
    p_query.add_argument("text", help="The search query")
    p_query.add_argument("--session", default="default", help="Session ID (default: 'default')")
    p_query.add_argument("--budget", type=int, default=2000, help="Character budget (default: 2000)")

    # Status
    sub.add_parser("status", help="Show system health and stats")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    dispatch = {
        "ingest": cmd_ingest,
        "query": cmd_query,
        "status": cmd_status,
    }
    
    dispatch[args.command](args)

if __name__ == "__main__":
    main()
