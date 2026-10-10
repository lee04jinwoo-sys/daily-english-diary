import React, { useState } from 'react';
import { DailyActivity, StatsResponse } from '../../types/essay';
import { StreakWidget } from './StreakWidget';
import { 
  ChevronLeft, 
  ChevronRight, 
  Calendar as CalendarIcon, 
  CheckCircle, 
  PenLine 
} from 'lucide-react';

interface DiaryCalendarProps {
  stats: StatsResponse | null;
  onSelectDate: (date: string) => void;
  currentDate: string;
}

export const DiaryCalendar: React.FC<DiaryCalendarProps> = ({
  stats,
  onSelectDate,
  currentDate,
}) => {
  const [viewDate, setViewDate] = useState(() => new Date());

  const year = viewDate.getFullYear();
  const month = viewDate.getMonth(); // 0-indexed

  const firstDayOfMonth = new Date(year, month, 1).getDay(); // 0 = Sunday
  const daysInMonth = new Date(year, month + 1, 0).getDate();

  const handlePrevMonth = () => {
    setViewDate(new Date(year, month - 1, 1));
  };

  const handleNextMonth = () => {
    setViewDate(new Date(year, month + 1, 1));
  };

  const handleToday = () => {
    setViewDate(new Date());
  };

  const monthNames = [
    '1월', '2월', '3월', '4월', '5월', '6월',
    '7월', '8월', '9월', '10월', '11월', '12월'
  ];

  const daysOfWeek = ['일', '월', '화', '수', '목', '금', '토'];

  // Build grid
  const days = [];
  for (let i = 0; i < firstDayOfMonth; i++) {
    days.push(null);
  }
  for (let d = 1; d <= daysInMonth; d++) {
    days.push(d);
  }

  const activityMap = stats?.daily_activity || {};

  return (
    <div className="flex-1 overflow-y-auto px-12 py-8 max-w-4xl mx-auto w-full space-y-8 transition-colors">
      {/* 1. Streak Overview */}
      <StreakWidget stats={stats} />

      {/* 2. Monthly Calendar Box */}
      <div className="bg-white dark:bg-[#222222] rounded-2xl border border-[#e9e8e4] dark:border-[#333333] p-6 shadow-xs space-y-6 transition-colors">
        {/* Calendar Navigation Header */}
        <div className="flex items-center justify-between pb-4 border-b border-stone-100 dark:border-[#2f2f2f]">
          <div className="flex items-center space-x-3">
            <div className="p-2 rounded-xl bg-stone-100 dark:bg-[#2c2c2c] text-stone-700 dark:text-stone-300">
              <CalendarIcon className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-base font-bold text-stone-900 dark:text-[#f0f0f0] font-serif">
                {year}년 {monthNames[month]}
              </h2>
              <p className="text-xs text-stone-500 dark:text-stone-400">
                날짜를 클릭하면 그날 쓴 에세이로 이동합니다.
              </p>
            </div>
          </div>

          <div className="flex items-center space-x-1.5">
            <button
              onClick={handleToday}
              className="px-3 py-1.5 text-xs font-semibold text-stone-600 dark:text-stone-300 hover:bg-stone-100 dark:hover:bg-[#2c2c2c] rounded-lg border border-stone-200 dark:border-[#3a3a3a] transition-colors"
            >
              오늘
            </button>
            <button
              onClick={handlePrevMonth}
              className="p-1.5 text-stone-500 dark:text-stone-400 hover:text-stone-900 dark:hover:text-stone-100 hover:bg-stone-100 dark:hover:bg-[#2c2c2c] rounded-lg transition-colors"
            >
              <ChevronLeft className="w-4 h-4" />
            </button>
            <button
              onClick={handleNextMonth}
              className="p-1.5 text-stone-500 dark:text-stone-400 hover:text-stone-900 dark:hover:text-stone-100 hover:bg-stone-100 dark:hover:bg-[#2c2c2c] rounded-lg transition-colors"
            >
              <ChevronRight className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* Days of Week Header */}
        <div className="grid grid-cols-7 gap-2 text-center text-xs font-semibold text-stone-400 dark:text-stone-500">
          {daysOfWeek.map((day, idx) => (
            <div key={idx} className={`py-1 ${idx === 0 ? 'text-red-400 dark:text-red-400/80' : idx === 6 ? 'text-blue-400 dark:text-blue-400/80' : ''}`}>
              {day}
            </div>
          ))}
        </div>

        {/* Calendar Day Tiles */}
        <div className="grid grid-cols-7 gap-2">
          {days.map((day, idx) => {
            if (day === null) {
              return <div key={`empty-${idx}`} className="h-24 rounded-xl bg-stone-50/40 dark:bg-stone-900/30 border border-transparent"></div>;
            }

            const dateStr = `${year}-${String(month + 1).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
            const activity: DailyActivity | undefined = activityMap[dateStr];
            const isToday = new Date().toISOString().slice(0, 10) === dateStr;
            const isSelected = currentDate === dateStr;

            const hasWritten = Boolean(activity && activity.best_band != null);
            const isDraftOnly = Boolean(activity && activity.best_band == null && activity.word_count > 0);

            return (
              <div
                key={dateStr}
                onClick={() => onSelectDate(dateStr)}
                className={`h-24 p-2 rounded-xl border flex flex-col justify-between transition-all cursor-pointer group ${
                  isSelected
                    ? 'border-stone-900 dark:border-stone-300 bg-stone-50 dark:bg-[#2c2c2c] shadow-xs ring-1 ring-stone-900 dark:ring-stone-300'
                    : hasWritten
                    ? 'bg-emerald-50/40 dark:bg-emerald-950/30 border-emerald-200 dark:border-emerald-800/40 hover:border-emerald-300 dark:hover:border-emerald-700 hover:bg-emerald-50/70 dark:hover:bg-emerald-950/50'
                    : isDraftOnly
                    ? 'bg-amber-50/40 dark:bg-amber-950/30 border-amber-200 dark:border-amber-800/40 hover:border-amber-300 dark:hover:border-amber-700'
                    : 'bg-white dark:bg-[#202020] border-stone-150 dark:border-[#2f2f2f] hover:border-stone-300 dark:hover:border-stone-600 hover:bg-stone-50/60 dark:hover:bg-[#262626]'
                }`}
              >
                {/* Day Header */}
                <div className="flex items-center justify-between">
                  <span
                    className={`text-xs font-semibold rounded-md px-1.5 py-0.5 ${
                      isToday
                        ? 'bg-stone-900 dark:bg-stone-100 text-white dark:text-stone-900'
                        : 'text-stone-700 dark:text-stone-300 group-hover:text-stone-900 dark:group-hover:text-white'
                    }`}
                  >
                    {day}
                  </span>

                  {hasWritten && (
                    <CheckCircle className="w-3.5 h-3.5 text-emerald-600 dark:text-emerald-400" />
                  )}
                </div>

                {/* Day Content Info */}
                <div className="space-y-1">
                  {hasWritten ? (
                    <>
                      <div className="text-[10px] text-emerald-800 dark:text-emerald-300 font-medium font-sans">
                        {activity!.essay_count}편 · {activity!.word_count} words
                      </div>
                      <div className="text-[9px] text-emerald-700 dark:text-emerald-300 bg-emerald-100/70 dark:bg-emerald-900/50 px-1 py-0.2 rounded font-semibold inline-block">
                        Band {activity!.best_band!.toFixed(1)}
                      </div>
                    </>
                  ) : isDraftOnly ? (
                    <div className="text-[10px] text-amber-700 dark:text-amber-400 font-medium">
                      첨삭 전
                    </div>
                  ) : (
                    <div className="text-[10px] text-stone-300 dark:text-stone-600 group-hover:text-stone-400 dark:group-hover:text-stone-400 flex items-center space-x-1">
                      <PenLine className="w-2.5 h-2.5" />
                      <span>-</span>
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
};
