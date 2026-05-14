import os
import re
from typing import Dict, List

def parse_bot_log(log_path: str) -> Dict:
    """Parses a bot log to extract high-signal status info for Gemini CLI."""
    status = {
        "online": False,
        "bot_user": "Unknown",
        "guild_count": 0,
        "emojis_loaded": False,
        "last_event": "None",
        "error": None
    }
    
    if not os.path.exists(log_path):
        status["error"] = "Log file not found."
        return status

    try:
        with open(log_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            
        for line in lines:
            if "has connected to Discord!" in line:
                status["online"] = True
                match = re.search(r"bot \(main\.py:\d+\): (.*?) has connected", line)
                if match: status["bot_user"] = match.group(1)
            
            if "Bot is in" in line:
                match = re.search(r"Bot is in (\d+) guilds", line)
                if match: status["guild_count"] = int(match.group(1))
                
            if "Successfully loaded all emojis" in line:
                status["emojis_loaded"] = True
                
            if "Reconstructed event:" in line:
                match = re.search(r"Reconstructed event: (.*?) \(ID:", line)
                if match: status["last_event"] = match.group(1)
                
            if "[ERROR" in line or "❌" in line:
                status["error"] = line.strip()
    except Exception as e:
        status["error"] = str(e)
        
    return status

def main():
    targets = [
        ("Distro Bot", "distro_task_log.txt"),
        ("Ocean Bot", "ocean_distro_task_log.txt")
    ]
    
    print("🚀 --- Gemini Deployment Report ---")
    for name, log in targets:
        s = parse_bot_log(log)
        icon = "✅" if s["online"] and not s["error"] else "❌"
        print(f"\n{icon} {name}: {s['bot_user']}")
        print(f"   Status: {'Online' if s['online'] else 'Offline'}")
        print(f"   Guilds: {s['guild_count']}")
        print(f"   Emojis: {'Loaded' if s['emojis_loaded'] else 'FAILED'}")
        print(f"   Latest Memory: {s['last_event']}")
        if s["error"]:
            print(f"   ⚠️ Alert: {s['error']}")
    print("\n--- End of Report ---")

if __name__ == "__main__":
    main()
