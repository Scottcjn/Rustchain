// SPDX-License-Identifier: MIT
// Real Atlas browser regression: no request interception or replacement app modules.
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const http = require('node:http');
const path = require('node:path');
const { chromium } = require('playwright');

const root = path.resolve(__dirname, '..');
const evidence = process.env.ATLAS_EVIDENCE_DIR || path.join(root, 'docs/evidence/atlas-minimap');
const proxyUrl = process.env.ATLAS_BROWSER_PROXY;
if (proxyUrl && new URL(proxyUrl).username) throw Error('Use a credential-free test proxy');
const server = http.createServer(async (request, response) => {
  if (request.method !== 'GET') { response.writeHead(405); response.end(); return; }
  try {
    const url = new URL(request.url, 'http://localhost');
    const relative = decodeURIComponent(url.pathname);
    const file = path.resolve(root, '.' + (relative.endsWith('/') ? relative + 'index.html' : relative));
    if (!file.startsWith(root + path.sep)) throw Error('Invalid path');
    const contents = await fs.readFile(file);
    const types = { '.html':'text/html', '.js':'text/javascript', '.mjs':'text/javascript', '.css':'text/css', '.png':'image/png', '.jpg':'image/jpeg', '.svg':'image/svg+xml' };
    response.setHeader('Content-Type', types[path.extname(file)] || 'application/octet-stream');
    response.end(contents);
  } catch { response.writeHead(404); response.end(); }
});

async function observe(page) {
  return page.evaluate(async () => {
    const data = await import('/site/beacon/data.js');
    const scene = await import('/site/beacon/scene.js');
    const agents = await import('/site/beacon/agents.js');
    const cities = await import('/site/beacon/cities.js');
    const model = await import('/site/beacon/minimap-model.mjs');
    const points = model.collectAtlasPoints(data.CITIES, data.AGENTS, cities.getCityCenter, agents.getAgentPosition);
    const bounds = model.computeAtlasBounds([...points.cityPoints, ...points.agentPoints], 24);
    const canvas = document.querySelector('.atlas-minimap canvas');
    const rect = canvas.getBoundingClientRect();
    const current = window.__minimapObservation;
    const ctx = canvas.getContext('2d');
    const image = ctx.getImageData(0, 0, canvas.width, canvas.height).data;
    let amber = 0, green = 0, cyan = 0;
    for (let i = 0; i < image.length; i += 4) {
      if (image[i] === 255 && image[i + 1] === 176 && image[i + 2] === 0) amber++;
      if (image[i + 1] > 200 && image[i] > 20 && image[i] < 80 && image[i + 2] < 80) green++;
      if (image[i] === 0 && image[i + 1] > 200 && image[i + 2] > 200) cyan++;
    }
    const camera = scene.getCamera().position;
    return {
      cities: points.cityPoints.length, agents: points.agentPoints.length,
      rect: { x:rect.x, y:rect.y, width:rect.width, height:rect.height },
      backing: { width:canvas.width, height:canvas.height },
      clientWidth:canvas.clientWidth, clientHeight:canvas.clientHeight,
      pointerEvents: getComputedStyle(canvas.parentElement).pointerEvents,
      hitTarget: document.elementFromPoint(rect.x + rect.width / 2, rect.y + rect.height / 2)?.id,
      overflow: canvas.parentElement.scrollWidth > canvas.parentElement.clientWidth,
      pixels: {amber, green, cyan},
      camera: {x:camera.x, y:camera.y, z:camera.z},
      projectedCamera: model.projectAtlasPoint(camera, bounds, canvas.clientWidth, canvas.clientHeight),
      projectedCities: points.cityPoints.map(point => model.projectAtlasPoint(point, bounds, canvas.clientWidth, canvas.clientHeight)),
      frame: current.frame, times: current.times, rafFrames: current.rafFrames,
      renderer: scene.getRenderer().getContext().getParameter(scene.getRenderer().getContext().VERSION),
    };
  });
}

(async () => {
  await fs.mkdir(evidence, {recursive:true});
  await new Promise(resolve => server.listen(0, '0.0.0.0', resolve));
  let browser;
  const report = {
    browser: 'Chromium', playwright: require('playwright/package.json').version,
    noInterception: true, rendering: 'SwiftShader software WebGL',
    proxyUsed: Boolean(proxyUrl), tlsTrustRelaxed: process.env.ATLAS_BROWSER_IGNORE_TLS === '1',
    backend: 'No local Beacon backend; real public GET APIs and built-in legacy fallback only',
    scenarios: [],
  };
  try {
    browser = await chromium.launch({
      executablePath: process.env.ATLAS_BROWSER_EXECUTABLE || undefined,
      headless: true,
      proxy: proxyUrl ? {server:proxyUrl, bypass:'localhost,127.0.0.1'} : undefined,
      args: ['--no-sandbox', '--use-angle=swiftshader', '--enable-unsafe-swiftshader'],
    });
    report.version = browser.version();
    for (const mobile of [false, true]) {
      const context = await browser.newContext({
        viewport: mobile ? {width:390, height:844} : {width:1280, height:800},
        deviceScaleFactor: mobile ? 3 : 1, isMobile:mobile, hasTouch:mobile,
        ignoreHTTPSErrors: report.tlsTrustRelaxed,
      });
      const page = await context.newPage();
      const errors = [], failedRequests = [], externalWrites = [];
      page.on('pageerror', error => errors.push(error.message));
      page.on('requestfailed', request => failedRequests.push({url:request.url(), error:request.failure()?.errorText}));
      page.on('request', request => {
        if (!['GET','HEAD'].includes(request.method()) && !['localhost','127.0.0.1'].includes(new URL(request.url()).hostname)) externalWrites.push(request.url());
      });
      await page.addInitScript(() => {
        const observation = window.__minimapObservation = {times:[], frame:{rects:[], camera:null}, rafFrames:0};
        function count() { observation.rafFrames++; requestAnimationFrame(count); }
        requestAnimationFrame(count);
        for (const name of ['clearRect','fillRect','moveTo']) {
          const original = CanvasRenderingContext2D.prototype[name];
          CanvasRenderingContext2D.prototype[name] = function(...args) {
            if (this.canvas.parentElement?.classList.contains('atlas-minimap')) {
              if (name === 'clearRect') { observation.times.push(performance.now()); observation.frame={rects:[],camera:null}; }
              if (name === 'fillRect') observation.frame.rects.push({x:args[0],y:args[1],width:args[2],height:args[3],color:this.fillStyle});
              if (name === 'moveTo' && this.strokeStyle === '#00ffff') observation.frame.camera={x:args[0],y:args[1]+5};
            }
            return original.apply(this,args);
          };
        }
      });
      await page.goto(`http://localhost:${server.address().port}/site/beacon/`, {waitUntil:'domcontentloaded'});
      try {
        await page.waitForFunction(() => document.querySelector('.atlas-minimap') && !document.querySelector('#loading'), null, {timeout:90000});
      } catch (error) {
        console.error(JSON.stringify({loading:await page.locator('#loading-status').textContent(), errors, failedRequests},null,2));
        throw error;
      }
      await page.waitForTimeout(1200);
      assert.deepEqual(errors, [], 'The actual Atlas must boot without JavaScript errors');
      const initial = await observe(page);
      assert.equal(initial.cities, 8);
      assert.ok(initial.agents > 0, 'Actual Atlas agents must be represented');
      assert.equal(initial.frame.rects.filter(mark => mark.width===5).length, initial.cities);
      assert.equal(initial.frame.rects.filter(mark => mark.width===2).length, initial.agents);
      assert.ok(initial.pixels.amber > 0 && initial.pixels.green > 0 && initial.pixels.cyan > 0);
      assert.equal(initial.pointerEvents, 'none');
      assert.equal(initial.hitTarget, 'atlas-canvas');
      assert.equal(initial.overflow, false);
      assert.equal(initial.rect.width, mobile ? 128 : 172);
      assert.equal(initial.rect.height, mobile ? 96 : 132);
      assert.equal(initial.backing.width, initial.clientWidth * (mobile ? 2 : 1), 'Minimap DPR must cap at 2');
      for (const [index, mark] of initial.frame.rects.filter(mark=>mark.width===5).entries()) {
        assert.ok(Math.abs(mark.x + 2.5 - initial.projectedCities[index].x) < 0.001);
        assert.ok(Math.abs(mark.y + 2.5 - initial.projectedCities[index].y) < 0.001);
      }
      await page.screenshot({path:path.join(evidence, mobile?'mobile.jpg':'desktop.jpg'),type:'jpeg',quality:75});
      const x=initial.rect.x+initial.rect.width/2, y=initial.rect.y+initial.rect.height/2;
      let afterPan = null;
      if (mobile) {
        const session = await context.newCDPSession(page);
        await session.send('Input.dispatchTouchEvent',{type:'touchStart',touchPoints:[{x:x-22,y},{x:x+22,y}]});
        for (let i=1;i<=6;i++) await session.send('Input.dispatchTouchEvent',{type:'touchMove',touchPoints:[{x:x-22-i*4,y:y-i*2},{x:x+22+i*4,y:y-i*2}]});
        await session.send('Input.dispatchTouchEvent',{type:'touchEnd',touchPoints:[]});
        await session.detach();
      } else {
        await page.mouse.move(x,y); await page.mouse.down({button:'right'});
        await page.mouse.move(x-55,y-18,{steps:10}); await page.mouse.up({button:'right'});
        await page.waitForTimeout(250);
        afterPan = await observe(page);
        assert.ok(Math.hypot(afterPan.camera.x-initial.camera.x,afterPan.camera.z-initial.camera.z)>5, 'Right drag through the minimap must pan the real camera');
        await page.mouse.move(x,y); await page.mouse.wheel(0,-420);
      }
      await page.waitForTimeout(900);
      const after = await observe(page);
      assert.ok(Math.abs(Math.hypot(after.camera.x,after.camera.y,after.camera.z)-Math.hypot(initial.camera.x,initial.camera.y,initial.camera.z))>5, 'Gestures through the minimap must reach real OrbitControls');
      assert.ok(Math.hypot(after.frame.camera.x-initial.frame.camera.x,after.frame.camera.y-initial.frame.camera.y)>0.1, 'Real camera marker must update after gestures');
      await page.waitForTimeout(3200);
      const final = await observe(page);
      const intervals=final.times.slice(1).map((time,index)=>time-final.times[index]);
      assert.ok(intervals.length>=2);
      assert.ok(Math.min(...intervals)>=97, 'Drawing must stay within the 10Hz cap (3ms measurement tolerance)');
      assert.deepEqual(errors, []);
      assert.deepEqual(externalWrites, []);
      const compact = observation => ({
        cities:observation.cities, agents:observation.agents, rect:observation.rect,
        backing:observation.backing, clientWidth:observation.clientWidth, clientHeight:observation.clientHeight,
        pointerEvents:observation.pointerEvents, hitTarget:observation.hitTarget, overflow:observation.overflow,
        pixels:observation.pixels, camera:observation.camera, cameraMark:observation.frame.camera,
        cityMarks:observation.frame.rects.filter(mark=>mark.width===5).length,
        agentMarks:observation.frame.rects.filter(mark=>mark.width===2).length,
        renderer:observation.renderer,
      });
      report.scenarios.push({mobile, initial:compact(initial), afterPan:afterPan?compact(afterPan):null, after:compact(after), drawCount:final.times.length, minimumDrawIntervalMs:Math.min(...intervals), firstDrawIntervalsMs:intervals.slice(0,10), rafFrames:final.rafFrames, failedRequests, pageErrors:errors, externalWrites});
      await context.close();
    }
    await fs.writeFile(path.join(evidence,'browser-receipt.json'),JSON.stringify(report,null,2)+'\n');
    console.log(JSON.stringify(report.scenarios.map(({mobile,initial,drawCount,minimumDrawIntervalMs,rafFrames,pageErrors})=>({mobile,cities:initial.cities,agents:initial.agents,drawCount,minimumDrawIntervalMs,rafFrames,pageErrors})),null,2));
  } finally { await browser?.close(); await new Promise(resolve=>server.close(resolve)); }
})().catch(error=>{console.error(error);process.exitCode=1;});
