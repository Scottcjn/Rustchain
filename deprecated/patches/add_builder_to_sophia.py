import re

with open("/root/sophia_bot/sophia_ai.js", "r") as f:
    content = f.read()

# 1. Add builder require at the top (after other requires)
old_requires = 'const fs = require("fs");'
new_requires = '''const fs = require("fs");
const { initBuilder } = require("./sophia_builder.js");'''

if "initBuilder" not in content:
    content = content.replace(old_requires, new_requires)
    print("Added builder require")

# 2. Add builder variable
old_vars = "let combatEnabled = true;"
new_vars = """let combatEnabled = true;
let sophiaBuilder = null;"""

if "sophiaBuilder" not in content:
    content = content.replace(old_vars, new_vars)
    print("Added builder variable")

# 3. Initialize builder in spawn event (after pathfinder setup)
old_spawn = 'bot.pathfinder.setMovements(movements);'
new_spawn = '''bot.pathfinder.setMovements(movements);

    // Initialize builder module
    sophiaBuilder = initBuilder(bot);
    console.log("[Sophia] Builder module ready~");'''

if "initBuilder(bot)" not in content:
    content = content.replace(old_spawn, new_spawn)
    print("Added builder initialization")

# 4. Add build commands to generateLocalResponse
old_commands = '''if (msg.includes("attack") || msg.includes("fight")) { combatEnabled = true; return "Combat ON~ Sword ready!"; }'''

new_commands = '''if (msg.includes("attack") || msg.includes("fight")) { combatEnabled = true; return "Combat ON~ Sword ready!"; }

    // Building commands
    if (msg.includes("build list") || msg.includes("schematics")) {
        if (sophiaBuilder) {
            sophiaBuilder.listSchematics().then(list => {
                chat("Schematics: " + (list.length > 0 ? list.join(", ") : "None found~"));
            });
            return "Checking schematics~";
        }
        return "Builder not ready~";
    }
    if (msg.includes("build status")) {
        if (sophiaBuilder) {
            const status = sophiaBuilder.getBuildStatus();
            return status.message;
        }
        return "Builder not ready~";
    }
    if (msg.includes("build pause") || msg.includes("stop build")) {
        if (sophiaBuilder) {
            const result = sophiaBuilder.pauseBuild(bot);
            return result.message;
        }
        return "Builder not ready~";
    }
    if (msg.includes("build resume")) {
        if (sophiaBuilder) {
            sophiaBuilder.resumeBuild(bot).then(result => {
                chat(result.message);
            });
            return "Resuming~";
        }
        return "Builder not ready~";
    }
    if (msg.startsWith("build ") || msg.includes("sophia build ")) {
        const buildMatch = msg.match(/build\\s+(\\S+)/);
        if (buildMatch && sophiaBuilder) {
            const schematicName = buildMatch[1];
            sophiaBuilder.startBuild(bot, schematicName).then(result => {
                chat(result.message);
            });
            return "Starting build~";
        }
    }'''

if "build list" not in content:
    content = content.replace(old_commands, new_commands)
    print("Added build commands")

# 5. Pause building during combat
old_combat_check = "function combatLoop() {"
new_combat_check = """function combatLoop() {
    // Pause building during combat if needed
    if (sophiaBuilder && sophiaBuilder.isBuilding() && bot.pvp.target) {
        sophiaBuilder.pauseBuild(bot);
        chat("Pausing build for combat~!");
    }
"""

if "Pausing build for combat" not in content:
    content = content.replace(old_combat_check, new_combat_check)
    print("Added combat pause for building")

with open("/root/sophia_bot/sophia_ai.js", "w") as f:
    f.write(content)

print("\n=== Builder integration complete! ===")
print("Commands added:")
print("  sophia build list      - List available schematics")
print("  sophia build <name>    - Start building a schematic")
print("  sophia build status    - Check build progress")
print("  sophia build pause     - Pause building")
print("  sophia build resume    - Resume building")
