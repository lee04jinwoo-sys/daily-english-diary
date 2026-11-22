import React, { useMemo, useRef, useState } from 'react';
import { api } from '../../api/client';
import { RecurringPattern, SuggestionItem } from '../../types/essay';
import { GrammarCardDraft, blankCount, planGrammarCards } from '../../utils/cardText';
import { BookmarkPlus, Check, Loader2 } from 'lucide-react';

interface BulkGrammarCardsButtonProps {
  originalText: string;
  suggestions: SuggestionItem[];
  patterns?: RecurringPattern[];
  essayId: string;
  /** Ids of the fixes that already have a grammar card. */
  registeredFixIds: ReadonlySet<string>;
  /** Called with the fixes whose card now exists in Anki (just added, or it was already there). */
  onRegistered: (fixIds: string[]) => void;
  ankiConnected: boolean;
  disabled?: boolean;
  onShowToast: (msg: string) => void;
}

type Phase = { kind: 'preparing' } | { kind: 'adding'; done: number; total: number } | null;

/**
 * Adds every grammar card of the essay to Anki in one go, one request after another (Anki handles one
 * at a time). Each sentence gets a card from the learner's own sentence; Anki rejects two grammar notes
 * with the same sentence, so the other fixes of a sentence get a new, similar sentence written by the
 * model (checked in code: one blank, no wrong-form hint). The user sees both lists before anything is
 * added. Sentences already in Anki come back as duplicates and are skipped.
 */
export const BulkGrammarCardsButton: React.FC<BulkGrammarCardsButtonProps> = ({
  originalText, suggestions, patterns, essayId, registeredFixIds, onRegistered, ankiConnected, disabled, onShowToast,
}) => {
  const plan = useMemo(
    () => planGrammarCards(originalText, suggestions, patterns || [], registeredFixIds),
    [originalText, suggestions, patterns, registeredFixIds],
  );
  const extras = useMemo(() => plan.skipped.filter((s) => s.reason === 'same_sentence' && s.draft), [plan]);
  const [phase, setPhase] = useState<Phase>(null);
  const stopRef = useRef(false);
  const busy = phase !== null;

  const total = plan.cards.length + extras.length;
  if (total === 0) {
    if (plan.registered.length === 0) return null;
    return (
      <div className="mt-2 flex items-center space-x-1.5 px-2.5 py-1.5 text-[11px] font-semibold text-emerald-700 dark:text-emerald-300" title="이 에세이의 문법 교정은 모두 Anki 카드로 등록되어 있습니다">
        <Check className="w-3.5 h-3.5" />
        <span>문법 카드 등록 완료 ({plan.registered.length})</span>
      </div>
    );
  }

  const run = async () => {
    // 1. similar sentences for the fixes that share a sentence with a chosen one
    const similar: GrammarCardDraft[] = [];
    let similarMissing = 0;
    if (extras.length > 0) {
      setPhase({ kind: 'preparing' });
      try {
        const res = await api.similarSentences(
          extras.map((e, i) => ({ id: String(i), answer: e.draft!.answer, mistake: e.draft!.mistake, sentence: e.draft!.sentence })),
        );
        extras.forEach((e, i) => {
          const sentence = res.sentences[String(i)];
          // the same blank rule the card template applies; the server already checked it, this is a guard
          if (sentence && blankCount(sentence, e.draft!.answer) === 1) similar.push({ ...e.draft!, sentence });
          else similarMissing++;
        });
      } catch (e: any) {
        setPhase(null);
        if (!window.confirm(`유사 문장을 만들지 못했습니다 (${e?.message || '오류'}).\n내 문장 카드 ${plan.cards.length}장만 등록할까요?`)) return;
        similarMissing = extras.length;
      }
    }

    // 2. one confirmation with everything that will be added
    const other = plan.skipped.filter((s) => s.reason !== 'same_sentence').length;
    const shown = similar.slice(0, 10).map((d) => `· ${d.sentence}`).join('\n');
    const lines = [
      `문법 카드를 Anki에 등록할까요?`,
      `· 내 문장 ${plan.cards.length}장` + (similar.length ? ` + 유사 문장 ${similar.length}장` : ''),
      similar.length ? `\n유사 문장 (모델이 만든 새 문장):\n${shown}${similar.length > 10 ? `\n… 외 ${similar.length - 10}장` : ''}` : '',
      similarMissing ? `\n유사 문장을 만들지 못해 제외: ${similarMissing}건` : '',
      other ? `빈칸을 만들 수 없는 교정 ${other}건은 제외됩니다.` : '',
      '\n이미 Anki에 있는 문장은 건너뜁니다.',
    ].filter(Boolean).join('\n');
    setPhase(null);
    if (!window.confirm(lines)) return;

    // 3. add them one by one
    const cards = [...plan.cards, ...similar];
    stopRef.current = false;
    let added = 0, duplicate = 0, failed = 0;
    let stopped = '';
    const nowRegistered: string[] = [];
    for (const [i, draft] of cards.entries()) {
      if (stopRef.current) { stopped = '중단됨'; break; }
      setPhase({ kind: 'adding', done: i, total: cards.length });
      try {
        const res = await api.addGrammarCard({
          sentence: draft.sentence, answer: draft.answer, mistake: draft.mistake, essay_id: essayId, fix_id: draft.fixId,
        });
        if (!res.success) { failed++; continue; }
        if (res.duplicate) duplicate++;
        else added++;
        if (draft.fixId) nowRegistered.push(draft.fixId);
      } catch (e: any) {
        failed++;
        if (/연결할 수 없/.test(e?.message || '')) { stopped = 'Anki 연결이 끊겨 중단됨'; break; }
      }
    }
    setPhase(null);
    if (nowRegistered.length) onRegistered(nowRegistered);
    onShowToast(
      `문법 카드 ${added}장 등록 · 이미 있음 ${duplicate}장` + (failed ? ` · 실패 ${failed}장` : '') + (stopped ? ` · ${stopped}` : ''),
    );
  };

  const label =
    phase?.kind === 'preparing' ? '유사 문장 만드는 중...'
    : phase?.kind === 'adding' ? `등록 중 ${phase.done + 1}/${phase.total}`
    : `문법 카드 일괄 등록 (${total})`;

  return (
    <div className="mt-2 flex items-center space-x-2">
      <button
        onClick={run}
        disabled={busy || disabled || !ankiConnected}
        title={ankiConnected ? '이 에세이의 문법 교정을 모두 Anki 문법 카드로 등록 (한 문장에 교정이 여럿이면 유사 문장으로)' : 'Anki 연결 안 됨'}
        className="flex items-center space-x-1.5 px-2.5 py-1.5 rounded-lg text-[11px] font-semibold border border-violet-200 dark:border-violet-800/60 text-violet-700 dark:text-violet-300 bg-violet-50 dark:bg-violet-950/40 hover:bg-violet-100 dark:hover:bg-violet-950/70 disabled:opacity-50 transition-colors"
      >
        {busy ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <BookmarkPlus className="w-3.5 h-3.5" />}
        <span>{label}</span>
      </button>
      {phase?.kind === 'adding' && (
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
