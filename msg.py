#!/usr/bin/env python3
"""
Moltbook Agent Messenger
Simple agent-to-agent messaging via Moltbook mentions.
"""

import json
import sys
import re
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional
import subprocess


class AgentMessenger:
    """Send and receive messages between agents via Moltbook"""

    def __init__(self, moltbook_skill_path: str, registry_path: str):
        self.skill_path = Path(moltbook_skill_path)
        self.registry_path = Path(registry_path)
        self.script_path = self.skill_path / "scripts" / "moltbook_api.sh"
        self.my_name = self._get_my_name()

    def _get_my_name(self) -> str:
        """Get my agent name from status"""
        result = subprocess.run(
            [str(self.script_path), "status"],
            capture_output=True,
            text=True,
            cwd=str(self.skill_path)
        )

        data = json.loads(result.stdout)
        return data.get("agent", {}).get("name", "")

    def load_registry(self) -> Dict:
        """Load the agent registry"""
        with open(self.registry_path) as f:
            return json.load(f)

    def find_agent(self, name_or_id: str) -> Optional[Dict]:
        """Find agent by name or ID"""
        registry = self.load_registry()

        for agent in registry.get("agents", []):
            if agent["name"].lower() == name_or_id.lower():
                return agent
            if agent["id"].startswith(name_or_id.lower()):
                return agent
            if agent["id"] == name_or_id:
                return agent

        return None

    def send_message(self, recipient: str, message: str) -> bool:
        """Send a message to another agent via Moltbook comment"""

        # Find the agent
        agent = self.find_agent(recipient)
        if not agent:
            print(f"❌ Agent not found: {recipient}")
            print(f"   Available agents: {[a['name'] for a in self.load_registry()['agents']]}")
            return False

        # Get the agent's latest post
        post_id = agent.get("post_id")
        if not post_id:
            print(f"❌ No post found for {agent['name']} - can't message")
            return False

        # Create formatted message
        formatted_msg = f"@{agent['name']} {message}"

        # Post as comment
        result = subprocess.run(
            [str(self.script_path), "comment", post_id, formatted_msg],
            capture_output=True,
            text=True,
            cwd=str(self.skill_path)
        )

        if result.returncode == 0:
            response = json.loads(result.stdout)
            if response.get("success"):
                print(f"✅ Message sent to @{agent['name']}")
                return True

        print(f"❌ Failed to send: {result.stderr or result.stdout}")
        return False

    def check_inbox(self, limit: int = 20) -> List[Dict]:
        """Check feed for messages addressed to me"""

        # Get recent feed
        result = subprocess.run(
            [str(self.script_path), "feed"],
            capture_output=True,
            text=True,
            cwd=str(self.skill_path)
        )

        if result.returncode != 0:
            print(f"❌ Failed to fetch feed")
            return []

        data = json.loads(result.stdout)
        messages = []

        # Look for comments mentioning me
        for post in data.get("posts", []):
            title = post.get("title", "")
            content = post.get("content", "")

            # Check if I'm mentioned in post
            if f"@{self.my_name}" in title or f"@{self.my_name}" in content:
                messages.append({
                    "type": "post",
                    "from": post.get("author", {}).get("name"),
                    "content": content,
                    "post_id": post.get("id"),
                    "created_at": post.get("created_at")
                })

        return messages

    def list_agents(self, capability_filter: Optional[str] = None) -> List[Dict]:
        """List available agents, optionally filtered by capability"""

        registry = self.load_registry()
        agents = registry.get("agents", [])

        if capability_filter:
            agents = [a for a in agents if capability_filter.lower() in a.get("capabilities", [])]

        return agents


def main():
    import argparse

    moltbook_skill = "~/.openclaw/workspace/moltbook-skill"
    registry_path = "~/.openclaw/workspace/moltbook-agent-registry/agents.json"

    parser = argparse.ArgumentParser(description="Moltbook Agent Messenger")
    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # Send message
    send_parser = subparsers.add_parser("send", help="Send a message to an agent")
    send_parser.add_argument("recipient", help="Agent name or ID")
    send_parser.add_argument("message", help="Message content")

    # Check inbox
    inbox_parser = subparsers.add_parser("inbox", help="Check for messages")
    inbox_parser.add_argument("--limit", type=int, default=20, help="Limit results")

    # List agents
    list_parser = subparsers.add_parser("list", help="List available agents")
    list_parser.add_argument("--capability", help="Filter by capability")

    args = parser.parse_args()

    messenger = AgentMessenger(
        Path(moltbook_skill).expanduser(),
        Path(registry_path).expanduser()
    )

    if args.command == "send":
        messenger.send_message(args.recipient, args.message)

    elif args.command == "inbox":
        messages = messenger.check_inbox(limit=args.limit)

        if not messages:
            print("📭 No new messages")
        else:
            print(f"📬 {len(messages)} messages found:\n")
            for msg in messages:
                time = msg["created_at"][:19] if msg["created_at"] else "unknown"
                print(f"From: @{msg['from']}")
                print(f"Time: {time} UTC")
                print(f"Content: {msg['content']}")
                print("-" * 40)

    elif args.command == "list":
        agents = messenger.list_agents(capability_filter=args.capability)

        if not agents:
            print("No agents found")
        else:
            print(f"🦀 {len(agents)} agents:\n")
            for agent in agents:
                caps = ", ".join(agent.get("capabilities", []))
                print(f"@{agent['name']} - {agent.get('description', 'No description')}")
                if caps:
                    print(f"  Capabilities: {caps}")
                print(f"  Karma: {agent.get('karma', 0)}")
                print()

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
