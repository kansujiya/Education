import { useEffect, useRef } from "react";

let mermaidPromise: Promise<typeof import("mermaid").default> | null = null;

async function loadMermaid() {
  if (!mermaidPromise) {
    mermaidPromise = import("mermaid").then((m) => {
      m.default.initialize({ startOnLoad: false, theme: "dark" });
      return m.default;
    });
  }
  return mermaidPromise;
}

export function MindMap({ source }: { source: string }) {
  const ref = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    let cancelled = false;
    if (!source.trim()) return;
    (async () => {
      const mermaid = await loadMermaid();
      const id = `mm-${Math.random().toString(36).slice(2, 8)}`;
      const { svg } = await mermaid.render(id, source);
      if (!cancelled && ref.current) {
        ref.current.innerHTML = svg;
      }
    })().catch((err) => {
      if (!cancelled && ref.current) {
        ref.current.textContent = `Mermaid render failed: ${String(err)}`;
      }
    });
    return () => {
      cancelled = true;
    };
  }, [source]);

  return <div className="svg-wrap" ref={ref} />;
}
