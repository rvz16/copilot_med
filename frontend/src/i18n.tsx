import { createContext, useContext } from 'react';
import type { ReactNode } from 'react';

export type UiLanguage = 'ru' | 'en';

interface I18nContextValue {
  language: UiLanguage;
  setLanguage: (language: UiLanguage) => void;
}

const I18nContext = createContext<I18nContextValue | null>(null);

interface I18nProviderProps extends I18nContextValue {
  children: ReactNode;
}

export function I18nProvider({ children, language, setLanguage }: I18nProviderProps) {
  return (
    <I18nContext.Provider value={{ language, setLanguage }}>
      {children}
    </I18nContext.Provider>
  );
}

export function useUiLanguage() {
  const context = useContext(I18nContext);
  if (!context) {
    throw new Error('useUiLanguage must be used inside I18nProvider');
  }
  return context;
}
