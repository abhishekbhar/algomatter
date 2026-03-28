"use client";

import { useRef, useCallback } from "react";
import Editor, { OnMount } from "@monaco-editor/react";
import type { editor, Position } from "monaco-editor";
import { useColorMode } from "@chakra-ui/react";

interface MonacoEditorProps {
  value: string;
  onChange: (value: string) => void;
  readOnly?: boolean;
  height?: string;
}

export default function MonacoEditor({ value, onChange, readOnly = false, height = "100%" }: MonacoEditorProps) {
  const { colorMode } = useColorMode();
  const editorRef = useRef<any>(null);

  const handleMount: OnMount = useCallback((editor, monaco) => {
    editorRef.current = editor;

    // Register AlgoMatterStrategy completions
    monaco.languages.registerCompletionItemProvider("python", {
      provideCompletionItems: (model: editor.ITextModel, position: Position) => {
        const word = model.getWordUntilPosition(position);
        const range = {
          startLineNumber: position.lineNumber,
          endLineNumber: position.lineNumber,
          startColumn: word.startColumn,
          endColumn: word.endColumn,
        };
        return {
          suggestions: [
            { label: "self.buy", kind: monaco.languages.CompletionItemKind.Method, insertText: 'self.buy(quantity=${1:1}, order_type="${2:market}")', insertTextRules: monaco.languages.CompletionItemInsertTextRule.InsertAsSnippet, range, detail: "Place a buy order" },
            { label: "self.sell", kind: monaco.languages.CompletionItemKind.Method, insertText: 'self.sell(quantity=${1:1}, order_type="${2:market}")', insertTextRules: monaco.languages.CompletionItemInsertTextRule.InsertAsSnippet, range, detail: "Place a sell order" },
            { label: "self.cancel_order", kind: monaco.languages.CompletionItemKind.Method, insertText: "self.cancel_order(${1:order_id})", insertTextRules: monaco.languages.CompletionItemInsertTextRule.InsertAsSnippet, range, detail: "Cancel a pending order" },
            { label: "self.position", kind: monaco.languages.CompletionItemKind.Property, insertText: "self.position", range, detail: "Current position or None" },
            { label: "self.portfolio", kind: monaco.languages.CompletionItemKind.Property, insertText: "self.portfolio", range, detail: "Portfolio (balance, equity, margin)" },
            { label: "self.open_orders", kind: monaco.languages.CompletionItemKind.Property, insertText: "self.open_orders", range, detail: "List of pending orders" },
            { label: "self.params", kind: monaco.languages.CompletionItemKind.Property, insertText: "self.params", range, detail: "User-configurable parameters" },
            { label: "self.state", kind: monaco.languages.CompletionItemKind.Property, insertText: "self.state", range, detail: "Persistent state dict" },
            { label: "self.history", kind: monaco.languages.CompletionItemKind.Method, insertText: "self.history(${1:20})", insertTextRules: monaco.languages.CompletionItemInsertTextRule.InsertAsSnippet, range, detail: "Last N candles" },
            { label: "self.log", kind: monaco.languages.CompletionItemKind.Method, insertText: 'self.log("${1:message}")', insertTextRules: monaco.languages.CompletionItemInsertTextRule.InsertAsSnippet, range, detail: "Log message to UI" },
          ],
        };
      },
    });
  }, []);

  return (
    <Editor
      height={height}
      language="python"
      theme={colorMode === "dark" ? "vs-dark" : "vs"}
      value={value}
      onChange={(v) => onChange(v || "")}
      onMount={handleMount}
      options={{
        readOnly,
        minimap: { enabled: false },
        fontSize: 14,
        lineNumbers: "on",
        scrollBeyondLastLine: false,
        automaticLayout: true,
        tabSize: 4,
        insertSpaces: true,
      }}
    />
  );
}
