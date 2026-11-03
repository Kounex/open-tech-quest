import { useCallback, useEffect, useRef, useState } from "react";
import { request } from "./api";
export function useResource<T>(path: string | null, interval = 10000) {
  const [data, setData] = useState<T | null>(null),
    [error, setError] = useState(""),
    [loading, setLoading] = useState(true),
    [updatedAt, setUpdatedAt] = useState<number | null>(null);
  const sequence = useRef(0);
  const refresh = useCallback(async () => {
    if (!path) return;
    const id = ++sequence.current;
    try {
      const result = await request<T>(path);
      if (id === sequence.current) {
        setData(result);
        setUpdatedAt(Date.now());
        setError("");
      }
    } catch (e) {
      if (id === sequence.current)
        setError(e instanceof Error ? e.message : "Unable to load");
    } finally {
      if (id === sequence.current) setLoading(false);
    }
  }, [path]);
  useEffect(() => {
    setData(null);
    setLoading(true);
    setError("");
    void refresh();
    const tick = window.setInterval(() => {
      if (!document.hidden) void refresh();
    }, interval);
    const visible = () => {
      if (!document.hidden) void refresh();
    };
    window.addEventListener("online", visible);
    document.addEventListener("visibilitychange", visible);
    return () => {
      ++sequence.current;
      clearInterval(tick);
      window.removeEventListener("online", visible);
      document.removeEventListener("visibilitychange", visible);
    };
  }, [refresh, interval]);
  return { data, error, loading, refresh, setData, updatedAt };
}
export function usePath() {
  const [path, setPath] = useState(location.pathname);
  useEffect(() => {
    const update = () => {
      setPath(location.pathname);
      window.scrollTo(0, 0);
    };
    window.addEventListener("popstate", update);
    return () => window.removeEventListener("popstate", update);
  }, []);
  return path;
}
export function navigate(path: string) {
  history.pushState(null, "", path);
  window.dispatchEvent(new PopStateEvent("popstate"));
}
