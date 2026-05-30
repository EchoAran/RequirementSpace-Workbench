const rawApiUrl = (import.meta.env.VITE_API_URL as string) || '';
export const API_BASE_URL = rawApiUrl 
  ? (rawApiUrl.endsWith('/api') ? rawApiUrl : `${rawApiUrl.replace(/\/$/, '')}/api`)
  : '/api';

export interface RequestOptions extends RequestInit {
  params?: Record<string, string | number | boolean | undefined>;
}

export class HttpError extends Error {
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

export async function request<T>(url: string, options: RequestOptions = {}): Promise<T> {
  const { params, headers, body, ...restOptions } = options;

  // 1. Build Query String if params exist
  let queryString = '';
  if (params) {
    const searchParams = new URLSearchParams();
    Object.entries(params).forEach(([key, val]) => {
      if (val !== undefined && val !== null) {
        searchParams.append(key, String(val));
      }
    });
    const qs = searchParams.toString();
    if (qs) {
      queryString = `?${qs}`;
    }
  }

  const fullUrl = `${API_BASE_URL}${url}${queryString}`;

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
    ...restOptions,
    headers: {
      ...defaultHeaders,
      ...headers,
    },
    body: finalBody,
  };

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
    // Network or other unexpected errors
    throw new HttpError(
      0,
      'Network Error',
      error instanceof Error ? error.message : '网络连接失败，请检查服务是否正常启动。',
      error
    );
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
