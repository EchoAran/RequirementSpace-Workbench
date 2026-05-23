import { useEffect, useMemo, useState } from 'react';
import { GraphPatch, RequirementNode, RequirementSpaceIR } from '@/core/schema';
import { useWorkspaceStore } from '@/store/useWorkspaceStore';
import {
  ActionButton,
  ActionRow,
  Badge,
  LinkList,
  PanelShell,
  RelationEditor,
  RelationSpec,
  scopeOptions,
  Section,
  SelectField,
  TextField,
} from './shared';

const statusOptions = [
  { value: 'needs_confirmation', label: '待确认' },
  { value: 'ai_assumption', label: 'AI 假设' },
  { value: 'confirmed', label: '已确认' },
  { value: 'conflict', label: '有冲突' },
  { value: 'deferred', label: '暂缓' },
  { value: 'excluded', label: '已排除' },
];

const relationSpecsByKind: Record<string, RelationSpec[]> = {
  goal: [{ label: '包含能力', linkType: 'contains', direction: 'out', targetKinds: ['capability'], multiple: true }],
  capability: [
    { label: '父级能力', linkType: 'contains', direction: 'in', targetKinds: ['goal', 'capability'] },
    { label: '子能力', linkType: 'contains', direction: 'out', targetKinds: ['capability'], multiple: true },
    { label: '依赖能力', linkType: 'depends_on', direction: 'out', targetKinds: ['capability'], multiple: true },
  ],
  task: [
    { label: '执行者', linkType: 'performed_by', direction: 'out', targetKinds: ['actor'] },
    { label: '支撑能力', linkType: 'supports', direction: 'out', targetKinds: ['capability'], multiple: true },
  ],
  flow: [{ label: '实现任务', linkType: 'realizes', direction: 'out', targetKinds: ['task'], multiple: true }],
  flow_step: [
    { label: '执行者', linkType: 'performed_by', direction: 'out', targetKinds: ['actor'] },
    { label: '支撑任务', linkType: 'supports', direction: 'out', targetKinds: ['task'], multiple: true },
    { label: '读取对象', linkType: 'reads', direction: 'out', targetKinds: ['business_object'], multiple: true },
    { label: '写入对象', linkType: 'writes', direction: 'out', targetKinds: ['business_object'], multiple: true },
    { label: '触发状态变化', linkType: 'changes_state', direction: 'out', targetKinds: ['state_transition'], multiple: true },
  ],
  rule: [{ label: '约束目标', linkType: 'guards', direction: 'out', targetKinds: ['flow_step', 'state_transition'], multiple: true }],
  business_object: [
    { label: '负责人', linkType: 'owns', direction: 'in', targetKinds: ['actor'] },
    { label: '字段', linkType: 'contains', direction: 'out', targetKinds: ['field'], multiple: true },
    { label: '状态机', linkType: 'contains', direction: 'out', targetKinds: ['state_machine'], multiple: true },
  ],
  state_machine: [
    { label: '所属对象', linkType: 'contains', direction: 'in', targetKinds: ['business_object'] },
    { label: '状态', linkType: 'contains', direction: 'out', targetKinds: ['object_state'], multiple: true },
    { label: '流转', linkType: 'contains', direction: 'out', targetKinds: ['state_transition'], multiple: true },
  ],
  screen: [
    { label: '可访问角色', linkType: 'accessible_by', direction: 'out', targetKinds: ['actor'], multiple: true },
    { label: '包含组件', linkType: 'contains', direction: 'out', targetKinds: ['ui_component'], multiple: true },
    { label: '读取对象', linkType: 'reads', direction: 'out', targetKinds: ['business_object'], multiple: true },
    { label: '写入对象', linkType: 'writes', direction: 'out', targetKinds: ['business_object'], multiple: true },
  ],
  ui_component: [
    { label: '父组件/页面', linkType: 'contains', direction: 'in', targetKinds: ['screen', 'ui_component'] },
    { label: '子组件', linkType: 'contains', direction: 'out', targetKinds: ['ui_component'], multiple: true },
    { label: '绑定字段', linkType: 'binds_field', direction: 'out', targetKinds: ['field'], multiple: true },
    { label: '触发步骤', linkType: 'invokes_step', direction: 'out', targetKinds: ['flow_step'], multiple: true },
  ],
};

export function NodePanel({ node: rawNode, ir }: { node: RequirementNode; ir: RequirementSpaceIR }) {
  const node = rawNode as any;
  const { updateNodeAttributes, setNodeStatus, setScopeStatus, applyPatch } = useWorkspaceStore();
  const [title, setTitle] = useState(node.title);
  const [description, setDescription] = useState(node.description || '');

  const relationSpecs = useMemo(() => relationSpecsByKind[node.kind] || [], [node.kind]);

  useEffect(() => {
    setTitle(node.title);
    setDescription(node.description || '');
  }, [node.id, node.title, node.description]);

  const saveCore = async () => {
    await updateNodeAttributes(node.id, { title, description } as any);
  };

  const updateRelationPatch = async (patch: GraphPatch) => {
    await applyPatch(patch);
  };

  return (
    <PanelShell title={node.title} subtitle={`Node · ${node.kind}`}>
      <Section title="状态">
        <div className="flex flex-wrap gap-2">
          <Badge>{node.status}</Badge>
          {node.scopeStatus ? <Badge>{node.scopeStatus}</Badge> : null}
          {typeof node.confidence === 'number' ? <Badge>置信度 {Math.round(node.confidence * 100)}%</Badge> : null}
        </div>
        <SelectField label="节点状态" value={node.status} options={statusOptions} onChange={(value) => void setNodeStatus(node.id, value as any)} />
        <SelectField
          label="范围状态"
          value={node.scopeStatus || 'in_scope'}
          options={scopeOptions()}
          onChange={(value) => void setScopeStatus(node.id, value as any)}
        />
      </Section>

      <Section title="属性">
        <TextField label="标题" value={title} onChange={setTitle} />
        <TextField label="描述" value={description} onChange={setDescription} multiline />
        <ActionRow>
          <ActionButton onClick={() => void saveCore()}>保存属性</ActionButton>
          <ActionButton variant="secondary" onClick={() => { setTitle(node.title); setDescription(node.description || ''); }}>
            重置
          </ActionButton>
        </ActionRow>
      </Section>

      {'outcome' in node || 'trigger' in node || 'purpose' in node || 'route' in node || 'componentType' in node || 'stepType' in node ? (
        <Section title="结构属性">
          {'outcome' in node ? <TextField label="结果" value={(node.outcome as string) || ''} onChange={(value) => void updateNodeAttributes(node.id, { outcome: value } as any)} /> : null}
          {'trigger' in node ? <TextField label="触发条件" value={(node.trigger as string) || ''} onChange={(value) => void updateNodeAttributes(node.id, { trigger: value } as any)} /> : null}
          {'purpose' in node ? <TextField label="用途" value={(node.purpose as string) || ''} onChange={(value) => void updateNodeAttributes(node.id, { purpose: value } as any)} /> : null}
          {'route' in node ? <TextField label="路由" value={(node.route as string) || ''} onChange={(value) => void updateNodeAttributes(node.id, { route: value } as any)} /> : null}
          {'componentType' in node ? (
            <TextField label="组件类型" value={(node.componentType as string) || ''} onChange={(value) => void updateNodeAttributes(node.id, { componentType: value } as any)} />
          ) : null}
          {'stepType' in node ? <TextField label="步骤类型" value={(node.stepType as string) || ''} onChange={(value) => void updateNodeAttributes(node.id, { stepType: value } as any)} /> : null}
        </Section>
      ) : null}

      <Section title="关系编辑">
        {relationSpecs.length === 0 && <div className="text-xs text-slate-400 italic">当前对象暂无专用关系编辑器。</div>}
        {relationSpecs.map((spec, index) => (
          <div key={`${spec.linkType}-${spec.label}-${index}`}>
            <RelationEditor ir={ir} node={node} spec={spec} onApplyPatch={updateRelationPatch} />
          </div>
        ))}
      </Section>

      <Section title="关系总览">
        <LinkList ir={ir} nodeId={node.id} />
      </Section>
    </PanelShell>
  );
}
