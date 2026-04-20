/** Prefer direct backend origin in dev (see `.env.development`) so SSE is not proxied. */
export function apiUrl(path: string): string {
  const origin = import.meta.env.VITE_API_ORIGIN?.trim();
  if (origin) {
    return `${origin.replace(/\/$/, '')}${path.startsWith('/') ? path : `/${path}`}`;
  }
  return path;
}

/** Turns browser `TypeError: Failed to fetch` (connection refused, CORS, etc.) into an actionable hint. */
export function apiFetchErrorMessage(error: unknown): string {
  if (error instanceof TypeError) {
    const m = error.message.toLowerCase();
    if (
      m.includes('failed to fetch') ||
      m.includes('networkerror') ||
      m.includes('load failed') ||
      m.includes('network request failed')
    ) {
      return (
        'Cannot reach the API on port 8765. Start the backend from the repo root: ' +
        'uvicorn foresight_x.ui.api_server:app --host 127.0.0.1 --port 8765'
      );
    }
  }
  if (error instanceof Error) return error.message;
  return 'Request failed';
}
