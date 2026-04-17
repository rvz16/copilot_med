import type { UiLanguage } from '../i18n';

export interface DoctorAccount {
  id: string;
  username: string;
  password: string;
  name: string;
  name_en: string;
  specialty: string;
  tagline: string;
  specialty_en: string;
  tagline_en: string;
}

export const SAMPLE_DOCTORS: DoctorAccount[] = [
  {
    id: 'doc_amelia_carter',
    username: 'amelia.carter',
    password: 'medc2026',
    name: 'Доктор Amelia Carter',
    name_en: 'Dr. Amelia Carter',
    specialty: 'Семейная медицина',
    tagline: 'Первичный приём и непрерывное наблюдение пациентов',
    specialty_en: 'Family medicine',
    tagline_en: 'Primary care intake and longitudinal patient follow-up',
  },
  {
    id: 'doc_michael_reyes',
    username: 'michael.reyes',
    password: 'clinic2026',
    name: 'Доктор Michael Reyes',
    name_en: 'Dr. Michael Reyes',
    specialty: 'Терапия',
    tagline: 'Ведение взрослых пациентов, диагностика и контроль лечения',
    specialty_en: 'Internal medicine',
    tagline_en: 'Adult patient care, diagnostics, and treatment follow-up',
  },
  {
    id: 'doc_sofia_petrova',
    username: 'sofia.petrova',
    password: 'steth2026',
    name: 'Доктор Sofia Petrova',
    name_en: 'Dr. Sofia Petrova',
    specialty: 'Неврология',
    tagline: 'Головная боль, головокружение и когнитивные жалобы',
    specialty_en: 'Neurology',
    tagline_en: 'Headache, dizziness, and cognitive complaint workups',
  },
];

export function authenticateDoctor(username: string, password: string): DoctorAccount | null {
  const normalizedUsername = username.trim().toLowerCase();
  const normalizedPassword = password.trim();

  return (
    SAMPLE_DOCTORS.find(
      (doctor) =>
        doctor.username.toLowerCase() === normalizedUsername &&
        doctor.password === normalizedPassword,
    ) ?? null
  );
}

export function findDoctorById(id: string | null): DoctorAccount | null {
  if (!id) return null;
  return SAMPLE_DOCTORS.find((doctor) => doctor.id === id) ?? null;
}

export function getDoctorSpecialty(doctor: DoctorAccount, language: UiLanguage): string {
  return language === 'en' ? doctor.specialty_en : doctor.specialty;
}

export function getDoctorTagline(doctor: DoctorAccount, language: UiLanguage): string {
  return language === 'en' ? doctor.tagline_en : doctor.tagline;
}

export function getDoctorDisplayName(doctor: DoctorAccount, language: UiLanguage): string {
  return language === 'en' ? doctor.name_en : doctor.name;
}
