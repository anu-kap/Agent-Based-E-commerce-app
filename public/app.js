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

function addProductCards(container, products = [], options = {}) {
  const usableProducts = products.filter((product) => product && product.sku && product.name && product.price !== undefined);
  if (!usableProducts.length) return;

  const grid = document.createElement("div");
  grid.className = "product-grid";

  for (const product of usableProducts.slice(0, options.limit || 4)) {
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

    const meta = document.createElement("p");
    meta.className = "product-meta";
    meta.textContent = product.inventory === "available" ? "Available now" : "Campus store item";
    body.append(meta);

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

function addRadarReport(container, radar = {}) {
  if (!radar.reportId) return;

  const report = document.createElement("section");
  report.className = "radar-report";

  const header = document.createElement("div");
  header.className = "radar-header";
  const title = document.createElement("h3");
  title.textContent = "Campus Demand Radar";
  const badge = document.createElement("span");
  badge.textContent = radar.reportId;
  header.append(title, badge);
  report.append(header);

  const summary = document.createElement("p");
  summary.className = "radar-summary";
  summary.textContent = "This scan combines public campus signals, weather, recent shopper intent, and live Shopify products to tell the store what to feature this week.";
  report.append(summary);

  const signalGrid = document.createElement("div");
  signalGrid.className = "signal-grid";
  for (const source of radar.sourceSummary || []) {
    const item = document.createElement("div");
    item.className = "signal";
    const name = document.createElement("strong");
    name.textContent = source.name;
    const status = document.createElement("span");
    status.textContent = source.status;
    item.append(name, status);
    signalGrid.append(item);
  }
  report.append(signalGrid);

  if (radar.featuredProducts?.length) {
    const productsTitle = document.createElement("p");
    productsTitle.className = "radar-subhead";
    productsTitle.textContent = "Products to feature now";
    report.append(productsTitle);
    const productList = document.createElement("div");
    productList.className = "radar-products";
    for (const product of radar.featuredProducts.slice(0, 3)) {
      const row = document.createElement("div");
      row.className = "radar-product";
      const name = document.createElement("strong");
      name.textContent = product.name;
      const price = document.createElement("span");
      price.textContent = formatMoney(product);
      row.append(name, price);
      productList.append(row);
    }
    report.append(productList);
  }

  const actionsTitle = document.createElement("p");
  actionsTitle.className = "radar-subhead";
  actionsTitle.textContent = "Merchant actions";
  report.append(actionsTitle);

  const actions = document.createElement("ol");
  actions.className = "radar-actions";
  for (const action of radar.actions || []) {
    const item = document.createElement("li");
    item.textContent = action;
    actions.append(item);
  }
  report.append(actions);

  if (radar.kestra) {
    const panel = document.createElement("div");
    panel.className = "automation-status";
    const title = document.createElement("strong");
    title.textContent = radar.kestra.status === "triggered" ? "Kestra radar workflow started" : "Kestra radar workflow ready";
    const detail = document.createElement("span");
    detail.textContent = radar.kestra.executionId
      ? `Execution ${radar.kestra.executionId}`
      : "Start Kestra locally to execute the scheduled version of this scan.";
    panel.append(title, detail);
    report.append(panel);
  }

  container.append(report);
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
    addRadarReport(bubble, meta.radar || {});
  }

  if (trace.length) {
    const traceEl = document.createElement("details");
    traceEl.className = "trace";
    const summary = document.createElement("summary");
    summary.textContent = "Agent trace";
    traceEl.append(summary);
    for (const item of trace) {
      const chip = document.createElement("span");
      chip.textContent = item;
      traceEl.append(chip);
    }
    bubble.append(traceEl);
  }

  messages.append(bubble);
  if (meta.radar?.reportId) {
    messages.scrollTop = Math.max(0, bubble.offsetTop - messages.offsetTop);
  } else {
    messages.scrollTop = messages.scrollHeight;
  }
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
    "Fresh session started. Tell me who you are shopping for, the occasion, size, budget, or pickup timing — or ask me to run a campus demand scan.",
    ["session.reset"]
  );
});

for (const button of suggestions) {
  button.addEventListener("click", () => sendMessage(button.textContent));
}

addMessage(
  "agent",
  "Hi! I'm Storefront Concierge. I can search a live Shopify catalog, build a cart, and run a Campus Demand Radar that mashes up campus events, weather, recent shopper intent, and live inventory to recommend what to feature this week. Try one of the prompts below to start.",
  ["agent.ready", "shopify.mcp.live", "kestra.radar.ready"]
);
