export function isYearRecapSeasonActive(
  now = new Date(),
): boolean {
  return now.getMonth() === 11
}
