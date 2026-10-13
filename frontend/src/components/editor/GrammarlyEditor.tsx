import React, { useState, useRef, useEffect } from 'react';
import { SuggestionItem, ReviewResponse, CardType, Essay, SentencePair, ReviewPart, REVIEW_PARTS } from '../../types/essay';
import { SuggestionCard } from './SuggestionCard';
import { CompareTabs } from './CompareTabs';
import { SentenceStudyView } from './SentenceStudyView';
import { WordPopover } from '../common/WordPopover';
import { EssayPromptHeader } from './EssayPromptHeader';
import { EssayFeedback } from './EssayFeedback';
import { useWritingTimer, formatDuration, IDLE_LIMIT_MS } from '../../hooks/useWritingTimer';
import { api } from '../../api/client';
import { GrammarCardDraft, correctedSentence, grammarDraft, isGrammarFix } from '../../utils/cardText';
import { 
  Sparkles, 
  BookOpen, 
  CheckCircle, 
  BookmarkPlus, 
  PenLine, 
  Eye, 
  Copy, 
  Check,
  Loader2,
  Timer,
  Pause
} from 'lucide-react';

interface GrammarlyEditorProps {
  essay: Essay;
  onPromptChange: (prompt: string) => void;
  onRevise: () => void;
  previousBand?: number | null;
  content: string;
  onContentChange: (content: string) => void;
  onReview: () => void;
  isReviewing: boolean;
  pendingParts: ReviewPart[];
  reviewResult: ReviewResponse | null;
  suggestions: SuggestionItem[];
  onOpenAnkiModal: (cardType: CardType, text: string, context?: string) => void;
  onOpenGrammarModal: (draft: GrammarCardDraft) => void;
  onShowToast: (msg: string) => void;
}

export const GrammarlyEditor: React.FC<GrammarlyEditorProps> = ({
  essay,
  onPromptChange,
  onRevise,
  previousBand,
  content,
  onContentChange,
  onReview,
  isReviewing,
  pendingParts,
  reviewResult,
  suggestions,
  onOpenAnkiModal,
  onOpenGrammarModal,
  onShowToast,
}) => {
  const essayId = essay.id;
  const timer = useWritingTimer(essay.id, essay.writing_seconds);

  const [activeSuggestionId, setActiveSuggestionId] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<'editor' | 'sentence' | 'native'>('editor');
  // Sentence pairs are generated on demand the first time the tab is opened.
  const [lazyPairs, setLazyPairs] = useState<SentencePair[] | null>(null);
  const [pairsState, setPairsState] = useState<'idle' | 'loading' | 'error'>('idle');
  const storedPairs = reviewResult?.sentence_pairs || [];
  const sentencePairs = storedPairs.length > 0 ? storedPairs : lazyPairs || [];

  useEffect(() => {
    setLazyPairs(null);
    setPairsState('idle');
  }, [reviewResult]);

  useEffect(() => {
    // During a review nothing is saved yet, so there is nothing to build pairs from.
    if (activeTab !== 'sentence' || !reviewResult || isReviewing || storedPairs.length > 0 || lazyPairs || pairsState !== 'idle') return;
    setPairsState('loading');
    api.getSentencePairs(essay.id)
      .then((pairs) => {
        setLazyPairs(pairs);
        setPairsState('idle');
      })
      .catch((e) => {
        setPairsState('error');
        onShowToast(`문장별 대조를 만들지 못했습니다: ${e.message}`);
      });
  }, [activeTab, reviewResult, isReviewing, storedPairs.length, lazyPairs, pairsState, essay.id, onShowToast]);
  const [isEditMode, setIsEditMode] = useState<boolean>(true);
  const [copied, setCopied] = useState<string | null>(null);
  const [savingVocabIndex, setSavingVocabIndex] = useState<number | null>(null);
  const [savedVocabIndexes, setSavedVocabIndexes] = useState<Set<number>>(new Set());

  // Word Popover State for Tab 3
  const [popoverState, setPopoverState] = useState<{
    word: string;
    context: string;
    position: { x: number; y: number } | null;
  }>({
    word: '',
    context: '',
    position: null,
  });

  const suggestionListRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const wordCount = content.trim() ? content.trim().split(/\s+/).length : 0;
  const mustFixPer100 = (() => {
    if (!reviewResult) return '0';
    const words = reviewResult.original_text.trim().split(/\s+/).filter(Boolean).length || 1;
    const mustFix = (reviewResult.suggestions || []).filter((s) => (s.tier || 'accuracy') === 'accuracy').length;
    return ((mustFix / words) * 100).toFixed(1);
  })();

  // Cross-check Key Expressions against Anki
  useEffect(() => {
    if (!reviewResult?.key_expressions || reviewResult.key_expressions.length === 0) return;
    const words = reviewResult.key_expressions.map((k) => normalizeVocabPlaceholder(k.expression));
    api.checkExistingCards({ sentences: [], words })
      .then((res) => {
        if (res.existing_words && res.existing_words.length > 0) {
          const matched = new Set(res.existing_words.map((w) => w.toLowerCase()));
          const newSaved = new Set<number>();
          reviewResult.key_expressions.forEach((k, idx) => {
            const norm = normalizeVocabPlaceholder(k.expression).toLowerCase();
            if (matched.has(norm) || matched.has(k.expression.toLowerCase())) {
              newSaved.add(idx);
            }
          });
          setSavedVocabIndexes(newSaved);
        }
      })
      .catch(() => {});
  }, [reviewResult?.key_expressions, essayId]);

  const handleCopy = (text: string, label: string) => {
    navigator.clipboard.writeText(text);
    setCopied(label);
    setTimeout(() => setCopied(null), 2000);
  };

  // Prevent macOS double space turning into period
  const handleTextareaKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === ' ' && textareaRef.current) {
      const selStart = textareaRef.current.selectionStart;
      if (selStart > 0 && content[selStart - 1] === ' ') {
        e.preventDefault();
        timer.markActivity();
        const newContent = content.slice(0, selStart) + ' ' + content.slice(selStart);
        onContentChange(newContent);
        setTimeout(() => {
          if (textareaRef.current) {
            textareaRef.current.selectionStart = selStart + 1;
            textareaRef.current.selectionEnd = selStart + 1;
          }
        }, 0);
      }
    }
  };

  const normalizeVocabPlaceholder = (word: string): string => {
    if (!word) return '';
    let res = word
      .replace(/~\s*-?ing\b/gi, 'V-ing')
      .replace(/~\s*동사원형\b/gi, 'V')
      .replace(/~\s*원형\b/gi, 'V')
      .replace(/\bdoing\s+(something|sth)\b/gi, 'V-ing')
      .replace(/\bdoing\b/gi, 'V-ing')
      .replace(/~\b/g, 'A');

    const placeholders = ['A', 'B', 'C'];
    let placeholderIdx = 0;
    res = res.replace(/\b(someone|somebody|sb|sbd|something|sth)\b/gi, () => {
      if (placeholderIdx < placeholders.length) {
        return placeholders[placeholderIdx++];
      }
      return 'A';
    });
    return res.trim();
  };

  const handleDirectAddVocab = async (k: any, idx: number) => {
    setSavingVocabIndex(idx);
    const normalizedWord = normalizeVocabPlaceholder(k.expression);
    const isAlreadySaved = savedVocabIndexes.has(idx);

    try {
      if (isAlreadySaved) {
        onShowToast(`'${normalizedWord}'은(는) 이미 Anki에 있습니다.`);
      } else {
        // Add to Anki
        const res = await api.addVocabCard({
          word: normalizedWord,
          meaning: k.meaning,
          pos: k.pos || 'idiom',
          synonyms: k.synonyms || '',
          example: k.example || '',
          explanation: k.explanation || '',
        });
        if (res.success) {
          setSavedVocabIndexes((prev) => new Set(prev).add(idx));
          onShowToast(res.duplicate ? '이미 Anki에 등록된 표현입니다.' : `'${normalizedWord}' Anki 단어 카드가 저장되었습니다! 🎉`);
        } else {
          onShowToast('서버 Anki에 연결되어 있지 않습니다 (상단 Anki 상태 확인)');
        }
      }
    } catch (e: any) {
      onShowToast(`Anki 처리 실패: ${e.message}`);
    } finally {
      setSavingVocabIndex(null);
    }
  };

  const handleWordClickNative = (word: string, context: string, e: React.MouseEvent) => {
    e.stopPropagation();
    const clean = word.replace(/[.,/#!$%^&*;:{}=\-_`~()?"']/g, '').trim();
    if (!clean || clean.length < 2) return;
    setPopoverState({
      word: clean,
      context,
      position: { x: e.clientX, y: e.clientY },
    });
  };

  const renderInteractiveNativeText = (text: string) => {
    if (!text) return null;
    const tokens = text.split(/(\s+)/);
    return (
      <span>
        {tokens.map((token, idx) => {
          if (/^\s+$/.test(token)) {
            return token;
          }
          const clean = token.replace(/[.,/#!$%^&*;:{}=\-_`~()?"']/g, '').trim();
          return (
            <span
              key={idx}
              onClick={(e) => handleWordClickNative(clean, text, e)}
              className="hover:bg-indigo-100 dark:hover:bg-indigo-900/60 hover:text-indigo-900 dark:hover:text-indigo-200 rounded-xs cursor-pointer transition-colors"
              title="단어 사전 & Anki 등록"
            >
              {token}
            </span>
          );
        })}
      </span>
    );
  };

  // Auto-resize textarea height to fit content
  useEffect(() => {
    if (isEditMode && textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = `${Math.max(280, textareaRef.current.scrollHeight)}px`;
    }
  }, [content, isEditMode]);

  // When new review arrives, switch to review mode to show clean highlights
  useEffect(() => {
    if (reviewResult && suggestions.length > 0) {
      setIsEditMode(false);
    } else {
      setIsEditMode(true);
    }
  }, [reviewResult, suggestions.length]);

  // Filtered suggestions for side panel (strictly matching current content)
  // Corrections are a record of what was wrong: they are never applied to the text or hidden.
  // Highlights appear only where the original phrase is still in the text.
  const pendingSuggestions = suggestions.filter((s) => content.includes(s.original_phrase));

  // The learner's whole sentence (as reviewed) with one fix applied, for sentence cards.
  const sentenceForCard = (sg: SuggestionItem): string => correctedSentence(reviewResult?.original_text || '', sg);

  // Render Clean Interactive Document with Grammarly Highlights
  const renderInteractiveDocument = () => {
    if (!content.trim()) {
      return (
        <div 
          onClick={() => setIsEditMode(true)}
          className="text-stone-400 dark:text-stone-500 font-serif italic py-10 cursor-text"
        >
          아직 작성한 내용이 없습니다. 클릭하여 에세이를 써보세요.
        </div>
      );
    }

    if (pendingSuggestions.length === 0) {
      return (
        <div className="font-serif text-base text-[#2c2b28] dark:text-[#e4e4e4] leading-relaxed whitespace-pre-wrap">
          {content}
        </div>
      );
    }

    // Sort valid suggestions - STRICT VERIFICATION OF CONTENT SLICE!
    const validSuggestions = pendingSuggestions
      .filter((s) => (
        s.start_idx >= 0 &&
        s.end_idx > s.start_idx &&
        s.end_idx <= content.length &&
        content.slice(s.start_idx, s.end_idx) === s.original_phrase
      ))
      .sort((a, b) => a.start_idx - b.start_idx);

    if (validSuggestions.length === 0) {
      return (
        <div className="font-serif text-base text-[#2c2b28] dark:text-[#e4e4e4] leading-relaxed whitespace-pre-wrap">
          {content}
        </div>
      );
    }

    const elements: React.ReactNode[] = [];
    let lastIndex = 0;

    validSuggestions.forEach((s) => {
      if (s.start_idx < lastIndex) return;

      if (s.start_idx > lastIndex) {
        elements.push(
          <span key={`text-${lastIndex}`}>
            {content.slice(lastIndex, s.start_idx)}
          </span>
        );
      }

      const isSelected = activeSuggestionId === s.id;
      const tier = s.tier || (
        s.category?.toLowerCase().startsWith('spell') || s.category?.toLowerCase().startsWith('gramm')
          ? 'accuracy'
          : s.category?.toLowerCase().includes('vocab') || s.category?.toLowerCase().includes('natural') || s.category?.toLowerCase().includes('idiom')
          ? 'idiom'
          : 'style'
      );

      let highlightClass = 'highlight-accuracy';
      let activeRingClass = 'ring-2 ring-rose-500/80 ring-offset-1 dark:ring-offset-[#222222] bg-rose-100/70 dark:bg-rose-950/70';

      if (tier === 'idiom') {
        highlightClass = 'highlight-idiom';
        activeRingClass = 'ring-2 ring-amber-500/80 ring-offset-1 dark:ring-offset-[#222222] bg-amber-100/70 dark:bg-amber-950/70';
      } else if (tier === 'style') {
        highlightClass = 'highlight-style';
        activeRingClass = 'ring-2 ring-sky-500/80 ring-offset-1 dark:ring-offset-[#222222] bg-sky-100/70 dark:bg-sky-950/70';
      }

      elements.push(
        <span
          key={`highlight-${s.id}`}
          id={`highlight-${s.id}`}
          onClick={(e) => {
            e.stopPropagation();
            setActiveSuggestionId(s.id);
            const cardEl = document.getElementById(`suggestion-card-${s.id}`);
            if (cardEl) {
              cardEl.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
            }
          }}
          className={`${highlightClass} ${isSelected ? `${activeRingClass} font-semibold` : ''} inline cursor-pointer`}
          title={`[${tier === 'accuracy' ? '필수 교정' : tier === 'idiom' ? '원어민 표현' : '스타일 팁'}] ${s.suggested_phrase} - ${s.explanation}`}
        >
          {content.slice(s.start_idx, s.end_idx)}
        </span>
      );

      lastIndex = s.end_idx;
    });

    if (lastIndex < content.length) {
      elements.push(
        <span key={`text-end`}>
          {content.slice(lastIndex)}
        </span>
      );
    }

    return (
      <div className="font-serif text-base text-[#2c2b28] dark:text-[#e4e4e4] leading-relaxed whitespace-pre-wrap select-text">
        {elements}
      </div>
    );
  };

  return (
    <div className="flex-1 flex flex-col h-[calc(100vh-3.5rem)] overflow-hidden transition-colors">
      {/* Editor Top Bar: Tabs & Stats & Review Action - SOLID FLEX NO-WRAP */}
      <div className="h-14 px-8 bg-[#fcfbf9] dark:bg-[#191919] border-b border-[#e9e8e4] dark:border-[#2f2f2f] flex items-center justify-between transition-colors shrink-0 z-10">
        <CompareTabs
          activeTab={activeTab}
          onTabChange={setActiveTab}
        />

        <div className="flex items-center space-x-3 shrink-0">
          <span
            className={`flex items-center space-x-1 text-xs font-medium tabular-nums px-2 py-0.5 rounded-md border ${
              timer.isRunning
                ? 'text-blue-700 dark:text-blue-300 bg-blue-50 dark:bg-blue-950/40 border-blue-200 dark:border-blue-800/60'
                : 'text-[#787774] dark:text-[#999999] bg-transparent border-transparent'
            }`}
            title={`타자를 치는 동안만 잽니다. ${IDLE_LIMIT_MS / 60000}분 동안 입력이 없으면 멈추고, 다시 치면 이어서 잽니다.`}
          >
            {timer.isRunning ? <Timer className="w-3.5 h-3.5" /> : <Pause className="w-3.5 h-3.5" />}
            <span>{formatDuration(timer.seconds)}</span>
            {!timer.isRunning && (
              <span className="font-sans">
                {timer.hasStarted ? '멈춤' : wordCount > 0 ? '기록 없음 · 입력하면 시작' : '입력하면 시작'}
              </span>
            )}
          </span>
          <span className="text-xs text-[#787774] dark:text-[#999999] font-medium font-sans">
            {wordCount} words
          </span>

          {reviewResult && (
            <button
              onClick={() => {
                setActiveTab('editor');
                setTimeout(() => document.getElementById('essay-feedback')?.scrollIntoView({ behavior: 'smooth', block: 'start' }), 0);
              }}
              className="flex items-center space-x-1.5 px-2.5 py-1 bg-emerald-50 dark:bg-emerald-950/40 border border-emerald-200 dark:border-emerald-800/60 text-emerald-800 dark:text-emerald-300 hover:bg-emerald-100 dark:hover:bg-emerald-900/50 rounded-full text-xs font-semibold transition-colors"
              title="첨삭 당시 기준, 100단어당 필수 교정(명백한 오류) 수. 클릭하면 피드백으로 이동합니다."
            >
              <Sparkles className="w-3.5 h-3.5 text-emerald-600 dark:text-emerald-400" />
              <span>필수 교정 {mustFixPer100} / 100단어</span>
              <span className="text-emerald-600/70 dark:text-emerald-400/70">· 피드백 보기 ↓</span>
            </button>
          )}

          <button
            onClick={() => {
              setIsEditMode(false);
              onReview();
            }}
            disabled={isReviewing || !content.trim()}
            className="flex items-center space-x-1.5 px-4 py-2 bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-700 hover:to-indigo-700 dark:from-blue-500 dark:to-indigo-500 text-white text-xs font-semibold rounded-lg shadow-sm hover:shadow transition-all active:scale-95 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <Sparkles className={`w-3.5 h-3.5 ${isReviewing ? 'animate-spin' : ''}`} />
            <span>
              {isReviewing ? `AI 첨삭 중... (${REVIEW_PARTS.length - pendingParts.length}/${REVIEW_PARTS.length})` : 'AI 첨삭 받기'}
            </span>
          </button>
        </div>
      </div>

      {/* 1. Tab: Editor & Grammarly Suggestions */}
      {activeTab === 'editor' && (
        <div className="flex-1 flex overflow-hidden">
          {/* Left: Scrollable Paper Page Container */}
          <div className="flex-1 overflow-y-auto px-10 py-6 max-w-3xl mx-auto w-full space-y-5 pb-20">
            <EssayPromptHeader essay={essay} onPromptChange={onPromptChange} previousBand={previousBand} />

            {/* Editor Canvas Box */}
            <div className="w-full bg-white dark:bg-[#222222] rounded-2xl border border-[#e9e8e4] dark:border-[#333333] shadow-xs p-6 flex flex-col transition-colors">
              {/* Header inside canvas: Mode indicator and Toggle */}
              <div className="flex items-center justify-between pb-3 mb-4 border-b border-stone-100 dark:border-[#2d2d2d]">
                <div className="text-xs font-medium text-stone-500 dark:text-stone-400 flex items-center space-x-1.5">
                  {isEditMode ? (
                    <>
                      <PenLine className="w-3.5 h-3.5 text-amber-600 dark:text-amber-400" />
                      <span>직접 작성/수정 모드</span>
                    </>
                  ) : (
                    <div className="flex items-center space-x-3 flex-wrap gap-y-1">
                      <div className="flex items-center space-x-1.5">
                        <Eye className="w-3.5 h-3.5 text-blue-600 dark:text-blue-400" />
                        <span>
                          인라인 첨삭 하이라이트 뷰 {pendingSuggestions.length > 0 && `(${pendingSuggestions.length}곳)`}
                        </span>
                      </div>
                      {pendingSuggestions.length > 0 && (
                        <div className="hidden sm:flex items-center space-x-2.5 pl-2.5 border-l border-stone-200 dark:border-[#383838] text-[11px]">
                          <span className="inline-flex items-center space-x-1 text-rose-700 dark:text-rose-300">
                            <span className="w-2 h-2 rounded-full bg-rose-500"></span>
                            <span>필수 교정</span>
                          </span>
                          <span className="inline-flex items-center space-x-1 text-amber-800 dark:text-amber-300">
                            <span className="w-2 h-2 rounded-full bg-amber-500"></span>
                            <span>원어민 표현</span>
                          </span>
                          <span className="inline-flex items-center space-x-1 text-sky-700 dark:text-sky-300">
                            <span className="w-2 h-2 rounded-full bg-sky-500"></span>
                            <span>스타일 팁</span>
                          </span>
                        </div>
                      )}
                    </div>
                  )}
                </div>

                <button
                  onClick={() => setIsEditMode((prev) => !prev)}
                  className={`flex items-center space-x-1.5 px-3 py-1 rounded-lg text-xs font-semibold transition-all border ${
                    isEditMode
                      ? 'bg-blue-50 dark:bg-blue-950/50 text-blue-700 dark:text-blue-300 border-blue-200 dark:border-blue-800'
                      : 'bg-stone-100 dark:bg-[#2c2c2c] text-stone-700 dark:text-stone-300 border-stone-200 dark:border-[#3a3a3a] hover:bg-stone-200 dark:hover:bg-[#383838]'
                  }`}
                >
                  {isEditMode ? (
                    <>
                      <Eye className="w-3.5 h-3.5" />
                      <span>첨삭 하이라이트 보기</span>
                    </>
                  ) : (
                    <>
                      <PenLine className="w-3.5 h-3.5" />
                      <span>텍스트 직접 편집</span>
                    </>
                  )}
                </button>
              </div>

              {/* Document Text */}
              {isEditMode ? (
                <textarea
                  ref={textareaRef}
                  value={content}
                  onChange={(e) => {
                    timer.markActivity();
                    onContentChange(e.target.value);
                  }}
                  onKeyDown={handleTextareaKeyDown}
                  spellCheck={true}
                  placeholder="위 질문에 대한 내 입장을 영어로 써보세요. 분량은 자유입니다.&#10;&#10;다 쓰면 상단의 [AI 첨삭 받기]를 눌러 4대 기준 채점, 논증 피드백, 인라인 교정을 받으세요."
                  className="w-full min-h-[280px] bg-transparent resize-none outline-none font-serif text-base text-[#2c2b28] dark:text-[#e4e4e4] leading-relaxed placeholder:text-stone-300 dark:placeholder:text-[#555555] placeholder:font-sans selection:bg-amber-100 dark:selection:bg-amber-900/60 overflow-hidden"
                  autoFocus
                />
              ) : (
                <div 
                  className="w-full min-h-[280px] cursor-text"
                  onDoubleClick={() => setIsEditMode(true)}
                >
                  {renderInteractiveDocument()}
                </div>
              )}
            </div>

            {/* AI Review Summary / Feedback & Key Expressions */}
            {reviewResult && (
              <div className="space-y-4 pt-2">
                <EssayFeedback review={reviewResult} pendingParts={pendingParts} onRevise={onRevise} onOpenAnkiModal={onOpenAnkiModal} onOpenGrammarModal={onOpenGrammarModal} />

                {/* Key Expressions Extracted */}
                {reviewResult.key_expressions && reviewResult.key_expressions.length > 0 && (
                  <div className="bg-white dark:bg-[#222222] rounded-xl border border-stone-200 dark:border-[#333333] p-5 shadow-xs">
                    <div className="text-xs font-semibold text-[#37352f] dark:text-[#e0e0e0] flex items-center justify-between mb-3.5">
                      <span className="flex items-center space-x-1.5">
                        <BookOpen className="w-3.5 h-3.5 text-blue-600 dark:text-blue-400" />
                        <span>다음 에세이에 쓸 논증 표현 (Key Expressions)</span>
                      </span>
                      <span className="text-[11px] text-[#787774] dark:text-[#999999]">
                        클릭하여 Anki 단어 카드에 등록
                      </span>
                    </div>

                    <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                      {reviewResult.key_expressions.map((k, idx) => (
                        <div
                          key={idx}
                          className="bg-[#faf9f6] dark:bg-[#1a1a1a] border border-[#ebe9e1] dark:border-[#333333] hover:border-emerald-300 dark:hover:border-emerald-600/60 p-3 rounded-lg flex items-start justify-between group transition-all"
                        >
                          <div className="space-y-1 pr-2">
                            <div className="flex items-center space-x-2">
                              <span className="text-xs font-semibold text-emerald-900 dark:text-emerald-300 font-serif">
                                {normalizeVocabPlaceholder(k.expression)}
                              </span>
                              {k.pos && (
                                <span className="text-[10px] px-1.5 py-0.2 bg-emerald-50 dark:bg-emerald-950/50 border border-emerald-200/80 dark:border-emerald-800/40 text-emerald-700 dark:text-emerald-400 rounded-xs font-mono">
                                  {k.pos}
                                </span>
                              )}
                            </div>
                            <div className="text-[11px] text-stone-600 dark:text-stone-400 font-sans">
                              {k.meaning}
                            </div>
                            {k.synonyms && (
                              <div className="text-[10px] text-stone-400 dark:text-stone-500">
                                유의어: {k.synonyms}
                              </div>
                            )}
                            {k.example && (
                              <div className="text-[10px] text-stone-400 dark:text-stone-500 italic">
                                "{k.example}"
                              </div>
                            )}
                          </div>
                          <button
                            onClick={() => handleDirectAddVocab(k, idx)}
                            disabled={savingVocabIndex === idx}
                            className={`p-1.5 rounded-lg text-xs font-medium transition-all shrink-0 flex items-center space-x-1 border ${
                              savedVocabIndexes.has(idx)
                                ? 'bg-emerald-100 dark:bg-emerald-950 text-emerald-800 dark:text-emerald-300 border-emerald-300 dark:border-emerald-700'
                                : 'bg-white dark:bg-[#252525] text-stone-400 hover:text-emerald-700 dark:hover:text-emerald-300 hover:bg-emerald-50 dark:hover:bg-emerald-950/50 border-stone-200 dark:border-[#383838]'
                            }`}
                            title={savedVocabIndexes.has(idx) ? '이미 Anki에 있음' : 'Anki 단어장에 원클릭 저장'}
                          >
                            {savingVocabIndex === idx ? (
                              <Loader2 className="w-3.5 h-3.5 animate-spin text-emerald-600" />
                            ) : savedVocabIndexes.has(idx) ? (
                              <Check className="w-3.5 h-3.5" />
                            ) : (
                              <BookmarkPlus className="w-3.5 h-3.5" />
                            )}
                          </button>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Right: Grammarly Suggestions Side Panel with Pending / Applied Tabs */}
          <div 
            ref={suggestionListRef}
            className="w-96 border-l border-[#e9e8e4] dark:border-[#2a2a2a] bg-[#f7f6f3]/60 dark:bg-[#1c1c1c]/90 overflow-y-auto p-4 flex flex-col space-y-3 transition-colors"
          >
            <div className="pb-2 border-b border-[#e9e8e4] dark:border-[#2f2f2f]">
              <div className="text-xs font-semibold text-stone-800 dark:text-stone-200">교정 기록 ({suggestions.length})</div>
              <div className="text-[11px] text-stone-500 dark:text-stone-400 mt-0.5">
                원문은 그대로 남습니다. 고쳐 쓰기에서 직접 다시 써 보세요.
              </div>
            </div>

            {suggestions.length === 0 ? (
              <div className="flex-1 flex flex-col items-center justify-center text-center p-6 text-stone-400 dark:text-stone-500 space-y-2">
                <CheckCircle className="w-8 h-8 text-emerald-500/80 dark:text-emerald-400/80" />
                <div className="text-xs font-medium text-stone-600 dark:text-stone-300">
                  {pendingParts.includes('corrections')
                    ? '문장별로 교정을 찾고 검증하는 중입니다...'
                    : reviewResult ? '교정할 부분이 없습니다.' : '에세이 작성 후 [AI 첨삭 받기]를 눌러보세요.'}
                </div>
              </div>
            ) : (
              suggestions.map((item) => (
                <div key={item.id} id={`suggestion-card-${item.id}`}>
                  <SuggestionCard
                    suggestion={item}
                    isActive={activeSuggestionId === item.id}
                    onSelect={() => {
                      setActiveSuggestionId(item.id);
                      document.getElementById(`highlight-${item.id}`)?.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
                    }}
                    sentenceForCard={sentenceForCard(item)}
                    onOpenAnkiModal={onOpenAnkiModal}
                    onOpenGrammarCard={isGrammarFix(item) ? () => onOpenGrammarModal(grammarDraft(reviewResult?.original_text || '', item)) : undefined}
                  />
                </div>
              ))
            )}
          </div>
        </div>
      )}

      {/* 2. Tab: Sentence Study View (Shadowing Player Style 1:1) */}
      {activeTab === 'sentence' && (
        <div className="flex-1 overflow-y-auto px-10 py-6 max-w-4xl mx-auto w-full">
          {pairsState === 'error' && reviewResult ? (
            <div className="flex flex-col items-center justify-center py-24 space-y-3">
              <div className="text-xs text-red-600 dark:text-red-400">문장별 대조를 만들지 못했습니다.</div>
              <button
                onClick={() => setPairsState('idle')}
                className="px-3 py-1.5 text-xs font-semibold rounded-lg border border-stone-200 dark:border-[#3a3a3a] text-stone-700 dark:text-stone-300 hover:bg-stone-50 dark:hover:bg-[#2c2c2c]"
              >
                다시 시도
              </button>
            </div>
          ) : pairsState === 'loading' ? (
            <div className="flex flex-col items-center justify-center py-24 text-stone-400 dark:text-stone-500 space-y-3">
              <Loader2 className="w-6 h-6 animate-spin" />
              <div className="text-xs">문장별 대조를 만드는 중입니다 (처음 한 번만)...</div>
            </div>
          ) : (
          <SentenceStudyView
            sentencePairs={sentencePairs}
            originalContent={content}
            nativeContent={reviewResult?.upgraded_text || ''}
            essayId={essayId}
            onShowToast={onShowToast}
          />
          )}
        </div>
      )}

      {/* 3. Tab: Native Paraphrase Complete Story */}
      {activeTab === 'native' && (
        <div className="flex-1 overflow-y-auto px-10 py-6 max-w-3xl mx-auto w-full pb-20">
          {popoverState.position && (
            <WordPopover
              word={popoverState.word}
              context={popoverState.context}
              position={popoverState.position}
              onClose={() => setPopoverState({ word: '', context: '', position: null })}
              onShowToast={onShowToast}
            />
          )}

          <div className="bg-white dark:bg-[#222222] rounded-2xl border border-indigo-100 dark:border-indigo-900/40 p-8 shadow-xs space-y-6">
            <div className="flex items-center justify-between pb-4 border-b border-indigo-50 dark:border-indigo-900/30">
              <div>
                <h3 className="text-base font-bold text-indigo-950 dark:text-indigo-200 flex items-center space-x-2">
                  <span>📖 C1+ Upgraded Version (같은 논지, 한 단계 위)</span>
                </h3>
                <p className="text-xs text-indigo-600 dark:text-indigo-400 mt-0.5">
                  단어를 클릭하면 팝업 사전이 뜨며, 버튼 클릭 시 Anki로 즉시 저장됩니다.
                </p>
              </div>
              <button
                onClick={() => handleCopy(reviewResult?.upgraded_text || '', 'native')}
                className="flex items-center space-x-1 text-xs text-indigo-700 dark:text-indigo-300 hover:bg-indigo-50 dark:hover:bg-indigo-950/50 border border-indigo-200 dark:border-indigo-800/60 px-3 py-1.5 rounded-lg transition-colors"
              >
                {copied === 'native' ? <Check className="w-3.5 h-3.5 text-emerald-600 dark:text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
                <span>{copied === 'native' ? '복사됨' : '본문 복사'}</span>
              </button>
            </div>
            <div className="font-serif text-base text-[#2c2b28] dark:text-[#e8e8e8] leading-relaxed whitespace-pre-wrap selection:bg-indigo-100 dark:selection:bg-indigo-900">
              {reviewResult?.upgraded_text
                ? renderInteractiveNativeText(reviewResult.upgraded_text)
                : '아직 업그레이드 버전이 없습니다. [AI 첨삭 받기]를 먼저 실행해주세요.'}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
