import { useEffect, useRef } from "react";
export default function EditorDialog({ title, busy, onClose, children }) {
  const ref = useRef(null);
  useEffect(() => { const dialog = ref.current; dialog.showModal(); return () => dialog.close(); }, []);
  return <dialog ref={ref} className="workflow-dialog" aria-labelledby="editor-dialog-title" onCancel={event => { event.preventDefault(); if (!busy) onClose(); }}>
    <h2 id="editor-dialog-title">{title}</h2>{children}
  </dialog>;
}
