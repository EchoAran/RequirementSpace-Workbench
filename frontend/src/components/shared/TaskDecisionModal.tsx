import React, { useState } from 'react';
import { X, CheckCircle2, AlertTriangle, MessageSquare, ShieldAlert } from 'lucide-react';
import { useWorkspaceStore } from '@/store/useWorkspaceStore';

interface TaskDecisionModalProps {
  task: any;
  projectId: string;
  onClose: () => void;
  onDecided: () => void;
}

const fieldLabels: Record<string, string> = {
  name: '名称',
  description: '说明',
  content: '内容',
  data_type: '数据类型',
  example: '示例',
  position: '位置',
  step_type: '步骤类型',
  status: '状态',
  positive_summary: '纳入范围',
  negative_summary: '排除范围',
  reason: '原因',
  kano_category: 'Kano 分类',
};

const nodeKindLabels: Record<string, string> = {
  actor: '角色',
  feature: '功能特性',
  scenario: '场景',
  acceptance_criterion: '验收标准',
  business_object: '业务对象',
  business_object_attribute: '对象属性',
  flow: '业务流程',
  flow_step: '流程步骤',
  scope: '范围规划',
};

const formatValue = (val: unknown) => {
  if (Array.isArray(val) && val.length === 0) return '无';
  if (val && typeof val === 'object') return JSON.stringify(val, null, 2);
  if (val === null || val === undefined || val === '') return '未填写';
  return String(val);
};

const getSnapshotTitle = (task: any, target?: any, index?: number) => {
  const snapshot = target?.snapshot || task.contentSnapshot || {};
  const snapshotName = snapshot.name || snapshot.content;
  if (target) {
    const kindLabel = nodeKindLabels[target.node_kind] || target.node_kind || '对象';
    return target.node_name || snapshotName || `${kindLabel} #${target.node_id ?? (index ?? 0) + 1}`;
  }
  return task.nodeName || snapshotName || task.title || '确认对象';
};

const getSnapshotGroups = (task: any) => {
  if (Array.isArray(task.targets) && task.targets.length > 0) {
    return task.targets.map((target: any, index: number) => ({
      title: getSnapshotTitle(task, target, index),
      snapshot: target.snapshot || {},
    }));
  }

  return [{
    title: getSnapshotTitle(task),
    snapshot: task.contentSnapshot || {},
  }];
};

export function TaskDecisionModal({ task, projectId, onClose, onDecided }: TaskDecisionModalProps) {
  const decideTask = useWorkspaceStore((state) => state.decideTask);
  const [decisionNote, setDecisionNote] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const snapshotGroups = getSnapshotGroups(task);

  const handleDecision = async (decision: 'approve' | 'reject') => {
    try {
      setLoading(true);
      setError(null);
      await decideTask(projectId, task.id, {
        decision,
        decisionNote: decisionNote.trim() || undefined,
      });
      onDecided();
    } catch (err: any) {
      const detail = err?.response?.data?.detail;
      if (detail === 'task_content_changed') {
        setError('操作失败：目标内容已经发生变化，这个确认任务已失效。');
      } else if (detail && typeof detail === 'object' && detail.message === 'task_content_changed') {
        const mismatches = detail.mismatches || [];
        const mismatchStr = mismatches.map((m: any) => `${m.node_kind} (ID: ${m.node_id})`).join(', ');
        setError(`操作失败：以下目标内容已经发生变化，确认任务已失效：${mismatchStr}`);
      } else {
        setError(detail || err?.message || '操作失败');
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-slate-900/40 backdrop-blur-sm z-50 flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl shadow-xl w-full max-w-4xl max-h-[90vh] flex flex-col overflow-hidden border border-slate-200">
        <div className="px-6 py-4 border-b border-slate-150 flex items-center justify-between bg-slate-50/50">
          <div>
            <span className="text-[10px] font-bold tracking-wider uppercase bg-indigo-50 text-indigo-600 px-2 py-0.5 rounded-full">
              确认任务审批
            </span>
            <h3 className="text-base font-bold text-slate-800 mt-1">{task.title}</h3>
          </div>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-600 p-1 hover:bg-slate-100 rounded-lg transition-colors">
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-6 space-y-5">
          {error && (
            <div className="bg-rose-50 border border-rose-100 text-rose-700 px-4 py-3 rounded-xl text-xs flex items-start gap-2">
              <ShieldAlert className="w-4 h-4 shrink-0 mt-0.5" />
              <span>{error}</span>
            </div>
          )}

          {task.contentChanged && (
            <div className="bg-amber-50 border border-amber-100 text-amber-800 px-4 py-3 rounded-xl text-xs flex items-start gap-2">
              <AlertTriangle className="w-4 h-4 text-amber-600 shrink-0 mt-0.5" />
              <div>
                <strong className="block font-semibold mb-0.5">内容已经发生变化</strong>
                <span>该对象在任务发起后被修改过。提交审批时，系统会再次校验并阻止确认过期内容。</span>
              </div>
            </div>
          )}

          {task.description && (
            <div className="bg-slate-50 rounded-xl p-3 border border-slate-200/60">
              <div className="text-[10px] font-bold text-slate-400 uppercase tracking-wide">指派说明</div>
              <div className="text-xs text-slate-600 mt-1 leading-relaxed whitespace-pre-wrap">{task.description}</div>
            </div>
          )}

          <div className="space-y-2.5">
            <div className="text-[10px] font-bold text-slate-400 uppercase tracking-wide">发起确认时的内容记录</div>
            <div className="space-y-3">
              {snapshotGroups.map((group, index) => {
                const entries = Object.entries(group.snapshot);
                return (
                  <div key={`${group.title}-${index}`} className="border border-slate-150 rounded-xl overflow-hidden bg-slate-50/30 text-xs">
                    {snapshotGroups.length > 1 && (
                      <div className="px-3.5 py-2 bg-slate-50 border-b border-slate-100 font-semibold text-slate-700">
                        {group.title}
                      </div>
                    )}
                    <table className="w-full border-collapse">
                      <tbody>
                        {entries.map(([key, val]) => (
                          <tr key={key} className="border-b border-slate-100 last:border-b-0">
                            <td className="px-3.5 py-2 text-[11px] font-semibold text-slate-500 bg-slate-50/50 w-1/3 border-r border-slate-100">
                              {fieldLabels[key] || key}
                            </td>
                            <td className="px-3.5 py-2 text-slate-700 break-all leading-normal whitespace-pre-wrap">
                              {formatValue(val)}
                            </td>
                          </tr>
                        ))}
                        {entries.length === 0 && (
                          <tr>
                            <td className="px-4 py-3 text-slate-400 text-center italic">
                              该确认对象没有可展示的内容字段
                            </td>
                          </tr>
                        )}
                      </tbody>
                    </table>
                  </div>
                );
              })}
            </div>
          </div>

          <div className="space-y-1.5">
            <label className="text-[10px] font-bold text-slate-400 uppercase tracking-wide flex items-center gap-1">
              <MessageSquare className="w-3.5 h-3.5 text-slate-400" />
              <span>审批批注 (选填)</span>
            </label>
            <textarea
              value={decisionNote}
              onChange={(e) => setDecisionNote(e.target.value)}
              placeholder="请输入审批意见、驳回原因或修改备注..."
              className="w-full text-xs text-slate-700 border border-slate-200 rounded-xl px-3.5 py-2.5 min-h-[70px] focus:outline-none focus:border-indigo-500 transition-colors"
            />
          </div>
        </div>

        <div className="px-6 py-4 border-t border-slate-150 bg-slate-50/30 flex items-center justify-between gap-3 shrink-0">
          <div className="text-[10px] text-slate-400">
            处理人 <span className="font-semibold text-slate-500">{task.assigneeEmail}</span>
          </div>
          <div className="flex items-center gap-3">
            <button
              onClick={() => handleDecision('reject')}
              disabled={loading}
              className="px-4 py-2 rounded-xl text-xs font-semibold border border-rose-200 text-rose-600 bg-white hover:bg-rose-50/50 transition-colors cursor-pointer disabled:opacity-50"
            >
              驳回
            </button>
            <button
              onClick={() => handleDecision('approve')}
              disabled={loading}
              className="px-4 py-2 rounded-xl text-xs font-semibold bg-indigo-600 hover:bg-indigo-700 text-white shadow-sm flex items-center gap-1.5 transition-colors cursor-pointer disabled:opacity-50"
            >
              <CheckCircle2 className="w-4 h-4" />
              <span>通过</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
