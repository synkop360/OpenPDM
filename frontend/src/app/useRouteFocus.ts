import { useEffect } from "react";
import { useLocation } from "react-router-dom";

export function useRouteFocus(targetId = "main-content"): void {
  const { pathname } = useLocation();

  useEffect(() => {
    const frame = window.requestAnimationFrame(() => {
      document.getElementById(targetId)?.focus({ preventScroll: true });
    });
    return () => window.cancelAnimationFrame(frame);
  }, [pathname, targetId]);
}
