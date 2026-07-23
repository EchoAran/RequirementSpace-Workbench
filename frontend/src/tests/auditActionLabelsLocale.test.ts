import { describe, expect, it } from 'vitest';
import {
  auditActionTypeLabels,
  auditActionTypeLabelsEn,
  getAuditActionTypeLabel,
  getAuditSummary,
  withAuditActionTypeLabel,
} from '../core/auditActionLabels';

describe('audit action labels by UI locale', () => {
  it.each([
    ['zh-CN', '采纳生成候选方案'],
    ['en-US', 'Accept Generated Option'],
  ])('maps generation_choice_accepted for %s', (locale, label) => {
    expect(getAuditActionTypeLabel('generation_choice_accepted', locale)).toBe(label);
    expect(withAuditActionTypeLabel({ actionType: 'generation_choice_accepted' }, locale)).toEqual({
      actionType: 'generation_choice_accepted',
      actionTypeLabel: label,
    });
  });

  it.each([
    ['zh-CN', '更新确认状态'],
    ['en-US', 'Update Confirmation Status'],
  ])('keeps actionType and localizes exported actionTypeLabel for %s', (locale, label) => {
    const exportRow = withAuditActionTypeLabel({ action_type: 'update_confirmation_status' }, locale);

    expect(exportRow).toMatchObject({
      action_type: 'update_confirmation_status',
      actionTypeLabel: label,
    });
  });

  it('keeps the Chinese and English action-type key sets identical', () => {
    expect(Object.keys(auditActionTypeLabels).sort()).toEqual(Object.keys(auditActionTypeLabelsEn).sort());
  });

  it('returns the corresponding localized label for every mapped action type', () => {
    for (const actionType of Object.keys(auditActionTypeLabels)) {
      expect(getAuditActionTypeLabel(actionType, 'zh-CN')).toBe(auditActionTypeLabels[actionType]);
      expect(getAuditActionTypeLabel(actionType, 'en-US')).toBe(auditActionTypeLabelsEn[actionType]);
    }
  });

  it('localizes coded and legacy Chinese summaries in English mode', () => {
    expect(getAuditSummary({
      actionType: 'update_user_requirements',
      summary: 'update_user_requirements',
    }, 'en-US')).toBe('Update User Requirements');
    expect(getAuditSummary({
      actionType: 'update_user_requirements',
      summary: '\u624b\u52a8\u66f4\u65b0\u7528\u6237\u9700\u6c42\u6587\u6863',
    }, 'en-US')).toBe('Update User Requirements');
  });

  it('preserves a free-form summary already written in the active language', () => {
    expect(getAuditSummary({
      actionType: 'update_user_requirements',
      summary: 'Updated requirement details for checkout',
    }, 'en-US')).toBe('Updated requirement details for checkout');
  });
});
