const messages = document.querySelector("#messages");
const form = document.querySelector("#chat-form");
const input = document.querySelector("#message");
const reset = document.querySelector("#reset");
const suggestions = document.querySelectorAll(".suggestions button");

let sessionId = crypto.randomUUID();

function addMessage(role, text, trace = []) {
  const bubble = document.createElement("article");
  bubble.className = `message ${role}`;
  bubble.textContent = text;

  if (trace.length) {
    const traceEl = document.createElement("div");
    traceEl.className = "trace";
    for (const item of trace) {
      const chip = document.createElement("span");
      chip.textContent = item;
      traceEl.append(chip);
    }
    bubble.append(traceEl);
  }

  messages.append(bubble);
  messages.scrollTop = messages.scrollHeight;
}

async function sendMessage(text) {
  addMessage("user", text);
  input.value = "";
  input.disabled = true;

  try {
    const response = await fetch("/api/chat", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ message: text, sessionId })
    });
    const result = await response.json();
    if (!response.ok) {
      throw new Error(result.error || "Chat request failed");
    }
    addMessage("agent", result.reply, result.trace || []);
  } catch (error) {
    addMessage("agent", `I hit an execution error: ${error.message}`);
  } finally {
    input.disabled = false;
    input.focus();
  }
}

form.addEventListener("submit", (event) => {
  event.preventDefault();
  const text = input.value.trim();
  if (text) sendMessage(text);
});

reset.addEventListener("click", () => {
  sessionId = crypto.randomUUID();
  messages.textContent = "";
  addMessage(
    "agent",
    "Fresh shopping session started. Tell me what you want, a budget, and any constraints.",
    ["session.reset"]
  );
});

for (const button of suggestions) {
  button.addEventListener("click", () => sendMessage(button.textContent));
}

addMessage(
  "agent",
  "Hi, I can search the catalog, compare options, manage a cart, and simulate checkout. Try asking for waterproof trail shoes under $150.",
  ["agent.ready", "mcp.tools.loaded"]
);
