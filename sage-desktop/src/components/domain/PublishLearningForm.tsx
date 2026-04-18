import { useState } from "react";

interface Payload {
  author_agent: string;
  author_solution: string;
  topic: string;
  title: string;
  content: string;
  tags: string[];
  confidence: number;
}

interface Props {
  onSubmit: (payload: Payload) => void;
  isSubmitting?: boolean;
}

function parseTags(raw: string): string[] {
  return raw
    .split(",")
    .map((t) => t.trim())
    .filter((t) => t.length > 0);
}

export function PublishLearningForm({ onSubmit, isSubmitting }: Props) {
  const [authorAgent, setAuthorAgent] = useState("");
  const [authorSolution, setAuthorSolution] = useState("");
  const [topic, setTopic] = useState("");
  const [title, setTitle] = useState("");
  const [content, setContent] = useState("");
  const [tagsRaw, setTagsRaw] = useState("");
  const [confidence, setConfidence] = useState(0.5);

  const disabled =
    isSubmitting ||
    !authorAgent.trim() ||
    !authorSolution.trim() ||
    !topic.trim() ||
    !title.trim() ||
    !content.trim();

  const handleSubmit = () => {
    if (disabled) return;
    onSubmit({
      author_agent: authorAgent.trim(),
      author_solution: authorSolution.trim(),
      topic: topic.trim(),
      title: title.trim(),
      content: content.trim(),
      tags: parseTags(tagsRaw),
      confidence,
    });
  };

  return (
    <form
      className="space-y-2 rounded border border-slate-200 bg-white p-3"
      onSubmit={(e) => {
        e.preventDefault();
        handleSubmit();
      }}
    >
      <h4 className="text-sm font-semibold text-slate-800">Publish learning</h4>
      <div className="grid grid-cols-2 gap-2">
        <label className="text-xs text-slate-600">
          author_agent
          <input
            aria-label="author_agent"
            className="mt-0.5 block w-full rounded border border-slate-300 px-2 py-1 text-sm"
            value={authorAgent}
            onChange={(e) => setAuthorAgent(e.target.value)}
          />
        </label>
        <label className="text-xs text-slate-600">
          author_solution
          <input
            aria-label="author_solution"
            className="mt-0.5 block w-full rounded border border-slate-300 px-2 py-1 text-sm"
            value={authorSolution}
            onChange={(e) => setAuthorSolution(e.target.value)}
          />
        </label>
        <label className="text-xs text-slate-600">
          topic
          <input
            aria-label="topic"
            className="mt-0.5 block w-full rounded border border-slate-300 px-2 py-1 text-sm"
            value={topic}
            onChange={(e) => setTopic(e.target.value)}
          />
        </label>
        <label className="text-xs text-slate-600">
          title
          <input
            aria-label="title"
            className="mt-0.5 block w-full rounded border border-slate-300 px-2 py-1 text-sm"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
          />
        </label>
      </div>
      <label className="block text-xs text-slate-600">
        content
        <textarea
          aria-label="content"
          className="mt-0.5 block h-24 w-full rounded border border-slate-300 px-2 py-1 text-sm"
          value={content}
          onChange={(e) => setContent(e.target.value)}
        />
      </label>
      <div className="grid grid-cols-2 gap-2">
        <label className="text-xs text-slate-600">
          tags (comma-separated)
          <input
            aria-label="tags"
            className="mt-0.5 block w-full rounded border border-slate-300 px-2 py-1 text-sm font-mono"
            value={tagsRaw}
            onChange={(e) => setTagsRaw(e.target.value)}
          />
        </label>
        <label className="text-xs text-slate-600">
          confidence (0–1)
          <input
            aria-label="confidence"
            type="number"
            min={0}
            max={1}
            step={0.05}
            className="mt-0.5 block w-full rounded border border-slate-300 px-2 py-1 text-sm"
            value={confidence}
            onChange={(e) => setConfidence(Number(e.target.value))}
          />
        </label>
      </div>
      <button
        type="submit"
        className="rounded bg-sky-600 px-3 py-1 text-sm text-white disabled:opacity-50"
        disabled={disabled}
      >
        Publish
      </button>
    </form>
  );
}
