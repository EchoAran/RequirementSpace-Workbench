import { HttpError } from '@/lib/http';

/**
 * 版本控制错误 → i18n token 映射（Phase E）。
 *
 * 后端失败响应 detail 是对象：{code, message, ...}。前端按 HTTP status + detail.code
 * 映射为稳定的 i18n 键 token（组件用 t() 解析），替代直出服务端英文。
 * 额外携带 compare_ref / reasons 供错误恢复面板渲染动作与原因。
 */

export interface VcErrorInfo {
  code?: string;
  reasons?: string[];
  compareRef?: string;
}

export interface VcErrorResult {
  token: string;
  info: VcErrorInfo;
}

export function extractVcError(e: unknown): VcErrorResult {
  const status = (e as HttpError)?.status;
  const detail = (e as HttpError)?.detail as Record<string, unknown> | undefined;
  const info: VcErrorInfo = {
    code: typeof detail?.code === 'string' ? detail.code : undefined,
    reasons: Array.isArray(detail?.reasons) ? (detail.reasons as string[]) : undefined,
    compareRef: typeof detail?.compare_ref === 'string' ? detail.compare_ref : undefined,
  };
  if (status === 409 && info.code === 'head_changed') return { token: 'versionControl.mergeRequest.headChanged', info };
  if (status === 409 && info.code === 'merge_conflict') return { token: 'versionControl.mergeRequest.errors.mergeConflict', info };
  if (status === 400 && info.code === 'merge_blocked') return { token: 'versionControl.mergeRequest.errors.blocked', info };
  if (status === 403) return { token: 'versionControl.mergeRequest.errors.forbidden', info };
  if (status === 404) return { token: 'versionControl.mergeRequest.errors.notFound', info };
  return { token: 'versionControl.mergeRequest.mergeFailed', info };
}

/** 审批/评论/关闭等副操作的通用错误提取（无 code 细分，仅按状态码分 403/其他）。 */
export function extractActionError(e: unknown): string {
  const status = (e as HttpError)?.status;
  if (status === 403) return 'versionControl.mergeRequest.errors.forbidden';
  if (status === 404) return 'versionControl.mergeRequest.errors.notFound';
  if (status === 409) return 'versionControl.mergeRequest.errors.staleState';
  return 'versionControl.mergeRequest.mergeFailed';
}
