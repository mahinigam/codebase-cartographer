import React from "react";
import { Bot, FileText, ChevronRight } from "lucide-react";
import { SemanticMatch } from "../lib/api";
import { MarkdownView } from "./MarkdownView";
import { Spinner } from "./Spinner";

type Props = {
  question: string;
  answer: string;
  semanticMatches: SemanticMatch[];
  loading: boolean;
  onSelectFile: (path: string, source: any) => void;
  onClear: () => void;
};

export function AskPanel({
  question,
  answer,
  semanticMatches,
  loading,
  onSelectFile,
  onClear,
}: Props) {
  if (!question && !answer && !loading) return null;

  return (
    <div className="ask-panel">
      <div className="ask-header">
        <Bot size={16} className="bot-icon" />
        <span className="question-text">{question}</span>
        <button className="ghost-btn" onClick={onClear}>Clear</button>
      </div>

      <div className="ask-content">
        {loading ? (
          <div className="loading-state">
            <Spinner />
            <span>Analyzing architecture...</span>
          </div>
        ) : (
          <>
            {answer && (
              <div className="answer-box">
                <MarkdownView content={answer} />
              </div>
            )}
            
            {semanticMatches.length > 0 && (
              <div className="evidence-box">
                <div className="evidence-title">EVIDENCE & MATCHES</div>
                <div className="evidence-list">
                  {semanticMatches.map((match, index) => (
                    <div 
                      key={`${match.path}-${index}`} 
                      className="evidence-item clickable"
                      onClick={() => onSelectFile(match.path, "ai")}
                    >
                      <FileText size={14} className="item-icon" />
                      <div className="item-info">
                        <div className="item-path">{match.path}</div>
                        <div className="item-summary">{match.summary.substring(0, 80)}...</div>
                      </div>
                      <ChevronRight size={14} className="action-icon" />
                    </div>
                  ))}
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
