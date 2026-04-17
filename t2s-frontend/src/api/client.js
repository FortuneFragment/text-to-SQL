export const API_BASE = import.meta.env.VITE_API_BASE || "http://127.0.0.1:8000/api/v1";

// 中文备注：处理apiRequest相关业务数据并返回结果。
// 执行流程：先处理输入与上下文，再执行核心逻辑，最后返回结果或抛出异常。
export async function apiRequest(path, options = {}) {
  const headers = { ...(options.headers || {}) };
  const isFormData = typeof FormData !== "undefined" && options.body instanceof FormData;
  if (!isFormData && !headers["Content-Type"]) {
    headers["Content-Type"] = "application/json";
  }

  const response = await fetch(`${API_BASE}${path}`, {
    headers,
    ...options,
  });

  if (!response.ok) {
    let detail = "请求失败";
    try {
      const body = await response.json();
      detail = body.detail || JSON.stringify(body);
    } catch {
      detail = await response.text();
    }
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
