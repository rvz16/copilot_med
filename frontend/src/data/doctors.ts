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
    name: 'Dr. Amelia Carter',
    specialty: 'Family Medicine',
    tagline: 'Primary care and continuity management',
  },
  {
    id: 'doc_michael_reyes',
    username: 'michael.reyes',
    password: 'clinic2026',
    name: 'Dr. Michael Reyes',
    specialty: 'Internal Medicine',
    tagline: 'Adult care, diagnostics, and follow-up',
  },
  {
    id: 'doc_sofia_petrova',
    username: 'sofia.petrova',
    password: 'steth2026',
    name: 'Dr. Sofia Petrova',
    specialty: 'Neurology',
    tagline: 'Headache, dizziness, and cognitive assessments',
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
