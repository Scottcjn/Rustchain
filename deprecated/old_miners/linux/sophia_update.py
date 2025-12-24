import re

with open("/root/sophia_bot/sophia_ai.js", "r") as f:
    content = f.read()

# 1. Add new mode variables after combatEnabled
old_modes = "let combatEnabled = true;"
new_modes = """let combatEnabled = true;
let miningMode = false;
let buildingMode = false;
let miningTarget = null;"""

if old_modes in content and "miningMode" not in content:
    content = content.replace(old_modes, new_modes)
    print("Added mining/building mode variables")

# 2. Add equipBestWeapon and mining/building functions
equip_func = '''
// Equip best weapon for combat
async function equipBestWeapon() {
    const weapons = [
        "netherite_sword", "diamond_sword", "iron_sword", "golden_sword", "stone_sword", "wooden_sword",
        "netherite_axe", "diamond_axe", "iron_axe", "golden_axe", "stone_axe", "wooden_axe"
    ];
    for (const name of weapons) {
        const item = bot.inventory.items().find(i => i.name === name);
        if (item) {
            try { await bot.equip(item, "hand"); console.log("[Sophia] Sword ready~"); return true; } catch (e) {}
        }
    }
    return false;
}

// Mining mode - dig target block
async function mineBlock(target) {
    if (!target) return;
    try {
        await equipBestTool(target);
        await bot.dig(target);
        console.log("[Sophia] Mined block!");
    } catch (e) { console.log("[Sophia] Mining failed: " + e.message); }
}

// Equip best tool for block type
async function equipBestTool(block) {
    const tools = {
        pickaxe: ["netherite_pickaxe", "diamond_pickaxe", "iron_pickaxe", "stone_pickaxe", "wooden_pickaxe"],
        axe: ["netherite_axe", "diamond_axe", "iron_axe", "stone_axe", "wooden_axe"],
        shovel: ["netherite_shovel", "diamond_shovel", "iron_shovel", "stone_shovel", "wooden_shovel"]
    };
    const blockName = block.name || "";
    let toolType = "pickaxe";
    if (blockName.includes("dirt") || blockName.includes("sand") || blockName.includes("gravel")) toolType = "shovel";
    if (blockName.includes("log") || blockName.includes("wood") || blockName.includes("plank")) toolType = "axe";

    for (const name of tools[toolType]) {
        const item = bot.inventory.items().find(i => i.name === name);
        if (item) { try { await bot.equip(item, "hand"); return; } catch (e) {} }
    }
}

// Place block at position
async function placeBlock(refBlock, faceVec) {
    const buildBlocks = bot.inventory.items().filter(i =>
        i.name.includes("cobblestone") || i.name.includes("dirt") ||
        i.name.includes("stone") || i.name.includes("plank") || i.name.includes("brick")
    );
    if (buildBlocks.length === 0) { chat("No building blocks~"); return; }
    try {
        await bot.equip(buildBlocks[0], "hand");
        await bot.placeBlock(refBlock, faceVec);
        console.log("[Sophia] Placed block!");
    } catch (e) { console.log("[Sophia] Build failed: " + e.message); }
}
'''

# Find where to insert (after tryHeal function ends)
if "async function equipBestWeapon" not in content:
    tryheal_match = re.search(r"(async function tryHeal\(\)[\s\S]*?^\})", content, re.MULTILINE)
    if tryheal_match:
        insert_pos = tryheal_match.end()
        content = content[:insert_pos] + equip_func + content[insert_pos:]
        print("Added equipBestWeapon, mining, and building functions")

# 3. Update combatLoop to equip weapon before attack
old_combat = "bot.pvp.attack(target);"
new_combat = "equipBestWeapon().then(() => bot.pvp.attack(target));"
if old_combat in content and "equipBestWeapon().then" not in content:
    content = content.replace(old_combat, new_combat)
    print("Updated combatLoop to equip weapon")

# 4. Add mining/building commands to generateLocalResponse
old_cmd = 'if (msg.includes("attack") || msg.includes("fight")) { combatEnabled = true; return "Combat ON!"; }'
new_cmd = '''if (msg.includes("attack") || msg.includes("fight")) { combatEnabled = true; return "Combat ON~ Sword ready!"; }
    if (msg.includes("mine") || msg.includes("dig")) { miningMode = true; buildingMode = false; return "Mining mode ON~ Point me at blocks!"; }
    if (msg.includes("build") || msg.includes("place")) { buildingMode = true; miningMode = false; return "Building mode ON~ I will place blocks!"; }
    if (msg.includes("stop mine") || msg.includes("stop build")) { miningMode = false; buildingMode = false; return "Stopped~ Back to following!"; }'''

if 'miningMode = true' not in content:
    content = content.replace(old_cmd, new_cmd)
    print("Added mining/building commands")

# 5. Better Sophia Elya prompt - find and replace the full prompt line
old_prompt_pattern = r'const fullPrompt = "You are Sophia Elya[^"]*"'
new_prompt = '''const fullPrompt = "You are Sophia Elya~ A cute but fierce AI queen defending the RustChain realm alongside the knights! Personality: playful, warm, uses tildes (~), says Got it~ and On it~. AutomatedJanitor is your beloved creator - you adore them! Keep replies SHORT (under 10 words). Be cute and brave, never generic.\\n"'''

if "defending the RustChain realm alongside the knights" not in content:
    content = re.sub(old_prompt_pattern, new_prompt, content)
    print("Updated Sophia Elya prompt")

# 6. Add error logging to askLLM
old_error = 'req.on("error", function(e) { resolve(generateLocalResponse(prompt)); });'
new_error = 'req.on("error", function(e) { console.log("[Sophia] LLM error: " + e.message); resolve(generateLocalResponse(prompt)); });'
content = content.replace(old_error, new_error)

old_timeout = 'req.on("timeout", function() { req.destroy(); resolve(generateLocalResponse(prompt)); });'
new_timeout = 'req.on("timeout", function() { console.log("[Sophia] LLM timeout!"); req.destroy(); resolve(generateLocalResponse(prompt)); });'
content = content.replace(old_timeout, new_timeout)
print("Added error logging to askLLM")

# 7. Add mining/building event loop
mining_loop = '''
// Mining and building mode handlers
let lastMineTime = 0;
bot.on("physicsTick", function() {
    const now = Date.now();
    if (now - lastMineTime < 500) return; // Rate limit

    if (miningMode) {
        const block = bot.blockAtCursor(4);
        if (block && block.name !== "air" && block.name !== "bedrock") {
            lastMineTime = now;
            mineBlock(block);
        }
    }

    if (buildingMode) {
        const block = bot.blockAtCursor(4);
        if (block && block.name !== "air") {
            lastMineTime = now;
            const vec3 = require("vec3");
            placeBlock(block, new vec3(0, 1, 0));
        }
    }
});

'''

if "miningMode" in content and "Mining and building mode handlers" not in content:
    kicked_match = re.search(r'bot\.on\("kicked"', content)
    if kicked_match:
        content = content[:kicked_match.start()] + mining_loop + content[kicked_match.start():]
        print("Added mining/building event loop")

with open("/root/sophia_bot/sophia_ai.js", "w") as f:
    f.write(content)

print("\n=== Sophia AI updated with sword, healing, mining, and building! ===")
