import React from 'react';
import { ReviewResponse } from '../../types/essay';
import { MessageSquare, Target, RotateCcw, Scale } from 'lucide-react';

interface EssayFeedbackProps {
  review: ReviewResponse;
  onRevise: () => void;
}

const CRITERIA: Array<{ key: 'task_response' | 'coherence' | 'lexical' | 'grammar'; label: string }> = [
  { key: 'task_response', label: '과제 수행' },
  { key: 'coherence', label: '구성·흐름' },
  { key: 'lexical', label: '어휘' },
  { key: 'grammar', label: '문법 범위·정확성' },
];

export const EssayFeedback: React.FC<EssayFeedbackProps> = ({ review, onRevise }) => {
  const { rubric, argument } = review;
  const argumentRows = [
    { label: '입장(Thesis)', value: argument.thesis },
    { label: '가장 강한 부분', value: argument.strongest_point },
    { label: '가장 약한 논거', value: argument.weakest_point },
    { label: '다뤄야 할 반론', value: argument.missing_counterargument },
  ].filter((r) => r.value);

  return (
    <div className="space-y-4">
      {/* Rubric */}
      <div className="bg-white dark:bg-[#222222] rounded-xl border border-stone-200 dark:border-[#333333] p-5 shadow-xs">
        <div className="flex items-center justify-between mb-3.5">
          <div className="flex items-center space-x-1.5 text-xs font-semibold text-[#37352f] dark:text-[#e0e0e0]">
            <Scale className="w-3.5 h-3.5 text-indigo-600 dark:text-indigo-400" />
            <span>IELTS 4대 기준 채점 (추정)</span>
          </div>
          <span className="text-sm font-bold text-indigo-700 dark:text-indigo-300 tabular-nums">
            Band {rubric.overall_band.toFixed(1)}
          </span>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          {CRITERIA.map(({ key, label }) => (
            <div key={key} className="bg-[#faf9f6] dark:bg-[#1a1a1a] border border-[#ebe9e1] dark:border-[#333333] rounded-lg p-3">
              <div className="flex items-center justify-between text-xs">
                <span className="font-semibold text-stone-700 dark:text-stone-300">{label}</span>
                <span className="font-bold tabular-nums text-stone-900 dark:text-stone-100">
                  {rubric[key].band.toFixed(1)}
                </span>
              </div>
              <div className="h-1.5 mt-2 rounded-full bg-stone-200 dark:bg-[#333333] overflow-hidden">
                <div
                  className="h-full bg-indigo-500 dark:bg-indigo-400 rounded-full"
                  style={{ width: `${(rubric[key].band / 9) * 100}%` }}
                />
              </div>
              {rubric[key].comment && (
                <p className="text-[11px] text-stone-600 dark:text-stone-400 mt-2 leading-relaxed">{rubric[key].comment}</p>
              )}
            </div>
          ))}
        </div>
      </div>

      {/* Overall feedback */}
      {review.overall_feedback && (
        <div className="bg-gradient-to-br from-amber-50/70 to-orange-50/50 dark:from-amber-950/30 dark:to-orange-950/20 border border-amber-200/80 dark:border-amber-800/40 rounded-xl p-5 shadow-xs">
          <div className="flex items-center space-x-2 text-xs font-semibold text-amber-900 dark:text-amber-300 mb-2">
            <MessageSquare className="w-4 h-4 text-amber-600 dark:text-amber-400" />
            <span>총평</span>
          </div>
          <p className="text-xs text-amber-950 dark:text-amber-200 leading-relaxed">{review.overall_feedback}</p>
        </div>
      )}

      {/* Argument */}
      {(argumentRows.length > 0 || argument.paragraph_comments.length > 0) && (
        <div className="bg-white dark:bg-[#222222] rounded-xl border border-stone-200 dark:border-[#333333] p-5 shadow-xs space-y-3">
          <div className="flex items-center space-x-1.5 text-xs font-semibold text-[#37352f] dark:text-[#e0e0e0]">
            <Target className="w-3.5 h-3.5 text-rose-600 dark:text-rose-400" />
            <span>논증 피드백</span>
          </div>
          <dl className="space-y-2.5">
            {argumentRows.map((r) => (
              <div key={r.label} className="text-xs">
                <dt className="font-semibold text-stone-500 dark:text-stone-400 text-[11px]">{r.label}</dt>
                <dd className="text-stone-800 dark:text-stone-200 leading-relaxed mt-0.5">{r.value}</dd>
              </div>
            ))}
          </dl>
          {argument.paragraph_comments.length > 0 && (
            <div className="pt-2 border-t border-stone-100 dark:border-[#2d2d2d] space-y-1.5">
              {argument.paragraph_comments.map((c, i) => (
                <div key={i} className="text-xs flex items-start space-x-2">
                  <span className="shrink-0 font-mono text-[10px] px-1.5 py-0.5 rounded bg-stone-100 dark:bg-[#2c2c2c] text-stone-600 dark:text-stone-300">
                    ¶{c.paragraph}
                  </span>
                  <span className="text-stone-700 dark:text-stone-300 leading-relaxed">{c.comment}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Revision focus */}
      <div className="bg-indigo-50/60 dark:bg-indigo-950/20 border border-indigo-200/70 dark:border-indigo-800/40 rounded-xl p-5 shadow-xs space-y-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-1.5 text-xs font-semibold text-indigo-900 dark:text-indigo-200">
            <RotateCcw className="w-3.5 h-3.5" />
            <span>고쳐 쓸 때 집중할 것</span>
          </div>
          <button
            onClick={onRevise}
            className="flex items-center space-x-1 px-3 py-1.5 bg-indigo-600 hover:bg-indigo-700 dark:bg-indigo-500 dark:hover:bg-indigo-600 text-white text-xs font-semibold rounded-lg shadow-xs transition-all active:scale-95"
          >
            <RotateCcw className="w-3.5 h-3.5" />
            <span>같은 주제로 고쳐 쓰기</span>
          </button>
        </div>
        {review.revision_focus.length > 0 && (
          <ol className="list-decimal list-inside space-y-1 text-xs text-indigo-950 dark:text-indigo-100">
            {review.revision_focus.map((f, i) => (
              <li key={i} className="leading-relaxed">{f}</li>
            ))}
          </ol>
        )}
      </div>
    </div>
  );
};
