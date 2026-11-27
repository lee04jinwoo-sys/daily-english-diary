import React, { useMemo, useRef, useState } from 'react';
import { api } from '../../api/client';
import { RecurringPattern, SuggestionItem } from '../../types/essay';
import { GrammarCardDraft, planGrammarCards } from '../../utils/cardText';
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

type Phase = { kind: 'checking' } | { kind: 'adding'; done: number; total: number } | null;

/**
 * Adds every grammar card of the essay to Anki in one go. Every fix gets a fresh, standalone
 * 10-18 word native example sentence + distractors generated and checked by Sonnet before anything is added.
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
    // 1. Every fix gets a fresh 10-18w native standalone sentence, translation, and distractors checked by Sonnet.
    const candidates: GrammarCardDraft[] = [...plan.cards, ...extras.map((e) => e.draft!)];
    const ready: GrammarCardDraft[] = [];
    const rejected: string[] = [];
    setPhase({ kind: 'checking' });
    try {
      const res = await api.prepareGrammarCards(
        candidates.map((d, i) => ({ id: String(i), sentence: d.sentence, answer: d.answer, mistake: d.mistake })),
      );
      candidates.forEach((d, i) => {
        const c = res.cards[String(i)];
        if (c) ready.push({ ...d, sentence: c.sentence, translation: c.translation, distractors: c.distractors });
        else rejected.push(`${d.answer} (${d.mistake}) — ${res.rejected[String(i)] ?? '검사 실패'}`);
      });
    } catch (e: any) {
      setPhase(null);
      onShowToast(`카드 예문 생성·검사에 실패해 등록하지 않았습니다: ${e?.message || '오류'}`);
      return;
    }

    // 2. One confirmation with all generated standalone sentences before adding
    const other = plan.skipped.filter((s) => s.reason !== 'same_sentence').length;
    const shown = ready.slice(0, 10).map((d) => `· ${d.sentence}`).join('\n');
    const lines = [
      `문법 카드 ${ready.length}장을 Anki에 등록할까요? (새 원어민 예문 · 검사 통과)`,
      shown ? `\n생성된 예문:\n${shown}${ready.length > 10 ? `\n… 외 ${ready.length - 10}장` : ''}` : '',
      rejected.length ? `\n검사를 통과하지 못해 제외: ${rejected.length}건\n${rejected.slice(0, 5).map((r) => `· ${r}`).join('\n')}` : '',
      other ? `빈칸을 만들 수 없는 교정 ${other}건은 제외됩니다.` : '',
      '\n이미 Anki에 있는 문장은 건너뜁니다.',
    ].filter(Boolean).join('\n');
    setPhase(null);
    if (ready.length === 0) {
      onShowToast(`등록할 카드가 없습니다: ${rejected.length}건이 검사를 통과하지 못했습니다.`);
      return;
    }
    if (!window.confirm(lines)) return;

    // 3. Add them one by one with checked translation & distractors
    const cards = ready;
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
          translation: draft.translation, distractors: draft.distractors,
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
    phase?.kind === 'checking' ? '새 예문 생성·검사 중...'
    : phase?.kind === 'adding' ? `등록 중 ${phase.done + 1}/${phase.total}`
    : `문법 카드 일괄 등록 (${total})`;

  return (
    <div className="mt-2 flex items-center space-x-2">
      <button
        onClick={run}
        disabled={busy || disabled || !ankiConnected}
        title={ankiConnected ? '이 에세이의 문법 교정마다 10~18단어 새 원어민 예문으로 Anki 문법 카드 등록' : 'Anki 연결 안 됨'}
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
