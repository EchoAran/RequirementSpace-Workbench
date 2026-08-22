import i18n from '../i18n';

const rawApiUrl = (import.meta.env.VITE_API_URL as string) || '';
const API_BASE_URL = rawApiUrl
  ? (rawApiUrl.endsWith('/api') ? rawApiUrl : `${rawApiUrl.replace(/\/$/, '')}/api`)
  : '/api';

export interface RequestOptions extends RequestInit {
  params?: Record<string, string | number | boolean | undefined>;
  timeout?: number;
}

class HttpError extends Error {
  status: number;
  statusText: string;
  detail: any;

  constructor(status: number, statusText: string, message: string, detail?: any) {
    super(message);
    this.name = 'HttpError';
    this.status = status;
    this.statusText = statusText;
    this.detail = detail;
  }
}

export { HttpError };

// 401 callback mechanism to avoid circular dependencies with stores
type UnauthorizedCallback = () => void;
const unauthorizedCallbacks: Set<UnauthorizedCallback> = new Set();

// 分支请求上下文：整个项目工作区以 URL 的 branch 为唯一来源。Workspace Store 在切换分支时
// 调用 setRequestBranch，所有随后发出的项目请求自动携带 ?branch=<ref>，无需逐个调用点改参。
let activeBranch: string | undefined;

export function setRequestBranch(branch?: string) {
  activeBranch = branch;
}

export function getRequestBranch(): string | undefined {
  return activeBranch;
}

export function onUnauthorized(callback: UnauthorizedCallback) {
  unauthorizedCallbacks.add(callback);
  return () => {
    unauthorizedCallbacks.delete(callback);
  };
}

function triggerUnauthorized() {
  unauthorizedCallbacks.forEach(cb => cb());
}

export async function request<T>(url: string, options: RequestOptions = {}): Promise<T> {
  const { params, headers, body, timeout, ...restOptions } = options;

  // 0. 注入分支请求上下文：支持 url 自带 query 或 params 传参，安全合并无冗余问号。
  const [basePath, existingQuery] = url.split('?');
  const searchParams = new URLSearchParams(existingQuery || '');

  const mergedParams: Record<string, unknown> = { ...(params || {}) };
  if (activeBranch && mergedParams.branch === undefined && !searchParams.has('branch')) {
    mergedParams.branch = activeBranch;
  }

  Object.entries(mergedParams).forEach(([key, val]) => {
    if (val !== undefined && val !== null) {
      searchParams.set(key, String(val));
    }
  });

  const qs = searchParams.toString();
  const queryString = qs ? `?${qs}` : '';
  const fullUrl = `${API_BASE_URL}${basePath}${queryString}`;

  // 2. Set default headers
  const defaultHeaders: Record<string, string> = {
    'Accept': 'application/json',
  };

  let finalBody = body;
  if (body && typeof body === 'object' && !(body instanceof FormData) && !(body instanceof Blob)) {
    defaultHeaders['Content-Type'] = 'application/json';
    finalBody = JSON.stringify(body);
  }

  const config: RequestInit = {
    credentials: 'include',
    ...restOptions,
    headers: {
      ...defaultHeaders,
      ...headers,
    },
    body: finalBody,
  };

  let timeoutId: any = null;
  if (timeout) {
    const controller = new AbortController();
    config.signal = controller.signal;
    timeoutId = setTimeout(() => controller.abort(), timeout);
  }

  try {
    const response = await fetch(fullUrl, config);

    // Check if the response is JSON
    const contentType = response.headers.get('Content-Type') || '';
    const isJson = contentType.includes('application/json');

    let responseData: any = null;
    if (isJson) {
      responseData = await response.json();
    } else {
      responseData = await response.text();
    }

    if (!response.ok) {
      if (response.status === 401) {
        triggerUnauthorized();
      }

      // Extract error detail from FastAPI's typical error response
      let errorMessage = `HTTP Error ${response.status}: ${response.statusText}`;
      let detail: any = null;

      if (responseData && typeof responseData === 'object') {
        detail = responseData.detail;
        if (typeof detail === 'string') {
          errorMessage = detail;
        } else if (Array.isArray(detail)) {
          // FastAPI validation error list
          errorMessage = detail.map((err: any) => `${err.loc.join('.')}: ${err.msg}`).join('; ');
        } else if (responseData.message) {
          errorMessage = responseData.message;
        }
      } else if (typeof responseData === 'string' && responseData.trim()) {
        errorMessage = responseData;
      }

      throw new HttpError(response.status, response.statusText, errorMessage, detail);
    }

    return responseData as T;
  } catch (error) {
    if (error instanceof HttpError) {
      throw error;
    }
    if (error instanceof Error && error.name === 'AbortError') {
      throw new HttpError(
        504,
        i18n.t('http.timeoutStatus'),
        i18n.t('http.timeoutMessage'),
      );
    }
    // Network or other unexpected errors
    throw new HttpError(
      0,
      i18n.t('http.networkStatus'),
      error instanceof Error ? error.message : i18n.t('http.networkMessage'),
      error
    );
  } finally {
    if (timeoutId) {
      clearTimeout(timeoutId);
    }
  }
}

export const http = {
  get: <T>(url: string, params?: Record<string, any>, options?: RequestOptions) =>
    request<T>(url, { method: 'GET', params, ...options }),

  post: <T>(url: string, body?: any, options?: RequestOptions) =>
    request<T>(url, { method: 'POST', body, ...options }),

  put: <T>(url: string, body?: any, options?: RequestOptions) =>
    request<T>(url, { method: 'PUT', body, ...options }),

  patch: <T>(url: string, body?: any, options?: RequestOptions) =>
    request<T>(url, { method: 'PATCH', body, ...options }),

  delete: <T>(url: string, options?: RequestOptions) =>
    request<T>(url, { method: 'DELETE', ...options }),
};
