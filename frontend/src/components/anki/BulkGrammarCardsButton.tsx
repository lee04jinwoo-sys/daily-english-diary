import React, { useMemo, useRef, useState } from 'react';
import { api } from '../../api/client';
import { SuggestionItem } from '../../types/essay';
import { planGrammarCards } from '../../utils/cardText';
import { BookmarkPlus, Loader2 } from 'lucide-react';

interface BulkGrammarCardsButtonProps {
  originalText: string;
  suggestions: SuggestionItem[];
  ankiConnected: boolean;
  disabled?: boolean;
  onShowToast: (msg: string) => void;
}

/**
 * Adds every grammar card of the essay to Anki, one after another (Anki handles one request at a
 * time). The same plan and the same API as the single-card modal, so the cards are identical to
 * the ones added by hand. Already existing sentences come back as duplicates and are skipped.
 */
export const BulkGrammarCardsButton: React.FC<BulkGrammarCardsButtonProps> = ({
  originalText, suggestions, ankiConnected, disabled, onShowToast,
}) => {
  const plan = useMemo(() => planGrammarCards(originalText, suggestions), [originalText, suggestions]);
  const [progress, setProgress] = useState<{ done: number; total: number } | null>(null);
  const stopRef = useRef(false);
  const running = progress !== null;

  if (plan.cards.length === 0) return null;

  const run = async () => {
    const sameSentence = plan.skipped.filter((s) => s.reason === 'same_sentence').length;
    const other = plan.skipped.length - sameSentence;
    const notes = [
      '이미 Anki에 있는 문장은 건너뜁니다.',
      sameSentence > 0 ? `한 문장에 교정이 여러 개면 카드는 문장당 1장입니다 (${sameSentence}건 제외).` : '',
      other > 0 ? `빈칸을 만들 수 없는 교정 ${other}건은 제외됩니다.` : '',
    ].filter(Boolean).join('\n');
    if (!window.confirm(`문법 카드 ${plan.cards.length}장을 Anki에 등록할까요?\n${notes}`)) return;

    stopRef.current = false;
    let added = 0, duplicate = 0, failed = 0;
    let stopped = '';
    for (const [i, draft] of plan.cards.entries()) {
      if (stopRef.current) { stopped = '중단됨'; break; }
      setProgress({ done: i, total: plan.cards.length });
      try {
        const res = await api.addGrammarCard({ sentence: draft.sentence, answer: draft.answer, mistake: draft.mistake });
        if (!res.success) failed++;
        else if (res.duplicate) duplicate++;
        else added++;
      } catch (e: any) {
        failed++;
        if (/연결할 수 없/.test(e?.message || '')) { stopped = 'Anki 연결이 끊겨 중단됨'; break; }
      }
    }
    setProgress(null);
    onShowToast(
      `문법 카드 ${added}장 등록 · 이미 있음 ${duplicate}장` + (failed ? ` · 실패 ${failed}장` : '') + (stopped ? ` · ${stopped}` : ''),
    );
  };

  return (
    <div className="mt-2 flex items-center space-x-2">
      <button
        onClick={run}
        disabled={running || disabled || !ankiConnected}
        title={ankiConnected ? '이 에세이의 문법 교정을 모두 Anki 문법 카드로 등록' : 'Anki 연결 안 됨'}
        className="flex items-center space-x-1.5 px-2.5 py-1.5 rounded-lg text-[11px] font-semibold border border-violet-200 dark:border-violet-800/60 text-violet-700 dark:text-violet-300 bg-violet-50 dark:bg-violet-950/40 hover:bg-violet-100 dark:hover:bg-violet-950/70 disabled:opacity-50 transition-colors"
      >
        {running ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <BookmarkPlus className="w-3.5 h-3.5" />}
        <span>{running ? `등록 중 ${progress!.done + 1}/${progress!.total}` : `문법 카드 일괄 등록 (${plan.cards.length})`}</span>
      </button>
      {running && (
        <button
          onClick={() => { stopRef.current = true; }}
          className="text-[11px] text-stone-500 dark:text-stone-400 hover:text-stone-800 dark:hover:text-stone-200 underline"
        >
          중단
        </button>
      )}
    </div>
  );
};
