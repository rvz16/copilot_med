import type { UiLanguage } from '../i18n';

export function formatDateTime(value: string | null | undefined, language: UiLanguage = 'ru'): string {
  if (!value) return '—';

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '—';

  return new Intl.DateTimeFormat(language === 'en' ? 'en-US' : 'ru-RU', {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(date);
}

export function formatDurationMs(value: number | null | undefined, language: UiLanguage = 'ru'): string {
  if (typeof value !== 'number' || Number.isNaN(value)) return '—';
  if (value < 1000) return `${Math.round(value)} ms`;

  const seconds = value / 1000;
  return `${seconds.toFixed(seconds >= 10 ? 0 : 1)} ${language === 'en' ? 's' : 'с'}`;
}

export function formatStatusLabel(status: string, language: UiLanguage = 'ru'): string {
  const labels =
    language === 'en'
      ? {
          idle: 'idle',
          created: 'preparing',
          active: 'active',
          analyzing: 'analyzing',
          finished: 'finished',
          closed: 'finished',
          recording: 'recording',
          stopped: 'stopped',
          pending: 'pending',
          processing: 'deep analysis',
          completed: 'ready',
          failed: 'error',
        }
      : {
          idle: 'ожидание',
          created: 'подготовка',
          active: 'активна',
          analyzing: 'идёт разбор',
          finished: 'завершена',
          closed: 'завершена',
          recording: 'идёт запись',
          stopped: 'остановлена',
          pending: 'ожидает',
          processing: 'глубокий разбор',
          completed: 'готово',
          failed: 'ошибка',
        };

  switch (status) {
    case 'idle':
      return labels.idle;
    case 'created':
      return labels.created;
    case 'active':
      return labels.active;
    case 'analyzing':
      return labels.analyzing;
    case 'finished':
      return labels.finished;
    case 'closed':
      return labels.closed;
    case 'recording':
      return labels.recording;
    case 'stopped':
      return labels.stopped;
    case 'pending':
      return labels.pending;
    case 'processing':
      return labels.processing;
    case 'completed':
      return labels.completed;
    case 'failed':
      return labels.failed;
    default:
      return status;
  }
}
