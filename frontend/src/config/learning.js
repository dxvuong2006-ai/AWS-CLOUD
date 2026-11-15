// Demo threshold only. Real completion is computed and returned by the backend.
// Keep the existing 10% test setup; set VITE_MOCK_COMPLETION_PERCENT=95 for the normal demo rule.
const configured = Number(import.meta.env.VITE_MOCK_COMPLETION_PERCENT ?? 10);
export const MOCK_COMPLETION_PERCENT = Number.isFinite(configured) && configured > 0 && configured <= 100 ? configured : 10;
export const PROGRESS_SAVE_INTERVAL_MS = 5000;
