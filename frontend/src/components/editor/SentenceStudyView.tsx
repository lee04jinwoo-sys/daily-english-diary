import React, { useState, useEffect } from 'react';
import { SentencePair } from '../../types/essay';
import { WordPopover } from '../common/WordPopover';
import { api } from '../../api/client';
import { 
  Volume2, 
  BookmarkPlus, 
  Sparkles, 
  Check, 
  Loader2,
  CheckCircle2,
  Pencil
} from 'lucide-react';

interface SentenceStudyViewProps {
  sentencePairs?: SentencePair[];
  originalContent: string;
  nativeContent: string;
  essayId?: string;
  onShowToast: (msg: string) => void;
}

interface EditableSentence {
  corrected: string;
  native: string;
  translation: string;
}

// Clean word for punctuation-independent comparison
const cleanWord = (w: string) => w.replace(/[.,/#!$%^&*;:{}=\-_`~()?"']/g, '').toLowerCase();

// Punctuation-aware word-level LCS Diff helper
function computeWordDiff(origStr: string, fixedStr: string) {
  const origWords = origStr.split(/\s+/).filter(Boolean);
  const fixedWords = fixedStr.split(/\s+/).filter(Boolean);

  const m = origWords.length;
  const n = fixedWords.length;
  const dp: number[][] = Array.from({ length: m + 1 }, () => Array(n + 1).fill(0));

  for (let i = 0; i < m; i++) {
    for (let j = 0; j < n; j++) {
      if (cleanWord(origWords[i]) === cleanWord(fixedWords[j])) {
        dp[i + 1][j + 1] = dp[i][j] + 1;
      } else {
        dp[i + 1][j + 1] = Math.max(dp[i + 1][j], dp[i][j + 1]);
      }
    }
  }

  const diffOps: { type: 'equal' | 'delete' | 'insert'; text: string }[] = [];
  let curI = m, curJ = n;
  while (curI > 0 || curJ > 0) {
    if (curI > 0 && curJ > 0 && cleanWord(origWords[curI - 1]) === cleanWord(fixedWords[curJ - 1])) {
      diffOps.unshift({ type: 'equal', text: origWords[curI - 1] });
      curI--;
      curJ--;
    } else if (curJ > 0 && (curI === 0 || dp[curI][curJ - 1] >= dp[curI - 1][curJ])) {
      diffOps.unshift({ type: 'insert', text: fixedWords[curJ - 1] });
      curJ--;
    } else if (curI > 0 && (curJ === 0 || dp[curI][curJ - 1] < dp[curI - 1][curJ])) {
      diffOps.unshift({ type: 'delete', text: origWords[curI - 1] });
      curI--;
    }
  }

  return diffOps;
}

export const SentenceStudyView: React.FC<SentenceStudyViewProps> = ({
  sentencePairs = [],
  originalContent,
  nativeContent,
  essayId = '',
  onShowToast,
}) => {
  const [playingKey, setPlayingKey] = useState<string | null>(null);
  const [savingKey, setSavingKey] = useState<string | null>(null);
  const [savedKeys, setSavedKeys] = useState<Set<string>>(new Set());
  const [existingSentences, setExistingSentences] = useState<Set<string>>(new Set());
  const [existingWords, setExistingWords] = useState<Set<string>>(new Set());

  // Editing state: keys that are currently in edit mode (e.g. "S1-corr", "S1-nat")
  const [editingKey, setEditingKey] = useState<string | null>(null);

  // Editable local state for sentences
  const [editedData, setEditedData] = useState<Record<string, EditableSentence>>({});

  // Word Popover State
  const [popoverState, setPopoverState] = useState<{
    word: string;
    context: string;
    position: { x: number; y: number } | null;
  }>({
    word: '',
    context: '',
    position: null,
  });

  // Build fallback pairs if sentencePairs is empty
  const pairs: SentencePair[] = React.useMemo(() => {
    if (sentencePairs && sentencePairs.length > 0) {
      return sentencePairs;
    }
    if (!nativeContent.trim()) return [];

    const origSentences = originalContent.match(/[^.!?]+[.!?]+/g) || [originalContent];
    const nativeSentences = nativeContent.match(/[^.!?]+[.!?]+/g) || [nativeContent];

    return nativeSentences.map((nat, idx) => {
      const orig = origSentences[idx]?.trim() || '';
      return {
        id: `S${idx + 1}`,
        index: idx + 1,
        original: orig,
        corrected: orig,
        native: nat.trim(),
        translation: '',
        explanation: '',
        vocab: [],
      };
    });
  }, [sentencePairs, originalContent, nativeContent]);

  // Reset editing data whenever the essay or pairs change to prevent cross-essay state leakage
  useEffect(() => {
    setEditedData({});
    setEditingKey(null);
    setSavedKeys(new Set());
  }, [essayId]);

  // Sync edited data with pairs
  useEffect(() => {
    const initial: Record<string, EditableSentence> = {};
    pairs.forEach((p) => {
      initial[p.id] = {
        corrected: p.corrected || p.original,
        native: p.native,
        translation: p.translation,
      };
    });
    if (Object.keys(initial).length > 0) {
      setEditedData(initial);
    }
  }, [pairs, essayId]);

  // Fast Anki cross-check for all sentences and words in this essay
  useEffect(() => {
    if (!pairs || pairs.length === 0) return;
    const sList: string[] = [];
    const wList: string[] = [];
    pairs.forEach((p) => {
      if (p.corrected) sList.push(p.corrected);
      if (p.native) sList.push(p.native);
      if (p.original) sList.push(p.original);
      (p.vocab || []).forEach((v) => {
        if (v.word) wList.push(v.word);
      });
    });

    api.checkExistingCards({ sentences: sList, words: wList })
      .then((res) => {
        if (res.existing_sentences && res.existing_sentences.length > 0) {
          setExistingSentences(new Set(res.existing_sentences.map((s) => s.trim().toLowerCase())));
        }
        if (res.existing_words && res.existing_words.length > 0) {
          setExistingWords(new Set(res.existing_words.map((w) => w.trim().toLowerCase())));
        }
      })
      .catch(() => {});
  }, [pairs, essayId]);

  const handleFieldChange = (id: string, field: keyof EditableSentence, value: string) => {
    setEditedData((prev) => ({
      ...prev,
      [id]: {
        ...(prev[id] || { corrected: '', native: '', translation: '' }),
        [field]: value,
      },
    }));
  };

  // Play browser TTS audio
  const handlePlayAudio = (key: string, text: string) => {
    if (!window.speechSynthesis) return;
    window.speechSynthesis.cancel();

    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = 'en-US';
    utterance.rate = 0.95;

    utterance.onstart = () => setPlayingKey(key);
    utterance.onend = () => setPlayingKey(null);
    utterance.onerror = () => setPlayingKey(null);

    window.speechSynthesis.speak(utterance);
  };

  // Direct 1-Click Anki Sentence Registration (no deletion)
  const handleDirectAddSentence = async (key: string, sentenceText: string, translationText: string) => {
    const cleanSentence = sentenceText.trim();
    if (!cleanSentence) {
      onShowToast('영어 문장이 비어있습니다.');
      return;
    }

    const isAlreadySaved = savedKeys.has(key) || existingSentences.has(cleanSentence.toLowerCase());

    setSavingKey(key);
    try {
      if (isAlreadySaved) {
        onShowToast('이미 Anki에 있는 문장입니다.');
      } else {
        // Add to Anki
        const res = await api.addSentenceCard({
          sentence: cleanSentence,
          translation: translationText.trim(),
          deck_name: '1. Language::1.1. English::Sentence',
          model_name: 'English Sentence',
        });

        if (res.success) {
          setSavedKeys((prev) => new Set(prev).add(key));
          setExistingSentences((prev) => new Set(prev).add(cleanSentence.toLowerCase()));
          onShowToast(res.duplicate ? '이미 Anki에 등록된 문장입니다 (중복 방지)' : 'Anki 등록 완료! 🎉');
        } else {
          onShowToast('Anki 앱이 켜져 있는지 확인해주세요! (상단 Anki 상태 확인)');
        }
      }
    } catch (e: any) {
      onShowToast(`Anki 처리 실패: ${e.message}`);
    } finally {
      setSavingKey(null);
    }
  };

  // Open Popover for a clicked token
  const handleWordClick = (word: string, context: string, e: React.MouseEvent) => {
    e.stopPropagation();
    const clean = word.replace(/[.,/#!$%^&*;:{}=\-_`~()?"']/g, '').trim();
    if (!clean || clean.length < 2) return;

    setPopoverState({
      word: clean,
      context,
      position: { x: e.clientX, y: e.clientY },
    });
  };

  // Handle Drag / Selection Lookup
  const handleMouseUp = (context: string) => {
    const selection = window.getSelection();
    if (!selection || selection.isCollapsed) return;

    const selectedText = selection.toString().trim();
    if (selectedText.length >= 2) {
      const range = selection.getRangeAt(0);
      const rect = range.getBoundingClientRect();
      setPopoverState({
        word: selectedText,
        context,
        position: { x: rect.left + rect.width / 2, y: rect.bottom },
      });
    }
  };

  // Render clickable tokens
  const renderInteractiveSentence = (text: string, contextSentence: string) => {
    if (!text) return null;
    const tokens = text.split(/(\s+)/);

    return (
      <span onMouseUp={() => handleMouseUp(contextSentence)} className="leading-relaxed">
        {tokens.map((token, idx) => {
          if (/^\s+$/.test(token)) {
            return token;
          }
          const clean = token.replace(/[.,/#!$%^&*;:{}=\-_`~()?"']/g, '').trim();
          const isWordInAnki = existingWords.has(clean.toLowerCase());
          return (
            <span
              key={idx}
              onClick={(e) => handleWordClick(clean, contextSentence, e)}
              className={`rounded-xs cursor-pointer transition-colors ${
                isWordInAnki
                  ? 'border-b border-dotted border-emerald-500 font-medium hover:bg-emerald-100 dark:hover:bg-emerald-950/60'
                  : 'hover:bg-blue-100 dark:hover:bg-blue-900/60 hover:text-blue-900 dark:hover:text-blue-200'
              }`}
              title={isWordInAnki ? 'Anki에 등록된 단어 (클릭하여 확인)' : '단어 사전 & Anki 등록'}
            >
              {token}
            </span>
          );
        })}
      </span>
    );
  };

  // Precision Diff for draft: only strike through actual deleted/wrong words
  const renderDraftWithPrecisionDiff = (origStr: string, fixedStr: string, contextSentence: string) => {
    const diffOps = computeWordDiff(origStr, fixedStr);

    return (
      <span onMouseUp={() => handleMouseUp(contextSentence)} className="leading-relaxed">
        {diffOps
          .filter((op) => op.type !== 'insert')
          .map((op, idx) => {
            if (op.type === 'delete') {
              return (
                <span
                  key={idx}
                  onClick={(e) => handleWordClick(op.text, contextSentence, e)}
                  className="inline-block line-through decoration-red-500 decoration-2 font-medium text-red-600 dark:text-red-400 bg-red-100/60 dark:bg-red-950/70 px-1 rounded-sm cursor-pointer mx-0.5"
                  title="틀린 부분 (클릭하여 단어 사전 확인)"
                >
                  {op.text}
                </span>
              );
            }
            return (
              <span
                key={idx}
                onClick={(e) => handleWordClick(op.text, contextSentence, e)}
                className="hover:bg-stone-200/60 dark:hover:bg-[#333333] cursor-pointer rounded-xs px-0.5 transition-colors"
              >
                {op.text}{' '}
              </span>
            );
          })}
      </span>
    );
  };

  if (pairs.length === 0) {
    return (
      <div className="bg-white dark:bg-[#1f1f1f] rounded-2xl border border-stone-200 dark:border-[#2f2f2f] p-10 text-center space-y-3">
        <Sparkles className="w-8 h-8 text-blue-500 mx-auto animate-pulse" />
        <h3 className="text-sm font-bold text-stone-900 dark:text-[#f0f0f0]">
          에세이 작성 후 [AI 첨삭 받기]를 실행해주세요.
        </h3>
      </div>
    );
  }

  return (
    <div className="space-y-4 pb-16 max-w-3xl mx-auto w-full">
      {/* Floating Word Popover */}
      {popoverState.position && (
        <WordPopover
          word={popoverState.word}
          context={popoverState.context}
          position={popoverState.position}
          onClose={() => setPopoverState({ word: '', context: '', position: null })}
          onShowToast={onShowToast}
        />
      )}

      {/* Sentence Cards List */}
      <div className="space-y-4">
        {pairs.map((sp) => {
          const current = editedData[sp.id] || {
            corrected: sp.corrected || sp.original,
            native: sp.native,
            translation: sp.translation,
          };

          const corrKey = `${sp.id}-corr`;
          const natKey = `${sp.id}-nat`;

          const isCorrPlaying = playingKey === corrKey;
          const isNatPlaying = playingKey === natKey;

          const isCorrSaving = savingKey === corrKey;
          const isNatSaving = savingKey === natKey;

          const isCorrSaved = savedKeys.has(corrKey) || existingSentences.has(current.corrected.trim().toLowerCase());
          const isNatSaved = savedKeys.has(natKey) || existingSentences.has(current.native.trim().toLowerCase());

          const isCorrEditing = editingKey === corrKey;
          const isNatEditing = editingKey === natKey;

          const cleanOrig = sp.original.trim().replace(/\s+/g, ' ');
          const cleanCorr = current.corrected.trim().replace(/\s+/g, ' ');
          const cleanNat = current.native.trim().replace(/\s+/g, ' ');

          // Are all versions identical (perfect sentence)?
          const isAllIdentical = (cleanOrig === cleanCorr) && (cleanCorr === cleanNat);
          const isOriginalCorrect = (cleanOrig === cleanCorr);

          return (
            <div
              key={sp.id}
              className="bg-white dark:bg-[#1e1e1e] rounded-2xl border border-stone-200 dark:border-[#2f2f2f] p-5 shadow-xs transition-all space-y-3.5"
            >
              {/* Header: #Number & Korean Translation Input inline */}
              <div className="flex items-start space-x-3 pb-2 border-b border-stone-100 dark:border-[#2a2a2a]">
                <span className="text-xs font-bold text-stone-500 dark:text-stone-400 font-mono shrink-0 pt-0.5">
                  #{sp.index}
                </span>

                {/* Auto-growing Textarea for Translation */}
                <textarea
                  rows={1}
                  value={current.translation}
                  ref={(el) => {
                    if (el) {
                      el.style.height = 'auto';
                      el.style.height = `${el.scrollHeight}px`;
                    }
                  }}
                  onChange={(e) => {
                    e.target.style.height = 'auto';
                    e.target.style.height = `${e.target.scrollHeight}px`;
                    handleFieldChange(sp.id, 'translation', e.target.value);
                  }}
                  placeholder="한국어 해석 입력..."
                  className="flex-1 bg-transparent text-xs font-medium text-stone-700 dark:text-stone-300 placeholder:text-stone-400 dark:placeholder:text-stone-600 outline-none resize-none overflow-hidden leading-relaxed"
                />

                <div className="flex items-center space-x-1.5 shrink-0 pt-0.5">
                  {(isCorrSaved || isNatSaved) && (
                    <span className="inline-flex items-center space-x-1 text-[10px] bg-emerald-100 dark:bg-emerald-950/80 text-emerald-800 dark:text-emerald-300 px-2 py-0.5 rounded-full font-semibold border border-emerald-300/60 dark:border-emerald-700/60">
                      <Check className="w-3 h-3 text-emerald-600 dark:text-emerald-400" />
                      <span>Anki 등록됨</span>
                    </span>
                  )}
                  {isOriginalCorrect && (
                    <span className="inline-flex items-center space-x-1 text-[11px] text-emerald-600 dark:text-emerald-400 font-medium">
                      <CheckCircle2 className="w-3.5 h-3.5" />
                      <span>정확한 문장</span>
                    </span>
                  )}
                </div>
              </div>

              {/* CASE 1: Completely Identical Sentence (Single Minimal Row!) */}
              {isAllIdentical ? (
                <div className="flex items-start justify-between gap-4 pt-1">
                  <div className="flex-1 font-serif text-base text-stone-900 dark:text-stone-100 leading-relaxed break-words">
                    {isCorrEditing ? (
                      <textarea
                        autoFocus
                        rows={1}
                        value={current.corrected}
                        ref={(el) => {
                          if (el) {
                            el.style.height = 'auto';
                            el.style.height = `${el.scrollHeight}px`;
                          }
                        }}
                        onBlur={() => setEditingKey(null)}
                        onKeyDown={(e) => {
                          if (e.key === 'Enter' && !e.shiftKey) {
                            e.preventDefault();
                            setEditingKey(null);
                          }
                        }}
                        onChange={(e) => {
                          e.target.style.height = 'auto';
                          e.target.style.height = `${e.target.scrollHeight}px`;
                          handleFieldChange(sp.id, 'corrected', e.target.value);
                          handleFieldChange(sp.id, 'native', e.target.value);
                        }}
                        className="w-full bg-stone-50 dark:bg-[#262626] border border-stone-300 dark:border-[#404040] rounded-lg p-2 font-serif text-base outline-none resize-none overflow-hidden"
                      />
                    ) : (
                      <div className="flex items-center space-x-2 group">
                        <span className="flex-1">
                          {renderInteractiveSentence(current.corrected, current.corrected)}
                        </span>
                        <button
                          onClick={() => setEditingKey(corrKey)}
                          className="opacity-0 group-hover:opacity-100 text-stone-400 hover:text-stone-700 dark:hover:text-stone-200 p-1 rounded transition-opacity"
                          title="문장 직접 수정"
                        >
                          <Pencil className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    )}
                  </div>

                  <div className="flex items-center space-x-2 shrink-0 pt-0.5">
                    <button
                      onClick={() => handlePlayAudio(corrKey, current.corrected)}
                      className={`p-2 rounded-lg text-xs transition-all ${
                        isCorrPlaying
                          ? 'bg-emerald-600 text-white animate-pulse'
                          : 'bg-stone-100 dark:bg-[#2a2a2a] text-stone-600 dark:text-stone-300 hover:bg-stone-200 dark:hover:bg-[#333333]'
                      }`}
                      title="발음 듣기"
                    >
                      <Volume2 className="w-4 h-4" />
                    </button>

                    <button
                      onClick={() => handleDirectAddSentence(corrKey, current.corrected, current.translation)}
                      disabled={isCorrSaving}
                      className={`flex items-center space-x-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition-all shadow-xs active:scale-95 border ${
                        isCorrSaved
                          ? 'bg-emerald-100 dark:bg-emerald-950 text-emerald-800 dark:text-emerald-300 border-emerald-300 dark:border-emerald-700'
                          : 'bg-stone-900 hover:bg-stone-800 dark:bg-stone-100 dark:hover:bg-white text-white dark:text-stone-900 border-transparent'
                      }`}
                      title={isCorrSaved ? '이미 Anki에 있음' : 'Anki 문장 카드로 저장'}
                    >
                      {isCorrSaving ? (
                        <Loader2 className="w-3.5 h-3.5 animate-spin" />
                      ) : isCorrSaved ? (
                        <Check className="w-3.5 h-3.5" />
                      ) : (
                        <BookmarkPlus className="w-3.5 h-3.5" />
                      )}
                      <span>{isCorrSaving ? '처리 중' : isCorrSaved ? '등록됨 ✓ (취소)' : '⭐ Anki 등록'}</span>
                    </button>
                  </div>
                </div>
              ) : (
                /* CASE 2: Corrections or Native Polish exist */
                <div className="space-y-3 pt-1">
                  {/* Original Draft with PRECISION DIFF (only strike through wrong words!) */}
                  {!isOriginalCorrect && sp.original && (
                    <div className="text-xs text-stone-600 dark:text-stone-300 font-serif leading-relaxed bg-stone-50 dark:bg-[#191919] p-2.5 rounded-lg border border-stone-200/60 dark:border-[#2b2b2b] flex items-start space-x-2">
                      <span className="text-[10px] uppercase font-bold text-stone-400 dark:text-stone-500 shrink-0 mt-0.5">
                        초안
                      </span>
                      <div className="flex-1 break-words">
                        {renderDraftWithPrecisionDiff(sp.original, current.corrected, sp.original)}
                      </div>
                    </div>
                  )}

                  {/* Fixed Sentence (Interactive Token View + Pencil Inline Edit) */}
                  <div className="flex items-start justify-between gap-3 p-3 rounded-xl bg-emerald-50/40 dark:bg-emerald-950/20 border border-emerald-100 dark:border-emerald-900/30">
                    <div className="flex-1 space-y-1 min-w-0">
                      <div className="flex items-center space-x-2">
                        <span className="text-[10px] font-bold text-emerald-700 dark:text-emerald-400 uppercase tracking-wider">
                          Fixed (교정본)
                        </span>
                        <button
                          onClick={() => setEditingKey(isCorrEditing ? null : corrKey)}
                          className="text-emerald-600/70 hover:text-emerald-800 dark:text-emerald-400/70 dark:hover:text-emerald-200 p-0.5 rounded transition-colors"
                          title="문장 직접 수정하기"
                        >
                          <Pencil className="w-2.5 h-2.5" />
                        </button>
                      </div>

                      {isCorrEditing ? (
                        <textarea
                          autoFocus
                          rows={1}
                          value={current.corrected}
                          ref={(el) => {
                            if (el) {
                              el.style.height = 'auto';
                              el.style.height = `${el.scrollHeight}px`;
                            }
                          }}
                          onBlur={() => setEditingKey(null)}
                          onKeyDown={(e) => {
                            if (e.key === 'Enter' && !e.shiftKey) {
                              e.preventDefault();
                              setEditingKey(null);
                            }
                          }}
                          onChange={(e) => {
                            e.target.style.height = 'auto';
                            e.target.style.height = `${e.target.scrollHeight}px`;
                            handleFieldChange(sp.id, 'corrected', e.target.value);
                          }}
                          className="w-full bg-white dark:bg-[#1a1a1a] border border-emerald-300 dark:border-emerald-700 rounded-lg p-2 font-serif text-sm font-medium text-emerald-950 dark:text-emerald-100 outline-none resize-none overflow-hidden leading-relaxed break-words"
                        />
                      ) : (
                        <div className="font-serif text-sm font-medium text-emerald-950 dark:text-emerald-100 leading-relaxed break-words">
                          {renderInteractiveSentence(current.corrected, current.corrected)}
                        </div>
                      )}
                    </div>

                    <div className="flex items-center space-x-1.5 shrink-0 pt-0.5">
                      <button
                        onClick={() => handlePlayAudio(corrKey, current.corrected)}
                        className={`p-1.5 rounded-md text-xs transition-all ${
                          isCorrPlaying
                            ? 'bg-emerald-600 text-white'
                            : 'bg-white dark:bg-[#282828] text-emerald-800 dark:text-emerald-300 border border-emerald-200 dark:border-emerald-800'
                        }`}
                        title="발음 듣기"
                      >
                        <Volume2 className="w-3.5 h-3.5" />
                      </button>

                      <button
                        onClick={() => handleDirectAddSentence(corrKey, current.corrected, current.translation)}
                        disabled={isCorrSaving}
                        className={`flex items-center space-x-1 px-2.5 py-1.5 rounded-lg text-xs font-semibold transition-all shadow-xs active:scale-95 border ${
                          isCorrSaved
                            ? 'bg-emerald-100 dark:bg-emerald-950 text-emerald-800 dark:text-emerald-300 border-emerald-300 dark:border-emerald-700'
                            : 'bg-emerald-600 hover:bg-emerald-700 text-white border-transparent'
                        }`}
                        title={isCorrSaved ? '이미 Anki에 있음' : 'Anki 교정본 카드로 저장'}
                      >
                        {isCorrSaving ? (
                          <Loader2 className="w-3.5 h-3.5 animate-spin" />
                        ) : isCorrSaved ? (
                          <Check className="w-3.5 h-3.5" />
                        ) : (
                          <BookmarkPlus className="w-3.5 h-3.5" />
                        )}
                        <span>{isCorrSaving ? '처리 중' : isCorrSaved ? '등록됨 ✓ (취소)' : '⭐ 교정본 Anki'}</span>
                      </button>
                    </div>
                  </div>

                  {/* Native Sentence (Level +1) (Interactive Token View + Pencil Inline Edit) */}
                  {cleanCorr !== cleanNat && (
                    <div className="flex items-start justify-between gap-3 p-3 rounded-xl bg-blue-50/40 dark:bg-blue-950/20 border border-blue-100 dark:border-blue-900/30">
                      <div className="flex-1 space-y-1 min-w-0">
                        <div className="flex items-center space-x-2">
                          <span className="text-[10px] font-bold text-blue-700 dark:text-blue-400 uppercase tracking-wider">
                            Native (Level +1)
                          </span>
                          <button
                            onClick={() => setEditingKey(isNatEditing ? null : natKey)}
                            className="text-blue-600/70 hover:text-blue-800 dark:text-blue-400/70 dark:hover:text-blue-200 p-0.5 rounded transition-colors"
                            title="문장 직접 수정하기"
                          >
                            <Pencil className="w-2.5 h-2.5" />
                          </button>
                        </div>

                        {isNatEditing ? (
                          <textarea
                            autoFocus
                            rows={1}
                            value={current.native}
                            ref={(el) => {
                              if (el) {
                                el.style.height = 'auto';
                                el.style.height = `${el.scrollHeight}px`;
                              }
                            }}
                            onBlur={() => setEditingKey(null)}
                            onKeyDown={(e) => {
                              if (e.key === 'Enter' && !e.shiftKey) {
                                e.preventDefault();
                                setEditingKey(null);
                              }
                            }}
                            onChange={(e) => {
                              e.target.style.height = 'auto';
                              e.target.style.height = `${e.target.scrollHeight}px`;
                              handleFieldChange(sp.id, 'native', e.target.value);
                            }}
                            className="w-full bg-white dark:bg-[#1a1a1a] border border-blue-300 dark:border-blue-700 rounded-lg p-2 font-serif text-sm font-medium text-blue-950 dark:text-blue-100 outline-none resize-none overflow-hidden leading-relaxed break-words"
                          />
                        ) : (
                          <div className="font-serif text-sm font-medium text-blue-950 dark:text-blue-100 leading-relaxed break-words">
                            {renderInteractiveSentence(current.native, current.native)}
                          </div>
                        )}
                      </div>

                      <div className="flex items-center space-x-1.5 shrink-0 pt-0.5">
                        <button
                          onClick={() => handlePlayAudio(natKey, current.native)}
                          className={`p-1.5 rounded-md text-xs transition-all ${
                            isNatPlaying
                              ? 'bg-blue-600 text-white'
                              : 'bg-white dark:bg-[#282828] text-blue-800 dark:text-blue-300 border border-blue-200 dark:border-blue-800'
                          }`}
                          title="발음 듣기"
                        >
                          <Volume2 className="w-3.5 h-3.5" />
                        </button>

                        <button
                          onClick={() => handleDirectAddSentence(natKey, current.native, current.translation)}
                          disabled={isNatSaving}
                          className={`flex items-center space-x-1 px-2.5 py-1.5 rounded-lg text-xs font-semibold transition-all shadow-xs active:scale-95 border ${
                            isNatSaved
                              ? 'bg-blue-100 dark:bg-blue-950 text-blue-800 dark:text-blue-300 border-blue-300 dark:border-blue-700'
                              : 'bg-blue-600 hover:bg-blue-700 text-white border-transparent'
                          }`}
                          title={isNatSaved ? '이미 Anki에 있음' : 'Anki 원어민 카드로 저장'}
                        >
                          {isNatSaving ? (
                            <Loader2 className="w-3.5 h-3.5 animate-spin" />
                          ) : isNatSaved ? (
                            <Check className="w-3.5 h-3.5" />
                          ) : (
                            <Sparkles className="w-3.5 h-3.5" />
                          )}
                          <span>{isNatSaving ? '처리 중' : isNatSaved ? '등록됨 ✓ (취소)' : '✨ 원어민 Anki'}</span>
                        </button>
                      </div>
                    </div>
                  )}

                  {/* Native / Revision Explanation & Nuance Note */}
                  {sp.explanation && (
                    <div className="flex items-start space-x-2.5 text-xs text-stone-600 dark:text-stone-300 bg-amber-50/60 dark:bg-[#1e1c16] border border-amber-200/70 dark:border-amber-900/40 p-3 rounded-xl leading-relaxed">
                      <Sparkles className="w-3.5 h-3.5 text-amber-600 dark:text-amber-400 shrink-0 mt-0.5" />
                      <div className="flex-1 space-y-0.5 font-sans">
                        <span className="font-semibold text-amber-900 dark:text-amber-300 mr-1.5">
                          💡 뉘앙스 & 수정 이유:
                        </span>
                        <span className="text-stone-700 dark:text-stone-300">
                          {sp.explanation}
                        </span>
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
};
