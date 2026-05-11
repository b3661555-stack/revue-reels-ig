"""Generate IG_SESSION_B64 for GitHub Actions.

Run locally once:
    python generate_ig_session.py

It will log into Instagram interactively, then output the base64 session
string to add as a GitHub secret.
"""
import base64
import json
import os
import sys
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent / ".env", override=True)
except ImportError:
    pass

from instagrapi import Client


def main():
    username = os.environ.get("INSTAGRAM_USERNAME")
    password = os.environ.get("INSTAGRAM_PASSWORD")

    if not username or not password:
        print("Set INSTAGRAM_USERNAME and INSTAGRAM_PASSWORD in .env")
        sys.exit(1)

    print(f"Logging in as {username}...")
    cl = Client()

    # Use a realistic device/user-agent to avoid detection
    cl.delay_range = [1, 3]

    try:
        cl.login(username, password)
    except Exception as e:
        print(f"Login failed: {e}")
        print("\nIf you get a challenge (email/SMS verification):")
        print("  1. Open Instagram app on your phone")
        print("  2. Confirm the login attempt")
        print("  3. Run this script again")
        sys.exit(1)

    # Export session
    settings = cl.get_settings()
    session_json = json.dumps(settings)
    session_b64 = base64.b64encode(session_json.encode()).decode()

    print(f"\n✅ Login successful!")
    print(f"\nSession B64 length: {len(session_b64)} chars")
    print(f"\nAdd to GitHub secrets:")
    print(f"  gh secret set IG_SESSION_B64 --body '{session_b64[:50]}...'")
    print(f"\nOr add to .env:")

    # Write to .env
    env_path = Path(__file__).parent / ".env"
    env_content = env_path.read_text() if env_path.exists() else ""
    if "IG_SESSION_B64=" in env_content:
        lines = env_content.split("\n")
        lines = [l for l in lines if not l.startswith("IG_SESSION_B64=")]
        env_content = "\n".join(lines)
    env_content = env_content.rstrip() + f"\nIG_SESSION_B64={session_b64}\n"
    env_path.write_text(env_content)
    print(f"  Written to .env ✅")

    # Also set GitHub secret if gh CLI available
    try:
        import subprocess
        result = subprocess.run(
            ["gh", "secret", "set", "IG_SESSION_B64", "--body", session_b64],
            capture_output=True, text=True, timeout=15,
        )
        if result.returncode == 0:
            print(f"  GitHub secret set ✅")
        else:
            print(f"  GitHub secret failed: {result.stderr.strip()}")
            print(f"  Run manually: gh secret set IG_SESSION_B64")
    except Exception:
        print(f"  gh CLI not available, set secret manually")


if __name__ == "__main__":
    main()
