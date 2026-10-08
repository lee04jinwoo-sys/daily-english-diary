import { useState, useEffect, useRef, useCallback } from 'react';
import { api } from './api/client';
import { 
  DiaryListItem, 
  SuggestionItem, 
  ReviewResponse, 
  AnkiStatus, 
  CardType, 
  StatsResponse 
} from './types/diary';
import { Header } from './components/layout/Header';
import { Sidebar } from './components/layout/Sidebar';
import { GrammarlyEditor } from './components/editor/GrammarlyEditor';
import { AnkiCardModal } from './components/anki/AnkiCardModal';
import { DiaryCalendar } from './components/calendar/DiaryCalendar';
import { StatsDashboard } from './components/stats/StatsDashboard';
import confetti from 'canvas-confetti';

export function App() {
  const getTodayStr = () => new Date().toISOString().slice(0, 10);

  // States
  const [currentDate, setCurrentDate] = useState<string>(getTodayStr());
  const [title, setTitle] = useState<string>('');
  const [content, setContent] = useState<string>('');
  const [diaries, setDiaries] = useState<DiaryListItem[]>([]);
  const [suggestions, setSuggestions] = useState<SuggestionItem[]>([]);
  const [reviewResult, setReviewResult] = useState<ReviewResponse | null>(null);
  
  const [activeView, setActiveView] = useState<'editor' | 'calendar' | 'stats'>('editor');
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
    if (isDarkMode) {
      document.documentElement.classList.add('dark');
      document.body.classList.add('dark');
      try { localStorage.setItem('theme', 'dark'); } catch {}
    } else {
      document.documentElement.classList.remove('dark');
      document.body.classList.remove('dark');
      try { localStorage.setItem('theme', 'light'); } catch {}
    }
  }, [isDarkMode]);

  const toggleDarkMode = () => {
    setIsDarkMode((prev) => {
      const next = !prev;
      if (next) {
        document.documentElement.classList.add('dark');
        document.body.classList.add('dark');
        try { localStorage.setItem('theme', 'dark'); } catch {}
      } else {
        document.documentElement.classList.remove('dark');
        document.body.classList.remove('dark');
        try { localStorage.setItem('theme', 'light'); } catch {}
      }
      return next;
    });
  };

  // Toast Notification
  const [toastMessage, setToastMessage] = useState<string | null>(null);
  const [isCompleted, setIsCompleted] = useState<boolean>(false);

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

  const showToast = (msg: string) => {
    setToastMessage(msg);
    setTimeout(() => setToastMessage(null), 3000);
  };

  // Load Initial Data
  const loadDiariesAndStats = useCallback(async () => {
    try {
      const [diaryListRes, statsRes, ankiRes] = await Promise.allSettled([
        api.getDiaries(),
        api.getStats(),
        api.getAnkiStatus(),
      ]);

      if (diaryListRes.status === 'fulfilled') {
        setDiaries(diaryListRes.value.diaries);
        setStreak(diaryListRes.value.streak);
      }
      if (statsRes.status === 'fulfilled') {
        setStats(statsRes.value);
      }
      if (ankiRes.status === 'fulfilled') {
        setAnkiStatus(ankiRes.value);
      }
    } catch (e) {
      console.error('Failed to load initial data:', e);
    }
  }, []);

  useEffect(() => {
    loadDiariesAndStats();
  }, [loadDiariesAndStats]);

  useEffect(() => {
    if (activeView === 'stats') {
      api.getStats().then(setStats).catch(() => {});
    }
  }, [activeView]);

  // Load Diary for selected date
  const loadDiaryForDate = useCallback(async (date: string) => {
    try {
      const diary = await api.getDiary(date);
      setTitle(diary.title || '');
      setContent(diary.content || '');
      setIsCompleted(diary.is_completed || false);

      // Only load suggestions if this diary was actually reviewed (not an unreviewed draft)
      const isReviewed = !diary.is_draft && Boolean(diary.overall_feedback);

      if (isReviewed) {
        const savedSuggestions = await api.getDiarySuggestions(date);
        // Only keep suggestions whose phrase actually exists in the current content
        const validSuggestions = (savedSuggestions || []).filter((s) =>
          diary.content.includes(s.original_phrase)
        );
        setSuggestions(validSuggestions);

        setReviewResult({
          date: diary.date,
          original_text: diary.content,
          corrected_text: diary.corrected_content || diary.content,
          native_text: diary.native_content || diary.content,
          overall_feedback: diary.overall_feedback || '',
          followup_question: '',
          score: diary.grammar_score || 100,
          suggestions: validSuggestions,
          sentence_pairs: (diary as any).sentence_pairs || [],
          key_expressions: (diary as any).key_expressions || [],
        });
      } else {
        // Fresh draft or unreviewed diary: CLEAR ALL SUGGESTIONS!
        setSuggestions([]);
        setReviewResult(null);
      }
    } catch {
      // New or uncreated diary
      setTitle('');
      setContent('');
      setIsCompleted(false);
      setSuggestions([]);
      setReviewResult(null);
    }
  }, []);

  useEffect(() => {
    loadDiaryForDate(currentDate);
  }, [currentDate, loadDiaryForDate]);

  // Auto-save Debounce
  const autoSaveTimeoutRef = useRef<any>(null);

  const handleContentOrTitleChange = (newTitle: string, newContent: string) => {
    setTitle(newTitle);
    setContent(newContent);

    // If user modifies text significantly from reviewed text, clear stale suggestions
    if (reviewResult && newContent.trim() !== reviewResult.original_text.trim()) {
      setSuggestions([]);
      setReviewResult(null);
    }

    if (autoSaveTimeoutRef.current) {
      clearTimeout(autoSaveTimeoutRef.current);
    }

    autoSaveTimeoutRef.current = setTimeout(async () => {
      if (!newContent.trim() && !newTitle.trim()) return;
      setIsSaving(true);
      try {
        await api.saveDiary({
          date: currentDate,
          title: newTitle,
          content: newContent,
          is_draft: true,
          corrected_content: '',
          native_content: '',
          overall_feedback: '',
          grammar_score: 100,
          sentence_pairs: [],
          key_expressions: [],
        });
        const res = await api.getDiaries();
        setDiaries(res.diaries);
        setStreak(res.streak);
      } catch (e) {
        console.error('Auto-save error:', e);
      } finally {
        setIsSaving(false);
      }
    }, 1200);
  };

  // Trigger AI Review
  const handleReview = async () => {
    if (!content.trim()) return;

    setIsReviewing(true);
    try {
      const res = await api.reviewDiary({
        date: currentDate,
        title,
        content,
      });

      setReviewResult(res);
      setSuggestions(res.suggestions || []);

      // Auto-save reviewed result with sentence_pairs & key_expressions
      await api.saveDiary({
        date: currentDate,
        title,
        content,
        is_draft: false,
        corrected_content: res.corrected_text,
        native_content: res.native_text,
        overall_feedback: res.overall_feedback,
        grammar_score: res.score,
        sentence_pairs: res.sentence_pairs || [],
        key_expressions: res.key_expressions || [],
      });

      // Reload stats & diaries
      const [listRes, statsRes] = await Promise.all([api.getDiaries(), api.getStats()]);
      setDiaries(listRes.diaries);
      setStreak(listRes.streak);
      setStats(statsRes);

      // Celebration Confetti
      confetti({
        particleCount: 80,
        spread: 70,
        origin: { y: 0.7 },
      });
      showToast('AI 첨삭 및 문장별 학습 분석이 완료되었습니다! 🎉');
    } catch (e: any) {
      alert(`첨삭 처리 중 오류가 발생했습니다: ${e.message}`);
    } finally {
      setIsReviewing(false);
    }
  };

  // Grammarly One-Click Apply Engine with is_applied preservation
  const handleApplySuggestion = (suggestion: SuggestionItem) => {
    const origPhrase = suggestion.original_phrase;
    const repPhrase = suggestion.suggested_phrase;

    let newContent = content;
    const start = suggestion.start_idx;
    const end = suggestion.end_idx;

    if (start >= 0 && end > start && content.slice(start, end) === origPhrase) {
      newContent = content.slice(0, start) + repPhrase + content.slice(end);
    } else {
      newContent = content.replace(origPhrase, repPhrase);
    }

    const delta = repPhrase.length - (end - start);

    const updatedSuggestions = suggestions.map((s) => {
      if (s.id === suggestion.id) {
        return { ...s, is_applied: true };
      }
      if (s.start_idx > start) {
        return {
          ...s,
          start_idx: s.start_idx + delta,
          end_idx: s.end_idx + delta,
        };
      }
      return s;
    });

    setContent(newContent);
    setSuggestions(updatedSuggestions);
    handleContentOrTitleChange(title, newContent);
    showToast(`"${repPhrase}"으로 교정되었습니다.`);
  };

  // Dismiss Suggestion
  const handleDismissSuggestion = (id: string) => {
    setSuggestions((prev) => prev.filter((s) => s.id !== id));
  };

  // New Diary Handler
  const handleNewDiary = () => {
    const today = getTodayStr();
    setCurrentDate(today);
    setActiveView('editor');
  };

  // Delete Diary Handler
  const handleDeleteDiary = async (date: string) => {
    try {
      await api.deleteDiary(date);
      if (currentDate === date) {
        setTitle('');
        setContent('');
        setSuggestions([]);
        setReviewResult(null);
      }
      const [listRes, statsRes] = await Promise.all([api.getDiaries(), api.getStats()]);
      setDiaries(listRes.diaries);
      setStreak(listRes.streak);
      setStats(statsRes);
      showToast('일기가 삭제되었습니다.');
    } catch (e: any) {
      alert(`삭제 오류: ${e.message}`);
    }
  };

  const handleToggleComplete = async (targetDate?: string) => {
    const dateToToggle = targetDate || currentDate;
    try {
      const updated = await api.toggleDiaryComplete(dateToToggle);
      if (dateToToggle === currentDate) {
        setIsCompleted(updated.is_completed);
      }
      setDiaries((prev) =>
        prev.map((d) => (d.date === dateToToggle ? { ...d, is_completed: updated.is_completed } : d))
      );
      showToast(updated.is_completed ? '학습 완료로 표시되었습니다! 🎉' : '학습 완료가 해제되었습니다.');
    } catch (e: any) {
      showToast(`완료 상태 변경 실패: ${e.message}`);
    }
  };

  const handleOpenAnkiModal = (cardType: CardType, text: string, context?: string) => {
    setAnkiModal({
      isOpen: true,
      cardType,
      text,
      context,
    });
  };

  return (
    <div className="min-h-screen bg-[#fcfbf9] dark:bg-[#191919] text-[#37352f] dark:text-[#e6e6e6] flex flex-col font-sans transition-colors duration-200">
      {/* Toast Alert */}
      {toastMessage && (
        <div className="fixed top-16 right-8 z-50 bg-stone-900 dark:bg-stone-100 text-white dark:text-stone-900 text-xs font-semibold px-4 py-2.5 rounded-xl shadow-lg animate-in fade-in slide-in-from-top-2 duration-150 flex items-center space-x-2">
          <span>✨</span>
          <span>{toastMessage}</span>
        </div>
      )}

      {/* Top Header */}
      <Header
        currentDate={currentDate}
        onDateChange={(d) => {
          setCurrentDate(d);
          setActiveView('editor');
        }}
        ankiStatus={ankiStatus}
        onRefreshAnki={loadDiariesAndStats}
        isSaving={isSaving}
        onNewDiary={handleNewDiary}
        activeView={activeView}
        onViewChange={setActiveView}
        streak={streak}
        isDarkMode={isDarkMode}
        onToggleDarkMode={toggleDarkMode}
        isCompleted={isCompleted}
        onToggleComplete={() => handleToggleComplete()}
      />

      {/* Main Container */}
      <div className="flex-1 flex overflow-hidden">
        {/* Left Sidebar */}
        <Sidebar
          diaries={diaries}
          currentDate={currentDate}
          onSelectDate={(d) => {
            setCurrentDate(d);
            setActiveView('editor');
          }}
          onDeleteDiary={handleDeleteDiary}
          onToggleComplete={handleToggleComplete}
          streak={streak}
        />

        {/* Center Workspace */}
        {activeView === 'editor' && (
          <GrammarlyEditor
            title={title}
            onTitleChange={(t) => handleContentOrTitleChange(t, content)}
            content={content}
            onContentChange={(c) => handleContentOrTitleChange(title, c)}
            onReview={handleReview}
            isReviewing={isReviewing}
            reviewResult={reviewResult}
            suggestions={suggestions}
            onApplySuggestion={handleApplySuggestion}
            onDismissSuggestion={handleDismissSuggestion}
            onOpenAnkiModal={handleOpenAnkiModal}
            diaryDate={currentDate}
            onShowToast={showToast}
          />
        )}

        {activeView === 'calendar' && (
          <DiaryCalendar
            stats={stats}
            onSelectDate={(d) => {
              setCurrentDate(d);
              setActiveView('editor');
            }}
            currentDate={currentDate}
          />
        )}

        {activeView === 'stats' && (
          <StatsDashboard
            stats={stats}
            onOpenAnkiModal={handleOpenAnkiModal}
          />
        )}
      </div>

      {/* Anki Card Preview & Edit Modal */}
      <AnkiCardModal
        isOpen={ankiModal.isOpen}
        onClose={() => setAnkiModal((prev) => ({ ...prev, isOpen: false }))}
        cardType={ankiModal.cardType}
        initialText={ankiModal.text}
        context={ankiModal.context}
        diaryDate={currentDate}
        ankiStatus={ankiStatus}
        onCardAdded={(msg) => {
          showToast(msg);
          loadDiariesAndStats();
        }}
      />
    </div>
  );
}

export default App;
