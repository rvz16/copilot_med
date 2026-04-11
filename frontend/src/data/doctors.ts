export interface DoctorAccount {
  id: string;
  username: string;
  password: string;
  name: string;
  specialty: string;
  tagline: string;
}

export const SAMPLE_DOCTORS: DoctorAccount[] = [
  {
    id: 'doc_amelia_carter',
    username: 'amelia.carter',
    password: 'medc2026',
    name: 'Доктор Amelia Carter',
    specialty: 'Семейная медицина',
    tagline: 'Первичный приём и непрерывное наблюдение пациентов',
  },
  {
    id: 'doc_michael_reyes',
    username: 'michael.reyes',
    password: 'clinic2026',
    name: 'Доктор Michael Reyes',
    specialty: 'Терапия',
    tagline: 'Ведение взрослых пациентов, диагностика и контроль лечения',
  },
  {
    id: 'doc_sofia_petrova',
    username: 'sofia.petrova',
    password: 'steth2026',
    name: 'Доктор Sofia Petrova',
    specialty: 'Неврология',
    tagline: 'Головная боль, головокружение и когнитивные жалобы',
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
