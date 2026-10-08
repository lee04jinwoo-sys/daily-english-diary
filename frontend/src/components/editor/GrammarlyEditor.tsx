import React, { useState, useRef, useEffect } from 'react';
import { SuggestionItem, ReviewResponse, CardType } from '../../types/diary';
import { SuggestionCard } from './SuggestionCard';
import { CompareTabs } from './CompareTabs';
import { SentenceStudyView } from './SentenceStudyView';
import { WordPopover } from '../common/WordPopover';
import { api } from '../../api/client';
import { 
  Sparkles, 
  BookOpen, 
  CheckCircle, 
  MessageSquare, 
  BookmarkPlus, 
  PenLine, 
  Eye, 
  Copy, 
  Check,
  CheckCircle2,
  Clock,
  Loader2
} from 'lucide-react';

interface GrammarlyEditorProps {
  title: string;
  onTitleChange: (title: string) => void;
  content: string;
  onContentChange: (content: string) => void;
  onReview: () => void;
  isReviewing: boolean;
  reviewResult: ReviewResponse | null;
  suggestions: SuggestionItem[];
  onApplySuggestion: (suggestion: SuggestionItem) => void;
  onDismissSuggestion: (id: string) => void;
  onOpenAnkiModal: (cardType: CardType, text: string, context?: string) => void;
  diaryDate?: string;
  onShowToast: (msg: string) => void;
}

export const GrammarlyEditor: React.FC<GrammarlyEditorProps> = ({
  title,
  onTitleChange,
  content,
  onContentChange,
  onReview,
  isReviewing,
  reviewResult,
  suggestions,
  onApplySuggestion,
  onDismissSuggestion,
  onOpenAnkiModal,
  diaryDate = '',
  onShowToast,
}) => {
  const [activeSuggestionId, setActiveSuggestionId] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<'editor' | 'sentence' | 'native'>('editor');
  const [suggestionFilter, setSuggestionFilter] = useState<'pending' | 'applied'>('pending');
  const [isEditMode, setIsEditMode] = useState<boolean>(true);
  const [copied, setCopied] = useState<string | null>(null);
  const [isSavingFullNative, setIsSavingFullNative] = useState(false);
  const [isSavedFullNative, setIsSavedFullNative] = useState(false);
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
  }, [reviewResult?.key_expressions, diaryDate]);

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

  const handleDirectAddFullNative = async () => {
    if (!reviewResult?.native_text) return;
    setIsSavingFullNative(true);
    try {
      const res = await api.addSentenceCard({
        sentence: reviewResult.native_text,
        translation: title || '오늘의 원어민 일기 완성본',
        diary_date: diaryDate,
      });
      if (res.success) {
        setIsSavedFullNative(true);
        onShowToast(res.duplicate ? '이미 Anki에 등록된 문장입니다.' : '원어민 일기가 Anki에 저장되었습니다! 🎉');
      } else {
        onShowToast('Anki 앱이 켜져 있는지 확인해주세요! (상단 Anki 상태 확인)');
      }
    } catch (e: any) {
      onShowToast(`Anki 등록 실패: ${e.message}`);
    } finally {
      setIsSavingFullNative(false);
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
        // Toggle delete from Anki
        const res = await api.deleteCard({ card_type: 'vocab', text: normalizedWord });
        if (res.success) {
          setSavedVocabIndexes((prev) => {
            const next = new Set(prev);
            next.delete(idx);
            return next;
          });
          onShowToast(`'${normalizedWord}' 카드가 Anki에서 삭제되었습니다.`);
        } else {
          onShowToast(`삭제 실패: ${res.error}`);
        }
      } else {
        // Add to Anki
        const res = await api.addVocabCard({
          word: normalizedWord,
          meaning: k.meaning,
          pos: k.pos || 'idiom',
          synonyms: k.synonyms || '',
          example: k.example || '',
          explanation: k.explanation || '',
          diary_date: diaryDate,
        });
        if (res.success) {
          setSavedVocabIndexes((prev) => new Set(prev).add(idx));
          onShowToast(res.duplicate ? '이미 Anki에 등록된 표현입니다.' : `'${normalizedWord}' Anki 단어 카드가 저장되었습니다! 🎉`);
        } else {
          onShowToast('Anki 앱이 켜져 있는지 확인해주세요! (상단 Anki 상태 확인)');
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
  const pendingSuggestions = suggestions.filter(
    (s) => !s.is_applied && content.includes(s.original_phrase)
  );
  const appliedSuggestions = suggestions.filter(
    (s) => s.is_applied && content.includes(s.suggested_phrase)
  );

  // Render Clean Interactive Document with Grammarly Highlights
  const renderInteractiveDocument = () => {
    if (!content.trim()) {
      return (
        <div 
          onClick={() => setIsEditMode(true)}
          className="text-stone-400 dark:text-stone-500 font-serif italic py-10 cursor-text"
        >
          작성된 일기 내용이 없습니다. 클릭하여 일기를 작성해보세요.
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
            setSuggestionFilter('pending');
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
          <span className="text-xs text-[#787774] dark:text-[#999999] font-medium font-sans">
            {wordCount} words
          </span>

          {reviewResult && (
            <div className="flex items-center space-x-1.5 px-2.5 py-1 bg-emerald-50 dark:bg-emerald-950/40 border border-emerald-200 dark:border-emerald-800/60 text-emerald-800 dark:text-emerald-300 rounded-full text-xs font-semibold">
              <Sparkles className="w-3.5 h-3.5 text-emerald-600 dark:text-emerald-400" />
              <span>정확도 {reviewResult.score}점</span>
            </div>
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
            <span>{isReviewing ? 'AI 첨삭 중...' : 'AI 첨삭 받기'}</span>
          </button>
        </div>
      </div>

      {/* 1. Tab: Editor & Grammarly Suggestions */}
      {activeTab === 'editor' && (
        <div className="flex-1 flex overflow-hidden">
          {/* Left: Scrollable Paper Page Container */}
          <div className="flex-1 overflow-y-auto px-10 py-6 max-w-3xl mx-auto w-full space-y-5 pb-20">
            {/* Title Input */}
            <input
              type="text"
              placeholder="일기 제목을 입력하세요 (예: A rainy afternoon at the cafe)"
              value={title}
              onChange={(e) => onTitleChange(e.target.value)}
              className="w-full text-2xl font-serif font-bold text-[#1c1b18] dark:text-[#f0f0f0] placeholder:text-stone-300 dark:placeholder:text-[#555555] bg-transparent outline-none border-b border-transparent focus:border-stone-200 dark:focus:border-[#383838] pb-2 transition-colors"
            />

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
                          인라인 첨삭 하이라이트 뷰 {pendingSuggestions.length > 0 && `(${pendingSuggestions.length}개 미적용)`}
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
                  onChange={(e) => onContentChange(e.target.value)}
                  onKeyDown={handleTextareaKeyDown}
                  spellCheck={true}
                  placeholder="오늘 하루 있었던 일이나 생각을 자유롭게 영어로 적어보세요...&#10;&#10;작성을 마친 후 상단의 [AI 첨삭 받기]를 누르면 Grammarly 스타일의 실시간 문법 교정과 원어민 표현 제안을 받을 수 있습니다."
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
                {/* AI Warm Feedback */}
                <div className="bg-gradient-to-br from-amber-50/70 to-orange-50/50 dark:from-amber-950/30 dark:to-orange-950/20 border border-amber-200/80 dark:border-amber-800/40 rounded-xl p-5 shadow-xs">
                  <div className="flex items-center space-x-2 text-xs font-semibold text-amber-900 dark:text-amber-300 mb-2">
                    <MessageSquare className="w-4 h-4 text-amber-600 dark:text-amber-400" />
                    <span>AI 튜터의 오늘 일기 코멘트</span>
                  </div>
                  <p className="text-xs text-amber-950 dark:text-amber-200 leading-relaxed font-sans">
                    {reviewResult.overall_feedback}
                  </p>
                  
                  {reviewResult.followup_question && (
                    <div className="mt-3.5 pt-3 border-t border-amber-200/50 dark:border-amber-800/30 flex items-start space-x-2 text-xs text-amber-900 dark:text-amber-300 font-medium">
                      <span className="text-sm">💬</span>
                      <span>
                        <strong className="text-amber-800 dark:text-amber-300">Q.</strong> {reviewResult.followup_question}
                      </span>
                    </div>
                  )}
                </div>

                {/* Key Expressions Extracted */}
                {reviewResult.key_expressions && reviewResult.key_expressions.length > 0 && (
                  <div className="bg-white dark:bg-[#222222] rounded-xl border border-stone-200 dark:border-[#333333] p-5 shadow-xs">
                    <div className="text-xs font-semibold text-[#37352f] dark:text-[#e0e0e0] flex items-center justify-between mb-3.5">
                      <span className="flex items-center space-x-1.5">
                        <BookOpen className="w-3.5 h-3.5 text-blue-600 dark:text-blue-400" />
                        <span>오늘의 핵심 추천 표현 (Vocabulary & Idioms)</span>
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
                                ? 'bg-emerald-100 dark:bg-emerald-950 text-emerald-800 dark:text-emerald-300 border-emerald-300 dark:border-emerald-700 hover:bg-red-50 hover:text-red-700 hover:border-red-300 dark:hover:bg-red-950/40 dark:hover:text-red-300'
                                : 'bg-white dark:bg-[#252525] text-stone-400 hover:text-emerald-700 dark:hover:text-emerald-300 hover:bg-emerald-50 dark:hover:bg-emerald-950/50 border-stone-200 dark:border-[#383838]'
                            }`}
                            title={savedVocabIndexes.has(idx) ? '클릭 시 Anki에서 등록 취소(제거)' : 'Anki 단어장에 원클릭 저장'}
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
            {/* Filter Tabs: Pending vs Applied */}
            <div className="flex items-center justify-between pb-2 border-b border-[#e9e8e4] dark:border-[#2f2f2f]">
              <div className="flex items-center bg-stone-200/80 dark:bg-[#282828] p-0.5 rounded-lg text-xs font-medium">
                <button
                  onClick={() => setSuggestionFilter('pending')}
                  className={`flex items-center space-x-1 px-2.5 py-1 rounded-md transition-all ${
                    suggestionFilter === 'pending'
                      ? 'bg-white dark:bg-[#383838] text-stone-900 dark:text-white font-bold shadow-xs'
                      : 'text-stone-600 dark:text-stone-400 hover:text-stone-900'
                  }`}
                >
                  <Clock className="w-3 h-3" />
                  <span>미적용 ({pendingSuggestions.length})</span>
                </button>

                <button
                  onClick={() => setSuggestionFilter('applied')}
                  className={`flex items-center space-x-1 px-2.5 py-1 rounded-md transition-all ${
                    suggestionFilter === 'applied'
                      ? 'bg-white dark:bg-[#383838] text-emerald-800 dark:text-emerald-300 font-bold shadow-xs'
                      : 'text-stone-600 dark:text-stone-400 hover:text-stone-900'
                  }`}
                >
                  <CheckCircle2 className="w-3 h-3 text-emerald-600 dark:text-emerald-400" />
                  <span>적용 완료 ({appliedSuggestions.length})</span>
                </button>
              </div>
            </div>

            {/* Suggestions List */}
            {suggestionFilter === 'pending' ? (
              pendingSuggestions.length === 0 ? (
                <div className="flex-1 flex flex-col items-center justify-center text-center p-6 text-stone-400 dark:text-stone-500 space-y-2">
                  <CheckCircle className="w-8 h-8 text-emerald-500/80 dark:text-emerald-400/80" />
                  <div className="text-xs font-medium text-stone-600 dark:text-stone-300">
                    {reviewResult ? '모든 제안을 적용하셨습니다! 🎉' : '일기 작성 후 [AI 첨삭 받기]를 눌러보세요.'}
                  </div>
                  {appliedSuggestions.length > 0 && (
                    <button
                      onClick={() => setSuggestionFilter('applied')}
                      className="text-xs text-blue-600 dark:text-blue-400 underline font-medium"
                    >
                      적용 완료된 제안 {appliedSuggestions.length}개 확인하기
                    </button>
                  )}
                </div>
              ) : (
                pendingSuggestions.map((item) => (
                  <div key={item.id} id={`suggestion-card-${item.id}`}>
                    <SuggestionCard
                      suggestion={item}
                      isActive={activeSuggestionId === item.id}
                      onSelect={() => {
                        setActiveSuggestionId(item.id);
                        const highlightEl = document.getElementById(`highlight-${item.id}`);
                        if (highlightEl) {
                          highlightEl.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
                        }
                      }}
                      onApply={(s) => {
                        onApplySuggestion(s);
                        setActiveSuggestionId(null);
                      }}
                      onDismiss={(id) => {
                        onDismissSuggestion(id);
                        if (activeSuggestionId === id) setActiveSuggestionId(null);
                      }}
                      onOpenAnkiModal={onOpenAnkiModal}
                    />
                  </div>
                ))
              )
            ) : (
              appliedSuggestions.length === 0 ? (
                <div className="flex-1 flex flex-col items-center justify-center text-center p-6 text-stone-400 dark:text-stone-500 space-y-2">
                  <div className="text-xs font-medium text-stone-600 dark:text-stone-300">
                    아직 적용된 제안이 없습니다.
                  </div>
                </div>
              ) : (
                appliedSuggestions.map((item) => (
                  <div key={item.id} id={`suggestion-card-${item.id}`}>
                    <SuggestionCard
                      suggestion={item}
                      isActive={activeSuggestionId === item.id}
                      onSelect={() => setActiveSuggestionId(item.id)}
                      onApply={onApplySuggestion}
                      onDismiss={onDismissSuggestion}
                      onOpenAnkiModal={onOpenAnkiModal}
                    />
                  </div>
                ))
              )
            )}
          </div>
        </div>
      )}

      {/* 2. Tab: Sentence Study View (Shadowing Player Style 1:1) */}
      {activeTab === 'sentence' && (
        <div className="flex-1 overflow-y-auto px-10 py-6 max-w-4xl mx-auto w-full">
          <SentenceStudyView
            sentencePairs={reviewResult?.sentence_pairs || []}
            originalContent={content}
            nativeContent={reviewResult?.native_text || ''}
            diaryDate={diaryDate}
            onShowToast={onShowToast}
          />
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
              diaryDate={diaryDate}
            />
          )}

          <div className="bg-white dark:bg-[#222222] rounded-2xl border border-indigo-100 dark:border-indigo-900/40 p-8 shadow-xs space-y-6">
            <div className="flex items-center justify-between pb-4 border-b border-indigo-50 dark:border-indigo-900/30">
              <div>
                <h3 className="text-base font-bold text-indigo-950 dark:text-indigo-200 flex items-center space-x-2">
                  <span>📖 Native Paraphrased Story (원어민 완성본)</span>
                </h3>
                <p className="text-xs text-indigo-600 dark:text-indigo-400 mt-0.5">
                  단어를 클릭하면 팝업 사전이 뜨며, 버튼 클릭 시 Anki로 즉시 저장됩니다.
                </p>
              </div>
              <div className="flex items-center space-x-2">
                <button
                  onClick={() => handleCopy(reviewResult?.native_text || '', 'native')}
                  className="flex items-center space-x-1 text-xs text-indigo-700 dark:text-indigo-300 hover:bg-indigo-50 dark:hover:bg-indigo-950/50 border border-indigo-200 dark:border-indigo-800/60 px-3 py-1.5 rounded-lg transition-colors"
                >
                  {copied === 'native' ? <Check className="w-3.5 h-3.5 text-emerald-600 dark:text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
                  <span>{copied === 'native' ? '복사됨' : '본문 복사'}</span>
                </button>
                <button
                  onClick={handleDirectAddFullNative}
                  disabled={isSavingFullNative}
                  className={`flex items-center space-x-1 text-xs px-3 py-1.5 rounded-lg transition-all shadow-xs ${
                    isSavedFullNative
                      ? 'bg-emerald-700 text-white'
                      : 'text-white bg-indigo-600 hover:bg-indigo-700 dark:bg-indigo-500 dark:hover:bg-indigo-600'
                  }`}
                >
                  {isSavingFullNative ? (
                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  ) : isSavedFullNative ? (
                    <Check className="w-3.5 h-3.5" />
                  ) : (
                    <BookmarkPlus className="w-3.5 h-3.5" />
                  )}
                  <span>{isSavingFullNative ? '전송 중' : isSavedFullNative ? 'Anki 등록됨 ✓' : 'Anki에 전체 등록'}</span>
                </button>
              </div>
            </div>
            <div className="font-serif text-base text-[#2c2b28] dark:text-[#e8e8e8] leading-relaxed whitespace-pre-wrap selection:bg-indigo-100 dark:selection:bg-indigo-900">
              {reviewResult?.native_text
                ? renderInteractiveNativeText(reviewResult.native_text)
                : '아직 원어민 패러프레이징이 생성되지 않았습니다. [AI 첨삭 받기]를 먼저 실행해주세요.'}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
