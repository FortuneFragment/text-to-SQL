export const API_BASE = import.meta.env.VITE_API_BASE || "/api/v1";

function formatErrorDetail(value, fallback) {
  if (typeof value === "string") {
    return value;
  }
  if (value === undefined || value === null) {
    return fallback;
  }
  try {
    return JSON.stringify(value);
  } catch {
    return fallback;
  }
}

export async function readErrorDetail(response, fallback = "请求失败") {
  const text = await response.text();
  const trimmed = text.trim();
  if (!trimmed) {
    return fallback;
  }

  try {
    const body = JSON.parse(trimmed);
    return formatErrorDetail(body?.detail ?? body?.message ?? body, fallback);
  } catch {
    return trimmed;
  }
}

// 中文备注：处理apiRequest相关业务数据并返回结果。
// 执行流程：先处理输入与上下文，再执行核心逻辑，最后返回结果或抛出异常。
export async function apiRequest(path, options = {}) {
  const headers = { ...(options.headers || {}) };
  const isFormData = typeof FormData !== "undefined" && options.body instanceof FormData;
  const hasBody = options.body !== undefined && options.body !== null;
  if (hasBody && !isFormData && !headers["Content-Type"]) {
    headers["Content-Type"] = "application/json";
  }

  let response;
  try {
    response = await fetch(`${API_BASE}${path}`, {
      ...options,
      headers,
    });
  } catch (error) {
    throw new Error(`无法连接后端服务（${API_BASE}）：${error.message || "网络请求失败"}`);
  }

  if (!response.ok) {
    const detail = await readErrorDetail(response);
    throw new Error(detail || "请求失败");
  }

  if (response.status === 204) {
    return null;
  }

  const contentType = response.headers.get("content-type") || "";
  if (contentType.includes("application/json")) {
    return response.json();
  }
  return response.text();
}

function dispatchStreamEvent(event, payload, handlers) {
  switch (event) {
    case "status":
      handlers.onStatus?.(payload);
      break;
    case "selected_tables":
      handlers.onSelectedTables?.(payload);
      break;
    case "generated_sql":
      handlers.onGeneratedSql?.(payload);
      break;
    case "sql_result":
      handlers.onSqlResult?.(payload);
      break;
    case "answer_delta":
      handlers.onAnswerDelta?.(String(payload?.content || ""));
      break;
    case "done":
      handlers.onDone?.(payload);
      break;
    case "error":
      handlers.onError?.(payload);
      break;
  }
}

function parseStreamFrame(frame, handlers) {
  const lines = frame.split(/\r?\n/);
  let event = "";
  const dataLines = [];

  for (const rawLine of lines) {
    if (!rawLine || rawLine.startsWith(":")) continue;
    if (rawLine.startsWith("event:")) {
      event = rawLine.slice(6).trim();
      continue;
    }
    if (rawLine.startsWith("data:")) {
      dataLines.push(rawLine.slice(5).trimStart());
    }
  }

  if (!event || dataLines.length === 0) return;

  try {
    dispatchStreamEvent(event, JSON.parse(dataLines.join("\n")), handlers);
  } catch (error) {
    handlers.onError?.({ message: `解析流式响应失败：${error.message}` });
  }
}

export function streamRequest(path, payload, handlers = {}) {
  const abortController = new AbortController();

  async function run() {
    try {
      const response = await fetch(`${API_BASE}${path}`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Accept: "text/event-stream",
        },
        body: JSON.stringify(payload || {}),
        signal: abortController.signal,
      });

      if (!response.ok) {
        const detail = await readErrorDetail(response);
        handlers.onError?.({ message: detail || "请求失败" });
        return;
      }

      const reader = response.body?.getReader();
      if (!reader) {
        handlers.onError?.({ message: "无法读取流式响应" });
        return;
      }

      const decoder = new TextDecoder("utf-8");
      let buffer = "";
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const frames = buffer.split(/\r?\n\r?\n/);
        buffer = frames.pop() || "";
        for (const frame of frames) {
          parseStreamFrame(frame, handlers);
        }
      }

      if (buffer.trim()) {
        parseStreamFrame(buffer, handlers);
      }
    } catch (error) {
      if (error?.name === "AbortError") return;
      handlers.onError?.({ message: error?.message || "网络请求失败" });
    }
  }

  void run();
  return () => abortController.abort();
}
