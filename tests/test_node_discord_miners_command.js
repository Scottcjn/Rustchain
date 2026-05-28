const assert = require('assert');
const Module = require('module');
const path = require('path');

class FakeSlashCommandBuilder {
  setName() { return this; }
  setDescription() { return this; }
  addIntegerOption(callback) {
    callback({
      setName() { return this; },
      setDescription() { return this; },
      setMinValue() { return this; },
      setMaxValue() { return this; },
      setValue() { return this; },
    });
    return this;
  }
  addStringOption(callback) {
    callback({
      setName() { return this; },
      setDescription() { return this; },
    });
    return this;
  }
}

class FakeEmbedBuilder {
  constructor() {
    this.fields = [];
  }
  setColor(color) { this.color = color; return this; }
  setTitle(title) { this.title = title; return this; }
  setDescription(description) { this.description = description; return this; }
  addFields(...fields) { this.fields.push(...fields); return this; }
  setFooter(footer) { this.footer = footer; return this; }
  setTimestamp() { this.timestamped = true; return this; }
}

const originalLoad = Module._load;
Module._load = function patchedLoad(request, parent, isMain) {
  if (request === 'discord.js') {
    return {
      SlashCommandBuilder: FakeSlashCommandBuilder,
      EmbedBuilder: FakeEmbedBuilder,
    };
  }
  return originalLoad.call(this, request, parent, isMain);
};

async function run() {
  const commandPath = path.join(
    __dirname,
    '..',
    'discord-bot-nodejs-v2',
    'commands',
    'miners.js',
  );
  delete require.cache[require.resolve(commandPath)];
  const minersCommand = require(commandPath);

  let fetchedUrl = null;
  global.fetch = async (url) => {
    fetchedUrl = url;
    return {
      ok: true,
      async json() {
        return {
          miners: [
            {
              miner: 'alice-miner',
              hardware_type: 'PowerPC G4',
              device_arch: 'G4',
              device_family: 'PowerPC',
              antiquity_multiplier: 2.5,
              entropy_score: 0.9,
              ts_ok: 1700000000,
            },
            {
              miner_id: 'bob-miner',
              hardware_type: 'SPARC',
              antiquity_multiplier: 1.5,
            },
          ],
          pagination: { total: 2, limit: 100, offset: 0, count: 2 },
        };
      },
    };
  };

  const replies = [];
  const interaction = {
    options: {
      getInteger: () => 2,
      getString: () => '',
    },
    deferReply: async () => {},
    editReply: async (payload) => replies.push(payload),
  };

  await minersCommand.execute(interaction);

  assert.strictEqual(fetchedUrl, 'https://50.28.86.131/api/miners');
  assert.strictEqual(replies.length, 1);
  assert.ok(replies[0].embeds, 'expected miners command to render an embed');
  const embed = replies[0].embeds[0];
  assert.strictEqual(embed.title, '⛏️ Top RustChain Miners');
  assert.ok(embed.description.includes('alice-miner'));
  assert.ok(embed.description.includes('bob-miner'));
  assert.ok(embed.description.includes('PowerPC G4'));
  assert.ok(embed.description.includes('SPARC'));
}

run().finally(() => {
  Module._load = originalLoad;
  delete global.fetch;
}).catch((error) => {
  console.error(error);
  process.exit(1);
});
