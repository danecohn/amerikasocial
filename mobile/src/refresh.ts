import {createContext, useContext, useEffect, useRef} from 'react';

type RefreshTask = () => Promise<unknown> | unknown;
export const PageRefreshContext = createContext<Set<RefreshTask> | null>(null);

// Register without remounting forms or losing their unsaved drafts.
export function usePageRefresh(task: RefreshTask) {
  const tasks = useContext(PageRefreshContext);
  const latest = useRef(task);
  latest.current = task;
  useEffect(() => {
    if (!tasks) return;
    const refresh = () => latest.current();
    tasks.add(refresh);
    return () => { tasks.delete(refresh); };
  }, [tasks]);
}
