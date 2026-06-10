// ============================================================
// BEACON SECURITY UTILS
// Centralized HTML escaping to prevent XSS across the Atlas
// ============================================================

/**
 * Escapes HTML special characters to prevent XSS attacks.
 * @param {string} str The string to escape.
 * @returns {string} The escaped string.
 */
export function escapeHtml(str) {
  if (typeof str !== 'string') {
    return str;
  }
  const div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML;
}
