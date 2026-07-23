import type { TFunction } from 'i18next';

const SINGLE_TASK_TITLE_KEY = 'collaboration.taskTitles.singleConfirmation';
const BATCH_TASK_TITLE_KEY = 'collaboration.taskTitles.batchConfirmation';
const CONFLICT_TASK_TITLE_KEY = 'collaboration.taskTitles.resolveConflict';
const CONFLICT_TASK_DESCRIPTION_KEY = 'collaboration.taskDescriptions.resolveConflict';

function taskTargetName(task: any): string {
  return task?.nodeName
    || task?.contentSnapshot?.name
    || task?.contentSnapshot?.content
    || task?.targetId
    || task?.target_id
    || '';
}

function taskTargetType(task: any, t: TFunction): string {
  const kind = task?.targetType || task?.target_type;
  if (!kind) return t('nodeKind.unknown');
  const key = `confirmationWorkspace.nodeKindLabels.${kind}`;
  const translated = t(key);
  return translated === key ? kind : translated;
}

export function getCollaborationTaskTitle(task: any, t: TFunction): string {
  const title = String(task?.title || '');
  const batchCount = Array.isArray(task?.targets) ? task.targets.length : undefined;

  if (title === SINGLE_TASK_TITLE_KEY || /^请确认\s+[^:]+:\s*/.test(title)) {
    const legacyName = title.match(/^请确认\s+[^:]+:\s*(.+)$/)?.[1];
    return t(SINGLE_TASK_TITLE_KEY, {
      type: taskTargetType(task, t),
      name: taskTargetName(task) || legacyName,
    });
  }

  if (title === BATCH_TASK_TITLE_KEY || /^批量确认任务\s*[（(]\s*\d+\s*项\s*[）)]$/.test(title)) {
    const legacyCount = Number(title.match(/\d+/)?.[0]);
    return t(BATCH_TASK_TITLE_KEY, { count: batchCount ?? (legacyCount || 0) });
  }

  if (title === CONFLICT_TASK_TITLE_KEY || /^解决\s+.+\s+的 AI 写入冲突$/.test(title)) {
    return t(CONFLICT_TASK_TITLE_KEY);
  }

  return title;
}

export function getCollaborationTaskDescription(task: any, t: TFunction): string {
  const description = String(task?.description || '');
  if (
    description === CONFLICT_TASK_DESCRIPTION_KEY
    || description === '在 AI 生成建议后，项目相关上下文发生了变化，请手动处理冲突。'
  ) {
    return t(CONFLICT_TASK_DESCRIPTION_KEY);
  }
  return description;
}

const LEGACY_NOTIFICATION_KEYS: Record<string, { title: string; body: string }> = {
  '收到新的确认任务指派': {
    title: 'collaboration.notifications.singleTaskAssigned.title',
    body: 'collaboration.notifications.singleTaskAssigned.body',
  },
  '收到新的批量确认指派': {
    title: 'collaboration.notifications.batchTaskAssigned.title',
    body: 'collaboration.notifications.batchTaskAssigned.body',
  },
  '确认指派任务已失效': {
    title: 'collaboration.notifications.singleTaskSuperseded.title',
    body: 'collaboration.notifications.singleTaskSuperseded.body',
  },
  '批量确认指派已失效': {
    title: 'collaboration.notifications.batchTaskSuperseded.title',
    body: 'collaboration.notifications.batchTaskSuperseded.body',
  },
  '检测到 AI 写入冲突': {
    title: 'collaboration.notifications.conflictDetected.title',
    body: 'collaboration.notifications.conflictDetected.body',
  },
};

function decidedNotificationKeys(notification: any): { title: string; body: string } | undefined {
  const title = String(notification?.title || '');
  const body = String(notification?.body || '');
  const result = body.includes('已驳回') || body.includes('已丢弃') ? 'rejected' : 'approved';
  if (title === '批量确认任务已被处理') {
    return {
      title: `collaboration.notifications.batchTask${result === 'approved' ? 'Approved' : 'Rejected'}.title`,
      body: `collaboration.notifications.batchTask${result === 'approved' ? 'Approved' : 'Rejected'}.body`,
    };
  }
  if (title === '确认任务已被处理') {
    return {
      title: `collaboration.notifications.singleTask${result === 'approved' ? 'Approved' : 'Rejected'}.title`,
      body: `collaboration.notifications.singleTask${result === 'approved' ? 'Approved' : 'Rejected'}.body`,
    };
  }
  if (title === '冲突/草稿任务已被处理') {
    return {
      title: `collaboration.notifications.conflictTask${result === 'approved' ? 'Approved' : 'Rejected'}.title`,
      body: `collaboration.notifications.conflictTask${result === 'approved' ? 'Approved' : 'Rejected'}.body`,
    };
  }
  return undefined;
}

function translateStoredKey(value: string, t: TFunction): string {
  if (!value.startsWith('collaboration.notifications.')) return value;
  const translated = t(value);
  return translated === value ? value : translated;
}

export function getNotificationPresentation(
  notification: any,
  t: TFunction,
): { title: string; body: string } {
  const storedTitle = String(notification?.title || '');
  const storedBody = String(notification?.body || '');
  const keys = LEGACY_NOTIFICATION_KEYS[storedTitle] || decidedNotificationKeys(notification);

  if (keys) {
    return { title: t(keys.title), body: t(keys.body) };
  }

  return {
    title: translateStoredKey(storedTitle, t),
    body: translateStoredKey(storedBody, t),
  };
}
