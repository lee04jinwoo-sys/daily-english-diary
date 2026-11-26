import React from 'react';
import { ReviewResponse, CardType, RecurringPattern, ReviewPart } from '../../types/essay';
import { GrammarCardDraft, grammarDraft, isGrammarFix } from '../../utils/cardText';
import { MessageSquare, Target, RotateCcw, Scale, Repeat, BookmarkPlus, Loader2 } from 'lucide-react';

interface EssayFeedbackProps {
  review: ReviewResponse;
  pendingParts?: ReviewPart[];
  onRevise: () => void;
  onOpenAnkiModal: (cardType: CardType, text: string, context?: string) => void;
  onOpenGrammarModal: (draft: GrammarCardDraft) => void;
}

const PART_LABELS: Record<ReviewPart, string> = {
  feedback: '총평·내용 피드백',
  corrections: '교정·문법 수치',
};

export const EssayFeedback: React.FC<EssayFeedbackProps> = ({ review, pendingParts = [], onRevise, onOpenAnkiModal, onOpenGrammarModal }) => {
  const { argument } = review;
  const isPending = (part: ReviewPart) => pendingParts.includes(part);
  const metrics = isPending('corrections') ? null : review.metrics ?? null;
  const patterns = review.recurring_patterns || [];

  // Card front = the learner's own sentence, corrected; falls back to the fix itself.
  const cardTextFor = (p: RecurringPattern) => {
    const pair = (review.sentence_pairs || []).find((sp) => p.examples.some((ex) => sp.original.includes(ex)));
    return pair?.corrected || p.fix;
  };
  // A pattern's grammar card comes from the first grammar fix that corrected one of its examples.
  const grammarFixFor = (p: RecurringPattern) =>
    (review.suggestions || []).find((s) => isGrammarFix(s) && p.examples.some((ex) => ex.includes(s.original_phrase) || s.original_phrase.includes(ex)));
  const argumentRows = [
    { label: '입장(Thesis)', value: argument.thesis },
    { label: '가장 강한 부분', value: argument.strongest_point },
    { label: '가장 약한 논거', value: argument.weakest_point },
    { label: '다뤄야 할 반론', value: argument.missing_counterargument },
  ].filter((r) => r.value);

  return (
    <div id="essay-feedback" className="space-y-4 scroll-mt-4">
      {pendingParts.length > 0 && (
        <div className="flex items-center space-x-2 text-xs text-stone-600 dark:text-stone-300 bg-stone-100/70 dark:bg-[#262626] border border-stone-200 dark:border-[#333333] rounded-lg px-3 py-2">
          <Loader2 className="w-3.5 h-3.5 animate-spin shrink-0" />
          <span>아직 오는 중: {pendingParts.map((p) => PART_LABELS[p]).join(' · ')}</span>
        </div>
      )}

      {/* Grammar numbers, counted from the verified corrections */}
      <div className="bg-white dark:bg-[#222222] rounded-xl border border-stone-200 dark:border-[#333333] shadow-xs p-4">
        <div className="flex items-center space-x-1.5 text-xs text-stone-500 dark:text-stone-400 mb-3">
          <Scale className="w-3.5 h-3.5" />
          <span>문법 (검증된 교정 기준)</span>
        </div>
        <div className="grid grid-cols-3 gap-3">
          <div className="bg-[#faf9f6] dark:bg-[#1a1a1a] border border-[#ebe9e1] dark:border-[#333333] rounded-lg p-3">
            <div className="text-[11px] text-stone-500 dark:text-stone-400">100단어당 오류</div>
            <div className="text-xl font-bold tabular-nums text-stone-900 dark:text-stone-100 mt-1">
              {metrics ? metrics.errors_per_100.toFixed(1) : '…'}
            </div>
            {metrics && (
              <div className="text-[10px] text-stone-400 dark:text-stone-500 mt-1 tabular-nums">
                {metrics.accuracy_errors}개 / {metrics.words}단어
              </div>
            )}
          </div>
          <div className="bg-[#faf9f6] dark:bg-[#1a1a1a] border border-[#ebe9e1] dark:border-[#333333] rounded-lg p-3">
            <div className="text-[11px] text-stone-500 dark:text-stone-400">오류 없는 문장</div>
            <div className="text-xl font-bold tabular-nums text-stone-900 dark:text-stone-100 mt-1">
              {metrics ? `${metrics.clean_sentence_pct}%` : '…'}
            </div>
            {metrics && (
              <div className="text-[10px] text-stone-400 dark:text-stone-500 mt-1 tabular-nums">
                {metrics.clean_sentences} / {metrics.sentences}문장
              </div>
            )}
          </div>
          <div className="bg-[#faf9f6] dark:bg-[#1a1a1a] border border-[#ebe9e1] dark:border-[#333333] rounded-lg p-3">
            <div className="text-[11px] text-stone-500 dark:text-stone-400">어색한 표현</div>
            <div className="text-xl font-bold tabular-nums text-stone-500 dark:text-stone-400 mt-1">
              {metrics ? metrics.awkward : '…'}
            </div>
            <div className="text-[10px] text-stone-400 dark:text-stone-500 mt-1">참고 (수치에 안 넣음)</div>
          </div>
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

      {/* Recurring patterns */}
      {patterns.length > 0 && (
        <div className="bg-white dark:bg-[#222222] rounded-xl border border-rose-200/80 dark:border-rose-900/50 p-5 shadow-xs space-y-3">
          <div className="flex items-center space-x-1.5 text-xs font-semibold text-[#37352f] dark:text-[#e0e0e0]">
            <Repeat className="w-3.5 h-3.5 text-rose-600 dark:text-rose-400" />
            <span>반복되는 패턴 (다음 글 체크리스트)</span>
          </div>
          {patterns.map((p, i) => (
            <div key={i} className="bg-rose-50/50 dark:bg-rose-950/20 border border-rose-100 dark:border-rose-900/40 rounded-lg p-3 space-y-1.5">
              <div className="flex items-start justify-between gap-2">
                <span className="text-xs font-semibold text-stone-800 dark:text-stone-200">{p.pattern}</span>
                <span className="shrink-0 text-[11px] font-bold tabular-nums text-rose-700 dark:text-rose-300">×{p.count}</span>
              </div>
              {p.examples.length > 0 && (
                <div className="flex flex-wrap gap-1.5">
                  {p.examples.map((ex, j) => (
                    <span key={j} className="text-[11px] font-serif line-through text-rose-600/80 dark:text-rose-400/80">{ex}</span>
                  ))}
                </div>
              )}
              {p.fix && (
                <div className="text-xs font-serif text-emerald-700 dark:text-emerald-300 font-semibold">→ {p.fix}</div>
              )}
              <div className="flex items-end justify-between gap-2">
                {p.tip && <p className="text-[11px] text-stone-600 dark:text-stone-400 leading-relaxed">💡 {p.tip}</p>}
                <div className="shrink-0 flex items-center gap-1">
                {grammarFixFor(p) && (
                  <button
                    onClick={() => onOpenGrammarModal(grammarDraft(review.original_text, review.suggestions || [], grammarFixFor(p)!))}
                    className="flex items-center space-x-1 text-[11px] font-semibold text-violet-600 dark:text-violet-400 hover:bg-violet-50 dark:hover:bg-violet-950/50 px-2 py-1 rounded-md transition-colors"
                  >
                    <BookmarkPlus className="w-3.5 h-3.5" />
                    <span>문법 카드</span>
                  </button>
                )}
                <button
                  onClick={() => onOpenAnkiModal('sentence', cardTextFor(p), p.tip)}
                  className="shrink-0 flex items-center space-x-1 text-[11px] font-semibold text-blue-600 dark:text-blue-400 hover:bg-blue-50 dark:hover:bg-blue-950/50 px-2 py-1 rounded-md transition-colors"
                >
                  <BookmarkPlus className="w-3.5 h-3.5" />
                  <span>Anki 카드</span>
                </button>
                </div>
              </div>
            </div>
          ))}
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
      {/* Argument */}
      {(argumentRows.length > 0 || argument.paragraph_comments.length > 0) && (
        <div className="bg-white dark:bg-[#222222] rounded-xl border border-stone-200 dark:border-[#333333] p-5 shadow-xs space-y-3">
          <div className="flex items-center space-x-1.5 text-xs font-semibold text-[#37352f] dark:text-[#e0e0e0]">
            <Target className="w-3.5 h-3.5 text-rose-600 dark:text-rose-400" />
            <span>내용 피드백</span>
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
    </div>
  );
};
