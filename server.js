import { createServer } from "node:http";
import { readFile } from "node:fs/promises";
import { existsSync } from "node:fs";
import { extname, join, normalize } from "node:path";
import { spawn } from "node:child_process";
import { fileURLToPath } from "node:url";

const rootDir = fileURLToPath(new URL(".", import.meta.url));
const publicDir = join(rootDir, "public");
const port = Number(process.env.PORT || 3000);
const sessions = new Map();
const intentLog = [];

// Prefer the project venv if it exists (so local dev uses the same
// Python that has langgraph installed). Falls back to whatever
// `python3` resolves to on PATH (Docker/Render uses /opt/venv via PATH).
const venvPython = join(rootDir, ".venv", "bin", "python3");
const pythonBin = existsSync(venvPython) ? venvPython : "python3";

const mimeTypes = {
  ".html": "text/html; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".js": "application/javascript; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".svg": "image/svg+xml"
};

function readJson(req) {
  return new Promise((resolve, reject) => {
    let body = "";
    req.on("data", (chunk) => {
      body += chunk;
      if (body.length > 1_000_000) {
        reject(new Error("Request body too large"));
        req.destroy();
      }
    });
    req.on("end", () => {
      try {
        resolve(body ? JSON.parse(body) : {});
      } catch {
        reject(new Error("Invalid JSON"));
      }
    });
    req.on("error", reject);
  });
}

function runAgent(payload) {
  return new Promise((resolve, reject) => {
    const agent = spawn(pythonBin, ["agent/commerce_agent.py"], {
      cwd: rootDir,
      stdio: ["pipe", "pipe", "pipe"],
      env: { ...process.env, PYTHONUNBUFFERED: "1" }
    });

    let stdout = "";
    let stderr = "";
    agent.stdout.on("data", (chunk) => {
      stdout += chunk;
    });
    agent.stderr.on("data", (chunk) => {
      stderr += chunk;
    });
    agent.on("error", reject);
    agent.on("close", (code) => {
      if (code !== 0) {
        reject(new Error(stderr || `Agent exited with ${code}`));
        return;
      }
      try {
        resolve(JSON.parse(stdout));
      } catch {
        reject(new Error(`Agent returned invalid JSON: ${stdout}`));
      }
    });
    agent.stdin.end(JSON.stringify(payload));
  });
}

async function serveStatic(req, res) {
  const url = new URL(req.url, `http://${req.headers.host}`);
  const requested = url.pathname === "/" ? "/index.html" : decodeURIComponent(url.pathname);
  const safePath = normalize(requested).replace(/^(\.\.[/\\])+/, "");
  const filePath = join(publicDir, safePath);

  if (!filePath.startsWith(publicDir) || !existsSync(filePath)) {
    res.writeHead(404, { "content-type": "text/plain; charset=utf-8" });
    res.end("Not found");
    return;
  }

  const body = await readFile(filePath);
  res.writeHead(200, {
    "content-type": mimeTypes[extname(filePath)] || "application/octet-stream",
    "cache-control": "no-store"
  });
  res.end(body);
}

const server = createServer(async (req, res) => {
  try {
    if (req.method === "GET" && req.url === "/health") {
      res.writeHead(200, { "content-type": "application/json" });
      res.end(JSON.stringify({ ok: true, service: "storefront-concierge" }));
      return;
    }

    if (req.method === "POST" && req.url === "/api/chat") {
      const payload = await readJson(req);
      const sessionId = payload.sessionId || "demo";
      const session = sessions.get(sessionId) || {};
      if (payload.message) {
        intentLog.push({
          sessionId,
          message: payload.message,
          selectedSku: payload.selectedSku || "",
          timestamp: new Date().toISOString()
        });
        if (intentLog.length > 60) intentLog.shift();
      }
      const recentIntents = intentLog.slice(-15);
      const result = await runAgent({ ...payload, ...session, sessionId, recentIntents });
      sessions.set(sessionId, {
        products: result.products || session.products || [],
        cart: result.cart || session.cart || [],
        order: result.order || session.order || {},
        automation: result.automation || session.automation || {},
        radar: result.radar || session.radar || {}
      });
      res.writeHead(200, { "content-type": "application/json" });
      res.end(JSON.stringify(result));
      return;
    }

    if (req.method === "GET") {
      await serveStatic(req, res);
      return;
    }

    res.writeHead(405, { "content-type": "application/json" });
    res.end(JSON.stringify({ error: "Method not allowed" }));
  } catch (error) {
    res.writeHead(500, { "content-type": "application/json" });
    res.end(JSON.stringify({ error: error.message }));
  }
});

server.listen(port, () => {
  console.log(`Storefront Concierge running at http://localhost:${port}`);
});
