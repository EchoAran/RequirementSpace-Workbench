import { http } from './http';

export interface LLMConfigResponse {
  configured: boolean;
  source: 'personal' | 'server' | null;
  api_url: string | null;
  model_name: string | null;
  api_key_last4: string | null;
}

export interface LLMConfigRequest {
  api_url: string;
  api_key: string;
  model_name: string;
}

export interface LLMConfigTestRequest {
  api_url?: string;
  api_key?: string;
  model_name?: string;
}

export interface LLMConfigTestResponse {
  success: boolean;
  error_type: string | null;
  error_detail: string | null;
}

export const accountApi = {
  getLLMConfig: () => 
    http.get<LLMConfigResponse>('/account/llm-config'),

  updateLLMConfig: (data: LLMConfigRequest) => 
    http.put<LLMConfigResponse>('/account/llm-config', data),

  deleteLLMConfig: () => 
    http.delete<{ message: string }>('/account/llm-config'),

  testLLMConfig: (data?: LLMConfigTestRequest) => 
    http.post<LLMConfigTestResponse>('/account/llm-config/test', data || {}),
};
