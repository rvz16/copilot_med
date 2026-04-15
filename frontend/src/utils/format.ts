export function formatDateTime(value: string | null | undefined): string {
  if (!value) return '—';

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '—';

  return new Intl.DateTimeFormat('ru-RU', {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(date);
}

export function formatDurationMs(value: number | null | undefined): string {
  if (typeof value !== 'number' || Number.isNaN(value)) return '—';
  if (value < 1000) return `${Math.round(value)} ms`;

  const seconds = value / 1000;
  return `${seconds.toFixed(seconds >= 10 ? 0 : 1)} s`;
}

export function formatStatusLabel(status: string): string {
  switch (status) {
    case 'idle':
      return 'ожидание';
    case 'created':
      return 'подготовка';
    case 'active':
      return 'активна';
    case 'analyzing':
      return 'идёт разбор';
    case 'finished':
      return 'завершена';
    case 'closed':
      return 'завершена';
    case 'recording':
      return 'идёт запись';
    case 'stopped':
      return 'остановлена';
    case 'pending':
      return 'ожидает';
    case 'processing':
      return 'глубокий разбор';
    case 'completed':
      return 'готово';
    case 'failed':
      return 'ошибка';
    default:
      return status;
  }
}
