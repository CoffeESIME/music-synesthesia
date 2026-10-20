const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const fs = require('node:fs');
const path = require('node:path');
const os = require('node:os');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const root = path.join(__dirname, '..');
const hueEnabled = process.env.TEST_HUE_ENABLED !== 'false';
const code = fs.readFileSync(path.join(root, 'static/microphone.js'), 'utf8');
const detector = vm.runInNewContext(code + '\ndetectMicrophoneNote');
const names = ['C','C#','D','D#','E','F','F#','G','G#','A','A#','B'];
for (const rate of [11025, 12000]) {
    for (let midi = 36; midi <= 83; midi++) {
        const f = 440 * 2 ** ((midi - 69) / 12);
        const samples = Float32Array.from({ length: 1024 }, (_, i) =>
            0.2 * Math.sin(2 * Math.PI * f * i / rate) + 0.08 * Math.sin(4 * Math.PI * f * i / rate));
        assert.equal(detector(samples, rate), names[midi % 12], `MIDI ${midi}, rate ${rate}`);
    }
    assert.equal(detector(new Float32Array(1024), rate), null);
    assert.equal(detector(new Float32Array(1024).fill(0.2), rate), null);
}

const wav = Buffer.alloc(44 + 48000 * 2 * 4);
wav.write('RIFF'); wav.writeUInt32LE(wav.length - 8, 4); wav.write('WAVEfmt ', 8);
wav.writeUInt32LE(16, 16); wav.writeUInt16LE(1, 20); wav.writeUInt16LE(1, 22);
wav.writeUInt32LE(48000, 24); wav.writeUInt32LE(96000, 28); wav.writeUInt16LE(2, 32);
wav.writeUInt16LE(16, 34); wav.write('data', 36); wav.writeUInt32LE(wav.length - 44, 40);
for (let i = 0; i < 48000 * 4; i++) wav.writeInt16LE(Math.round(8000 * Math.sin(2 * Math.PI * 440 * i / 48000)), 44 + i * 2);
const fixture = path.join(fs.mkdtempSync(path.join(os.tmpdir(), 'hue-mic-')), 'tone.wav');
fs.writeFileSync(fixture, wav);

(async () => {
    const browser = await chromium.launch({ channel: 'chrome', headless: true, args: [
        '--use-fake-device-for-media-stream', '--use-fake-ui-for-media-stream',
        `--use-file-for-fake-audio-capture=${fixture}`,
    ] });
    try {
        const page = await browser.newPage();
        const errors = [];
        let lightCalls = 0;
        let serverStarts = 0;
        let socketCalls = 0;
        let sharedStateCalls = 0;
        let activeProfile = 'scriabin';
        page.on('pageerror', error => errors.push(error.message));
        await page.routeWebSocket('**/ws/color_stream', () => { socketCalls++; });
        const routeApp = route => {
            const url = new URL(route.request().url());
            if (url.pathname === '/api/listener/start') serverStarts++;
            if (url.pathname === '/api/set_light') lightCalls++;
            if (url.pathname === '/api/status' || url.pathname.startsWith('/api/profile/')) sharedStateCalls++;
            if (url.pathname === '/api/profile/newton') activeProfile = 'newton';
            const data = {
                '/api/profiles': {
                    scriabin: Object.fromEntries(names.map(note => [note, [0,255,0]])),
                    newton: Object.fromEntries(names.map(note => [note, [255,127,0]])),
                },
                '/api/lights': { light_ids: hueEnabled ? ['fake-light'] : [] },
                '/api/status': { running: false, profile: activeProfile, last_error: 'Invalid input device' },
                '/api/profile/newton': { profile: activeProfile },
                '/api/set_light': {},
                '/api/client-config': { https_port: 18744, hue_enabled: hueEnabled },
                '/api/upload': { audio_url: '/temp/tone.wav', timeline: [{ time: 0, note: 'A' }] },
            };
            if (data[url.pathname]) return route.fulfill({ json: data[url.pathname] });
            if (url.pathname === '/temp/tone.wav') return route.fulfill({ body: wav, contentType: 'audio/wav' });
            const filename = path.join(root, url.pathname === '/' ? 'static/index.html' : url.pathname);
            if (!fs.existsSync(filename)) return route.fulfill({ status: 404 });
            return route.fulfill({ body: fs.readFileSync(filename), contentType: filename.endsWith('.js') ? 'text/javascript' : filename.endsWith('.css') ? 'text/css' : 'text/html' });
        };
        await page.route('**/*', routeApp);
        await page.goto('https://microphone.test/');
        await page.locator('#start-button').click();
        await page.waitForFunction(() => browserMicrophone.running && lastMicrophoneNote === 'A');
        assert.equal(serverStarts, 0);
        assert.equal(lightCalls > 0, hueEnabled);
        assert.ok(!(await page.locator('#feedback').textContent()).includes('Invalid input device'));
        await page.locator('#profile-select').selectOption('newton');
        await page.waitForFunction(() => document.querySelector('#color-hex').textContent === '#FF7F00');
        await page.evaluate(() => { window.testTracks = browserMicrophone.stream.getTracks(); });
        await page.locator('#stop-button').click();
        assert.equal(await page.evaluate(() => testTracks.every(track => track.readyState === 'ended') && browserMicrophone.context === null), true);

        await page.locator('#audio-file-input').setInputFiles(fixture);
        await page.waitForFunction(() => songTimeline.length === 1);
        await page.evaluate(async () => { player.muted = true; await player.play(); });
        await page.waitForFunction(() => player.currentTime > 0);
        await page.locator('#start-button').click();
        await page.waitForFunction(() => browserMicrophone.running);
        assert.equal(await page.evaluate(() => player.paused), true);
        await page.evaluate(async () => { player.currentTime = 0; await player.play(); });
        await page.waitForFunction(() => !browserMicrophone.running);
        await page.evaluate(() => player.pause());
        if (!hueEnabled) {
            // A second visitor changing profiles must not affect this session.
            const other = await browser.newPage();
            await other.route('**/*', routeApp);
            await other.routeWebSocket('**/ws/color_stream', () => { socketCalls++; });
            await other.goto('https://microphone.test/');
            await other.waitForFunction(() => profilesReady);
            await other.locator('#profile-select').selectOption('newton');
            await other.locator('#profile-select').selectOption('scriabin');
            await other.locator('#start-button').click();
            await other.waitForFunction(() => lastMicrophoneNote === 'A');
            assert.equal(await other.locator('#color-hex').textContent(), '#00FF00');
            await page.waitForTimeout(5200);
            assert.equal(await page.locator('#profile-select').inputValue(), 'newton');
            await other.close();
            assert.equal(lightCalls, 0);
            assert.equal(socketCalls, 0);
            assert.equal(sharedStateCalls, 0);
        }

        await page.evaluate(() => {
            window.originalGetUserMedia = navigator.mediaDevices.getUserMedia.bind(navigator.mediaDevices);
            navigator.mediaDevices.getUserMedia = async () => { throw new DOMException('Denied', 'NotAllowedError'); };
        });
        await page.locator('#start-button').click();
        await page.waitForFunction(() => document.querySelector('#feedback').textContent.includes('Permite el acceso'));
        assert.equal(await page.evaluate(() => browserMicrophone.context), null);

        await page.evaluate(() => {
            navigator.mediaDevices.getUserMedia = () => new Promise(resolve => { window.resolvePermission = resolve; });
        });
        await page.locator('#start-button').click();
        await page.waitForFunction(() => typeof window.resolvePermission === 'function');
        await page.locator('#stop-button').click();
        await page.evaluate(async () => {
            const stream = await originalGetUserMedia({ audio: true });
            window.testTracks = stream.getTracks();
            resolvePermission(stream);
        });
        await page.waitForFunction(() => testTracks.every(track => track.readyState === 'ended'));
        assert.equal(await page.evaluate(() => browserMicrophone.running), false);

        await page.goto('http://192.0.2.55:18743/');
        await page.locator('#start-button').click();
        await page.waitForFunction(() => document.querySelector('#feedback').textContent.includes('requiere HTTPS'));
        assert.equal(await page.locator('#microphone-secure-link').getAttribute('href'), 'https://192.0.2.55:18744/');
        assert.deepEqual(errors, []);
        console.log(`PASS (${hueEnabled ? 'Hue' : 'web'}): 96 tonal signals, silence/DC rejection, browser mic, profile, stop, track playback, denied/canceled permissions, LAN HTTPS; no server capture. Light commands: ${lightCalls}.`);
    } finally {
        await browser.close();
        fs.unlinkSync(fixture);
        fs.rmdirSync(path.dirname(fixture));
    }
})().catch(error => { console.error(error); process.exitCode = 1; });
