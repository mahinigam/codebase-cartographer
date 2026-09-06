import { LoadBearingFile } from "../lib/api";

type Props = {
  files: LoadBearingFile[];
  onFileClick: (path: string) => void;
};

export function LoadBearingFiles({ files, onFileClick }: Props) {
  return (
    <aside className="sidePanel">
      <h2>Load-Bearing Files</h2>
      <div className="fileList">
        {files.length === 0 && (
          <p className="emptyHint">Scan a repository to see results.</p>
        )}
        {files.map((file, index) => (
          <button key={`${file.path}-${index}`} onClick={() => onFileClick(file.path)}>
            <span>{file.path}</span>
            <strong>{file.load_bearing_score}</strong>
          </button>
        ))}
      </div>
    </aside>
  );
}
