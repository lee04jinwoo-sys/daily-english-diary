import { useState, useEffect, useRef, useCallback } from 'react';
import { api } from './api/client';
import {
  Essay,
  EssayListItem,
  SuggestionItem,
  ReviewResponse,
  AnkiStatus,
  CardType,
  StatsResponse,
  Topic,
  ReviewPart,
  REVIEW_PARTS,
} from './types/essay';
import { Header, AppView } from './components/layout/Header';
import { Sidebar } from './components/layout/Sidebar';
import { GrammarlyEditor } from './components/editor/GrammarlyEditor';
import { AnkiCardModal } from './components/anki/AnkiCardModal';
import { GrammarCardModal } from './components/anki/GrammarCardModal';
import { GrammarCardDraft } from './utils/cardText';
import { EssayCalendar } from './components/calendar/EssayCalendar';
import { StatsDashboard } from './components/stats/StatsDashboard';
import { TopicPicker } from './components/topic/TopicPicker';
import confetti from 'canvas-confetti';

export function App() {
  // States
  const [essays, setEssays] = useState<EssayListItem[]>([]);
  const [currentEssay, setCurrentEssay] = useState<Essay | null>(null);
  const [content, setContent] = useState<string>('');
  const [suggestions, setSuggestions] = useState<SuggestionItem[]>([]);
  const [reviewResult, setReviewResult] = useState<ReviewResponse | null>(null);
  // Parts of the running review that have not arrived yet (empty when no review is running).
  const [pendingParts, setPendingParts] = useState<ReviewPart[]>([]);

  const [activeView, setActiveView] = useState<AppView>('editor');
  const [isSaving, setIsSaving] = useState<boolean>(false);
  const [isReviewing, setIsReviewing] = useState<boolean>(false);
  const [ankiStatus, setAnkiStatus] = useState<AnkiStatus | null>(null);
  const [streak, setStreak] = useState<number>(0);
  const [stats, setStats] = useState<StatsResponse | null>(null);

  // Theme State
  const [isDarkMode, setIsDarkMode] = useState<boolean>(() => {
    try {
      const saved = localStorage.getItem('theme');
      if (saved) return saved === 'dark';
      return window.matchMedia('(prefers-color-scheme: dark)').matches;
    } catch {
      return false;
    }
  });

  // Keep DOM and localStorage in sync
  useEffect(() => {
    document.documentElement.classList.toggle('dark', isDarkMode);
    document.body.classList.toggle('dark', isDarkMode);
    try { localStorage.setItem('theme', isDarkMode ? 'dark' : 'light'); } catch {}
  }, [isDarkMode]);

  // Toast Notification
  const [toastMessage, setToastMessage] = useState<string | null>(null);

  // Anki Modal State
  const [ankiModal, setAnkiModal] = useState<{
    isOpen: boolean;
    cardType: CardType;
    text: string;
    context?: string;
  }>({
    isOpen: false,
    cardType: 'sentence',
    text: '',
    context: '',
  });

  const [grammarDraft, setGrammarDraft] = useState<GrammarCardDraft | null>(null);

  const showToast = (msg: string) => {
    setToastMessage(msg);
    setTimeout(() => setToastMessage(null), 3000);
  };

  const refreshLists = useCallback(async () => {
    const [listRes, statsRes, ankiRes] = await Promise.allSettled([
      api.getEssays(),
      api.getStats(),
      api.getAnkiStatus(),
    ]);
    if (listRes.status === 'fulfilled') {
      setEssays(listRes.value.essays);
      setStreak(listRes.value.streak);
    }
    if (statsRes.status === 'fulfilled') setStats(statsRes.value);
    if (ankiRes.status === 'fulfilled') setAnkiStatus(ankiRes.value);
    return listRes.status === 'fulfilled' ? listRes.value.essays : [];
  }, []);

  const openEssay = useCallback(async (id: string) => {
    try {
      const essay = await api.getEssay(id);
      setCurrentEssay(essay);
      setContent(essay.content || '');
      if (essay.review) {
        const saved = await api.getEssaySuggestions(id);
        setSuggestions(saved || []);
        setReviewResult(essay.review);
      } else {
        setSuggestions([]);
        setReviewResult(null);
      }
      setActiveView('editor');
    } catch (e: any) {
      showToast(`에세이를 불러오지 못했습니다: ${e.message}`);
    }
  }, []);

  // Initial load: open the most recent essay, or start with a topic if there is none.
  useEffect(() => {
    refreshLists().then((list) => {
      if (list.length > 0) openEssay(list[0].id);
      else setActiveView('topic');
    });
  }, [refreshLists, openEssay]);

  useEffect(() => {
    if (activeView === 'stats') {
      api.getStats().then(setStats).catch(() => {});
    }
  }, [activeView]);

  // Auto-save Debounce (content / free-topic prompt only; the stored review is never touched)
  const autoSaveTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const scheduleSave = (essayId: string, data: { content?: string; prompt?: string }) => {
    if (autoSaveTimeoutRef.current) clearTimeout(autoSaveTimeoutRef.current);
    autoSaveTimeoutRef.current = setTimeout(async () => {
      setIsSaving(true);
      try {
        await api.updateEssay(essayId, data);
        const res = await api.getEssays();
        setEssays(res.essays);
        setStreak(res.streak);
      } catch (e) {
        console.error('Auto-save error:', e);
      } finally {
        setIsSaving(false);
      }
    }, 1200);
  };

  const handleContentChange = (newContent: string) => {
    setContent(newContent);
    if (currentEssay) scheduleSave(currentEssay.id, { content: newContent });
  };

  const handlePromptChange = (prompt: string) => {
    if (!currentEssay) return;
    setCurrentEssay({ ...currentEssay, prompt });
    scheduleSave(currentEssay.id, { content, prompt });
  };

  // Trigger AI Review (the server stores the result on the essay)
  const handleReview = async () => {
    if (!currentEssay || !content.trim()) return;

    setIsReviewing(true);
    // Parts are shown as they arrive; the first one replaces the previous review.
    let partial: ReviewResponse | null = null;
    let waiting = [...REVIEW_PARTS];
    try {
      const res = await api.reviewEssayStream({ essay_id: currentEssay.id, content }, (part, data) => {
        if (!partial) setSuggestions([]); // the previous review's corrections no longer apply
        partial = mergeReviewPart(partial ?? emptyReview(currentEssay.id, content), part, data);
        waiting = waiting.filter((p) => p !== part);
        setReviewResult(partial);
        setPendingParts(waiting);
        if (part === 'corrections') setSuggestions(data.suggestions || []);
      });
      setPendingParts([]);
      setReviewResult(res);
      setSuggestions(res.suggestions || []);
      setCurrentEssay(await api.getEssay(currentEssay.id));
      await refreshLists();

      confetti({ particleCount: 80, spread: 70, origin: { y: 0.7 } });
      showToast(`첨삭 완료 · Band ${res.rubric.overall_band.toFixed(1)}`);
    } catch (e: any) {
      setPendingParts([]);
      // A failed review is not saved: go back to what the essay had before.
      try {
        const essay = await api.getEssay(currentEssay.id);
        setReviewResult(essay.review ?? null);
        setSuggestions(essay.review ? (await api.getEssaySuggestions(currentEssay.id)) || [] : []);
      } catch {
        // keep whatever is on screen
      }
      alert(`첨삭 처리 중 오류가 발생했습니다: ${e.message}`);
    } finally {
      setIsReviewing(false);
    }
  };

  const handleStartEssay = async (topic: Topic | null, customPrompt?: string) => {
    try {
      const essay = topic
        ? await api.createEssay({ prompt: topic.prompt, essay_type: topic.type, category: topic.category, topic_id: topic.id })
        : await api.createEssay({ prompt: customPrompt || '', essay_type: 'free', category: 'free' });
      await refreshLists();
      await openEssay(essay.id);
    } catch (e: any) {
      alert(`에세이를 만들지 못했습니다: ${e.message}`);
    }
  };

  const handleRevise = async () => {
    if (!currentEssay) return;
    try {
      const revised = await api.reviseEssay(currentEssay.id);
      await refreshLists();
      await openEssay(revised.id);
      showToast('같은 주제로 고쳐 쓰기를 시작합니다. 이전 첨삭은 그대로 남아 있습니다.');
    } catch (e: any) {
      alert(`고쳐 쓰기를 시작하지 못했습니다: ${e.message}`);
    }
  };

  const handleDeleteEssay = async (id: string) => {
    try {
      await api.deleteEssay(id);
      const list = await refreshLists();
      if (currentEssay?.id === id) {
        if (list.length > 0) await openEssay(list[0].id);
        else {
          setCurrentEssay(null);
          setActiveView('topic');
        }
      }
      showToast('에세이가 삭제되었습니다.');
    } catch (e: any) {
      alert(`삭제 오류: ${e.message}`);
    }
  };

  const handleToggleComplete = async (id?: string) => {
    const targetId = id || currentEssay?.id;
    if (!targetId) return;
    try {
      const updated = await api.toggleEssayComplete(targetId);
      if (currentEssay?.id === targetId) setCurrentEssay(updated);
      setEssays((prev) => prev.map((e) => (e.id === targetId ? { ...e, is_completed: updated.is_completed } : e)));
      showToast(updated.is_completed ? '학습 완료로 표시되었습니다! 🎉' : '학습 완료가 해제되었습니다.');
    } catch (e: any) {
      showToast(`완료 상태 변경 실패: ${e.message}`);
    }
  };

  const handleSelectDate = (date: string) => {
    const onDate = essays.find((e) => e.date === date);
    if (onDate) openEssay(onDate.id);
    else showToast(`${date}에 쓴 에세이가 없습니다.`);
  };

  const handleOpenAnkiModal = (cardType: CardType, text: string, context?: string) => {
    setAnkiModal({ isOpen: true, cardType, text, context });
  };

  const previousBand = currentEssay?.revision_of
    ? essays.find((e) => e.id === currentEssay.revision_of)?.overall_band ?? null
    : null;

  return (
    <div className="min-h-screen bg-[#fcfbf9] dark:bg-[#191919] text-[#37352f] dark:text-[#e6e6e6] flex flex-col font-sans transition-colors duration-200">
      {/* Toast Alert */}
      {toastMessage && (
        <div className="fixed top-16 right-8 z-50 bg-stone-900 dark:bg-stone-100 text-white dark:text-stone-900 text-xs font-semibold px-4 py-2.5 rounded-xl shadow-lg animate-in fade-in slide-in-from-top-2 duration-150 flex items-center space-x-2">
          <span>✨</span>
          <span>{toastMessage}</span>
        </div>
      )}

      <Header
        ankiStatus={ankiStatus}
        onRefreshAnki={refreshLists}
        isSaving={isSaving}
        onNewEssay={() => setActiveView('topic')}
        activeView={activeView}
        onViewChange={(v) => setActiveView(v === 'editor' && !currentEssay ? 'topic' : v)}
        streak={streak}
        isDarkMode={isDarkMode}
        onToggleDarkMode={() => setIsDarkMode((prev) => !prev)}
        isCompleted={currentEssay?.is_completed ?? false}
        onToggleComplete={currentEssay ? () => handleToggleComplete() : undefined}
      />

      <div className="flex-1 flex overflow-hidden">
        <Sidebar
          essays={essays}
          currentEssayId={currentEssay?.id ?? null}
          onSelectEssay={openEssay}
          onDeleteEssay={handleDeleteEssay}
          onToggleComplete={handleToggleComplete}
          streak={streak}
        />

        {activeView === 'topic' && <TopicPicker onStart={handleStartEssay} />}

        {activeView === 'editor' && currentEssay && (
          <GrammarlyEditor
            key={currentEssay.id}
            essay={currentEssay}
            onPromptChange={handlePromptChange}
            onRevise={handleRevise}
            previousBand={previousBand}
            content={content}
            onContentChange={handleContentChange}
            onReview={handleReview}
            isReviewing={isReviewing}
            pendingParts={pendingParts}
            reviewResult={reviewResult}
            suggestions={suggestions}
            onOpenAnkiModal={handleOpenAnkiModal}
            onOpenGrammarModal={setGrammarDraft}
            onShowToast={showToast}
          />
        )}

        {activeView === 'calendar' && (
          <EssayCalendar
            stats={stats}
            onSelectDate={handleSelectDate}
            currentDate={currentEssay?.date ?? ''}
          />
        )}

        {activeView === 'stats' && (
          <StatsDashboard stats={stats} onOpenAnkiModal={handleOpenAnkiModal} />
        )}
      </div>

      <GrammarCardModal
        draft={grammarDraft}
        onClose={() => setGrammarDraft(null)}
        ankiStatus={ankiStatus}
        onCardAdded={showToast}
      />

      {/* Anki Card Preview & Edit Modal */}
      <AnkiCardModal
        isOpen={ankiModal.isOpen}
        onClose={() => setAnkiModal((prev) => ({ ...prev, isOpen: false }))}
        cardType={ankiModal.cardType}
        initialText={ankiModal.text}
        context={ankiModal.context}
        ankiStatus={ankiStatus}
        onCardAdded={(msg) => {
          showToast(msg);
          refreshLists();
        }}
      />
    </div>
  );
}

const EMPTY_SCORE = { band: 0, comment: '', spread: 0 };

function emptyReview(essayId: string, content: string): ReviewResponse {
  return {
    essay_id: essayId,
    original_text: content,
    corrected_text: content,
    upgraded_text: '',
    overall_feedback: '',
    rubric: { task_response: EMPTY_SCORE, coherence: EMPTY_SCORE, lexical: EMPTY_SCORE, grammar: EMPTY_SCORE, overall_band: 0 },
    argument: { thesis: '', strongest_point: '', weakest_point: '', missing_counterargument: '', paragraph_comments: [] },
    revision_focus: [],
    recurring_patterns: [],
    suggestions: [],
    sentence_pairs: [],
    key_expressions: [],
  };
}

function mergeReviewPart(review: ReviewResponse, part: ReviewPart, data: any): ReviewResponse {
  switch (part) {
    case 'content_scores':
    case 'language_scores':
      return { ...review, rubric: { ...review.rubric, ...data } };
    case 'feedback':
    case 'corrections':
      return { ...review, ...data };
    default:
      return review;
  }
}

export default App;
