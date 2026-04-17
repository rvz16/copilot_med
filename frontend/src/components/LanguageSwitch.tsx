import { useUiLanguage, type UiLanguage } from '../i18n';

const LABELS: Record<UiLanguage, { title: string; current: string }> = {
  ru: {
    title: 'Язык интерфейса',
    current: 'Текущий язык',
  },
  en: {
    title: 'Interface language',
    current: 'Current language',
  },
};

const OPTIONS: Array<{ value: UiLanguage; label: string }> = [
  { value: 'ru', label: 'RU' },
  { value: 'en', label: 'EN' },
];

export function LanguageSwitch() {
  const { language, setLanguage } = useUiLanguage();
  const copy = LABELS[language];

  return (
    <div className="language-switch" role="group" aria-label={copy.title}>
      {OPTIONS.map((option) => (
        <button
          key={option.value}
          type="button"
          className={`language-switch-button ${language === option.value ? 'is-active' : ''}`}
          onClick={() => setLanguage(option.value)}
          aria-pressed={language === option.value}
          title={`${copy.current}: ${option.label}`}
        >
          {option.label}
        </button>
      ))}
    </div>
  );
}
