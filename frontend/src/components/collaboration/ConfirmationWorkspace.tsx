import React, { useState, useEffect, useCallback } from 'react';
import { 
  CheckCircle2, 
  AlertCircle, 
  User, 
  Inbox, 
  Send, 
  XCircle, 
  Plus, 
  FileText, 
  Layers, 
  UserCheck, 
  Clock, 
  AlertTriangle,
  ChevronDown,
  Calendar,
  MessageSquare,
  Search,
  Check
} from 'lucide-react';
import { useWorkspaceStore } from '@/store/useWorkspaceStore';
import { useAuthStore } from '@/store/useAuthStore';
import { workspaceApi } from '@/lib/api';
import { ProjectMember } from '@/core/schema';
import { TaskDecisionModal } from '../shared/TaskDecisionModal';

// Node kind mapping helper
const NodeKindLabels: Record<string, string> = {
  actor: '角色 (Actor)',
  feature: '功能特性 (Feature)',
  scenario: '场景 (Scenario)',
  acceptance_criterion: '验收标准 (Acceptance Criterion)',
  business_object: '业务对象 (Business Object)',
  business_object_attribute: '对象属性 (Attribute)',
  flow: '业务流程 (Flow)',
  flow_step: '流程步骤 (Flow Step)',
  scope: '范围规划 (Scope)'
};

export function ConfirmationWorkspace() {
  const ir = useWorkspaceStore((state) => state.ir);
  const projectId = ir?.projectId;
  const currentUserId = useAuthStore((state) => state.user?.id);

  // Store actions
  const tasks = useWorkspaceStore((state) => state.tasks);
  const confirmationSummary = useWorkspaceStore((state) => state.confirmationSummary);
  const loadProjectTasks = useWorkspaceStore((state) => state.loadProjectTasks);
  const loadConfirmationSummary = useWorkspaceStore((state) => state.loadConfirmationSummary);
  const createBatchConfirmTask = useWorkspaceStore((state) => state.createBatchConfirmTask);
  const cancelTaskAction = useWorkspaceStore((state) => state.cancelTask);

  // Component local states
  const [activeTab, setActiveTab] = useState<'assumptions' | 'tasks'>('assumptions');
  const [taskFilter, setTaskFilter] = useState<'all' | 'assigned_to_me' | 'created_by_me' | 'rejected'>('all');
  const [selectedAssumptions, setSelectedAssumptions] = useState<Set<string>>(new Set());
  const [members, setMembers] = useState<ProjectMember[]>([]);
  
  // Modals state
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  const [decisionTask, setDecisionTask] = useState<any | null>(null);

  // Create task form state
  const [assigneeId, setAssigneeId] = useState<number | ''>('');
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [priority, setPriority] = useState<'low' | 'medium' | 'high'>('medium');
  const [dueAt, setDueAt] = useState('');
  const [formError, setFormError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  // Search/Filter for assumptions
  const [searchQuery, setSearchQuery] = useState('');
  const [kindFilter, setKindFilter] = useState<string>('all');

  // Load initial data
  useEffect(() => {
    if (projectId) {
      if (typeof loadProjectTasks === 'function') {
        loadProjectTasks(projectId);
      }
      if (typeof loadConfirmationSummary === 'function') {
        loadConfirmationSummary(projectId);
      }
      workspaceApi.listProjectMembers(projectId).then(setMembers).catch(console.error);
    }
  }, [projectId, loadProjectTasks, loadConfirmationSummary]);

  // Extract all AI Assumptions from local workspace IR state for multiselect creation
  const getAiAssumptions = () => {
    if (!ir) return [];
    const items: Array<{ id: string; nodeKind: string; nodeId: number; title: string; source: string; status: string }> = [];

    const pushLedger = (kind: string, id: number, title: string, source: string, status: string) => {
      if (status === 'ai_assumption') {
        items.push({
          id: `${kind}-${id}`,
          nodeKind: kind,
          nodeId: id,
          title,
          source: source || '',
          status
        });
      }
    };

    (ir.actors || []).forEach((a: any) => {
      pushLedger('actor', a.actorId, a.actorName, a.actorDescription, a.confirmationStatus);
    });
    (ir.features || []).forEach((f: any) => {
      pushLedger('feature', f.featureId, f.featureName, f.featureDescription, f.confirmationStatus);
      (f.scenarios || []).forEach((s: any) => {
        pushLedger('scenario', s.scenarioId, s.scenarioName, s.scenarioContent, s.confirmationStatus);
        (s.acceptanceCriteria || []).forEach((ac: any) => {
          pushLedger('acceptance_criterion', ac.criterionId, ac.criterionContent?.slice(0, 80) || '', ac.criterionContent, ac.confirmationStatus);
        });
      });
      if (f.scope) {
        pushLedger('scope', f.featureId, `${f.featureName} - 范围`, f.scope.positiveSummary || '', f.scope.confirmationStatus || f.confirmationStatus);
      }
    });
    (ir.businessObjects || []).forEach((b: any) => {
      pushLedger('business_object', b.businessObjectId, b.businessObjectName, b.businessObjectDescription, b.confirmationStatus);
      (b.attributes || []).forEach((attr: any) => {
        pushLedger('business_object_attribute', attr.attributeId, `${b.businessObjectName}.${attr.attributeName}`, attr.attributeDescription, attr.confirmationStatus);
      });
    });
    (ir.flows || []).forEach((fl: any) => {
      pushLedger('flow', fl.flowId, fl.flowName, fl.flowDescription, fl.confirmationStatus);
      (fl.steps || []).forEach((step: any) => {
        pushLedger('flow_step', step.stepId, step.stepName, step.stepDescription, step.confirmationStatus);
      });
    });

    return items.filter(item => {
      const matchesSearch = item.title.toLowerCase().includes(searchQuery.toLowerCase()) || 
                            item.source.toLowerCase().includes(searchQuery.toLowerCase());
      const matchesKind = kindFilter === 'all' || item.nodeKind === kindFilter;
      return matchesSearch && matchesKind;
    });
  };

  const filteredAssumptions = getAiAssumptions();

  // Handle assumptions selection
  const handleToggleSelect = (id: string) => {
    setSelectedAssumptions(prev => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  };

  const handleToggleSelectAll = () => {
    if (selectedAssumptions.size === filteredAssumptions.length) {
      setSelectedAssumptions(new Set());
    } else {
      setSelectedAssumptions(new Set(filteredAssumptions.map(i => i.id)));
    }
  };

  // Assignee filtering: active members and not viewers
  const eligibleAssignees = members.filter(m => m.status === 'active' && m.role !== 'viewer');

  // Submit batch task
  const handleCreateBatchTask = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!projectId || !assigneeId) return;

    const targets = filteredAssumptions
      .filter(item => selectedAssumptions.has(item.id))
      .map(item => ({
        nodeKind: item.nodeKind,
        nodeId: item.nodeId
      }));

    if (targets.length === 0) {
      setFormError('请选择至少一个确认目标节点。');
      return;
    }

    try {
      setSubmitting(true);
      setFormError(null);
      await createBatchConfirmTask(projectId, {
        targets,
        assignedToUserId: Number(assigneeId),
        title: title.trim() || undefined,
        description: description.trim() || undefined,
        priority,
        dueAt: dueAt || undefined
      });
      
      // Reset form and select state
      setIsCreateModalOpen(false);
      setSelectedAssumptions(new Set());
      setTitle('');
      setDescription('');
      setAssigneeId('');
      setPriority('medium');
      setDueAt('');
    } catch (err: any) {
      setFormError(err?.response?.data?.detail || err?.message || '创建确认任务失败');
    } finally {
      setSubmitting(false);
    }
  };

  // Filter tasks list based on filter tab
  const getFilteredTasks = () => {
    return (tasks || []).filter(task => {
      if (taskFilter === 'assigned_to_me') {
        return task.status === 'open' && task.assignedToUserId === currentUserId;
      }
      if (taskFilter === 'created_by_me') {
        return task.status === 'open' && task.createdByUserId === currentUserId;
      }
      if (taskFilter === 'rejected') {
        return task.status === 'rejected';
      }
      return true;
    });
  };

  const filteredTasks = getFilteredTasks();

  return (
    <div className="bg-slate-50/50 h-full p-6 space-y-6 flex flex-col">
      
      {/* 1. Dashboard summary header */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
        
        {/* Card 1: AI Assumptions */}
        <div className="bg-white rounded-2xl p-4 border border-slate-200 shadow-sm flex items-center gap-4">
          <div className="bg-indigo-50 text-indigo-600 rounded-xl p-3">
            <Layers className="w-6 h-6" />
          </div>
          <div>
            <div className="text-xs text-slate-400 font-semibold">AI 假设节点</div>
            <div className="text-xl font-bold text-slate-800 mt-0.5">
              {confirmationSummary?.aiAssumptionCount ?? 0}
            </div>
          </div>
        </div>

        {/* Card 2: Open Tasks */}
        <div className="bg-white rounded-2xl p-4 border border-slate-200 shadow-sm flex items-center gap-4">
          <div className="bg-sky-50 text-sky-600 rounded-xl p-3">
            <Inbox className="w-6 h-6" />
          </div>
          <div>
            <div className="text-xs text-slate-400 font-semibold">未完结任务</div>
            <div className="text-xl font-bold text-slate-800 mt-0.5">
              {confirmationSummary?.openTaskCount ?? 0}
            </div>
          </div>
        </div>

        {/* Card 3: Assigned To Me */}
        <div className="bg-white rounded-2xl p-4 border border-slate-200 shadow-sm flex items-center gap-4">
          <div className="bg-emerald-50 text-emerald-600 rounded-xl p-3">
            <UserCheck className="w-6 h-6" />
          </div>
          <div>
            <div className="text-xs text-slate-400 font-semibold">指派给我</div>
            <div className="text-xl font-bold text-slate-800 mt-0.5">
              {confirmationSummary?.assignedToMeCount ?? 0}
            </div>
          </div>
        </div>

        {/* Card 4: Created By Me */}
        <div className="bg-white rounded-2xl p-4 border border-slate-200 shadow-sm flex items-center gap-4">
          <div className="bg-violet-50 text-violet-600 rounded-xl p-3">
            <Send className="w-6 h-6" />
          </div>
          <div>
            <div className="text-xs text-slate-400 font-semibold">我创建的</div>
            <div className="text-xl font-bold text-slate-800 mt-0.5">
              {confirmationSummary?.createdByMeCount ?? 0}
            </div>
          </div>
        </div>

        {/* Card 5: Rejected Tasks */}
        <div className="bg-white rounded-2xl p-4 border border-slate-200 shadow-sm flex items-center gap-4 col-span-2 md:col-span-1">
          <div className="bg-rose-50 text-rose-600 rounded-xl p-3">
            <XCircle className="w-6 h-6" />
          </div>
          <div>
            <div className="text-xs text-slate-400 font-semibold">已驳回任务</div>
            <div className="text-xl font-bold text-slate-800 mt-0.5">
              {confirmationSummary?.rejectedCount ?? 0}
            </div>
          </div>
        </div>

      </div>

      {/* 2. Workspace Navigation Tabs */}
      <div className="bg-white border border-slate-200 rounded-2xl p-2 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <button
            onClick={() => setActiveTab('assumptions')}
            className={`px-4 py-2 rounded-xl text-sm font-semibold transition-all cursor-pointer ${
              activeTab === 'assumptions' 
                ? 'bg-slate-100 text-slate-800' 
                : 'text-slate-500 hover:text-slate-800'
            }`}
          >
            待审批资产 ({filteredAssumptions.length})
          </button>
          <button
            onClick={() => setActiveTab('tasks')}
            className={`px-4 py-2 rounded-xl text-sm font-semibold transition-all cursor-pointer ${
              activeTab === 'tasks' 
                ? 'bg-slate-100 text-slate-800' 
                : 'text-slate-500 hover:text-slate-800'
            }`}
          >
            确认任务列表 ({(tasks || []).length})
          </button>
        </div>

        {activeTab === 'assumptions' && selectedAssumptions.size > 0 && (
          <button
            onClick={() => setIsCreateModalOpen(true)}
            className="bg-indigo-600 hover:bg-indigo-700 text-white rounded-xl px-4 py-2 text-sm font-semibold shadow-sm flex items-center gap-1.5 transition-colors cursor-pointer"
          >
            <Plus className="w-4 h-4" />
            <span>发起确认指派 ({selectedAssumptions.size})</span>
          </button>
        )}
      </div>

      {/* 3. Panel Content */}
      <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden flex-1 min-h-[450px]">
        {activeTab === 'assumptions' ? (
          // ASSUMPTIONS LEDGER TAB
          <div className="flex flex-col h-full">
            {/* Filter tools */}
            <div className="px-6 py-4 border-b border-slate-100 bg-slate-50/30 flex flex-col md:flex-row md:items-center justify-between gap-3">
              <div className="flex items-center gap-2 flex-1 max-w-md bg-white border border-slate-200 rounded-xl px-3 py-1.5">
                <Search className="w-4 h-4 text-slate-400 shrink-0" />
                <input
                  type="text"
                  placeholder="搜索资产标题或背景描述..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="text-xs text-slate-700 focus:outline-none w-full bg-transparent"
                />
              </div>

              <div className="flex items-center gap-2">
                <select
                  value={kindFilter}
                  onChange={(e) => setKindFilter(e.target.value)}
                  className="rounded-xl border border-slate-200 px-3 py-2 text-xs text-slate-600 bg-white focus:outline-none focus:border-slate-300"
                >
                  <option value="all">所有类型</option>
                  {Object.entries(NodeKindLabels).map(([k, label]) => (
                    <option key={k} value={k}>{label}</option>
                  ))}
                </select>

                <button
                  onClick={handleToggleSelectAll}
                  className="rounded-xl border border-slate-200 px-3 py-2 text-xs font-semibold text-slate-600 bg-white hover:bg-slate-50 cursor-pointer"
                >
                  {selectedAssumptions.size === filteredAssumptions.length ? '取消全选' : '全选'}
                </button>
              </div>
            </div>

            {/* List */}
            <div className="flex-1 p-6 space-y-2.5 max-h-[60vh] overflow-y-auto">
              {filteredAssumptions.length === 0 ? (
                <div className="flex flex-col items-center justify-center py-20 text-slate-400 gap-3">
                  <FileText className="w-12 h-12 stroke-[1.5]" />
                  <p className="text-sm">暂无符合筛选条件的 AI 假设资产</p>
                </div>
              ) : (
                filteredAssumptions.map((item) => {
                  const isSelected = selectedAssumptions.has(item.id);
                  return (
                    <div
                      key={item.id}
                      onClick={() => handleToggleSelect(item.id)}
                      className={`flex items-start gap-4 p-4 rounded-xl border transition-all cursor-pointer ${
                        isSelected 
                          ? 'border-indigo-200 bg-indigo-50/20' 
                          : 'border-slate-150 hover:border-indigo-150 hover:bg-slate-50/40'
                      }`}
                    >
                      <input
                        type="checkbox"
                        checked={isSelected}
                        onChange={() => {}}
                        className="mt-1 h-4 w-4 rounded border-slate-300 text-indigo-600 focus:ring-indigo-500 cursor-pointer"
                      />
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                          <span className="text-[10px] font-bold text-slate-400 bg-slate-100 rounded-full px-2 py-0.5 uppercase tracking-wide">
                            {NodeKindLabels[item.nodeKind] || item.nodeKind}
                          </span>
                          <span className="inline-flex items-center rounded-full px-2.5 py-1 text-[10px] font-bold tracking-wide bg-indigo-50 text-indigo-700 border border-indigo-200">
                            AI 假设
                          </span>
                        </div>
                        <h4 className="text-sm font-bold text-slate-800 mt-2">{item.title}</h4>
                        {item.source && (
                          <p className="text-xs text-slate-500 mt-1 leading-relaxed whitespace-pre-wrap">
                            {item.source}
                          </p>
                        )}
                      </div>
                    </div>
                  );
                })
              )}
            </div>
          </div>
        ) : (
          // TASKS LIST TAB
          <div className="flex flex-col h-full">
            {/* Filter tabs */}
            <div className="px-6 py-4 border-b border-slate-100 bg-slate-50/30 flex items-center gap-2">
              {[
                { key: 'all', label: '全部任务' },
                { key: 'assigned_to_me', label: '指派给我' },
                { key: 'created_by_me', label: '我创建的' },
                { key: 'rejected', label: '驳回/拒绝' }
              ].map(f => (
                <button
                  key={f.key}
                  onClick={() => setTaskFilter(f.key as any)}
                  className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all cursor-pointer ${
                    taskFilter === f.key 
                      ? 'bg-slate-200 text-slate-800' 
                      : 'text-slate-500 hover:text-slate-800'
                  }`}
                >
                  {f.label}
                </button>
              ))}
            </div>

            {/* List */}
            <div className="flex-1 p-6 space-y-4 max-h-[60vh] overflow-y-auto">
              {filteredTasks.length === 0 ? (
                <div className="flex flex-col items-center justify-center py-20 text-slate-400 gap-3">
                  <Inbox className="w-12 h-12 stroke-[1.5]" />
                  <p className="text-sm">当前分类下暂无确认任务</p>
                </div>
              ) : (
                filteredTasks.map((task) => (
                  <div
                    key={task.id}
                    className="border border-slate-200 rounded-xl p-5 hover:border-slate-300 transition-all space-y-4 bg-white shadow-sm"
                  >
                    {/* Header */}
                    <div className="flex items-start justify-between gap-4">
                      <div className="space-y-1">
                        <div className="flex flex-wrap items-center gap-2">
                          {/* Priority badge */}
                          <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${
                            task.priority === 'high' 
                              ? 'bg-rose-50 text-rose-600' 
                              : task.priority === 'medium'
                              ? 'bg-amber-50 text-amber-600'
                              : 'bg-slate-100 text-slate-600'
                          }`}>
                            {task.priority === 'high' ? '高' : task.priority === 'medium' ? '中' : '低'} 优先级
                          </span>
                          
                          {/* Status badge */}
                          <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${
                            task.status === 'open' 
                              ? 'bg-sky-50 text-sky-600' 
                              : task.status === 'done'
                              ? 'bg-emerald-50 text-emerald-600'
                              : task.status === 'rejected'
                              ? 'bg-rose-50 text-rose-600'
                              : 'bg-slate-100 text-slate-600'
                          }`}>
                            {task.status === 'open' ? '办理中' : task.status === 'done' ? '已确认' : task.status === 'rejected' ? '已驳回' : '失效/取消'}
                          </span>

                          {/* Content changed notification */}
                          {task.contentChanged && (
                            <span className="flex items-center gap-1 text-[10px] font-bold text-amber-700 bg-amber-50 px-2 py-0.5 rounded-full">
                              <AlertTriangle className="w-3.5 h-3.5 text-amber-600" />
                              <span>内容已变更</span>
                            </span>
                          )}
                        </div>
                        <h4 className="text-sm font-bold text-slate-800 mt-1">{task.title}</h4>
                      </div>

                      {/* Decides button */}
                      {task.status === 'open' && task.assignedToUserId === currentUserId && (
                        <button
                          onClick={() => setDecisionTask(task)}
                          className="bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg px-3 py-1.5 text-xs font-semibold shadow-sm transition-colors cursor-pointer"
                        >
                          办理决策
                        </button>
                      )}
                    </div>

                    {/* Description */}
                    {task.description && (
                      <p className="text-xs text-slate-600 bg-slate-50 rounded-xl p-3 border border-slate-100 leading-relaxed">
                        {task.description}
                      </p>
                    )}

                    {/* Meta info row */}
                    <div className="flex flex-wrap items-center justify-between text-[11px] text-slate-400 gap-3 border-t border-slate-100 pt-3">
                      <div className="flex flex-wrap items-center gap-4">
                        <span className="flex items-center gap-1">
                          <User className="w-3.5 h-3.5 text-slate-400" />
                          <span>指派给: <span className="font-semibold text-slate-500">{task.assigneeEmail}</span></span>
                        </span>
                        <span>发起人: <span className="font-semibold text-slate-500">{task.creatorEmail}</span></span>
                      </div>
                      
                      {task.dueAt && (
                        <span className="flex items-center gap-1">
                          <Clock className="w-3.5 h-3.5 text-slate-400" />
                          <span>截止日: {new Date(task.dueAt).toLocaleDateString()}</span>
                        </span>
                      )}
                    </div>

                    {/* Target nodes details list */}
                    {task.taskType !== 'resolve_conflict' && task.taskType !== 'review_draft' && (
                      <div className="border border-slate-100 rounded-xl bg-slate-50/30 overflow-hidden text-xs">
                        <div className="bg-slate-50/70 px-3 py-1.5 border-b border-slate-100 text-[10px] font-bold text-slate-400 uppercase tracking-wider flex items-center justify-between">
                          <span>待确认资产清单</span>
                          <span>共 {task.targets?.length ?? 1} 个节点</span>
                        </div>
                        <div className="divide-y divide-slate-100">
                          {task.targets?.map((target: any, idx: number) => (
                            <div key={idx} className="px-3.5 py-2 flex items-center justify-between gap-3 bg-white">
                              <span className="font-semibold text-slate-700 truncate">
                                {target.node_name || target.snapshot?.name || target.snapshot?.content || `${NodeKindLabels[target.node_kind] || target.node_kind} #${target.node_id}`}
                              </span>
                              <span className="text-[10px] font-medium text-slate-400 uppercase tracking-wide shrink-0">
                                {NodeKindLabels[target.node_kind] || target.node_kind}
                              </span>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Resolve Conflict details */}
                    {(task.taskType === 'resolve_conflict' || task.taskType === 'review_draft') && task.payload && (
                      <div className="border border-amber-200 rounded-xl bg-amber-50/10 overflow-hidden text-xs space-y-3 p-4">
                        <div className="flex items-center gap-1.5 text-amber-800 font-bold">
                          <AlertTriangle className="w-4 h-4 text-amber-600" />
                          <span>检测到 AI 写入冲突 ({task.payload.target_type})</span>
                        </div>
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                          {/* Stale AI Suggestion */}
                          <div className="bg-white border border-slate-200 rounded-xl p-3.5 space-y-2">
                            <div className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">AI 冲突建议内容</div>
                            <div className="bg-slate-50 rounded-lg p-2.5 font-mono text-[11px] overflow-x-auto whitespace-pre-wrap max-h-40 overflow-y-auto">
                              {JSON.stringify(task.payload.stale_ai_result, null, 2)}
                            </div>
                          </div>

                          {/* Current Project Context */}
                          <div className="bg-white border border-slate-200 rounded-xl p-3.5 space-y-2">
                            <div className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">当前项目上下文</div>
                            <div className="bg-slate-50 rounded-lg p-2.5 font-mono text-[11px] overflow-x-auto whitespace-pre-wrap max-h-40 overflow-y-auto">
                              {JSON.stringify(task.payload.current_snapshot, null, 2)}
                            </div>
                          </div>
                        </div>
                      </div>
                    )}

                    {/* Rejection comment */}
                    {task.status === 'rejected' && task.decisionNote && (
                      <div className="bg-rose-50/40 border border-rose-100/60 rounded-xl p-3.5 text-xs text-rose-800 space-y-1">
                        <div className="font-bold flex items-center gap-1.5 text-rose-900">
                          <MessageSquare className="w-4 h-4 text-rose-600" />
                          <span>驳回意见:</span>
                        </div>
                        <p className="leading-relaxed whitespace-pre-wrap">{task.decisionNote}</p>
                      </div>
                    )}
                  </div>
                ))
              )}
            </div>
          </div>
        )}
      </div>

      {/* 4. Modals */}
      
      {/* Modal 1: Create confirmation task */}
      {isCreateModalOpen && (
        <div className="fixed inset-0 bg-slate-900/40 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl shadow-xl w-full max-w-lg border border-slate-200 overflow-hidden">
            <div className="px-6 py-4 border-b border-slate-150 flex items-center justify-between bg-slate-50/50">
              <h3 className="text-base font-bold text-slate-800">发起资产确认指派</h3>
              <button 
                onClick={() => setIsCreateModalOpen(false)}
                className="text-slate-400 hover:text-slate-600 p-1 hover:bg-slate-100 rounded-lg transition-colors cursor-pointer"
              >
                <XCircle className="w-5 h-5" />
              </button>
            </div>

            <form onSubmit={handleCreateBatchTask} className="p-6 space-y-4">
              {formError && (
                <div className="bg-rose-50 border border-rose-100 text-rose-700 px-4 py-3 rounded-xl text-xs flex items-center gap-2">
                  <AlertCircle className="w-4 h-4 shrink-0" />
                  <span>{formError}</span>
                </div>
              )}

              {/* Targets Summary info */}
              <div className="bg-slate-50 border border-slate-200/60 rounded-xl p-3 text-xs flex items-center justify-between">
                <span className="text-slate-500">确认资产范围</span>
                <span className="font-bold text-slate-800">共选择了 {selectedAssumptions.size} 个节点</span>
              </div>

              {/* Title */}
              <div className="space-y-1.5">
                <label className="text-xs font-bold text-slate-500">指派标题 (选填)</label>
                <input
                  type="text"
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  placeholder="例如: 核心流与特性资产校验"
                  className="w-full text-xs text-slate-700 border border-slate-200 rounded-xl px-3.5 py-2.5 focus:outline-none focus:border-indigo-500 transition-colors"
                />
              </div>

              {/* Description */}
              <div className="space-y-1.5">
                <label className="text-xs font-bold text-slate-500">指派说明 (选填)</label>
                <textarea
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  placeholder="请说明校验指派的具体意图或确认范围..."
                  className="w-full text-xs text-slate-700 border border-slate-200 rounded-xl px-3.5 py-2.5 min-h-[80px] focus:outline-none focus:border-indigo-500 transition-colors"
                />
              </div>

              {/* Assignee Selection */}
              <div className="space-y-1.5">
                <label className="text-xs font-bold text-slate-500 flex items-center gap-0.5">
                  <span>选择指派确认人</span>
                  <span className="text-rose-500">*</span>
                </label>
                <div className="relative">
                  <select
                    value={assigneeId}
                    onChange={(e) => setAssigneeId(e.target.value ? Number(e.target.value) : '')}
                    required
                    className="w-full text-xs text-slate-700 border border-slate-200 rounded-xl px-3.5 py-2.5 bg-white focus:outline-none focus:border-indigo-500 appearance-none transition-colors"
                  >
                    <option value="">-- 请选择拥有编辑权限的成员 --</option>
                    {eligibleAssignees.map(m => (
                      <option key={m.userId} value={m.userId}>
                        {m.email} ({m.role})
                      </option>
                    ))}
                  </select>
                  <ChevronDown className="w-4 h-4 text-slate-400 absolute right-3.5 top-3 pointer-events-none" />
                </div>
              </div>

              {/* Two columns: priority & due date */}
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-1.5">
                  <label className="text-xs font-bold text-slate-500">优先级</label>
                  <div className="relative">
                    <select
                      value={priority}
                      onChange={(e: any) => setPriority(e.target.value)}
                      className="w-full text-xs text-slate-700 border border-slate-200 rounded-xl px-3.5 py-2.5 bg-white focus:outline-none focus:border-indigo-500 appearance-none transition-colors"
                    >
                      <option value="low">低 (Low)</option>
                      <option value="medium">中 (Medium)</option>
                      <option value="high">高 (High)</option>
                    </select>
                    <ChevronDown className="w-4 h-4 text-slate-400 absolute right-3.5 top-3 pointer-events-none" />
                  </div>
                </div>

                <div className="space-y-1.5">
                  <label className="text-xs font-bold text-slate-500">截止日期 (选填)</label>
                  <div className="relative">
                    <input
                      type="date"
                      value={dueAt}
                      onChange={(e) => setDueAt(e.target.value)}
                      className="w-full text-xs text-slate-700 border border-slate-200 rounded-xl px-3.5 py-2.5 bg-white focus:outline-none focus:border-indigo-500 transition-colors"
                    />
                    <Calendar className="w-4 h-4 text-slate-400 absolute right-3.5 top-3 pointer-events-none" />
                  </div>
                </div>
              </div>

              {/* Form buttons */}
              <div className="flex items-center justify-end gap-3 pt-3 border-t border-slate-100">
                <button
                  type="button"
                  onClick={() => setIsCreateModalOpen(false)}
                  className="rounded-xl border border-slate-200 bg-white px-4 py-2.5 text-xs font-semibold text-slate-600 hover:bg-slate-50 transition-all cursor-pointer"
                >
                  取消
                </button>
                <button
                  type="submit"
                  disabled={submitting}
                  className="bg-indigo-600 hover:bg-indigo-700 text-white rounded-xl px-4 py-2.5 text-xs font-semibold shadow-sm transition-colors cursor-pointer disabled:opacity-50"
                >
                  {submitting ? '提交中...' : '确认指派'}
                </button>
              </div>

            </form>
          </div>
        </div>
      )}

      {/* Modal 2: Decision task trigger */}
      {decisionTask && projectId && (
        <TaskDecisionModal
          task={decisionTask}
          projectId={projectId}
          onClose={() => setDecisionTask(null)}
          onDecided={() => {
            setDecisionTask(null);
            loadProjectTasks(projectId);
            loadConfirmationSummary(projectId);
          }}
        />
      )}

    </div>
  );
}
