import React from 'react';
import { Essay, ESSAY_TYPE_LABELS, CATEGORY_LABELS } from '../../types/essay';
import { RotateCcw } from 'lucide-react';

interface EssayPromptHeaderProps {
  essay: Essay;
  onPromptChange: (prompt: string) => void;
  previousBand?: number | null;
}

export const EssayPromptHeader: React.FC<EssayPromptHeaderProps> = ({ essay, onPromptChange, previousBand }) => {
  const isFree = essay.essay_type === 'free';

  return (
    <div className="space-y-2">
      <div className="flex items-center flex-wrap gap-1.5 text-[11px] font-semibold">
        <span className="px-2 py-0.5 rounded-md bg-indigo-50 dark:bg-indigo-950/50 text-indigo-700 dark:text-indigo-300 border border-indigo-200/70 dark:border-indigo-800/50">
          {ESSAY_TYPE_LABELS[essay.essay_type]}
        </span>
        <span className="px-2 py-0.5 rounded-md bg-stone-100 dark:bg-[#2a2a2a] text-stone-600 dark:text-stone-300 border border-stone-200 dark:border-[#383838]">
          {CATEGORY_LABELS[essay.category]}
        </span>
        <span className="text-stone-400 dark:text-stone-500 font-normal">{essay.date}</span>
        {essay.revision_of && (
          <span className="inline-flex items-center space-x-1 px-2 py-0.5 rounded-md bg-amber-50 dark:bg-amber-950/40 text-amber-800 dark:text-amber-300 border border-amber-200/70 dark:border-amber-800/50">
            <RotateCcw className="w-3 h-3" />
            <span>고쳐 쓰기{previousBand != null ? ` · 이전 Band ${previousBand.toFixed(1)}` : ''}</span>
          </span>
        )}
      </div>

      {isFree && !essay.is_reviewed ? (
        <textarea
          value={essay.prompt}
          onChange={(e) => onPromptChange(e.target.value)}
          rows={2}
          placeholder="내가 답할 질문을 적어주세요 (예: Should chess be considered a sport?)"
          className="w-full text-xl font-serif font-bold text-[#1c1b18] dark:text-[#f0f0f0] placeholder:text-stone-300 dark:placeholder:text-[#555555] bg-transparent outline-none border-b border-transparent focus:border-stone-200 dark:focus:border-[#383838] pb-2 resize-none transition-colors"
        />
      ) : (
        <h1 className="text-xl font-serif font-bold text-[#1c1b18] dark:text-[#f0f0f0] leading-snug pb-2">
          {essay.prompt}
        </h1>
      )}
    </div>
  );
};
