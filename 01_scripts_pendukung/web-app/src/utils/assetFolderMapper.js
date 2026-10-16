export function sanitizeSegment(value) {
  return String(value || '').replace(/[<>:"/\\|?*]/g, '_').replace(/[\u0000-\u001f]/g, '_').replace(/\s+/g, ' ').trim().replace(/[. ]+$/, '') || 'UNKNOWN';
}
export function normalizeJplIdentifier(value) {
  const parts = String(value || '').trim().replace(/\s*-\s*/g, '-').split(/\s+/);
  if (parts.length < 3 || parts[0].toUpperCase() !== 'JPL') return String(value || '').trim();
  const stations = parts.slice(2).join(' ').split('-').map(s => s.toUpperCase().trim()).map(s => s === 'CS' ? 'COS' : s).sort();
  return `JPL ${parts[1].toUpperCase()} ${stations.join('-')}`;
}
export function determineBtp(identifier, fallback = '') {
  const text = `${identifier || ''} ${fallback || ''}`.toUpperCase().replace(/_/g, ' ');
  if (/\b(?:BOO\s*-\s*BOP|BOP\s*-\s*BOO|BOP\s*-\s*BTT|BTT\s*-\s*BOP|BOP|BTT|CGB|COS|MSG|CCR|BNR|BATU\s*TULIS|CIOMAS|MASENG|CIGOMBONG|CICURUG|BOGOR\s*PALEDANG|PALEDANG)\b/.test(text)) return 'BTP BD';
  if (/\b(?:BOO|CLT|BJD|BOGOR|CILEBUT|BOJONGGEDE)\b/.test(text)) return 'BTP JAK';
  return 'UNKNOWN';
}
export function buildAssetDestination({ kategori, asset, filename }) {
  const category = String(kategori || '').trim() || 'UNKNOWN';
  const id = String(asset?.id || '').trim(); const loc = String(asset?.loc || '').trim();
  let identifier = [id, loc].filter(Boolean).join(' ').replace(/\s+/g, ' ').trim();
  const categoryPrefix = new RegExp(`^${category}\\s+`, 'i');
  identifier = identifier.replace(categoryPrefix, '').trim();
  if (/^(PTPP|JPL)\b/i.test(category) || /^JPL\b/i.test(identifier)) identifier = normalizeJplIdentifier(identifier);
  const btp = determineBtp(identifier, filename);
  if (!identifier || btp === 'UNKNOWN' || category === 'UNKNOWN') return { ok: false, status: 'failed', failureReason: 'Identifier atau BTP tidak dapat dipetakan', identifier, btp, category };
  return { ok: true, status: 'mapped', identifier, btp, category, relativePath: [sanitizeSegment(btp), sanitizeSegment(category), sanitizeSegment(identifier), sanitizeSegment(filename)].join('/') };
}
export function isSafeRelativeDestination(relativePath) {
  const value = String(relativePath || '');
  if (!value || /^[a-zA-Z]:[\\/]/.test(value) || value.startsWith('/') || value.startsWith('\\')) return false;
  return value.split(/[\\/]+/).every(part => part && part !== '.' && part !== '..');
}
