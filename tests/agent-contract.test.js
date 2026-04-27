import { spawn } from "node:child_process";
import test from "node:test";
import assert from "node:assert/strict";

function runAgent(message) {
  return new Promise((resolve, reject) => {
    const child = spawn("python3", ["agent/commerce_agent.py"], { stdio: ["pipe", "pipe", "pipe"] });
    let stdout = "";
    let stderr = "";
    child.stdout.on("data", (chunk) => {
      stdout += chunk;
    });
    child.stderr.on("data", (chunk) => {
      stderr += chunk;
    });
    child.on("error", reject);
    child.on("close", (code) => {
      if (code !== 0) reject(new Error(stderr));
      else resolve(JSON.parse(stdout));
    });
    child.stdin.end(JSON.stringify({ message, sessionId: "test" }));
  });
}

test("agent searches catalog through MCP tools", async () => {
  const result = await runAgent("Find waterproof trail shoes under $150");
  assert.match(result.reply, /Northline Waterproof Trail Shoe/);
  assert.ok(result.trace.some((item) => item.includes("search_catalog")));
});

test("agent prepares checkout order", async () => {
  const result = await runAgent("Checkout with standard shipping");
  assert.match(result.reply, /ORD-DEMO-1001/);
  assert.ok(result.trace.includes("kestra.workflow.prepared"));
});
