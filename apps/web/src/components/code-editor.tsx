"use client";

import { java } from "@codemirror/lang-java";
import { javascript } from "@codemirror/lang-javascript";
import { python } from "@codemirror/lang-python";
import { sql } from "@codemirror/lang-sql";
import CodeMirror from "@uiw/react-codemirror";

const LANGS = { python: python(), javascript: javascript(), typescript: javascript({ typescript: true }), sql: sql(), java: java(), bash: [] };
export type CodeLanguage = keyof typeof LANGS;
export const CODE_LANGUAGES = Object.keys(LANGS) as CodeLanguage[];

export default function CodeEditor({ value, onChange, language }: { value: string; onChange: (v: string) => void; language: CodeLanguage }) {
  const ext = LANGS[language];
  return (
    <CodeMirror
      value={value}
      onChange={onChange}
      height="260px"
      theme={typeof window !== "undefined" && window.matchMedia?.("(prefers-color-scheme: dark)").matches ? "dark" : "light"}
      extensions={Array.isArray(ext) ? ext : [ext]}
      basicSetup={{ lineNumbers: true, foldGutter: false, highlightActiveLine: true, tabSize: 4 }}
      aria-label="Code editor"
      className="overflow-hidden rounded-md border border-border text-sm"
    />
  );
}
