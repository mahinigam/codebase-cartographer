import React, { useState, useEffect, useRef } from "react";
import { Search, File, Terminal, ArrowRight, CornerDownLeft } from "lucide-react";
import { searchFiles, askQuestion } from "../lib/api";

type Props = {
  isOpen: boolean;
  onClose: () => void;
  activeRepoPath: string;
  onSelectFile: (path: string, source: any) => void;
  onAsk: (question: string) => void;
};

export function CommandPalette({ isOpen, onClose, activeRepoPath, onSelectFile, onAsk }: Props) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<any[]>([]);
  const [selectedIndex, setSelectedIndex] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (isOpen) {
      inputRef.current?.focus();
      setQuery("");
      setResults([]);
      setSelectedIndex(0);
    }
  }, [isOpen]);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "k" && (e.metaKey || e.ctrlKey)) {
        e.preventDefault();
        if (isOpen) onClose();
      }
      if (e.key === "Escape" && isOpen) {
        onClose();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, onClose]);

  useEffect(() => {
    if (!query.trim()) {
      setResults([]);
      return;
    }
    const timer = setTimeout(async () => {
      try {
        const res = await searchFiles(query, activeRepoPath);
        setResults(res.results || []);
      } catch (err) {
        // ignore for now
      }
    }, 300);
    return () => clearTimeout(timer);
  }, [query, activeRepoPath]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setSelectedIndex((prev) => Math.min(prev + 1, results.length));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setSelectedIndex((prev) => Math.max(prev - 1, 0));
    } else if (e.key === "Enter") {
      e.preventDefault();
      if (selectedIndex === 0 && query.trim()) {
        onAsk(query);
        onClose();
      } else if (selectedIndex > 0 && results[selectedIndex - 1]) {
        onSelectFile(results[selectedIndex - 1].path, "search");
        onClose();
      }
    }
  };

  if (!isOpen) return null;

  return (
    <div className="command-palette-overlay" onClick={onClose}>
      <div className="command-palette" onClick={(e) => e.stopPropagation()}>
        <div className="palette-input-wrapper">
          <Search size={20} className="search-icon" />
          <input
            ref={inputRef}
            type="text"
            placeholder="Search files, symbols, or ask Cartographer..."
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={handleKeyDown}
          />
        </div>

        <div className="palette-results">
          {query.trim() && (
            <div
              className={`palette-item ${selectedIndex === 0 ? "selected" : ""}`}
              onClick={() => {
                onAsk(query);
                onClose();
              }}
              onMouseEnter={() => setSelectedIndex(0)}
            >
              <Terminal size={16} className="item-icon ai-icon" />
              <div className="item-content">
                <span className="item-title">Ask Cartographer: "{query}"</span>
              </div>
              <CornerDownLeft size={14} className="enter-hint" />
            </div>
          )}

          {results.length > 0 && <div className="palette-group-title">FILES & SYMBOLS</div>}
          
          {results.map((result, i) => (
            <div
              key={result.path}
              className={`palette-item ${selectedIndex === i + 1 ? "selected" : ""}`}
              onClick={() => {
                onSelectFile(result.path, "search");
                onClose();
              }}
              onMouseEnter={() => setSelectedIndex(i + 1)}
            >
              <File size={16} className="item-icon" />
              <div className="item-content">
                <span className="item-title">{result.path.split("/").pop()}</span>
                <span className="item-subtitle">{result.path}</span>
              </div>
              <CornerDownLeft size={14} className="enter-hint" />
            </div>
          ))}

          {!query.trim() && (
            <div className="palette-suggestions">
              <div className="palette-group-title">SUGGESTED</div>
              <div className="palette-item" onClick={() => { onAsk("Show the riskiest files"); onClose(); }}>
                <ArrowRight size={16} className="item-icon" />
                <span className="item-title">Show the riskiest files</span>
              </div>
              <div className="palette-item" onClick={() => { onAsk("Explain this repository architecture"); onClose(); }}>
                <ArrowRight size={16} className="item-icon" />
                <span className="item-title">Explain this repository architecture</span>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
