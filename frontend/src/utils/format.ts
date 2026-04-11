export function formatDateTime(value: string | null | undefined): string {
  if (!value) return '—';

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '—';

  return new Intl.DateTimeFormat('ru-RU', {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(date);
}

export function formatStatusLabel(status: string): string {
  switch (status) {
    case 'idle':
      return 'ожидание';
    case 'created':
      return 'подготовка';
    case 'active':
      return 'активна';
    case 'closed':
      return 'завершена';
    case 'recording':
      return 'идёт запись';
    case 'stopped':
      return 'остановлена';
    case 'pending':
      return 'ожидает';
    case 'processing':
      return 'обработка';
    case 'completed':
      return 'готово';
    case 'failed':
      return 'ошибка';
    default:
      return status;
  }
}
