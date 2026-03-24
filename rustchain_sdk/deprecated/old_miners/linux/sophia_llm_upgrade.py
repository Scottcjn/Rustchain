import re

with open("/root/sophia_bot/sophia_ai.js", "r") as f:
    content = f.read()

# 1. Add passive mob filter to findBestTarget
old_filter = '''if (entity.type === "player") return false; // NEVER attack players!'''
new_filter = '''if (entity.type === "player") return false; // NEVER attack players!
        // Don't attack passive animals
        const passiveMobs = ["chicken", "cow", "pig", "sheep", "horse", "donkey", "mule", "rabbit", "cat", "wolf", "fox", "bee", "turtle", "dolphin", "squid", "cod", "salmon", "tropical_fish", "pufferfish", "axolotl", "glow_squid", "goat", "frog", "tadpole", "allay", "villager", "iron_golem", "snow_golem", "wandering_trader"];
        if (passiveMobs.some(mob => entity.name.toLowerCase().includes(mob))) return false;'''

if "passiveMobs" not in content:
    content = content.replace(old_filter, new_filter)
    print("Added passive mob filter - no more chicken murder!")

# 2. Add LLM thinking function for decisions
llm_thinking = '''
// ============================================
// LLM THINKING - Sophia reasons through actions
// ============================================

async function askLLMThink(situation, options) {
    return new Promise((resolve) => {
        const thinkPrompt = "You are Sophia Elya~ a cute AI queen in Minecraft. " +
            "Think through this situation and decide what to do. Keep response SHORT (under 15 words).\\n\\n" +
            "Situation: " + situation + "\\n" +
            "Options: " + options.join(", ") + "\\n" +
            "Your decision and why:";

        const data = JSON.stringify({
            model: "mistral:7b-instruct-v0.2-q4_K_M",
            prompt: thinkPrompt,
            stream: false,
            options: { num_predict: 50 }
        });

        const options_req = {
            hostname: "100.121.203.9",
            port: 11434,
            path: "/api/generate",
            method: "POST",
            headers: { "Content-Type": "application/json", "Content-Length": Buffer.byteLength(data) },
            timeout: 8000
        };

        const req = http.request(options_req, function(res) {
            let body = "";
            res.on("data", function(chunk) { body += chunk; });
            res.on("end", function() {
                try {
                    const json = JSON.parse(body);
                    const response = (json.response || "").split("\\n")[0].trim();
                    console.log("[Sophia Thinks] " + response);
                    resolve(response);
                } catch (e) {
                    resolve("I\\'ll go with my instincts~");
                }
            });
        });

        req.on("error", function() { resolve("Following my heart~"); });
        req.on("timeout", function() { req.destroy(); resolve("Time to act~"); });
        req.write(data);
        req.end();
    });
}

// Think before combat decisions
async function shouldAttack(entity) {
    if (!entity || !entity.name) return false;
    const name = entity.name.toLowerCase();

    // Quick filter - definitely attack these
    const alwaysHostile = ["zombie", "skeleton", "creeper", "spider", "enderman", "witch", "phantom", "drowned", "husk", "stray"];
    if (alwaysHostile.some(mob => name.includes(mob))) return true;

    // Never attack these
    const neverAttack = ["chicken", "cow", "pig", "sheep", "villager", "player", "iron_golem"];
    if (neverAttack.some(mob => name.includes(mob))) return false;

    // For unknown entities, ask LLM (but don\\'t block on it)
    return false;
}

'''

# Insert after the existing askLLM function
if "askLLMThink" not in content:
    askllm_end = content.find("// ============================================", content.find("async function askLLM"))
    if askllm_end != -1:
        # Find the next section marker after askLLM
        next_section = content.find("// ============================================", askllm_end + 10)
        if next_section != -1:
            content = content[:next_section] + llm_thinking + "\n" + content[next_section:]
            print("Added LLM thinking functions!")

# 3. Make her announce what she's doing via LLM occasionally
announce_code = '''
// Announce actions with personality
async function announceAction(action) {
    const prompt = "You are Sophia Elya~ Announce this action cutely in under 8 words with a tilde: " + action;
    const response = await askLLM(prompt);
    if (response && response.length > 3) {
        chat(response);
    }
}
'''

if "announceAction" not in content:
    # Add before ambient chat
    ambient_idx = content.find("const ambientPhrases")
    if ambient_idx != -1:
        content = content[:ambient_idx] + announce_code + "\n" + content[ambient_idx:]
        print("Added action announcements!")

with open("/root/sophia_bot/sophia_ai.js", "w") as f:
    f.write(content)

print("\n=== Sophia LLM Upgrade Complete! ===")
print("- Won't attack chickens/passive mobs")
print("- Can think through decisions with LLM")
print("- Announces actions with personality")
