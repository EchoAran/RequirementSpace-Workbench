import React from 'react';
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { DiffEntityDetail, StructuredEntityCard, ScopeStatusBadge, KanoBadge } from '../components/version-control/DiffEntityDetail';
import { DiffEntry } from '../core/versionControl';

describe('DiffEntityDetail & Domain Entity Card Rendering', () => {
  it('ScopeStatusBadge renders correct status styling and label', () => {
    const { rerender } = render(<ScopeStatusBadge status="in_scope" />);
    expect(screen.getByText(/本期|纳入|In Scope/i)).toBeTruthy();

    rerender(<ScopeStatusBadge status="out_of_scope" />);
    expect(screen.getByText(/范围外|不纳入|排除|Out of Scope/i)).toBeTruthy();

    rerender(<ScopeStatusBadge status="deferred" />);
    expect(screen.getByText(/暂缓|待定|后延|Deferred/i)).toBeTruthy();
  });

  it('KanoBadge renders category text', () => {
    render(<KanoBadge category="Must-be" />);
    expect(screen.getByText(/Kano: Must-be/)).toBeTruthy();
  });

  it('StructuredEntityCard renders Business Object with attributes table', () => {
    const boData = {
      name: '支付交易单',
      description: '记录单笔在线支付的核心交易凭证',
      attributes: [
        { name: 'order_no', data_type: 'String', description: '订单号', example: 'ORD-20260822-001' },
        { name: 'amount', data_type: 'Decimal', description: '支付金额', example: '99.90' },
      ],
    };

    render(<StructuredEntityCard entityType="business_object" data={boData} />);

    expect(screen.getByText('支付交易单')).toBeTruthy();
    expect(screen.getByText('记录单笔在线支付的核心交易凭证')).toBeTruthy();
    expect(screen.getByText('order_no')).toBeTruthy();
    expect(screen.getByText('ORD-20260822-001')).toBeTruthy();
    expect(screen.getByText('amount')).toBeTruthy();
    expect(screen.getByText('99.90')).toBeTruthy();
  });

  it('StructuredEntityCard renders Scenario with AC list', () => {
    const scenarioData = {
      name: '买家扫码快捷支付',
      content: '买家打开 APP 扫描商户收款码完成付款',
      feature_name: '扫码支付',
      actor_name: '买家用户',
      acceptance_criteria: [
        '准则 1：余额充足时扣款成功并出具收据',
        '准则 2：余额不足时提示切换付款方式',
      ],
    };

    render(<StructuredEntityCard entityType="scenario" data={scenarioData} />);

    expect(screen.getByText('买家扫码快捷支付')).toBeTruthy();
    expect(screen.getByText('买家打开 APP 扫描商户收款码完成付款')).toBeTruthy();
    expect(screen.getByText('扫码支付')).toBeTruthy();
    expect(screen.getByText('买家用户')).toBeTruthy();
    expect(screen.getByText(/准则 1：余额充足时扣款成功/)).toBeTruthy();
    expect(screen.getByText(/准则 2：余额不足时提示切换/)).toBeTruthy();
  });

  it('StructuredEntityCard renders Scope with rationale and decision reason', () => {
    const scopeData = {
      status: 'in_scope',
      kano_category: 'Must-be',
      positive_summary: '核心交易闭环，一期必须支持',
      negative_summary: '排除将导致用户无法付款',
      reason: '高频核心路径',
    };

    render(<StructuredEntityCard entityType="scope" data={scopeData} />);

    expect(screen.getByText('核心交易闭环，一期必须支持')).toBeTruthy();
    expect(screen.getByText('排除将导致用户无法付款')).toBeTruthy();
    expect(screen.getByText('高频核心路径')).toBeTruthy();
  });

  it('DiffEntityDetail renders field_changed with friendly label and Before/After cards', () => {
    const entry: DiffEntry = {
      change_type: 'field_changed',
      entity_type: 'feature',
      entity_uuid: 'feat-100',
      entity_name: '人脸识别支付',
      field: 'description',
      before: '旧版说明：仅支持线下刷脸',
      after: '新版说明：支持线上与线下多渠道刷脸支付',
      path: 'features[0].description',
      text_blocks: [],
    };

    render(<DiffEntityDetail entry={entry} />);

    expect(screen.getByText('人脸识别支付')).toBeTruthy();
    expect(screen.getByText(/描述说明/)).toBeTruthy();
    expect(screen.getByText('旧版说明：仅支持线下刷脸')).toBeTruthy();
    expect(screen.getByText('新版说明：支持线上与线下多渠道刷脸支付')).toBeTruthy();
  });

  it('DiffEntityDetail renders entity_added with full structured card', () => {
    const entry: DiffEntry = {
      change_type: 'entity_added',
      entity_type: 'actor',
      entity_uuid: 'actor-200',
      entity_name: '清算结算员',
      after: {
        id: 999, // System key that should be filtered from main card
        project_id: 1,
        logical_uuid: 'actor-200-uuid',
        name: '清算结算员',
        description: '负责平台每日日终账单汇总与分账结算操作',
      },
      path: 'actors[0]',
      text_blocks: [],
    };

    render(<DiffEntityDetail entry={entry} />);

    expect(screen.getAllByText('清算结算员').length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText('负责平台每日日终账单汇总与分账结算操作')).toBeTruthy();
  });

  it('DiffEntityDetail renders relation_added and ordered_item_moved', () => {
    const relationEntry: DiffEntry = {
      change_type: 'relation_added',
      entity_type: 'feature',
      entity_uuid: 'feat-1',
      entity_name: '支付网关',
      relation_type: 'parent_of',
      related_entity_name: '银联快捷支付',
      path: 'relations[0]',
      text_blocks: [],
    };

    const { rerender } = render(<DiffEntityDetail entry={relationEntry} />);
    expect(screen.getAllByText('支付网关').length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText('银联快捷支付')).toBeTruthy();

    const moveEntry: DiffEntry = {
      change_type: 'ordered_item_moved',
      entity_type: 'flow_step',
      entity_uuid: 'step-1',
      entity_name: '风控反洗钱审查',
      before_position: 1,
      after_position: 3,
      path: 'steps[0].position',
      text_blocks: [],
    };

    rerender(<DiffEntityDetail entry={moveEntry} />);
    expect(screen.getByText('风控反洗钱审查')).toBeTruthy();
    expect(screen.getByText(/第 #1 位/)).toBeTruthy();
    expect(screen.getByText(/第 #3 位/)).toBeTruthy();
  });
});
