import { useEffect, useRef, useState } from "react";

// True while the element's content is wider than the element, so a box that scrolls sideways is a keyboard tab stop
// only when there is something to scroll. Checked after every render (content changes) and on every resize.
export function useScrollable<T extends HTMLElement>() {
  const ref = useRef<T>(null);
  const [scrollable, setScrollable] = useState(false);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const check = () => setScrollable(el.scrollWidth > el.clientWidth + 1);
    check();
    const observer = new ResizeObserver(check);
    observer.observe(el);
    return () => observer.disconnect();
  });
  return { ref, scrollable };
}
