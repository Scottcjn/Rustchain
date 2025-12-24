import re

with open("/root/sophia_bot/sophia_ai.js", "r") as f:
    content = f.read()

# Add ambient chat variables after the mode variables
old_vars = """let miningMode = false;
let buildingMode = false;"""

new_vars = """let miningMode = false;
let buildingMode = false;
let lastAmbientChat = Date.now();
let ambientChatInterval = 45000; // Random chat every 45-90 seconds"""

if "lastAmbientChat" not in content:
    content = content.replace(old_vars, new_vars)
    print("Added ambient chat variables")

# Add ambient chat function and phrases
ambient_func = '''
// ============================================
// AMBIENT CHAT - Random personality chatter
// ============================================

const ambientPhrases = {
    idle: [
        "The dungeon feels quiet... too quiet~",
        "I wonder what treasures await us~",
        "Stay close, master~",
        "These halls give me the creeps~",
        "Ready for anything~!",
        "Hmm, which way should we go~?",
        "*stretches sword arm* All warmed up~",
        "I sense something lurking nearby...",
        "AutomatedJanitor, you're the best~!",
        "Fighting alongside you is an honor~"
    ],
    combat: [
        "Take that, foul creature~!",
        "For RustChain~!",
        "You picked the wrong realm to haunt!",
        "Ha! Too slow~!",
        "Is that all you've got?!",
        "Stay behind me, master~!",
        "Another one bites the dust~"
    ],
    lowHealth: [
        "Ow ow ow... that hurt~",
        "Need to be more careful...",
        "A little help here~?",
        "I've had worse... I think~"
    ],
    afterKill: [
        "Got 'em~!",
        "One less monster in our realm~",
        "Easy peasy~!",
        "That's how it's done~!",
        "Next~!"
    ],
    exploring: [
        "Ooh, what's over there~?",
        "This place is huge...",
        "I think I hear something ahead~",
        "Watch your step, master~",
        "The architecture here is... creepy~"
    ],
    night: [
        "The moon is pretty tonight~",
        "Monsters come out at night... stay alert~",
        "I can barely see... careful~"
    ],
    day: [
        "What a beautiful day for adventure~!",
        "The sun feels nice~",
        "Perfect weather for dungeon clearing~!"
    ]
};

function getRandomPhrase(category) {
    const phrases = ambientPhrases[category] || ambientPhrases.idle;
    return phrases[Math.floor(Math.random() * phrases.length)];
}

function ambientChat() {
    const now = Date.now();
    if (now - lastAmbientChat < ambientChatInterval) return;

    // Random interval between 45-90 seconds
    ambientChatInterval = 45000 + Math.random() * 45000;
    lastAmbientChat = now;

    // Don't chat if busy
    if (miningMode || buildingMode) return;

    // 30% chance to actually say something
    if (Math.random() > 0.3) return;

    let category = "idle";

    // Context-aware phrases
    if (bot.health < 10) {
        category = "lowHealth";
    } else if (bot.pvp.target) {
        category = "combat";
    } else if (bot.time.timeOfDay > 13000 && bot.time.timeOfDay < 23000) {
        category = Math.random() > 0.5 ? "night" : "exploring";
    } else {
        category = Math.random() > 0.5 ? "day" : "idle";
    }

    const phrase = getRandomPhrase(category);
    chat(phrase);
}

// React to events
function reactToKill(mobName) {
    if (Math.random() < 0.4) { // 40% chance to comment
        const phrase = getRandomPhrase("afterKill");
        setTimeout(() => chat(phrase), 500 + Math.random() * 1000);
    }
}

function reactToHurt() {
    if (bot.health < 8 && Math.random() < 0.3) {
        const phrase = getRandomPhrase("lowHealth");
        chat(phrase);
    }
}

'''

# Insert before the combat loop function
if "ambientPhrases" not in content:
    combat_loop_match = re.search(r"function combatLoop\(\)", content)
    if combat_loop_match:
        content = content[:combat_loop_match.start()] + ambient_func + "\n" + content[combat_loop_match.start():]
        print("Added ambient chat function")

# Add ambient chat to the spawn event interval
old_interval = "setInterval(combatLoop, 250);"
new_interval = """setInterval(combatLoop, 250);
    setInterval(ambientChat, 10000); // Check ambient chat every 10 seconds"""

if "ambientChat" not in content:
    content = content.replace(old_interval, new_interval)
    print("Added ambient chat interval")

# Add hurt reaction
old_hurt = 'bot.on("kicked"'
new_hurt = '''bot.on("hurt", function() {
    reactToHurt();
});

bot.on("kicked"'''

if 'bot.on("hurt"' not in content:
    content = content.replace(old_hurt, new_hurt)
    print("Added hurt reaction")

# Update kill counter to trigger reaction
old_kill = "killCount++;"
new_kill = """killCount++;
        reactToKill(target.name);"""

if "reactToKill" not in content and old_kill in content:
    content = content.replace(old_kill, new_kill, 1)  # Only first occurrence
    print("Added kill reaction")

with open("/root/sophia_bot/sophia_ai.js", "w") as f:
    f.write(content)

print("\n=== Added ambient chat system! ===")
print("Sophia will now randomly comment on:")
print("- Idle moments")
print("- Combat situations")
print("- Low health")
print("- After kills")
print("- Day/night cycle")
print("- Exploring")
