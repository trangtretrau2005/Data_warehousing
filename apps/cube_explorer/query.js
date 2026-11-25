const state = { config: null, ai: null, lastResult: null };
const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => [...document.querySelectorAll(selector)];
const escapeHTML = (value) => String(value).replace(/[&<>"']/g, (character) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[character]);

const formatNumber = (value) => typeof value === "number"
  ? new Intl.NumberFormat("vi-VN", { maximumFractionDigits: 2 }).format(value)
  : String(value ?? "—");

function optionLabel(key, label, type) {
  const inputName = type === "measure" ? "measures" : "dimensions";
  return `<label class="choice-chip"><input type="checkbox" name="${inputName}" value="${key}"><span><b>${key}</b><br>${label}</span></label>`;
}

function filterLabel(value, name) {
  const escaped = value.replaceAll("&", "&amp;").replaceAll('"', "&quot;").replaceAll("<", "&lt;");
  return `<label><input type="checkbox" name="${name}" value="${escaped}"><span>${escaped}</span></label>`;
}

function updateSelections() {
  $$(".choice-chip").forEach((label) => label.classList.toggle("selected", label.querySelector("input").checked));
  const measures = $$('input[name="measures"]:checked');
  const dimensions = $$('input[name="dimensions"]:checked');
  $("#measure-count").textContent = `${measures.length} / 4`;
  $("#dimension-count").textContent = `${dimensions.length} / 3`;
  $$('input[name="measures"]:not(:checked)').forEach((input) => { input.disabled = measures.length >= 4; });
  $$('input[name="dimensions"]:not(:checked)').forEach((input) => { input.disabled = dimensions.length >= 3; });
}

function setAggregate(value) {
  const radio = $(`input[name="aggregate"][value="${value}"]`);
  radio.checked = true;
  $$(".aggregate-choice").forEach((label) => label.classList.toggle("selected", label.contains(radio)));
  $("#aggregate-help").textContent = value === "AVG"
    ? "AVG lấy trung bình các ô fact tháng × AreaCode × sản phẩm."
    : "SUM cộng các ô fact trong cùng phạm vi.";
}

function clearChecks(name) {
  $$(`input[name="${name}"]`).forEach((input) => { input.checked = false; });
}

function checkValues(name, values) {
  const wanted = new Set(values);
  $$(`input[name="${name}"]`).forEach((input) => { input.checked = wanted.has(input.value); });
}

function applyPreset(name) {
  clearChecks("measures"); clearChecks("dimensions"); clearChecks("markets"); clearChecks("products");
  $("#year-filter").value = "2013";
  $("#month-filter").value = "";
  $("#month-filter").disabled = false;
  if (name === "market-sales") {
    setAggregate("SUM"); checkValues("measures", ["Sales", "BudgetSales"]); checkValues("dimensions", ["Market"]);
  } else if (name === "avg-marketing") {
    setAggregate("AVG"); checkValues("measures", ["Marketing"]); checkValues("dimensions", ["Market"]); $("#year-filter").value = ""; $("#month-filter").disabled = true;
  } else {
    setAggregate("SUM"); checkValues("measures", ["Gap"]); checkValues("dimensions", ["MonthStart"]); checkValues("markets", ["South"]);
  }
  updateSelections();
}

function specFromForm() {
  return {
    aggregate: $('input[name="aggregate"]:checked').value,
    measures: $$('input[name="measures"]:checked').map((item) => item.value),
    groupBy: $$('input[name="dimensions"]:checked').map((item) => item.value),
    year: $("#year-filter").value || null,
    month: $("#month-filter").value || null,
    markets: $$('input[name="markets"]:checked').map((item) => item.value),
    products: $$('input[name="products"]:checked').map((item) => item.value),
  };
}

async function postJSON(url, body) {
  const response = await fetch(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
  const data = await response.json().catch(() => ({ error: "Server trả phản hồi không hợp lệ." }));
  if (!response.ok) throw new Error(data.error || "Không chạy được yêu cầu.");
  return data;
}

function showError(target, message) {
  target.textContent = message; target.hidden = false;
}

function setRunning(button, running) {
  button.disabled = running;
  button.classList.toggle("running", running);
  button.querySelector("span").textContent = running ? "Đang đọc mart…" : (button.id === "ask-ai" ? "Nhờ Gemini tạo truy vấn" : "Chạy truy vấn");
}

function cubeURL(context = {}) {
  const params = new URLSearchParams();
  if (!context.month && !context.year) params.set("year", "all");
  for (const key of ["year", "month", "market", "product", "measure", "mode"]) {
    if (context[key] !== null && context[key] !== undefined && context[key] !== "") params.set(key, context[key]);
  }
  if (Array.isArray(context.products) && context.products.length > 1) {
    params.delete("product");
    context.products.forEach((product) => params.append("products", product));
  }
  if (context.rollup?.dimension && context.rollup?.metric && Array.isArray(context.rollup.items)) {
    params.set("rollupDimension", context.rollup.dimension);
    params.set("rollupMetric", context.rollup.metric);
    params.set("rollupTitle", context.rollup.title || `${context.rollup.metric} theo ${context.rollup.dimension}`);
    context.rollup.items.forEach((item) => params.append("rollupItem", JSON.stringify(item)));
  }
  return params.size ? `/#${params.toString()}` : "/";
}

function describeCubeContext(context = {}) {
  if (context.rollup?.items?.length) {
    return `${context.note} Cube sẽ hiển thị ${context.rollup.items.length} khối roll-up, mỗi khối là một dòng kết quả ${context.rollup.dimension}.`;
  }
  const scope = [
    context.month ? `tháng ${context.month.slice(5, 7)}/${context.month.slice(0, 4)}` : (context.year ? `năm ${context.year}` : "mọi thời gian"),
    context.market || "tất cả Market",
    Array.isArray(context.products) && context.products.length > 1
      ? `${context.products.length} sản phẩm từ kết quả`
      : (context.product || "tất cả sản phẩm"),
    `chỉ tiêu ${context.measure || "Gap"}`,
  ].join(" · ");
  return `${context.note || "Mở cube bằng các chiều nhận diện được."} Cube sẽ mở: ${scope}. Bảng kết quả truy vấn vẫn là số liệu chuẩn.`;
}

function renderResult(result) {
  state.lastResult = result;
  const aiSQL = result.mode === "ai_sql";
  $("#result-section").hidden = false;
  $("#result-title").textContent = aiSQL ? "Gemini đã sinh và chạy SELECT an toàn" : "Truy vấn đã chạy thành công";
  $("#result-meta").textContent = aiSQL
    ? `Text-to-SQL · ${result.rowCount}${result.truncated ? "+" : ""} dòng · ${result.ai.model}`
    : `${result.spec.aggregate} · ${result.spec.measures.join(", ")} · ${result.rowCount} dòng`;
  $("#row-count").textContent = result.truncated ? "Hiển thị 200 dòng đầu · còn kết quả khác" : `${result.rowCount} dòng`;

  const cube = $("#open-cube");
  cube.href = cubeURL(result.cubeContext);
  cube.hidden = false;
  const cubeNote = $("#cube-context-note");
  cubeNote.textContent = describeCubeContext(result.cubeContext);
  cubeNote.hidden = false;

  const first = result.rows[0] || {};
  const measureColumns = aiSQL
    ? result.columns.filter((column) => typeof first[column] === "number")
    : result.columns.filter((column) => column.startsWith("SUM_") || column.startsWith("AVG_"));
  $("#result-summary").innerHTML = measureColumns.slice(0, 4).map((column) => `<div class="summary-item"><span>${escapeHTML(column.replace("_", " · "))}${result.rows.length > 1 ? " · dòng đầu" : ""}</span><strong>${escapeHTML(formatNumber(first[column]))}</strong></div>`).join("");
  $("#result-summary").hidden = measureColumns.length === 0;

  $("#result-head").innerHTML = `<tr>${result.columns.map((column) => `<th>${escapeHTML(column)}</th>`).join("")}</tr>`;
  $("#result-body").innerHTML = result.rows.map((row) => `<tr>${result.columns.map((column) => `<td class="${typeof row[column] === "number" ? "number" : ""}">${escapeHTML(formatNumber(row[column]))}</td>`).join("")}</tr>`).join("");
  $("#sql-output").textContent = result.sql;
  $("#sql-params").textContent = result.params.length
    ? result.params.map((value, index) => `?${index + 1} = ${JSON.stringify(value)}`).join(" · ")
    : (aiSQL ? "Không có parameter binding; đây là SQL nghiệp vụ đã canonicalize. Giới hạn 201 dòng chỉ được thêm nội bộ khi thực thi." : "[] · không có bộ lọc");
  $("#meaning-title").textContent = aiSQL ? "Cách đọc và giới hạn" : (result.spec.aggregate === "AVG" ? "AVG đang đo điều gì?" : "SUM đang đo điều gì?");
  const fallbackNote = result.ai?.fallbackAttempts?.length ? ` Đã fallback qua ${result.ai.fallbackAttempts.length} model trước đó.` : "";
  $("#meaning-text").textContent = aiSQL
    ? `${result.ai.explanation} ${result.explanation}${fallbackNote}`
    : `${result.explanation} SQL chỉ dùng cột đã được hệ thống cho phép.`;
  $("#result-section").scrollIntoView({ behavior: "smooth", block: "start" });
}

async function runBuilder(event) {
  event.preventDefault();
  const error = $("#builder-error"); error.hidden = true;
  const spec = specFromForm();
  if (!spec.measures.length) { showError(error, "Hãy chọn ít nhất một chỉ tiêu ở Bước 2."); return; }
  const button = $("#run-query"); setRunning(button, true);
  try { renderResult(await postJSON("/api/query", spec)); }
  catch (reason) { showError(error, reason.message); }
  finally { setRunning(button, false); }
}

async function askAI() {
  const error = $("#ai-error"); error.hidden = true;
  const question = $("#ai-question").value.trim();
  if (!question) { showError(error, "Hãy nhập một câu hỏi trước."); return; }
  const button = $("#ask-ai"); setRunning(button, true);
  try { renderResult(await postJSON("/api/ai/query", { question, model: $("#ai-model").value })); }
  catch (reason) { showError(error, reason.message); }
  finally { setRunning(button, false); button.disabled = !state.ai?.available; }
}

function switchTab(name) {
  const builder = name === "builder";
  $("#builder-panel").hidden = !builder; $("#ai-panel").hidden = builder;
  $("#builder-tab").classList.toggle("active", builder); $("#ai-tab").classList.toggle("active", !builder);
  $("#builder-tab").setAttribute("aria-selected", String(builder)); $("#ai-tab").setAttribute("aria-selected", String(!builder));
}

async function init() {
  try {
    const response = await fetch("/api/query/config");
    if (!response.ok) throw new Error();
    const payload = await response.json(); state.config = payload.config;
    $("#source-label").textContent = payload.source;
    $("#measure-options").innerHTML = Object.entries(payload.config.measures).map(([key, label]) => optionLabel(key, label, "measure")).join("");
    $("#dimension-options").innerHTML = Object.entries(payload.config.dimensions).map(([key, label]) => optionLabel(key, label, "dimension")).join("");
    $("#year-filter").insertAdjacentHTML("beforeend", payload.config.years.map((year) => `<option value="${year}">${year}</option>`).join(""));
    $("#month-filter").insertAdjacentHTML("beforeend", Array.from({ length: 12 }, (_, i) => `<option value="${i + 1}">Tháng ${String(i + 1).padStart(2, "0")}</option>`).join(""));
    $("#market-options").innerHTML = payload.config.markets.map((value) => filterLabel(value, "markets")).join("");
    $("#product-options").innerHTML = payload.config.products.map((value) => filterLabel(value, "products")).join("");
    applyPreset("market-sales");
  } catch { showError($("#builder-error"), "Không đọc được cấu hình mart. Hãy khởi động lại server."); }

  try {
    state.ai = await fetch("/api/ai/status").then((response) => response.json());
    const status = $("#ai-status"); status.className = `ollama-status ${state.ai.available ? "ready" : "offline"}`;
    status.querySelector("span").textContent = state.ai.message;
    $("#ai-dot").classList.toggle("ready", state.ai.available);
    const model = $("#ai-model");
    if (state.ai.models.length) {
      model.innerHTML = `<option value="__auto__">Tự động fallback theo quota</option>` + state.ai.models.map((item) => `<option value="${escapeHTML(item.id)}">${escapeHTML(item.name)} · ${escapeHTML(item.id)}</option>`).join("");
      model.disabled = false; $("#ask-ai").disabled = false;
      const order = $("#fallback-order"); order.hidden = false;
      order.textContent = `Thứ tự tự động: ${state.ai.models.map((item) => item.name).join(" → ")}`;
    }
  } catch { $("#ai-status").className = "ollama-status offline"; $("#ai-status span").textContent = "Không kiểm tra được Gemini API."; }
}

$("#query-form").addEventListener("submit", runBuilder);
$("#ask-ai").addEventListener("click", askAI);
$("#builder-tab").addEventListener("click", () => switchTab("builder"));
$("#ai-tab").addEventListener("click", () => switchTab("ai"));
$("#query-form").addEventListener("change", (event) => {
  if (event.target.name === "aggregate") setAggregate(event.target.value);
  if (event.target.name === "measures" || event.target.name === "dimensions") updateSelections();
  if (event.target.id === "year-filter") { $("#month-filter").disabled = !event.target.value; if (!event.target.value) $("#month-filter").value = ""; }
});
$$('[data-preset]').forEach((button) => button.addEventListener("click", () => applyPreset(button.dataset.preset)));
$$('.example-questions button').forEach((button) => button.addEventListener("click", () => { $("#ai-question").value = button.textContent; $("#question-count").textContent = button.textContent.length; }));
$("#ai-question").addEventListener("input", (event) => { $("#question-count").textContent = event.target.value.length; });
$("#edit-query").addEventListener("click", () => { const target = state.lastResult?.mode === "ai_sql" ? "ai" : "builder"; switchTab(target); $(target === "ai" ? "#ai-panel" : "#builder-panel").scrollIntoView({ behavior: "smooth" }); });
$("#copy-sql").addEventListener("click", async () => { if (state.lastResult) { await navigator.clipboard.writeText(`${state.lastResult.sql}\n-- params: ${JSON.stringify(state.lastResult.params)}`); $("#copy-sql").textContent = "Đã sao chép"; setTimeout(() => { $("#copy-sql").textContent = "Sao chép SQL"; }, 1200); } });
init();
