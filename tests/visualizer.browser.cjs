const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const outputDir = process.env.VISUALIZER_OUTPUT_DIR || path.join(require('node:os').tmpdir(), 'hue-visualizer-check');
fs.mkdirSync(outputDir, { recursive: true });

(async () => {
    const browser = await chromium.launch({ channel: 'chrome', headless: true });
    const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    const notes = ['C','C#','D','D#','E','F','F#','G','G#','A','A#','B'];
    const profile = Object.fromEntries(notes.map(note => [note, [135,206,235]]));
    let socket;
    await page.routeWebSocket('**/ws/color_stream', ws => { socket = ws; });
    await page.route('https://synesthesia.test/**', route => {
        const url = new URL(route.request().url());
        const data = {
            '/api/profiles': { scriabin: profile, newton: Object.fromEntries(notes.map(note => [note, [255,127,0]])) },
            '/api/lights': { light_ids: ['test'] },
            '/api/client-config': { https_port: 18744, hue_enabled: true },
            '/api/status': { running: false, profile: 'scriabin' },
            '/api/profile/newton': { profile: 'newton' },
            '/api/set_light': {},
        };
        if (data[url.pathname]) return route.fulfill({ json: data[url.pathname] });
        const filename = path.join(__dirname, '..', url.pathname === '/' ? 'static/index.html' : url.pathname);
        if (!fs.existsSync(filename)) return route.fulfill({ status: 404 });
        return route.fulfill({ body: fs.readFileSync(filename), contentType: filename.endsWith('.js') ? 'text/javascript' : filename.endsWith('.css') ? 'text/css' : 'text/html' });
    });
    await page.goto('https://synesthesia.test/');
    await page.waitForFunction(() => document.querySelector('#profile-select').disabled === false);
    socket.send(JSON.stringify({ nota: 'E', color: '#87CEEB' }));
    await page.waitForFunction(() => document.querySelector('#note-display').textContent === 'E');
    await page.waitForTimeout(900);
    await page.screenshot({ path: path.join(outputDir, 'visualizer-desktop.png') });
    const report = await page.evaluate(() => {
        const shapes = [];
        const start = performance.now();
        for (const note of ['C','C#','D','D#','E','F','F#','G','G#','A','A#','B']) {
            visualizer.setSignal(note, '#87CEEB');
            shapes.push(Array.from(visualizer.targets.slice(0, 8)).join(','));
            if (!visualizer.targets.every(Number.isFinite)) throw new Error('Invalid coordinate');
        }
        visualizer.setSignal('E', '#87CEEB');
        return { uniqueShapes: new Set(shapes).size, generationMs: performance.now() - start };
    });
    assert.equal(report.uniqueShapes, 12);
    await page.getByRole('button', { name: 'Anillos', exact: true }).click();
    assert.equal(await page.locator('#main-content').getAttribute('data-visualization'), 'rings');
    await page.screenshot({ path: path.join(outputDir, 'visualizer-rings.png') });
    await page.getByRole('button', { name: 'Pausar movimiento', exact: true }).click();
    assert.equal(await page.locator('#motion-button').getAttribute('aria-pressed'), 'true');
    await page.evaluate(() => visualizer.setRunning(true));
    await page.waitForTimeout(100);
    assert.equal(await page.evaluate(() => visualizer.frame), null);
    await page.getByRole('button', { name: 'Solo color', exact: true }).click();
    assert.equal(await page.locator('#note-visualizer').isVisible(), false);
    await page.getByRole('button', { name: 'Patrones', exact: true }).click();
    await page.locator('#profile-select').selectOption('newton');
    await page.waitForFunction(() => document.querySelector('#color-hex').textContent === '#FF7F00');
    await page.evaluate(() => {
        songTimeline = [{ time: 0, note: 'C' }, { time: 1, note: 'G' }];
        profileSelect.value = 'scriabin';
        player.currentTime = 1.2;
        syncTrackColor(true);
    });
    assert.equal(await page.locator('#note-display').textContent(), 'G');
    await page.getByRole('button', { name: 'Reanudar movimiento', exact: true }).click();
    await page.evaluate(() => visualizer.setRunning(true));
    await page.waitForTimeout(100);
    assert.notEqual(await page.evaluate(() => visualizer.frame), null);
    await page.emulateMedia({ reducedMotion: 'reduce' });
    await page.locator('#motion-button').waitFor({ state: 'hidden' });
    assert.equal(await page.locator('#motion-button').isVisible(), false);
    await page.evaluate(() => visualizer.setRunning(true));
    await page.waitForTimeout(100);
    assert.equal(await page.evaluate(() => visualizer.frame), null);
    await page.setViewportSize({ width: 390, height: 844 });
    await page.locator('#main-content').scrollIntoViewIfNeeded();
    await page.screenshot({ path: path.join(outputDir, 'visualizer-mobile.png') });
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false);
    await page.getByRole('button', { name: 'Pantalla completa', exact: true }).click();
    await page.waitForFunction(() => document.fullscreenElement?.id === 'main-content');
    await page.getByRole('button', { name: 'Salir de pantalla completa', exact: true }).click();
    assert.deepEqual(errors, []);
    console.log(JSON.stringify({ ...report, errors, checks: 'WebSocket, 12 patterns, view modes, motion pause, profile, track seek, reduced motion, mobile overflow, fullscreen' }));
    await browser.close();
})().catch(error => { console.error(error); process.exit(1); });
