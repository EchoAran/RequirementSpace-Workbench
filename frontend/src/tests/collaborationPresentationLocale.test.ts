import { afterEach, describe, expect, it } from 'vitest';
import i18n from '../i18n';
import {
  getCollaborationTaskDescription,
  getCollaborationTaskTitle,
  getNotificationPresentation,
} from '../core/collaborationPresentation';
import { getStageNextActionLabel } from '../core/stageProgressText';

describe('collaboration locale presentation', () => {
  afterEach(async () => {
    await i18n.changeLanguage('zh-CN');
  });

  it('localizes stored system task titles while preserving user titles', async () => {
    await i18n.changeLanguage('en-US');

    expect(getCollaborationTaskTitle({
      title: 'collaboration.taskTitles.singleConfirmation',
      targetType: 'actor',
      nodeName: 'Product Owner',
    }, i18n.t)).toBe('Confirm Actor: Product Owner');
    expect(getCollaborationTaskTitle({
      title: 'collaboration.taskTitles.batchConfirmation',
      targets: [{}, {}],
    }, i18n.t)).toBe('Batch Confirmation Task (2 items)');
    expect(getCollaborationTaskTitle({ title: 'Review checkout scope' }, i18n.t)).toBe('Review checkout scope');
  });

  it('localizes system task descriptions and coded notifications', async () => {
    await i18n.changeLanguage('en-US');

    expect(getCollaborationTaskDescription({
      description: 'collaboration.taskDescriptions.resolveConflict',
    }, i18n.t)).toContain('project context changed');
    expect(getNotificationPresentation({
      title: 'collaboration.notifications.batchTaskAssigned.title',
      body: 'collaboration.notifications.batchTaskAssigned.body',
    }, i18n.t)).toEqual({
      title: 'New Batch Confirmation Assignment',
      body: 'A new batch confirmation task was assigned to you.',
    });
    expect(getNotificationPresentation({
      title: 'collaboration.notifications.batchTaskRejected.title',
      body: 'collaboration.notifications.batchTaskRejected.body',
    }, i18n.t)).toEqual({
      title: 'Batch Confirmation Task Rejected',
      body: 'A batch confirmation task you assigned was rejected.',
    });
  });

  it('maps the backend stage_transition kind to the locale resource', async () => {
    await i18n.changeLanguage('en-US');
    expect(getStageNextActionLabel({
      kind: 'stage_transition',
      label: '申请进入下一阶段',
    }, i18n.t)).toBe('Request Next Stage');
  });
});
