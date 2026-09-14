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
    || '';
}

function taskTargetType(task: any, t: TFunction): string {
  const kind = task?.targetType;
  if (!kind) return t('nodeKind.unknown');
  const key = `confirmationWorkspace.nodeKindLabels.${kind}`;
  const translated = t(key);
  return translated === key ? kind : translated;
}

export function getCollaborationTaskTitle(task: any, t: TFunction): string {
  const title = String(task?.title || '');
  const batchCount = Array.isArray(task?.targets) ? task.targets.length : undefined;

  if (title === SINGLE_TASK_TITLE_KEY) {
    return t(SINGLE_TASK_TITLE_KEY, {
      type: taskTargetType(task, t),
      name: taskTargetName(task),
    });
  }

  if (title === BATCH_TASK_TITLE_KEY) {
    return t(BATCH_TASK_TITLE_KEY, { count: batchCount ?? 0 });
  }

  if (title === CONFLICT_TASK_TITLE_KEY) {
    return t(CONFLICT_TASK_TITLE_KEY);
  }

  return title;
}

export function getCollaborationTaskDescription(task: any, t: TFunction): string {
  const description = String(task?.description || '');
  if (
    description === CONFLICT_TASK_DESCRIPTION_KEY
  ) {
    return t(CONFLICT_TASK_DESCRIPTION_KEY);
  }
  return description;
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
  return {
    title: translateStoredKey(storedTitle, t),
    body: translateStoredKey(storedBody, t),
  };
}
