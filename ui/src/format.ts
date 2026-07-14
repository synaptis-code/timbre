/** Formatage d'une taille en octets → « 63 Mo ». */
export const formatMo = (bytes: number) => `${Math.round(bytes / 1_000_000)} Mo`;
