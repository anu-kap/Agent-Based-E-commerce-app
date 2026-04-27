const messages = document.querySelector("#messages");
const form = document.querySelector("#chat-form");
const input = document.querySelector("#message");
const reset = document.querySelector("#reset");
const suggestions = document.querySelectorAll(".suggestions button");

let sessionId = crypto.randomUUID();

function formatMoney(product) {
  const currency = product.currency || "USD";
  const price = Number(product.price || 0);
  return `${currency} $${price.toFixed(price % 1 === 0 ? 0 : 2)}`;
}

function addProductCards(container, products = []) {
  const usableProducts = products.filter((product) => product && product.sku && product.name && product.price !== undefined);
  if (!usableProducts.length) return;

  const grid = document.createElement("div");
  grid.className = "product-grid";

  for (const product of usableProducts.slice(0, 4)) {
    const card = document.createElement("article");
    card.className = "product-card";

    if (product.imageUrl) {
      const image = document.createElement("img");
      image.src = product.imageUrl;
      image.alt = product.name;
      image.loading = "lazy";
      card.append(image);
    }

    const body = document.createElement("div");
    body.className = "product-body";

    const title = document.createElement("h3");
    title.textContent = product.name;
    body.append(title);

    const price = document.createElement("p");
    price.className = "product-price";
    price.textContent = formatMoney(product);
    body.append(price);

    if (product.description) {
      const description = document.createElement("p");
      description.className = "product-description";
      description.textContent = product.description.replace(/<[^>]*>/g, "");
      body.append(description);
    }

    const actions = document.createElement("div");
    actions.className = "product-actions";

    const add = document.createElement("button");
    add.type = "button";
    add.textContent = "Add";
    add.title = `Add ${product.name} to cart`;
    add.addEventListener("click", () => {
      sendMessage(`Add ${product.name} to my cart`, { selectedSku: product.sku });
    });
    actions.append(add);

    if (product.url) {
      const link = document.createElement("a");
      link.href = product.url;
      link.target = "_blank";
      link.rel = "noreferrer";
      link.textContent = "View";
      actions.append(link);
    }

    body.append(actions);
    card.append(body);
    grid.append(card);
  }

  container.append(grid);
}

function addCheckoutLink(container, order = {}) {
  const checkoutUrl = order.quote?.checkoutUrl;
  if (!checkoutUrl) return;

  const actions = document.createElement("div");
  actions.className = "post-cart-actions";

  const link = document.createElement("a");
  link.className = "checkout-link";
  link.href = checkoutUrl;
  link.target = "_blank";
  link.rel = "noreferrer";
  link.textContent = "Open Shopify checkout";
  actions.append(link);

  const simulate = document.createElement("button");
  simulate.type = "button";
  simulate.className = "simulate-order";
  simulate.textContent = "Simulate order paid";
  simulate.title = "Trigger Kestra post-order automation";
  simulate.addEventListener("click", () => {
    sendMessage("Simulate Shopify order paid webhook");
  });
  actions.append(simulate);

  container.append(actions);
}

function addAutomationStatus(container, automation = {}) {
  if (!automation.kestra) return;

  const panel = document.createElement("div");
  panel.className = "automation-status";

  const title = document.createElement("strong");
  title.textContent = automation.kestra.status === "triggered" ? "Kestra workflow started" : "Kestra workflow ready";
  panel.append(title);

  const detail = document.createElement("span");
  detail.textContent = automation.kestra.executionId
    ? `Execution ${automation.kestra.executionId}`
    : "Start Kestra locally to execute this workflow.";
  panel.append(detail);

  if (automation.kestra.url) {
    const link = document.createElement("a");
    link.href = automation.kestra.url;
    link.target = "_blank";
    link.rel = "noreferrer";
    link.textContent = "Open Kestra";
    panel.append(link);
  }

  container.append(panel);
}

function addMessage(role, text, trace = [], meta = {}) {
  const bubble = document.createElement("article");
  bubble.className = `message ${role}`;
  bubble.textContent = text;

  if (role === "agent") {
    if ((meta.trace || []).includes("mcp.search_catalog")) {
      addProductCards(bubble, meta.products || []);
    }
    if (!(meta.trace || []).includes("kestra.post_order_workflow")) {
      addCheckoutLink(bubble, meta.order || {});
    }
    addAutomationStatus(bubble, meta.automation || {});
  }

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

async function sendMessage(text, extraPayload = {}) {
  addMessage("user", text);
  input.value = "";
  input.disabled = true;

  try {
    const response = await fetch("/api/chat", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ message: text, sessionId, ...extraPayload })
    });
    const result = await response.json();
    if (!response.ok) {
      throw new Error(result.error || "Chat request failed");
    }
    addMessage("agent", result.reply, result.trace || [], result);
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
  "Hi, I can guide campus-store shoppers to the right spirit gear, build a real Shopify cart, and then simulate post-order automation for the merchant. Try asking for a hoodie, alumni gift, hat, or mug.",
  ["agent.ready", "mcp.tools.loaded"]
);
