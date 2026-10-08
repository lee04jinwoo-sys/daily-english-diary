import React, { useState } from 'react';
import { AnkiStatus } from '../../types/diary';
import { api } from '../../api/client';
import { 
  Calendar as CalendarIcon, 
  CheckCircle2, 
  RefreshCw, 
  Zap, 
  Plus, 
  BarChart3, 
  BookOpen, 
  Flame,
  Sun,
  Moon
} from 'lucide-react';

interface HeaderProps {
  currentDate: string;
  onDateChange: (date: string) => void;
  ankiStatus: AnkiStatus | null;
  onRefreshAnki: () => void;
  isSaving: boolean;
  onNewDiary: () => void;
  activeView: 'editor' | 'calendar' | 'stats';
  onViewChange: (view: 'editor' | 'calendar' | 'stats') => void;
  streak: number;
  isDarkMode: boolean;
  onToggleDarkMode: () => void;
  isCompleted?: boolean;
  onToggleComplete?: () => void;
}

export const Header: React.FC<HeaderProps> = ({
  currentDate,
  onDateChange,
  ankiStatus,
  onRefreshAnki,
  isSaving,
  onNewDiary,
  activeView,
  onViewChange,
  streak,
  isDarkMode,
  onToggleDarkMode,
  isCompleted = false,
  onToggleComplete,
}) => {
  const [isLaunchingAnki, setIsLaunchingAnki] = useState(false);

  const handleLaunchAnki = async () => {
    try {
      setIsLaunchingAnki(true);
      await api.launchAnki();
      setTimeout(() => {
        onRefreshAnki();
        setIsLaunchingAnki(false);
      }, 2500);
    } catch {
      setIsLaunchingAnki(false);
    }
  };

  return (
    <header className="h-14 border-b border-[#e9e8e4] dark:border-[#2f2f2f] bg-[#faf9f6]/95 dark:bg-[#1c1c1c]/95 backdrop-blur px-4 sm:px-6 flex items-center justify-between sticky top-0 z-20 transition-colors">
      {/* Left: Brand & Navigation */}
      <div className="flex items-center space-x-4 sm:space-x-6 min-w-0">
        <div className="flex items-center space-x-2 cursor-pointer shrink-0" onClick={() => onViewChange('editor')}>
          <span className="text-xl">✍️</span>
          <span className="font-serif font-semibold text-lg text-[#37352f] dark:text-[#f0f0f0] tracking-tight">
            Daily English Diary
          </span>
        </div>

        {/* View Tabs */}
        <div className="flex items-center bg-[#efeee9] dark:bg-[#282828] p-0.5 rounded-lg text-xs font-medium text-[#787774] dark:text-[#a0a0a0] shrink-0">
          <button
            onClick={() => onViewChange('editor')}
            className={`flex items-center space-x-1 px-3 py-1.5 rounded-md transition-all ${
              activeView === 'editor'
                ? 'bg-white dark:bg-[#383838] text-[#37352f] dark:text-white shadow-xs font-semibold'
                : 'hover:text-[#37352f] dark:hover:text-white'
            }`}
          >
            <BookOpen className="w-3.5 h-3.5" />
            <span>일기 에디터</span>
          </button>
          <button
            onClick={() => onViewChange('calendar')}
            className={`flex items-center space-x-1 px-3 py-1.5 rounded-md transition-all ${
              activeView === 'calendar'
                ? 'bg-white dark:bg-[#383838] text-[#37352f] dark:text-white shadow-xs font-semibold'
                : 'hover:text-[#37352f] dark:hover:text-white'
            }`}
          >
            <CalendarIcon className="w-3.5 h-3.5" />
            <span>캘린더 & 스트릭</span>
          </button>
          <button
            onClick={() => onViewChange('stats')}
            className={`flex items-center space-x-1 px-3 py-1.5 rounded-md transition-all ${
              activeView === 'stats'
                ? 'bg-white dark:bg-[#383838] text-[#37352f] dark:text-white shadow-xs font-semibold'
                : 'hover:text-[#37352f] dark:hover:text-white'
            }`}
          >
            <BarChart3 className="w-3.5 h-3.5" />
            <span>학습 분석</span>
          </button>
        </div>
      </div>

      {/* Right: Streak, Date, Auto-save, Anki, Dark Mode Toggle, New Diary */}
      <div className="flex items-center space-x-2.5 sm:space-x-3.5 shrink-0">
        {/* Streak Counter */}
        <div 
          className="flex items-center space-x-1.5 px-2.5 py-1 rounded-full bg-amber-50 dark:bg-amber-950/40 border border-amber-200 dark:border-amber-800 text-amber-800 dark:text-amber-300 text-xs font-semibold cursor-pointer hover:bg-amber-100 dark:hover:bg-amber-900/50 transition-colors"
          onClick={() => onViewChange('calendar')}
          title="연속 작성 스트릭"
        >
          <Flame className="w-4 h-4 text-amber-500 fill-amber-500 animate-pulse" />
          <span>{streak}일 연속</span>
        </div>

        {/* Date Picker */}
        <div className="flex items-center space-x-1.5 text-xs text-[#55534e] dark:text-[#b0b0b0] bg-white dark:bg-[#252525] border border-[#e2e1db] dark:border-[#383838] px-2.5 py-1 rounded-md shadow-xs">
          <CalendarIcon className="w-3.5 h-3.5 text-[#787774] dark:text-[#888888]" />
          <input
            type="date"
            value={currentDate}
            onChange={(e) => onDateChange(e.target.value)}
            className="bg-transparent outline-none text-xs text-[#37352f] dark:text-[#e0e0e0] font-medium cursor-pointer"
          />
        </div>

        {/* Auto-save status */}
        <div className="flex items-center space-x-1 text-xs text-[#787774] dark:text-[#999999] min-w-[70px]">
          {isSaving ? (
            <span className="flex items-center space-x-1 text-amber-600 dark:text-amber-400">
              <RefreshCw className="w-3 h-3 animate-spin" />
              <span>저장 중..</span>
            </span>
          ) : (
            <span className="flex items-center space-x-1 text-emerald-600 dark:text-emerald-400">
              <CheckCircle2 className="w-3 h-3" />
              <span>저장됨</span>
            </span>
          )}
        </div>

        {/* Diary Completion Toggle */}
        {onToggleComplete && (
          <button
            onClick={onToggleComplete}
            className={`flex items-center space-x-1 px-2.5 py-1 rounded-full text-xs font-semibold transition-all border shadow-xs ${
              isCompleted
                ? 'bg-emerald-100 dark:bg-emerald-950 text-emerald-800 dark:text-emerald-300 border-emerald-300 dark:border-emerald-700'
                : 'bg-white dark:bg-[#252525] text-stone-600 dark:text-stone-300 hover:text-emerald-700 dark:hover:text-emerald-300 hover:border-emerald-300 dark:hover:border-emerald-700 border-stone-200 dark:border-stone-700'
            }`}
            title={isCompleted ? '학습 완료 해제' : '오늘의 일기 학습 완료로 표시'}
          >
            <CheckCircle2 className={`w-3.5 h-3.5 ${isCompleted ? 'text-emerald-600 dark:text-emerald-400' : 'text-stone-400 dark:text-stone-500'}`} />
            <span>{isCompleted ? '학습 완료됨 ✓' : '학습 완료'}</span>
          </button>
        )}

        {/* Anki Connection Pill */}
        <div className="flex items-center space-x-1.5">
          {ankiStatus?.connected ? (
            <div 
              className="flex items-center space-x-1.5 px-2.5 py-1 rounded-full bg-blue-50 dark:bg-blue-950/40 border border-blue-200 dark:border-blue-800 text-blue-800 dark:text-blue-300 text-xs font-medium cursor-default"
              title="AnkiConnect 연결됨 (문장/단어 카드 추가 가능)"
            >
              <span className="w-2 h-2 rounded-full bg-blue-500 animate-pulse"></span>
              <span>Anki 연동됨</span>
            </div>
          ) : (
            <button
              onClick={handleLaunchAnki}
              disabled={isLaunchingAnki}
              className="flex items-center space-x-1 px-2.5 py-1 rounded-full bg-stone-100 dark:bg-[#2c2c2c] hover:bg-stone-200 dark:hover:bg-[#383838] border border-stone-300 dark:border-[#444444] text-stone-700 dark:text-stone-300 text-xs font-medium transition-colors"
              title="클릭하여 Anki 앱을 실행합니다"
            >
              <Zap className={`w-3 h-3 text-stone-500 dark:text-stone-400 ${isLaunchingAnki ? 'animate-spin' : ''}`} />
              <span>{isLaunchingAnki ? 'Anki 실행 중...' : 'Anki 실행'}</span>
            </button>
          )}
        </div>

        {/* Dark Mode Toggle Button */}
        <button
          type="button"
          onClick={onToggleDarkMode}
          className="p-1.5 rounded-lg bg-[#efeee9] dark:bg-[#2a2a2a] hover:bg-[#e2e1db] dark:hover:bg-[#383838] text-stone-700 dark:text-amber-300 border border-[#e2e1db] dark:border-[#3a3a3a] transition-all shadow-xs shrink-0 cursor-pointer"
          title={isDarkMode ? '라이트 모드로 전환' : '다크 모드로 전환'}
          aria-label={isDarkMode ? '라이트 모드로 전환' : '다크 모드로 전환'}
        >
          {isDarkMode ? (
            <Sun className="w-4 h-4 text-amber-500 fill-amber-500/20" />
          ) : (
            <Moon className="w-4 h-4 text-stone-700" />
          )}
        </button>

        {/* New Diary Button */}
        <button
          onClick={onNewDiary}
          className="flex items-center space-x-1.5 px-3 py-1.5 bg-[#2c2b28] hover:bg-[#1c1b18] dark:bg-[#e6e6e6] dark:hover:bg-white dark:text-[#191919] text-white text-xs font-medium rounded-lg shadow-xs transition-all active:scale-95"
        >
          <Plus className="w-3.5 h-3.5" />
          <span>오늘 일기</span>
        </button>
      </div>
    </header>
  );
};
