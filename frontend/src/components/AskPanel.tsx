import { Search } from "lucide-react";
import { SemanticMatch } from "../lib/api";
import { MarkdownView } from "./MarkdownView";
import { Spinner } from "./Spinner";

type Props = {
  question: string;
  onQuestionChange: (q: string) => void;
  onAsk: () => void;
  answer: string;
  semanticMatches: SemanticMatch[];
  loading: boolean;
};

export function AskPanel({
  question,
  onQuestionChange,
  onAsk,
  answer,
  semanticMatches,
  loading,
}: Props) {
  return (
    <div className="panel" id="ask-panel">
      <h2>Ask Cartographer</h2>
      <textarea
        id="question-input"
        value={question}
        onChange={(e) => onQuestionChange(e.target.value)}
        placeholder="What are the riskiest parts of this codebase?"
        onKeyDown={(e) => {
          if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) onAsk();
        }}
      />
      <button id="ask-button" onClick={onAsk} disabled={loading}>
        {loading ? <Spinner /> : <Search size={18} />}
        {loading ? "Thinking…" : "Ask"}
      </button>
      {answer && <MarkdownView content={answer} />}
      {semanticMatches.length > 0 && (
        <div className="semantic">
          <h3>Semantic Matches</h3>
          {semanticMatches.map((match, index) => (
            <div key={`${match.path}-${index}`}>
              <strong>{match.path}</strong>
              <span>score {match.score.toFixed(3)}</span>
              <p>{match.summary}</p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
