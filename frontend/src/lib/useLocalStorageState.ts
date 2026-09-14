import { useState } from 'react';

/**
 * localStorage 持久化的 useState。
 * 初始值从 localStorage 读取（缺失或解析失败时回退 initial），每次更新同步写回。
 * 用于保存折叠状态等 UI 偏好，在页面切换和浏览器刷新后保持。
 */
export function useLocalStorageState<T>(key: string, initial: T) {
  const [value, setValue] = useState<T>(() => {
    try {
      const saved = localStorage.getItem(key);
      return saved === null ? initial : (JSON.parse(saved) as T);
    } catch {
      return initial;
    }
  });

  const update = (next: T | ((prev: T) => T)) => {
    setValue((prev) => {
      const resolved = typeof next === 'function' ? (next as (p: T) => T)(prev) : next;
      try {
        localStorage.setItem(key, JSON.stringify(resolved));
      } catch {
        // 忽略写入失败（隐私模式/容量不足），状态仍在本会话内生效
      }
      return resolved;
    });
  };

  return [value, update] as const;
}
