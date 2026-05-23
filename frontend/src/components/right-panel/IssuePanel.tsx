import { useState } from 'react';
import { Issue, RequirementSpaceIR } from '@/core/schema';
import { useWorkspaceStore } from '@/store/useWorkspaceStore';
import { ActionButton, ActionRow, Badge, PanelShell, Section, SelectField, TextField } from './shared';

export function IssuePanel({ issue, ir }: { issue: Issue; ir: RequirementSpaceIR }) {
  const { updateIssueAttributes, createSlotFromIssue, expandSlot } = useWorkspaceStore();
  const [title, setTitle] = useState(issue.title);
  const [description, setDescription] = useState(issue.description || '');

  const openIssueFlow = async () => {
    const slotId = await createSlotFromIssue(issue.id);
    if (slotId) {
      await expandSlot(slotId);
    }
  };

  return (
    <PanelShell title={issue.title} subtitle="Issue">
      <Section title="状态">
        <div className="flex flex-wrap gap-2">
          <Badge>{issue.severity}</Badge>
          <Badge>{issue.category}</Badge>
          <Badge>{issue.status}</Badge>
        </div>
      </Section>

      <Section title="属性">
        <TextField label="标题" value={title} onChange={setTitle} />
        <TextField label="描述" value={description} onChange={setDescription} multiline />
        <SelectField
          label="严重度"
          value={issue.severity}
          options={[
            { value: 'low', label: '低' },
            { value: 'medium', label: '中' },
            { value: 'high', label: '高' },
          ]}
          onChange={(value) => void updateIssueAttributes(issue.id, { severity: value } as any)}
        />
        <SelectField
          label="状态"
          value={issue.status}
          options={[
            { value: 'open', label: '开放' },
            { value: 'resolved', label: '已解决' },
            { value: 'ignored', label: '已忽略' },
          ]}
          onChange={(value) => void updateIssueAttributes(issue.id, { status: value } as any)}
        />
        <ActionRow>
          <ActionButton onClick={() => void updateIssueAttributes(issue.id, { title, description })}>保存 Issue</ActionButton>
          <ActionButton variant="secondary" onClick={() => { setTitle(issue.title); setDescription(issue.description || ''); }}>
            重置
          </ActionButton>
        </ActionRow>
      </Section>

      <Section title="关联节点">
        {issue.relatedNodeIds.length === 0 && <div className="text-xs text-slate-400 italic">暂无关联节点</div>}
        {issue.relatedNodeIds.map((nodeId) => (
          <div key={nodeId} className="rounded-xl border border-slate-200 px-3 py-2 text-sm text-slate-700">
            {ir.nodes[nodeId]?.title || nodeId}
          </div>
        ))}
      </Section>

      <Section title="动作">
        <ActionRow>
          <ActionButton onClick={() => void openIssueFlow()}>创建 Slot 并展开</ActionButton>
          <ActionButton variant="secondary" onClick={() => void updateIssueAttributes(issue.id, { status: 'ignored' })}>
            忽略 Issue
          </ActionButton>
        </ActionRow>
      </Section>
    </PanelShell>
  );
}
