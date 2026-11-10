export default function CourseArtwork({ title = "" }) {
  const text = String(title).toLowerCase();
  return <svg width="46" height="46" viewBox="0 0 48 48" fill="none" stroke="currentColor" strokeWidth="2.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    {/python|javascript|lập trình|programming|coding/.test(text) ?
      <path d="m16 15-10 9 10 9M32 15l10 9-10 9M28 9l-8 30" /> :
      /dữ liệu|database|sql|data/.test(text) ?
      <><ellipse cx="24" cy="11" rx="15" ry="6" /><path d="M9 11v26c0 8 30 8 30 0V11M9 24c0 8 30 8 30 0" /></> :
      <path d="M13 36h23a9 9 0 0 0 1-18 13 13 0 0 0-25-1 10 10 0 0 0 1 19Z" />}
  </svg>;
}