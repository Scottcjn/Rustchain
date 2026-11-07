// SPDX-License-Identifier: MIT
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, readdirSync } from 'node:fs';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';

const beacon = new URL('../site/beacon/', import.meta.url);

test('Atlas runtime files and boot script parse as ES modules', () => {
  const html = readFileSync(new URL('index.html', beacon), 'utf8');
  const boot = html.match(/<script type="module">([\s\S]*?)<\/script>/)?.[1];
  assert.ok(boot, 'Atlas must have an executable boot module');
  const sources = readdirSync(beacon).filter(name => /\.m?js$/.test(name))
    .map(name => [name, readFileSync(new URL(name, beacon), 'utf8')]);
  for (const [name, source] of [...sources, ['index.html boot', boot]]) {
    const result = spawnSync(process.execPath, ['--input-type=module', '--check'], {
      input: source, encoding: 'utf8', cwd: fileURLToPath(beacon),
    });
    assert.equal(result.status, 0, `${name}: ${result.stderr}`);
  }
});

test('Atlas structured metadata is valid JSON rather than executable code', () => {
  const html = readFileSync(new URL('index.html', beacon), 'utf8');
  const metadata = html.match(/<script type="application\/ld\+json">([\s\S]*?)<\/script>/)?.[1];
  assert.ok(metadata);
  const page = JSON.parse(metadata);
  assert.equal(page['@type'], 'WebPage');
  assert.equal(page.url, 'https://rustchain.org/beacon/');
});
