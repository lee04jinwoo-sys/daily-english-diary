import React from 'react';
import { Flame, BookOpen, PenTool, ShieldCheck, Sparkles } from 'lucide-react';
import { StatsResponse } from '../../types/diary';

interface StreakWidgetProps {
  stats: StatsResponse | null;
}

export const StreakWidget: React.FC<StreakWidgetProps> = ({ stats }) => {
  const currentStreak = stats?.current_streak ?? 0;
  const maxStreak = stats?.max_streak ?? 0;
  const totalWords = stats?.total_words ?? 0;
  const totalSentences = stats?.total_sentences ?? 0;
  const avgErrorDensity = stats?.avg_error_density ?? 0.0;
  const avgNci = stats?.avg_nci ?? 85.0;

  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3.5">
      {/* 1. Streak */}
      <div className="bg-white dark:bg-[#202020] border border-amber-200/70 dark:border-amber-900/40 rounded-2xl p-4 shadow-xs flex flex-col justify-between transition-colors">
        <div className="flex items-center justify-between">
          <span className="text-xs font-semibold text-amber-800 dark:text-amber-300">연속 작성 스트릭</span>
          <div className="p-1.5 rounded-lg bg-amber-50 dark:bg-amber-950/60 text-amber-600 dark:text-amber-400">
            <Flame className="w-4 h-4 fill-amber-500 text-amber-500" />
          </div>
        </div>
        <div className="mt-2.5">
          <div className="flex items-baseline space-x-1">
            <span className="text-2xl font-extrabold text-stone-900 dark:text-white font-serif">{currentStreak}</span>
            <span className="text-xs text-stone-500 dark:text-stone-400">일 연속</span>
          </div>
          <p className="text-[10px] text-stone-400 dark:text-stone-500 mt-0.5">최고 기록 {maxStreak}일</p>
        </div>
      </div>

      {/* 2. Error Density (100단어당 오류 건수) */}
      <div className="bg-white dark:bg-[#202020] border border-rose-200/70 dark:border-rose-900/40 rounded-2xl p-4 shadow-xs flex flex-col justify-between transition-colors">
        <div className="flex items-center justify-between">
          <span className="text-xs font-semibold text-rose-800 dark:text-rose-300">평균 오류 밀도</span>
          <div className="p-1.5 rounded-lg bg-rose-50 dark:bg-rose-950/60 text-rose-600 dark:text-rose-400">
            <ShieldCheck className="w-4 h-4" />
          </div>
        </div>
        <div className="mt-2.5">
          <div className="flex items-baseline space-x-1">
            <span className="text-2xl font-extrabold text-stone-900 dark:text-white font-serif">{avgErrorDensity}</span>
            <span className="text-xs text-stone-500 dark:text-stone-400">건 / 100단어</span>
          </div>
          <p className="text-[10px] text-stone-400 dark:text-stone-500 mt-0.5">100단어당 실제 교정 건수</p>
        </div>
      </div>

      {/* 3. Native Conformance Index (NCI %) */}
      <div className="bg-white dark:bg-[#202020] border border-emerald-200/70 dark:border-emerald-900/40 rounded-2xl p-4 shadow-xs flex flex-col justify-between transition-colors">
        <div className="flex items-center justify-between">
          <span className="text-xs font-semibold text-emerald-800 dark:text-emerald-300">원어민 일치율 (NCI)</span>
          <div className="p-1.5 rounded-lg bg-emerald-50 dark:bg-emerald-950/60 text-emerald-600 dark:text-emerald-400">
            <Sparkles className="w-4 h-4" />
          </div>
        </div>
        <div className="mt-2.5">
          <div className="flex items-baseline space-x-1">
            <span className="text-2xl font-extrabold text-stone-900 dark:text-white font-serif">{avgNci}%</span>
            <span className="text-xs text-stone-500 dark:text-stone-400">일치</span>
          </div>
          <p className="text-[10px] text-stone-400 dark:text-stone-500 mt-0.5">교정 없이 채택된 단어 비율</p>
        </div>
      </div>

      {/* 4. Total Words */}
      <div className="bg-white dark:bg-[#202020] border border-blue-200/70 dark:border-blue-900/40 rounded-2xl p-4 shadow-xs flex flex-col justify-between transition-colors">
        <div className="flex items-center justify-between">
          <span className="text-xs font-semibold text-blue-800 dark:text-blue-300">누적 작성 단어</span>
          <div className="p-1.5 rounded-lg bg-blue-50 dark:bg-blue-950/60 text-blue-600 dark:text-blue-400">
            <PenTool className="w-4 h-4" />
          </div>
        </div>
        <div className="mt-2.5">
          <div className="flex items-baseline space-x-1">
            <span className="text-2xl font-extrabold text-stone-900 dark:text-white font-serif">{totalWords.toLocaleString()}</span>
            <span className="text-xs text-stone-500 dark:text-stone-400">단어</span>
          </div>
          <p className="text-[10px] text-stone-400 dark:text-stone-500 mt-0.5">총 {stats?.total_diaries ?? 0}편의 일기</p>
        </div>
      </div>

      {/* 5. Total Sentences */}
      <div className="bg-white dark:bg-[#202020] border border-indigo-200/70 dark:border-indigo-900/40 rounded-2xl p-4 shadow-xs flex flex-col justify-between transition-colors">
        <div className="flex items-center justify-between">
          <span className="text-xs font-semibold text-indigo-800 dark:text-indigo-300">누적 문장 수</span>
          <div className="p-1.5 rounded-lg bg-indigo-50 dark:bg-indigo-950/60 text-indigo-600 dark:text-indigo-400">
            <BookOpen className="w-4 h-4" />
          </div>
        </div>
        <div className="mt-2.5">
          <div className="flex items-baseline space-x-1">
            <span className="text-2xl font-extrabold text-stone-900 dark:text-white font-serif">{totalSentences}</span>
            <span className="text-xs text-stone-500 dark:text-stone-400">문장</span>
          </div>
          <p className="text-[10px] text-stone-400 dark:text-stone-500 mt-0.5">총 {stats?.total_errors ?? 0}건 교정</p>
        </div>
      </div>
    </div>
  );
};
