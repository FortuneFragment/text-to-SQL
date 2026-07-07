import { spawn } from "node:child_process";
import fs from "node:fs";
import http from "node:http";
import net from "node:net";
import path from "node:path";
import process from "node:process";
import { fileURLToPath } from "node:url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const frontendDir = path.resolve(__dirname, "..");
const repoRoot = path.resolve(frontendDir, "..");
const backendDir = path.join(repoRoot, "t2s-backend");
const backendTarget = process.env.VITE_PROXY_TARGET || "http://127.0.0.1:8000";
const backendUrl = new URL(backendTarget);
const backendCheckUrl = new URL(backendTarget);
if (backendCheckUrl.hostname === "0.0.0.0") {
  backendCheckUrl.hostname = "127.0.0.1";
}
const backendHealthUrl = new URL("/health", backendCheckUrl);
const isWindows = process.platform === "win32";
const localBackendHostnames = new Set(["127.0.0.1", "localhost", "0.0.0.0"]);

let backendProcess = null;
let viteProcess = null;

function getPythonPath() {
  const venvPython = path.join(backendDir, "venv", isWindows ? "Scripts/python.exe" : "bin/python");
  if (fs.existsSync(venvPython)) {
    return venvPython;
  }
  return isWindows ? "python.exe" : "python";
}

function requestHealth(timeoutMs = 1200) {
  return new Promise((resolve) => {
    const request = http.get(backendHealthUrl, { timeout: timeoutMs }, (response) => {
      response.resume();
      resolve(response.statusCode === 200);
    });

    request.on("timeout", () => {
      request.destroy();
      resolve(false);
    });
    request.on("error", () => resolve(false));
  });
}

function isPortOpen(timeoutMs = 800) {
  const port = Number(backendCheckUrl.port || 80);
  return new Promise((resolve) => {
    const socket = net.createConnection({ host: backendCheckUrl.hostname, port });
    const done = (result) => {
      socket.destroy();
      resolve(result);
    };

    socket.setTimeout(timeoutMs);
    socket.once("connect", () => done(true));
    socket.once("timeout", () => done(false));
    socket.once("error", () => done(false));
  });
}

async function waitForBackend(timeoutMs = 45000) {
  const startedAt = Date.now();
  while (Date.now() - startedAt < timeoutMs) {
    if (await requestHealth()) {
      return true;
    }
    await new Promise((resolve) => setTimeout(resolve, 500));
  }
  return false;
}

function startBackend() {
  const pythonPath = getPythonPath();
  backendProcess = spawn(
    pythonPath,
    ["-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", "8000", "--log-level", "info"],
    {
      cwd: backendDir,
      stdio: "inherit",
    }
  );

  backendProcess.on("error", (error) => {
    console.error(`Failed to start backend: ${error.message}`);
    process.exit(1);
  });

  backendProcess.on("exit", (code, signal) => {
    if (!viteProcess || viteProcess.exitCode !== null) {
      return;
    }
    console.error(`Backend exited unexpectedly: code=${code ?? "null"} signal=${signal ?? "null"}`);
    viteProcess.kill();
  });
}

function startVite() {
  const viteBin = path.join(frontendDir, "node_modules", "vite", "bin", "vite.js");
  viteProcess = spawn(process.execPath, [viteBin, "--host", "0.0.0.0", "--port", "5173"], {
    cwd: frontendDir,
    stdio: "inherit",
    env: {
      ...process.env,
      VITE_PROXY_TARGET: backendTarget,
    },
  });

  viteProcess.on("error", (error) => {
    if (backendProcess && backendProcess.exitCode === null) {
      backendProcess.kill();
    }
    console.error(`Failed to start Vite: ${error.message}`);
    process.exit(1);
  });

  viteProcess.on("exit", (code) => {
    if (backendProcess && backendProcess.exitCode === null) {
      backendProcess.kill();
    }
    process.exit(code ?? 0);
  });
}

function shutdown() {
  if (viteProcess && viteProcess.exitCode === null) {
    viteProcess.kill();
  }
  if (backendProcess && backendProcess.exitCode === null) {
    backendProcess.kill();
  }
}

process.on("SIGINT", shutdown);
process.on("SIGTERM", shutdown);

const canStartLocalBackend =
  localBackendHostnames.has(backendUrl.hostname) && Number(backendUrl.port || 80) === 8000;

if (!(await requestHealth())) {
  if (!canStartLocalBackend) {
    console.warn(`Backend health check failed for ${backendHealthUrl}. Starting Vite only.`);
  } else if (await isPortOpen()) {
    console.error(`Port ${backendUrl.port} is already in use, but ${backendHealthUrl} is not healthy.`);
    process.exit(1);
  } else {
    console.log(`Starting backend at ${backendTarget}...`);
    startBackend();
    if (!(await waitForBackend())) {
      console.error(`Backend did not become healthy: ${backendHealthUrl}`);
      shutdown();
      process.exit(1);
    }
  }
}

startVite();
