"use client";

import { useState, useRef, useEffect } from "react";

interface SearchableSelectProps {
  options: string[];
  value: string | null;
  onChange: (value: string | null) => void;
  placeholder?: string;
  allLabel?: string;
}

/**
 * 可搜索的下拉选择器：输入文字即时过滤选项。
 */
export function SearchableSelect({
  options,
  value,
  onChange,
  placeholder = "请选择",
  allLabel = "全部",
}: SearchableSelectProps) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  // 点击外部关闭
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  const filtered = query
    ? options.filter((o) => o.includes(query))
    : options;

  const displayValue = value || "";

  return (
    <div ref={containerRef} className="relative">
      <input
        ref={inputRef}
        className="w-full h-8 px-2 text-sm border rounded-md bg-white
                   focus:outline-none focus:ring-1 focus:ring-ring"
        placeholder={placeholder}
        value={open ? query : displayValue}
        onFocus={() => {
          setOpen(true);
          setQuery("");
        }}
        onChange={(e) => {
          setQuery(e.target.value);
          if (!open) setOpen(true);
        }}
      />
      {open && (
        <div className="absolute z-50 mt-1 w-full max-h-60 overflow-y-auto
                        bg-white border rounded-md shadow-lg">
          <button
            className="w-full px-2 py-1.5 text-left text-sm hover:bg-gray-100 text-muted-foreground"
            onMouseDown={(e) => {
              e.preventDefault();
              onChange(null);
              setOpen(false);
              setQuery("");
            }}
          >
            {allLabel}
          </button>
          {filtered.map((o) => (
            <button
              key={o}
              className={`w-full px-2 py-1.5 text-left text-sm hover:bg-gray-100
                ${o === value ? "bg-gray-50 font-medium" : ""}`}
              onMouseDown={(e) => {
                e.preventDefault();
                onChange(o);
                setOpen(false);
                setQuery("");
              }}
            >
              {o}
            </button>
          ))}
          {filtered.length === 0 && (
            <div className="px-2 py-1.5 text-sm text-muted-foreground">无匹配项</div>
          )}
        </div>
      )}
    </div>
  );
}
