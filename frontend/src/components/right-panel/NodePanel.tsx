import { useTranslation } from 'react-i18next';
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







export function NodePanel({ node: rawNode, ir }: { node: RequirementNode; ir: RequirementSpaceIR }) {
  const { t } = useTranslation();
  const statusOptions = [
    { value: 'needs_confirmation', label: t('panel.nodeStatus.needs_confirmation') },
    { value: 'ai_assumption', label: t('panel.nodeStatus.ai_assumption') },
    { value: 'confirmed', label: t('panel.nodeStatus.confirmed') },
    { value: 'conflict', label: t('panel.nodeStatus.conflict') },
    { value: 'deferred', label: t('panel.nodeStatus.deferred') },
    { value: 'excluded', label: t('panel.nodeStatus.excluded') },
  ];
  const scopeStatusOptions = [
    { value: 'current', label: t('panel.scopeKano.current') },
    { value: 'postponed', label: t('panel.scopeKano.postponed') },
    { value: 'exclude', label: t('panel.scopeKano.exclude') },
  ];
  const kindMap: Record<string, string> = {
    actor: t('panel.kindLabel.actor'),
    feature: t('panel.kindLabel.feature'),
    scenario: t('panel.kindLabel.scenario'),
    acceptance_criterion: t('panel.kindLabel.acceptance_criterion'),
    business_object: t('panel.kindLabel.business_object'),
    flow_step: t('panel.kindLabel.flow_step'),
    flow: t('panel.kindLabel.flow'),
  };
  const node = rawNode as any;
  const { updateNodeAttributes, setNodeStatus, setScopeStatus } = useWorkspaceStore();
  const [title, setTitle] = useState(node.title);
  const [description, setDescription] = useState(node.description || '');

  useEffect(() => {
    setTitle(node.title);
    setDescription(node.description || '');
  }, [node.id, node.title, node.description]);

  // 兼容两种字段名：selectAllNodes 映射的 status 和原始 API 返回的 confirmationStatus
  const displayStatus = node.status || node.confirmationStatus || 'ai_assumption';

  const saveCore = async () => {
    await updateNodeAttributes(node.id, { title, description } as any);
  };

  const translatedKind = kindMap[node.kind] || node.kind;

  return (
    <PanelShell title={node.title} subtitle={t('panel.node') + ' / ' + translatedKind}>
      <Section title={t('panel.statusAndScope')}>
        <div className="flex flex-wrap gap-2 mb-3">
          <Badge>
            {statusOptions.find(o => o.value === displayStatus)?.label || displayStatus}
          </Badge>
          {node.scopeStatus ? (
            <Badge>
              {scopeStatusOptions.find(o => o.value === node.scopeStatus)?.label || node.scopeStatus}
            </Badge>
          ) : null}
          {typeof node.confidence === 'number' ? (
            <Badge>{t('panel.aiConfidence', { confidence: Math.round(node.confidence * 100) })}</Badge>
          ) : null}
        </div>
        <SelectField
          label={t('panel.nodeStatusLabel')}
          value={displayStatus}
          options={statusOptions}
          onChange={(value) => void setNodeStatus(node.id, node.kind, value as any)}
        />
        <SelectField
          label={t('panel.scopeLabel')}
          value={node.scopeStatus || 'in_scope'}
          options={scopeStatusOptions}
          onChange={(value) => void setScopeStatus(node.id, value as any)}
        />
      </Section>

      <Section title={t('panel.elementEdit')}>
        <TextField label={t('panel.elementName')} value={title} onChange={setTitle} />
        <TextField label={t('panel.description')} value={description} onChange={setDescription} multiline />
        <ActionRow>
          <ActionButton onClick={() => void saveCore()}>{t('panel.saveBtn')}</ActionButton>
          <ActionButton
            variant="secondary"
            onClick={() => {
              setTitle(node.title);
              setDescription(node.description || '');
            }}
          >
            {t('panel.resetBtn')}
          </ActionButton>
        </ActionRow>
      </Section>

      {'outcome' in node || 'trigger' in node || 'purpose' in node || 'route' in node || 'componentType' in node || 'stepType' in node ? (
        <Section title={t('panel.structuralAttrs')}>
          {'outcome' in node ? <TextField label={t('panel.outcome')} value={(node.outcome as string) || ''} onChange={(value) => void updateNodeAttributes(node.id, { outcome: value } as any)} /> : null}
          {'trigger' in node ? <TextField label={t('panel.trigger')} value={(node.trigger as string) || ''} onChange={(value) => void updateNodeAttributes(node.id, { trigger: value } as any)} /> : null}
          {'purpose' in node ? <TextField label={t('panel.purpose')} value={(node.purpose as string) || ''} onChange={(value) => void updateNodeAttributes(node.id, { purpose: value } as any)} /> : null}
          {'route' in node ? <TextField label={t('panel.route')} value={(node.route as string) || ''} onChange={(value) => void updateNodeAttributes(node.id, { route: value } as any)} /> : null}
          {'componentType' in node ? <TextField label={t('panel.componentType')} value={(node.componentType as string) || ''} onChange={(value) => void updateNodeAttributes(node.id, { componentType: value } as any)} /> : null}
          {'stepType' in node ? <TextField label={t('panel.stepType')} value={(node.stepType as string) || ''} onChange={(value) => void updateNodeAttributes(node.id, { stepType: value } as any)} /> : null}
        </Section>
      ) : null}

      <Section title={t('panel.dependencies')}>
        <LinkList ir={ir} nodeId={node.id} />
      </Section>
    </PanelShell>
  );
}
