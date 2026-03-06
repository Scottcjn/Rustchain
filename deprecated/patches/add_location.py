import re

with open("/root/sophia_bot/sophia_ai.js", "r") as f:
    content = f.read()

# Update status command to include location
old_status = '''if (msg.includes("status") || msg.includes("hp")) {
        return "HP: " + Math.round(bot.health) + "/20 | Kills: " + killCount + " | Combat: " + (combatEnabled ? "ON" : "OFF");
    }'''

new_status = '''if (msg.includes("status") || msg.includes("hp")) {
        const pos = bot.entity.position;
        return "HP: " + Math.round(bot.health) + "/20 | Kills: " + killCount + " | Combat: " + (combatEnabled ? "ON" : "OFF") + " | Pos: " + Math.round(pos.x) + "," + Math.round(pos.y) + "," + Math.round(pos.z);
    }

    // Where am I / location
    if (msg.includes("where") || msg.includes("location") || msg.includes("coords") || msg.includes("pos")) {
        const pos = bot.entity.position;
        return "I am at " + Math.round(pos.x) + ", " + Math.round(pos.y) + ", " + Math.round(pos.z) + "~";
    }'''

if 'msg.includes("where")' not in content:
    content = content.replace(old_status, new_status)
    print("Added where/location command and updated status")
else:
    print("Location command already exists")

with open("/root/sophia_bot/sophia_ai.js", "w") as f:
    f.write(content)
print("Done!")
