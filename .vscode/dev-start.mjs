import { spawn } from 'node:child_process';
import { resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const workspace = resolve(fileURLToPath(new URL('..', import.meta.url)));
const mode = process.argv[2];

const services = {
  backend: {
    url: 'http://127.0.0.1:8000/api/health',
    isReady: (response, body) => response.ok && body.includes('"status":"healthy"'),
    readyLine: 'Uvicorn running on http://127.0.0.1:8000',
    command: 'python',
    args: ['-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', '8000'],
    cwd: resolve(workspace, 'backend'),
  },
  frontend: {
    url: 'http://127.0.0.1:8080/',
    isReady: (response, body) => response.ok && body.includes('TerraPulse AI'),
    readyLine: 'Local:   http://127.0.0.1:8080/',
    command: process.execPath,
    args: [resolve(workspace, 'terrapulse-frontend/node_modules/vite/bin/vite.js'), '--host', '127.0.0.1', '--port', '8080', '--strictPort'],
    cwd: resolve(workspace, 'terrapulse-frontend'),
  },
};

const service = services[mode];
if (!service) throw new Error('Choose backend or frontend.');

async function alreadyRunning() {
  try {
    const response = await fetch(service.url, { signal: AbortSignal.timeout(1200) });
    const body = await response.text();
    return service.isReady(response, body);
  } catch {
    return false;
  }
}

if (await alreadyRunning()) {
  process.stdout.write(`${service.readyLine} (already running)\n`);
  setInterval(() => {}, 60_000);
} else {
  const child = spawn(service.command, service.args, { cwd: service.cwd, stdio: 'inherit', windowsHide: true });
  const stopChild = () => { if (!child.killed) child.kill(); };
  process.on('SIGINT', stopChild);
  process.on('SIGTERM', stopChild);
  child.on('error', (error) => { process.stderr.write(`${error.message}\n`); process.exitCode = 1; });
  child.on('exit', (code) => { process.exit(code ?? 1); });
}
