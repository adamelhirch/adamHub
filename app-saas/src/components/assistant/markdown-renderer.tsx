import React, { useState } from "react";
import {
  View,
  Text,
  ScrollView,
  TouchableOpacity,
  Linking,
} from "react-native";
import { Ionicons } from "@expo/vector-icons";
import * as Clipboard from "expo-clipboard";

interface MarkdownRendererProps {
  content: string;
  isStreaming?: boolean;
}

interface TableData {
  headers: string[];
  alignments: ("left" | "center" | "right")[];
  rows: string[][];
}

export function MarkdownRenderer({ content, isStreaming }: MarkdownRendererProps) {
  if (!content) {
    return null;
  }

  const blocks = parseMarkdownBlocks(content);

  return (
    <View className="w-full">
      {blocks.map((block, index) => {
        switch (block.type) {
          case "table":
            return <MarkdownTable key={index} data={block.data} />;
          case "header":
            return (
              <MarkdownHeader
                key={index}
                level={block.level}
                text={block.text}
              />
            );
          case "code":
            return (
              <MarkdownCodeBlock
                key={index}
                code={block.code}
                language={block.language}
              />
            );
          case "list":
            return (
              <MarkdownList
                key={index}
                items={block.items}
                ordered={block.ordered}
              />
            );
          case "quote":
            return <MarkdownQuote key={index} text={block.text} />;
          case "hr":
            return <View key={index} className="h-[1px] bg-slate-200 my-3 w-full" />;
          case "paragraph":
          default:
            return (
              <Text key={index} className="text-sm leading-6 text-slate-800 mb-2">
                {renderInlineMarkdown(block.text)}
              </Text>
            );
        }
      })}
      {isStreaming ? (
        <Text className="text-slate-900 font-bold text-sm animate-pulse"> ▊</Text>
      ) : null}
    </View>
  );
}

// ─── Table Component ──────────────────────────────────────────────────────────

function MarkdownTable({ data }: { data: TableData }) {
  const { headers, alignments, rows } = data;
  if (!headers || headers.length === 0) return null;

  return (
    <View className="my-2.5 rounded-xl border border-slate-200 overflow-hidden bg-white shadow-xs">
      <ScrollView
        horizontal
        showsHorizontalScrollIndicator={true}
        bounces={false}
        contentContainerStyle={{ minWidth: "100%" }}
      >
        <View className="flex-col">
          {/* Table Header */}
          <View className="flex-row bg-slate-100/90 border-b border-slate-200">
            {headers.map((head, idx) => {
              const align = alignments[idx] || "left";
              return (
                <View
                  key={idx}
                  className="px-3.5 py-2.5 min-w-[90px] max-w-[220px] justify-center"
                >
                  <Text
                    className={`text-xs font-bold text-slate-800 tracking-wider ${
                      align === "center"
                        ? "text-center"
                        : align === "right"
                        ? "text-right"
                        : "text-left"
                    }`}
                  >
                    {renderInlineMarkdown(head)}
                  </Text>
                </View>
              );
            })}
          </View>

          {/* Table Rows */}
          {rows.map((row, rowIdx) => {
            const isEven = rowIdx % 2 === 0;
            return (
              <View
                key={rowIdx}
                className={`flex-row border-b border-slate-100 ${
                  isEven ? "bg-white" : "bg-slate-50/70"
                }`}
              >
                {headers.map((_, colIdx) => {
                  const cell = row[colIdx] || "";
                  const align = alignments[colIdx] || "left";
                  return (
                    <View
                      key={colIdx}
                      className="px-3.5 py-2.5 min-w-[90px] max-w-[220px] justify-center"
                    >
                      <Text
                        className={`text-xs leading-5 text-slate-700 ${
                          align === "center"
                            ? "text-center"
                            : align === "right"
                            ? "text-right"
                            : "text-left"
                        }`}
                      >
                        {renderInlineMarkdown(cell)}
                      </Text>
                    </View>
                  );
                })}
              </View>
            );
          })}
        </View>
      </ScrollView>
    </View>
  );
}

// ─── Header Component ─────────────────────────────────────────────────────────

function MarkdownHeader({ level, text }: { level: number; text: string }) {
  if (level === 1) {
    return (
      <Text className="text-lg font-bold text-slate-900 mt-3 mb-1.5 tracking-tight">
        {renderInlineMarkdown(text)}
      </Text>
    );
  }
  if (level === 2) {
    return (
      <Text className="text-base font-bold text-slate-800 mt-2.5 mb-1 tracking-tight">
        {renderInlineMarkdown(text)}
      </Text>
    );
  }
  return (
    <Text className="text-sm font-semibold text-slate-700 mt-2 mb-1">
      {renderInlineMarkdown(text)}
    </Text>
  );
}

// ─── Code Block Component ─────────────────────────────────────────────────────

function MarkdownCodeBlock({ code, language }: { code: string; language?: string }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    await Clipboard.setStringAsync(code);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <View className="my-2.5 rounded-xl border border-slate-200 bg-slate-900 overflow-hidden shadow-xs">
      <View className="flex-row items-center justify-between px-3.5 py-1.5 bg-slate-950 border-b border-slate-800">
        <Text className="text-[11px] font-mono text-slate-400 uppercase">
          {language || "code"}
        </Text>
        <TouchableOpacity
          onPress={handleCopy}
          className="flex-row items-center px-2 py-1 rounded bg-slate-800 hover:bg-slate-700"
          hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
        >
          <Ionicons
            name={copied ? "checkmark" : "copy-outline"}
            size={12}
            color={copied ? "#f8fafc" : "#94a3b8"}
          />
          <Text className={`text-[10px] ml-1 font-medium ${copied ? "text-white font-semibold" : "text-slate-300"}`}>
            {copied ? "Copié !" : "Copier"}
          </Text>
        </TouchableOpacity>
      </View>
      <ScrollView horizontal showsHorizontalScrollIndicator={false} className="p-3">
        <Text className="font-mono text-xs leading-5 text-slate-100">
          {code}
        </Text>
      </ScrollView>
    </View>
  );
}

// ─── List Component ───────────────────────────────────────────────────────────

function MarkdownList({
  items,
  ordered,
}: {
  items: string[];
  ordered?: boolean;
}) {
  return (
    <View className="my-1.5 pl-1">
      {items.map((item, idx) => (
        <View key={idx} className="flex-row items-start mb-1.5">
          {ordered ? (
            <View className="w-5 h-5 rounded-full bg-slate-100 border border-slate-200 items-center justify-center mr-2 mt-0.5">
              <Text className="text-[10px] font-bold text-slate-700">
                {idx + 1}
              </Text>
            </View>
          ) : (
            <View className="w-1.5 h-1.5 rounded-full bg-slate-400 mr-2.5 mt-2" />
          )}
          <Text className="flex-1 text-sm leading-5 text-slate-800">
            {renderInlineMarkdown(item)}
          </Text>
        </View>
      ))}
    </View>
  );
}

// ─── Quote Component ──────────────────────────────────────────────────────────

function MarkdownQuote({ text }: { text: string }) {
  return (
    <View className="my-2 border-l-4 border-slate-300 bg-slate-50 rounded-r-lg px-3.5 py-2">
      <Text className="text-sm italic leading-5 text-slate-600">
        {renderInlineMarkdown(text)}
      </Text>
    </View>
  );
}

// ─── Inline Markdown Parser ───────────────────────────────────────────────────

export function renderInlineMarkdown(text: string): React.ReactNode[] {
  if (!text) return [];

  // Match bold, italic, inline code, links
  // Order: links [title](url) -> bold **...** -> italic *...* -> code `...`
  const regex = /(\[.*?\]\(.*?\)|\*\*.*?\*\*|\*.*?\*|`.*?`)/g;
  const parts = text.split(regex);

  return parts.map((part, index) => {
    if (!part) return null;

    // Link: [title](url)
    if (part.startsWith("[") && part.includes("](") && part.endsWith(")")) {
      const match = part.match(/^\[(.*?)\]\((.*?)\)$/);
      if (match) {
        const title = match[1];
        const url = match[2];
        return (
          <Text
            key={index}
            className="text-blue-600 underline font-medium"
            onPress={() => {
              if (url) Linking.openURL(url).catch(() => {});
            }}
          >
            {title}
          </Text>
        );
      }
    }

    // Bold: **text**
    if (part.startsWith("**") && part.endsWith("**") && part.length >= 4) {
      const inner = part.slice(2, -2);
      return (
        <Text key={index} className="font-bold text-slate-900">
          {inner}
        </Text>
      );
    }

    // Italic: *text*
    if (part.startsWith("*") && part.endsWith("*") && part.length >= 2) {
      const inner = part.slice(1, -1);
      return (
        <Text key={index} className="italic text-slate-600">
          {inner}
        </Text>
      );
    }

    // Inline Code: `text`
    if (part.startsWith("`") && part.endsWith("`") && part.length >= 2) {
      const inner = part.slice(1, -1);
      return (
        <Text
          key={index}
          className="font-mono text-xs text-slate-800 bg-slate-100 border border-slate-200 rounded px-1.5 py-0.5"
        >
          {inner}
        </Text>
      );
    }

    return <Text key={index}>{part}</Text>;
  });
}

// ─── Block Parser ─────────────────────────────────────────────────────────────

type Block =
  | { type: "table"; data: TableData }
  | { type: "header"; level: number; text: string }
  | { type: "code"; code: string; language: string }
  | { type: "list"; items: string[]; ordered: boolean }
  | { type: "quote"; text: string }
  | { type: "hr" }
  | { type: "paragraph"; text: string };

function parseMarkdownBlocks(content: string): Block[] {
  const lines = content.replace(/\r\n/g, "\n").split("\n");
  const blocks: Block[] = [];

  let i = 0;
  while (i < lines.length) {
    const line = lines[i];
    const trimmed = line.trim();

    // Empty line
    if (!trimmed) {
      i++;
      continue;
    }

    // Horizontal rule: --- or ***
    if (/^(\-{3,}|\*{3,})$/.test(trimmed)) {
      blocks.push({ type: "hr" });
      i++;
      continue;
    }

    // Fenced Code Block: ```lang
    if (trimmed.startsWith("```")) {
      const language = trimmed.slice(3).trim();
      const codeLines: string[] = [];
      i++;
      while (i < lines.length && !lines[i].trim().startsWith("```")) {
        codeLines.push(lines[i]);
        i++;
      }
      if (i < lines.length) i++; // consume closing ```
      blocks.push({
        type: "code",
        code: codeLines.join("\n"),
        language,
      });
      continue;
    }

    // Markdown Table: starts with | and next line has |-
    if (trimmed.startsWith("|") && trimmed.endsWith("|")) {
      const tableLines: string[] = [];
      while (i < lines.length && lines[i].trim().startsWith("|") && lines[i].trim().endsWith("|")) {
        tableLines.push(lines[i].trim());
        i++;
      }

      if (tableLines.length >= 2 && tableLines[1].includes("-")) {
        const parsedTable = parseTableLines(tableLines);
        if (parsedTable) {
          blocks.push({ type: "table", data: parsedTable });
          continue;
        }
      }
      // If not a valid table, process tableLines as paragraphs
      for (const tLine of tableLines) {
        blocks.push({ type: "paragraph", text: tLine });
      }
      continue;
    }

    // Headers: #, ##, ###, ####
    const headerMatch = trimmed.match(/^(#{1,4})\s+(.+)$/);
    if (headerMatch) {
      blocks.push({
        type: "header",
        level: headerMatch[1].length,
        text: headerMatch[2],
      });
      i++;
      continue;
    }

    // Blockquote: > text
    if (trimmed.startsWith(">")) {
      const quoteLines: string[] = [];
      while (i < lines.length && lines[i].trim().startsWith(">")) {
        quoteLines.push(lines[i].replace(/^>\s?/, ""));
        i++;
      }
      blocks.push({
        type: "quote",
        text: quoteLines.join("\n"),
      });
      continue;
    }

    // Unordered list: - item or * item
    if (/^[\*\-]\s+/.test(trimmed)) {
      const listItems: string[] = [];
      while (i < lines.length && /^[\*\-]\s+/.test(lines[i].trim())) {
        listItems.push(lines[i].trim().replace(/^[\*\-]\s+/, ""));
        i++;
      }
      blocks.push({
        type: "list",
        ordered: false,
        items: listItems,
      });
      continue;
    }

    // Ordered list: 1. item, 2. item
    if (/^\d+\.\s+/.test(trimmed)) {
      const listItems: string[] = [];
      while (i < lines.length && /^\d+\.\s+/.test(lines[i].trim())) {
        listItems.push(lines[i].trim().replace(/^\d+\.\s+/, ""));
        i++;
      }
      blocks.push({
        type: "list",
        ordered: true,
        items: listItems,
      });
      continue;
    }

    // Regular paragraph (accumulate multi-line paragraphs)
    const paragraphLines: string[] = [];
    while (
      i < lines.length &&
      lines[i].trim() &&
      !lines[i].trim().startsWith("```") &&
      !lines[i].trim().startsWith("|") &&
      !lines[i].trim().startsWith(">") &&
      !/^#{1,4}\s+/.test(lines[i].trim()) &&
      !/^[\*\-]\s+/.test(lines[i].trim()) &&
      !/^\d+\.\s+/.test(lines[i].trim()) &&
      !/^(\-{3,}|\*{3,})$/.test(lines[i].trim())
    ) {
      paragraphLines.push(lines[i].trim());
      i++;
    }

    if (paragraphLines.length > 0) {
      blocks.push({
        type: "paragraph",
        text: paragraphLines.join(" "),
      });
    }
  }

  return blocks;
}

function parseTableLines(lines: string[]): TableData | null {
  if (lines.length < 2) return null;

  const headerLine = lines[0];
  const separatorLine = lines[1];
  const rowLines = lines.slice(2);

  const headers = splitRow(headerLine);
  if (headers.length === 0) return null;

  const sepCells = splitRow(separatorLine);
  const alignments: ("left" | "center" | "right")[] = [];

  for (let i = 0; i < headers.length; i++) {
    const sep = sepCells[i] || "";
    if (sep.startsWith(":") && sep.endsWith(":")) {
      alignments.push("center");
    } else if (sep.endsWith(":")) {
      alignments.push("right");
    } else {
      alignments.push("left");
    }
  }

  const rows: string[][] = [];
  for (const rLine of rowLines) {
    const cells = splitRow(rLine);
    while (cells.length < headers.length) {
      cells.push("");
    }
    rows.push(cells.slice(0, headers.length));
  }

  return { headers, alignments, rows };
}

function splitRow(line: string): string[] {
  let content = line.trim();
  if (content.startsWith("|")) content = content.substring(1);
  if (content.endsWith("|")) content = content.substring(0, content.length - 1);
  return content.split("|").map((c) => c.trim());
}
