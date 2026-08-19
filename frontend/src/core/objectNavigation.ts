import { RequirementSpace } from '@/core/schema';

/**
 * Diff 条目 → 建模对象跳转（Phase G）。
 *
 * Diff 条目携带 entity_type + entity_uuid（后端 logical_uuid）。通过 logicalUuid 在前端 IR
 * 中定位对应对象，再导航到 What/Flow/Scope 建模页并用 setSelectedObject 高亮。
 */

export type ModelingPage = '/what' | '/flow' | '/scope';

/** entity_type → 建模页映射。project_metadata 无建模对象，返回 null（不显示跳转）。 */
export function jumpTargetForEntity(entityType: string): ModelingPage | null {
  switch (entityType) {
    case 'actor':
    case 'feature':
    case 'feature_relation':
    case 'scenario':
    case 'acceptance_criterion':
      return '/what';
    case 'flow':
    case 'flow_step':
    case 'business_object':
    case 'business_object_attribute':
      return '/flow';
    case 'scope':
      return '/scope';
    default:
      return null;
  }
}

/**
 * 在 IR 中按 logicalUuid 查找实体（含嵌套场景验收标准、业务对象属性、流程步骤）。
 * 依赖后端 project_detail 增量补的 logicalUuid 字段；未命中返回 null（仅跳页不选中）。
 */
export function findIrNodeByUuid(ir: RequirementSpace | null, entityType: string, uuid: string): any | null {
  if (!ir) return null;

  switch (entityType) {
    case 'actor':
      return (ir.actors || []).find((a) => a?.logicalUuid === uuid) || null;
    case 'feature':
      return (ir.features || []).find((f) => f?.logicalUuid === uuid) || null;
    case 'feature_relation':
      for (const f of ir.features || []) {
        if (f?.logicalUuid === uuid) return f;
      }
      return null;
    case 'scenario':
      return (ir.features || []).flatMap((f) => f?.scenarios || [])
        .find((s) => s?.logicalUuid === uuid) || null;
    case 'acceptance_criterion':
      for (const f of ir.features || []) {
        for (const s of f?.scenarios || []) {
          const found = (s?.acceptanceCriteria || []).find((ac) => ac?.logicalUuid === uuid);
          if (found) return found;
        }
      }
      return null;
    case 'business_object':
      return (ir.businessObjects || []).find((bo) => bo?.logicalUuid === uuid) || null;
    case 'business_object_attribute':
      for (const bo of ir.businessObjects || []) {
        const found = (bo?.businessObjectAttributes || []).find((attr) => attr?.logicalUuid === uuid);
        if (found) return found;
      }
      return null;
    case 'flow':
      return (ir.flows || []).find((f) => f?.logicalUuid === uuid) || null;
    case 'flow_step':
      for (const f of ir.flows || []) {
        const found = (f?.flowSteps || []).find((s) => s?.logicalUuid === uuid);
        if (found) return found;
      }
      return null;
    case 'scope':
      for (const f of ir.features || []) {
        if (f?.scope?.logicalUuid === uuid) return f.scope;
      }
      return null;
    default:
      return null;
  }
}
