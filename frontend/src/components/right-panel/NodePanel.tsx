import { useEffect, useState } from 'react';
import { RequirementNode, RequirementSpaceIR } from '@/core/schema';
import { useWorkspaceStore } from '@/store/useWorkspaceStore';
import {
  ActionButton,
  ActionRow,
  Badge,
  LinkList,
  PanelShell,
  scopeOptions,
  Section,
  SelectField,
  TextField,
} from './shared';

const statusOptions = [
  { value: 'needs_confirmation', label: '待确认' },
  { value: 'ai_assumption', label: 'AI 假设' },
  { value: 'confirmed', label: '已确认' },
  { value: 'conflict', label: '发生冲突' },
  { value: 'deferred', label: '已暂缓' },
  { value: 'excluded', label: '已排除' },
];

const scopeStatusOptions = [
  { value: 'current', label: '本期包含' },
  { value: 'postponed', label: '暂缓处理' },
  { value: 'exclude', label: '已排除' },
];

const kindMap: Record<string, string> = {
  actor: '角色',
  feature: '功能模块',
  scenario: '业务场景',
  acceptance_criterion: '交付验收标准',
  business_object: '业务主数据实体',
  flow_step: '流程步骤',
  flow: '业务流程',
};

export function NodePanel({ node: rawNode, ir }: { node: RequirementNode; ir: RequirementSpaceIR }) {
  const node = rawNode as any;
  const { updateNodeAttributes, setNodeStatus, setScopeStatus } = useWorkspaceStore();
  const [title, setTitle] = useState(node.title);
  const [description, setDescription] = useState(node.description || '');

  useEffect(() => {
    setTitle(node.title);
    setDescription(node.description || '');
  }, [node.id, node.title, node.description]);

  const saveCore = async () => {
    await updateNodeAttributes(node.id, { title, description } as any);
  };

  const translatedKind = kindMap[node.kind] || node.kind;

  return (
    <PanelShell title={node.title} subtitle={`系统元素 / ${translatedKind}`}>
      <Section title="状态与交付范围">
        <div className="flex flex-wrap gap-2 mb-3">
          <Badge>
            {statusOptions.find(o => o.value === node.status)?.label || node.status}
          </Badge>
          {node.scopeStatus ? (
            <Badge>
              {scopeStatusOptions.find(o => o.value === node.scopeStatus)?.label || node.scopeStatus}
            </Badge>
          ) : null}
          {typeof node.confidence === 'number' ? (
            <Badge>AI 置信度 {Math.round(node.confidence * 100)}%</Badge>
          ) : null}
        </div>
        <SelectField
          label="节点审查状态"
          value={node.status}
          options={statusOptions}
          onChange={(value) => void setNodeStatus(node.id, value as any)}
        />
        <SelectField
          label="本期交付范围"
          value={node.scopeStatus || 'in_scope'}
          options={scopeStatusOptions}
          onChange={(value) => void setScopeStatus(node.id, value as any)}
        />
      </Section>

      <Section title="属性信息编辑">
        <TextField label="元素名称" value={title} onChange={setTitle} />
        <TextField label="职责说明 / 描述" value={description} onChange={setDescription} multiline />
        <ActionRow>
          <ActionButton onClick={() => void saveCore()}>保存更改</ActionButton>
          <ActionButton
            variant="secondary"
            onClick={() => {
              setTitle(node.title);
              setDescription(node.description || '');
            }}
          >
            重置修改
          </ActionButton>
        </ActionRow>
      </Section>

      {'outcome' in node || 'trigger' in node || 'purpose' in node || 'route' in node || 'componentType' in node || 'stepType' in node ? (
        <Section title="结构规范细节">
          {'outcome' in node ? <TextField label="预期成效" value={(node.outcome as string) || ''} onChange={(value) => void updateNodeAttributes(node.id, { outcome: value } as any)} /> : null}
          {'trigger' in node ? <TextField label="触发条件" value={(node.trigger as string) || ''} onChange={(value) => void updateNodeAttributes(node.id, { trigger: value } as any)} /> : null}
          {'purpose' in node ? <TextField label="业务价值" value={(node.purpose as string) || ''} onChange={(value) => void updateNodeAttributes(node.id, { purpose: value } as any)} /> : null}
          {'route' in node ? <TextField label="对应路由/物理路径" value={(node.route as string) || ''} onChange={(value) => void updateNodeAttributes(node.id, { route: value } as any)} /> : null}
          {'componentType' in node ? <TextField label="组件形态" value={(node.componentType as string) || ''} onChange={(value) => void updateNodeAttributes(node.id, { componentType: value } as any)} /> : null}
          {'stepType' in node ? <TextField label="步骤协作方式" value={(node.stepType as string) || ''} onChange={(value) => void updateNodeAttributes(node.id, { stepType: value } as any)} /> : null}
        </Section>
      ) : null}

      <Section title="拓扑链接关系">
        <LinkList ir={ir} nodeId={node.id} />
      </Section>
    </PanelShell>
  );
}
