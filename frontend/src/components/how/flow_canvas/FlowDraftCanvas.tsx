import { useId } from 'react';
import { useTranslation } from 'react-i18next';
import { Database, User } from 'lucide-react';

interface FlowDraftCanvasProps {
  flow: any;
  className?: string;
}

interface DraftStep {
  id: string;
  name: string;
  description: string;
  type: string;
  actors: string[];
  inputs: string[];
  outputs: string[];
  refs: string[];
}

interface DraftTransition {
  id: string;
  sourceId: string;
  targetId: string;
  label: string;
  condition: string;
}

const NODE_WIDTH = 248;
const NODE_HEIGHT = 144;
const COLUMN_WIDTH = 328;
const ROW_HEIGHT = 184;

function asArray(value: any): any[] {
  return Array.isArray(value) ? value : [];
}

function firstValue(item: any, keys: string[]) {
  for (const key of keys) {
    const value = item?.[key];
    if (value !== undefined && value !== null && value !== '') return value;
  }
  return undefined;
}

function normalizeRef(value: unknown) {
  return value === undefined || value === null ? '' : String(value).trim();
}

function normalizeFlow(flow: any) {
  const rawSteps = asArray(flow?.flow_steps ?? flow?.flowSteps ?? flow?.steps);
  const steps: DraftStep[] = rawSteps.map((step, index) => {
    const refs = [
      firstValue(step, ['step_number', 'stepNumber']),
      firstValue(step, ['step_name', 'stepName', 'name']),
      firstValue(step, ['step_ref', 'stepRef']),
      firstValue(step, ['step_id', 'stepId', 'id']),
    ].map(normalizeRef).filter(Boolean);

    return {
      id: `step-${index}`,
      name: String(firstValue(step, ['step_name', 'stepName', 'name']) ?? ''),
      description: String(firstValue(step, ['step_description', 'stepDescription', 'description']) ?? ''),
      type: String(firstValue(step, ['step_type', 'stepType']) ?? 'actorAction'),
      actors: asArray(firstValue(step, ['actor_names', 'actorNames'])).map(String),
      inputs: asArray(firstValue(step, ['input_business_object_names', 'inputBusinessObjectNames'])).map(String),
      outputs: asArray(firstValue(step, ['output_business_object_names', 'outputBusinessObjectNames'])).map(String),
      refs,
    };
  });

  const stepIdByRef = new Map<string, string>();
  steps.forEach((step) => step.refs.forEach((ref) => stepIdByRef.set(ref, step.id)));

  const rawTransitions = asArray(flow?.flow_transitions ?? flow?.flowTransitions ?? flow?.transitions);
  const transitions: DraftTransition[] = rawTransitions.flatMap((transition, index) => {
    const sourceRef = normalizeRef(firstValue(transition, [
      'source_step_number', 'sourceStepNumber', 'source_step_name', 'sourceStepName',
      'source_step_ref', 'sourceStepRef', 'source_step_id', 'sourceStepId',
    ]));
    const targetRef = normalizeRef(firstValue(transition, [
      'target_step_number', 'targetStepNumber', 'target_step_name', 'targetStepName',
      'target_step_ref', 'targetStepRef', 'target_step_id', 'targetStepId',
    ]));
    const sourceId = stepIdByRef.get(sourceRef);
    const targetId = stepIdByRef.get(targetRef);
    if (!sourceId || !targetId) return [];

    return [{
      id: `transition-${index}`,
      sourceId,
      targetId,
      label: String(firstValue(transition, ['label']) ?? ''),
      condition: String(firstValue(transition, ['condition_text', 'conditionText']) ?? ''),
    }];
  });

  return { steps, transitions };
}

function computePositions(steps: DraftStep[], transitions: DraftTransition[]) {
  const positions: Record<string, { x: number; y: number }> = {};
  if (steps.length === 0) return positions;

  const targetIds = new Set(transitions.map((transition) => transition.targetId));
  const startSteps = steps.filter((step) => !targetIds.has(step.id));
  const queue = (startSteps.length > 0 ? startSteps : [steps[0]]).map((step) => ({ id: step.id, column: 0 }));
  const visited = new Set<string>();
  const columnOccupancy: Record<number, number> = {};

  while (queue.length > 0) {
    const current = queue.shift()!;
    if (visited.has(current.id)) continue;
    visited.add(current.id);

    const row = columnOccupancy[current.column] ?? 0;
    columnOccupancy[current.column] = row + 1;
    positions[current.id] = {
      x: 32 + current.column * COLUMN_WIDTH,
      y: 32 + row * ROW_HEIGHT,
    };

    transitions
      .filter((transition) => transition.sourceId === current.id)
      .forEach((transition) => queue.push({ id: transition.targetId, column: current.column + 1 }));
  }

  steps.filter((step) => !visited.has(step.id)).forEach((step) => {
    let column = 0;
    while ((columnOccupancy[column] ?? 0) >= 3) column += 1;
    const row = columnOccupancy[column] ?? 0;
    columnOccupancy[column] = row + 1;
    positions[step.id] = { x: 32 + column * COLUMN_WIDTH, y: 32 + row * ROW_HEIGHT };
  });

  return positions;
}

function transitionPath(source: { x: number; y: number }, target: { x: number; y: number }) {
  const startX = source.x + NODE_WIDTH;
  const startY = source.y + NODE_HEIGHT / 2;
  const endX = target.x;
  const endY = target.y + NODE_HEIGHT / 2;

  if (endX <= startX) {
    const controlY = Math.min(startY, endY) - Math.max(72, Math.abs(startX - endX) * 0.2);
    const middleX = (startX + endX) / 2;
    return `M ${startX} ${startY} C ${startX + 72} ${startY}, ${startX + 36} ${controlY}, ${middleX} ${controlY} S ${endX - 72} ${endY}, ${endX} ${endY}`;
  }

  const controlOffset = Math.min(76, (endX - startX) / 2);
  return `M ${startX} ${startY} C ${startX + controlOffset} ${startY}, ${endX - controlOffset} ${endY}, ${endX} ${endY}`;
}

export function FlowDraftCanvas({ flow, className = '' }: FlowDraftCanvasProps) {
  const { t } = useTranslation();
  const markerId = `draft-arrow-${useId().replace(/:/g, '')}`;
  const { steps, transitions } = normalizeFlow(flow);

  if (steps.length === 0) {
    return (
      <div className={`rounded-xl border border-dashed border-slate-200 bg-slate-50 p-6 text-center text-xs text-slate-500 ${className}`}>
        {t('draftPreview.emptyDraft')}
      </div>
    );
  }

  const positions = computePositions(steps, transitions);
  const canvasWidth = Math.max(720, ...Object.values(positions).map((position) => position.x + NODE_WIDTH + 32));
  const canvasHeight = Math.max(280, ...Object.values(positions).map((position) => position.y + NODE_HEIGHT + 32));

  return (
    <div
      className={`max-h-[520px] overflow-auto rounded-xl border border-slate-200 bg-slate-50 ${className}`}
      data-testid="flow-draft-canvas"
      aria-label={t('draftPreview.flowsTitle')}
    >
      <div
        className="relative min-w-full bg-[radial-gradient(#dbe3ee_1.25px,transparent_1.25px)] [background-size:22px_22px]"
        style={{ width: canvasWidth, height: canvasHeight }}
      >
        <svg className="absolute inset-0" width={canvasWidth} height={canvasHeight} aria-hidden="true">
          <defs>
            <marker id={markerId} markerWidth="8" markerHeight="6" refX="6" refY="3" orient="auto">
              <polygon points="0 0, 8 3, 0 6" fill="#6366f1" />
            </marker>
          </defs>
          {transitions.map((transition) => {
            const source = positions[transition.sourceId];
            const target = positions[transition.targetId];
            return (
              <path
                key={transition.id}
                d={transitionPath(source, target)}
                fill="none"
                stroke="#818cf8"
                strokeWidth="2"
                markerEnd={`url(#${markerId})`}
                data-testid="flow-draft-edge"
              />
            );
          })}
        </svg>

        {transitions.map((transition) => {
          const source = positions[transition.sourceId];
          const target = positions[transition.targetId];
          const text = [transition.label, transition.condition].filter(Boolean).join(' · ');
          if (!text) return null;
          return (
            <span
              key={`${transition.id}-label`}
              className="absolute z-10 max-w-48 -translate-x-1/2 -translate-y-1/2 truncate rounded-full border border-indigo-200 bg-white px-2 py-0.5 text-[10px] font-semibold text-indigo-700 shadow-sm"
              style={{
                left: (source.x + NODE_WIDTH + target.x) / 2,
                top: (source.y + target.y) / 2 + NODE_HEIGHT / 2,
              }}
              title={text}
            >
              {text}
            </span>
          );
        })}

        {steps.map((step, index) => {
          const position = positions[step.id];
          const isJudgment = step.type === 'judgment';
          const isSystem = step.type === 'systemAction';
          const typeLabel = isJudgment
            ? t('how.stepType.judgment')
            : isSystem
              ? t('how.stepType.systemAction')
              : t('how.stepType.actorAction');
          const accentClass = isJudgment
            ? 'border-slate-200 border-l-4 border-l-amber-400'
            : isSystem
              ? 'border-slate-200 border-l-4 border-l-sky-400'
              : 'border-slate-200 border-l-4 border-l-indigo-500';
          const badgeClass = isJudgment
            ? 'border-amber-200 bg-amber-50 text-amber-800'
            : isSystem
              ? 'border-sky-200 bg-sky-50 text-sky-800'
              : 'border-indigo-200 bg-indigo-50 text-indigo-800';

          return (
            <article
              key={step.id}
              className={`absolute z-20 flex overflow-hidden rounded-xl border bg-white p-3 shadow-sm ${accentClass}`}
              style={{ left: position.x, top: position.y, width: NODE_WIDTH, height: NODE_HEIGHT }}
            >
              <div className="min-w-0 flex-1">
                <div className="flex items-center justify-between gap-2">
                  <span className="text-[10px] font-bold font-mono text-slate-300">
                    {t('draftPreview.flowStepNum', { num: String(index + 1).padStart(3, '0') })}
                  </span>
                  <span className={`shrink-0 rounded-md border px-1.5 py-0.5 text-[10px] font-bold ${badgeClass}`}>
                    {typeLabel}
                  </span>
                </div>
                <h6 className="mt-2 truncate text-xs font-extrabold text-slate-900" title={step.name}>{step.name}</h6>
                {step.description && (
                  <p className="mt-1 line-clamp-2 text-[10px] leading-relaxed text-slate-500">{step.description}</p>
                )}
                <div className="mt-2 space-y-1 text-[10px] text-slate-600">
                  {step.actors.length > 0 && (
                    <div className="flex items-center gap-1 truncate" title={step.actors.join(', ')}>
                      <User className="h-3 w-3 shrink-0 text-slate-400" />
                      <span className="truncate">{step.actors.join(', ')}</span>
                    </div>
                  )}
                  {(step.inputs.length > 0 || step.outputs.length > 0) && (
                    <div className="flex items-center gap-1 truncate" title={[...step.inputs, ...step.outputs].join(', ')}>
                      <Database className="h-3 w-3 shrink-0 text-slate-400" />
                      <span className="truncate">
                        {step.inputs.length > 0 ? `${t('draftPreview.flowStepInput')}: ${step.inputs.join(', ')}` : ''}
                        {step.inputs.length > 0 && step.outputs.length > 0 ? ' · ' : ''}
                        {step.outputs.length > 0 ? `${t('draftPreview.flowStepOutput')}: ${step.outputs.join(', ')}` : ''}
                      </span>
                    </div>
                  )}
                </div>
              </div>
            </article>
          );
        })}
      </div>
    </div>
  );
}
