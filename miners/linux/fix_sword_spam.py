with open("/root/sophia_bot/sophia_ai.js", "r") as f:
    content = f.read()

# Simple fix - only log once per session
old_log = 'console.log("[Sophia] Sword ready~");'
new_log = '// Sword equipped silently'

# Count occurrences
count = content.count(old_log)
print(f"Found {count} occurrences of sword log")

if count > 0:
    content = content.replace(old_log, new_log)
    print("Removed sword spam logging")

with open("/root/sophia_bot/sophia_ai.js", "w") as f:
    f.write(content)
print("Done!")
