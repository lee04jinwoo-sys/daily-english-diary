import React, { useEffect, useState } from 'react';
import { api } from '../../api/client';
import { AnkiStatus } from '../../types/essay';
import { GrammarCardDraft, blankCount, blankedSentence } from '../../utils/cardText';
import { isCompleteSentence } from '../../utils/sentences';
import { X, BookmarkPlus, AlertCircle, CheckCircle2 } from 'lucide-react';

interface GrammarCardModalProps {
  draft: GrammarCardDraft | null;
  onClose: () => void;
  ankiStatus: AnkiStatus | null;
  onCardAdded: (message: string) => void;
  essayId?: string;
  /** Called when the card exists in Anki (just added, or it was already there). */
  onRegistered?: (fixId: string) => void;
}

const inputCls =
  'w-full px-3 py-1.5 bg-white dark:bg-[#1a1a1a] border border-stone-200 dark:border-[#383838] rounded-lg text-xs font-serif text-stone-900 dark:text-stone-100 outline-none focus:border-stone-400 dark:focus:border-[#555555]';

/**
 * English Grammar multiple-choice card: the answer is blanked on the front and my own
 * mistake is one of the wrong options. Anki Manager fills the translation, the explanation
 * and the other two options under its card rules.
 */
export const GrammarCardModal: React.FC<GrammarCardModalProps> = ({ draft, onClose, ankiStatus, onCardAdded, essayId, onRegistered }) => {
  const [sentence, setSentence] = useState('');
  const [answer, setAnswer] = useState('');
  const [mistake, setMistake] = useState('');
  const [translation, setTranslation] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  // The sentence that passed the grammar + translation check (Sonnet); a changed sentence is checked again.
  const [checkedSentence, setCheckedSentence] = useState<string | null>(null);
  const [checkState, setCheckState] = useState<'idle' | 'checking' | 'ok' | 'failed'>('idle');
  const [checkNote, setCheckNote] = useState('');

  const runCheck = async (s: string, a: string, m: string): Promise<{ sentence: string; translation: string } | null> => {
    setCheckState('checking');
    try {
      const res = await api.prepareGrammarCards([{ id: '0', sentence: s, answer: a, mistake: m }]);
      const card = res.cards['0'];
      if (card) {
        setSentence(card.sentence);
        setTranslation(card.translation);
        setCheckedSentence(card.sentence);
        setCheckState('ok');
        setCheckNote(card.sentence !== s ? '문장의 오류를 고쳤습니다.' : '');
        return card;
      }
      setCheckState('failed');
      setCheckNote(res.rejected['0'] || '검사를 통과하지 못했습니다.');
    } catch (e: any) {
      setCheckState('failed');
      setCheckNote(`검사 실패: ${e?.message || '오류'}`);
    }
    return null;
  };

  useEffect(() => {
    if (!draft) return;
    setSentence(draft.sentence);
    setAnswer(draft.answer);
    setMistake(draft.mistake);
    setTranslation('');
    setCheckedSentence(null);
    setCheckNote('');
    setErrorMsg(null);
    runCheck(draft.sentence, draft.answer, draft.mistake);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [draft]);

  if (!draft) return null;

  const blanks = blankCount(sentence, answer);
  const sameAsAnswer = !!mistake.trim() && mistake.trim().toLowerCase() === answer.trim().toLowerCase();
  const problem =
    blanks === 0 ? '정답이 문장 안에 단어 단위로 없어서 빈칸을 만들 수 없습니다.'
    : blanks > 1 ? `정답이 문장에 ${blanks}번 나옵니다. 빈칸이 한 곳만 생기도록 정답을 더 길게 잡으세요.`
    : sameAsAnswer ? '내가 쓴 형태가 정답과 같습니다.'
    : !isCompleteSentence(sentence) ? '완전한 한 문장이 아닙니다 (두 문장이거나, 소문자로 시작하거나, 문장부호로 끝나지 않음). 문장을 고쳐 주세요.'
    : null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (problem) return;
    setIsSubmitting(true);
    setErrorMsg(null);
    try {
      // only a checked sentence goes to Anki; an edited sentence is checked again first
      let final = { sentence: sentence.trim(), translation: translation.trim() };
      if (checkedSentence !== final.sentence || !final.translation) {
        const card = await runCheck(final.sentence, answer.trim(), mistake.trim());
        if (!card) {
          setErrorMsg('문장·해설 검사를 통과하지 못해 등록하지 않았습니다. 문장을 고친 뒤 다시 시도하세요.');
          return;
        }
        final = card;
      }
      const res = await api.addGrammarCard({
        sentence: final.sentence, answer: answer.trim(), mistake: mistake.trim(),
        essay_id: essayId, fix_id: draft.fixId, translation: final.translation,
      });
      if (res.success) {
        if (draft.fixId) onRegistered?.(draft.fixId);
        onCardAdded(res.duplicate ? '이미 존재하는 문법 문장입니다 (중복 방지)' : 'Anki 문법 카드가 등록되었습니다!');
        onClose();
      }
    } catch (err: any) {
      setErrorMsg(err.message || 'Anki 문법 카드 등록에 실패했습니다.');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-xs flex items-center justify-center p-4">
      <div className="bg-white dark:bg-[#222222] rounded-2xl border border-stone-200 dark:border-[#383838] shadow-2xl max-w-lg w-full overflow-hidden animate-in fade-in zoom-in-95 duration-150">
        <div className="px-6 py-4 border-b border-stone-100 dark:border-[#2f2f2f] flex items-center justify-between bg-[#faf9f6] dark:bg-[#1a1a1a]">
          <div className="flex items-center space-x-2">
            <div className="p-1.5 rounded-lg bg-violet-50 dark:bg-violet-950/50 text-violet-700 dark:text-violet-300">
              <BookmarkPlus className="w-4 h-4" />
            </div>
            <div>
              <h3 className="text-sm font-bold text-stone-900 dark:text-[#f0f0f0]">문법 카드 등록</h3>
              <p className="text-[11px] text-stone-500 dark:text-stone-400">
                내가 쓴 틀린 형태가 오답 보기로 들어갑니다. 해설·설명·나머지 보기는 Anki Manager가 채웁니다.
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="text-stone-400 dark:text-stone-500 hover:text-stone-700 dark:hover:text-stone-200 p-1.5 rounded-lg hover:bg-stone-100 dark:hover:bg-[#2c2c2c] transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="px-6 py-4 space-y-3.5">
          {errorMsg && (
            <div className="p-2.5 bg-red-50 dark:bg-red-950/40 border border-red-200 dark:border-red-800/60 rounded-lg text-xs text-red-700 dark:text-red-300 flex items-center space-x-1.5">
              <AlertCircle className="w-4 h-4 shrink-0 text-red-500" />
              <span>{errorMsg}</span>
            </div>
          )}

          {/* Front preview, as the card template renders it */}
          <div className="bg-[#faf9f6] dark:bg-[#1a1a1a] border border-[#ebe9e1] dark:border-[#383838] rounded-lg p-3 space-y-2">
            <div className="text-[10px] font-bold uppercase text-stone-400 dark:text-stone-500">앞면 미리보기</div>
            <p className="font-serif text-sm text-stone-900 dark:text-stone-100 leading-relaxed">{blankedSentence(sentence, answer)}</p>
            <div className="flex flex-wrap gap-1.5 text-[11px] font-serif">
              {answer.trim() && (
                <span className="px-2 py-0.5 rounded bg-emerald-100/70 dark:bg-emerald-950/60 text-emerald-800 dark:text-emerald-300">{answer.trim()}</span>
              )}
              {mistake.trim() && (
                <span className="px-2 py-0.5 rounded bg-rose-100/70 dark:bg-rose-950/60 text-rose-700 dark:text-rose-300">{mistake.trim()}</span>
              )}
              <span className="px-2 py-0.5 rounded border border-dashed border-stone-300 dark:border-[#444444] text-stone-400 dark:text-stone-500 font-sans">
                + 오답 {mistake.trim() ? 2 : 3}개 자동 생성
              </span>
            </div>
            {draft.explanation && <p className="text-[11px] text-stone-500 dark:text-stone-400">💡 {draft.explanation}</p>}
          </div>

          <div>
            <label className="block text-[11px] font-semibold text-stone-700 dark:text-stone-300 mb-1">문장 (교정된 완성 문장)</label>
            <textarea rows={2} value={sentence} onChange={(e) => setSentence(e.target.value)} className={`${inputCls} resize-none`} />
          </div>
          <div>
            <label className="block text-[11px] font-semibold text-stone-700 dark:text-stone-300 mb-1">해설 (한국어 뜻)</label>
            <textarea rows={2} value={translation} onChange={(e) => setTranslation(e.target.value)} className={`${inputCls} resize-none font-sans`} placeholder={checkState === 'checking' ? '검사 중...' : ''} />
            <p className={`mt-1 text-[11px] ${checkState === 'failed' ? 'text-amber-700 dark:text-amber-300' : 'text-stone-500 dark:text-stone-400'}`}>
              {checkState === 'checking' ? '문장 문법과 해설을 검사하는 중... (Sonnet)'
                : checkState === 'ok' ? `✓ 문법·해설 검사 통과${checkNote ? ` · ${checkNote}` : ''}`
                : checkState === 'failed' ? `⚠ ${checkNote}` : ''}
            </p>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-[11px] font-semibold text-stone-700 dark:text-stone-300 mb-1">정답 (빈칸)</label>
              <input type="text" value={answer} onChange={(e) => setAnswer(e.target.value)} className={inputCls} />
            </div>
            <div>
              <label className="block text-[11px] font-semibold text-stone-700 dark:text-stone-300 mb-1">내가 쓴 형태 (오답 보기)</label>
              <input type="text" value={mistake} onChange={(e) => setMistake(e.target.value)} className={inputCls} />
            </div>
          </div>

          {problem && (
            <div className="text-[11px] text-amber-700 dark:text-amber-300 flex items-center space-x-1.5">
              <AlertCircle className="w-3.5 h-3.5 shrink-0" />
              <span>{problem}</span>
            </div>
          )}

          <div className="pt-3 border-t border-stone-100 dark:border-[#2f2f2f] flex items-center justify-between">
            <span className="text-[11px] font-mono text-stone-400 dark:text-stone-500 truncate">
              {ankiStatus?.connected ? (
                <span className="flex items-center space-x-1 text-emerald-600 dark:text-emerald-400 font-sans">
                  <CheckCircle2 className="w-3.5 h-3.5" />
                  <span>English::Grammar</span>
                </span>
              ) : (
                <span className="text-amber-600 dark:text-amber-400 font-sans">⚠️ Anki 연결 안 됨</span>
              )}
            </span>
            <div className="flex items-center space-x-2">
              <button
                type="button"
                onClick={onClose}
                className="px-3.5 py-2 text-xs font-medium text-stone-600 dark:text-stone-400 hover:bg-stone-100 dark:hover:bg-[#2c2c2c] rounded-lg transition-colors"
              >
                취소
              </button>
              <button
                type="submit"
                disabled={isSubmitting || !!problem || checkState === 'checking'}
                className="px-4 py-2 bg-stone-900 hover:bg-stone-800 dark:bg-stone-100 dark:hover:bg-white text-white dark:text-stone-900 text-xs font-semibold rounded-lg shadow-sm transition-all active:scale-95 disabled:opacity-50 flex items-center space-x-1.5"
              >
                {isSubmitting ? (
                  <span>오답 생성 · 등록 중...</span>
                ) : (
                  <>
                    <BookmarkPlus className="w-3.5 h-3.5" />
                    <span>Anki에 문법 카드 등록</span>
                  </>
                )}
              </button>
            </div>
          </div>
        </form>
      </div>
    </div>
  );
};
