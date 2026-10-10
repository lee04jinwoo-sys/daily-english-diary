import React, { useMemo } from 'react';
import { DailyActivity } from '../../types/essay';
import { Calendar } from 'lucide-react';

interface ActivityHeatmapProps {
  dailyActivity: Record<string, DailyActivity>;
}

export const ActivityHeatmap: React.FC<ActivityHeatmapProps> = ({ dailyActivity }) => {
  // Generate last 16 weeks (112 days) up to today
  const { weeks, monthLabels } = useMemo(() => {
    const today = new Date();
    const days: Array<{ dateStr: string; dayOfWeek: number; activity?: DailyActivity }> = [];

    // 16 weeks * 7 days = 112 days
    const totalDays = 16 * 7;
    const startDay = new Date(today);
    startDay.setDate(today.getDate() - totalDays + (6 - today.getDay()));

    for (let i = 0; i < totalDays; i++) {
      const cur = new Date(startDay);
      cur.setDate(startDay.getDate() + i);
      const yyyy = cur.getFullYear();
      const mm = String(cur.getMonth() + 1).padStart(2, '0');
      const dd = String(cur.getDate()).padStart(2, '0');
      const dateStr = `${yyyy}-${mm}-${dd}`;

      days.push({
        dateStr,
        dayOfWeek: cur.getDay(),
        activity: dailyActivity[dateStr],
      });
    }

    // Split into columns of 7 days
    const weekCols: Array<typeof days> = [];
    for (let i = 0; i < days.length; i += 7) {
      weekCols.push(days.slice(i, i + 7));
    }

    // Month labels
    const labels: Array<{ text: string; colIndex: number }> = [];
    let lastMonth = -1;
    weekCols.forEach((col, idx) => {
      const firstDay = new Date(col[0].dateStr);
      const m = firstDay.getMonth();
      if (m !== lastMonth) {
        labels.push({ text: `${m + 1}월`, colIndex: idx });
        lastMonth = m;
      }
    });

    return { weeks: weekCols, monthLabels: labels };
  }, [dailyActivity]);

  const getColorClass = (act?: DailyActivity) => {
    if (!act || act.word_count === 0) {
      return 'bg-stone-100 dark:bg-[#262626] border-stone-200/50 dark:border-[#303030]';
    }
    const w = act.word_count;
    if (w < 100) {
      return 'bg-emerald-200 dark:bg-emerald-900/60 border-emerald-300 dark:border-emerald-800';
    }
    if (w < 250) {
      return 'bg-emerald-400 dark:bg-emerald-700 border-emerald-500 dark:border-emerald-600';
    }
    if (w < 400) {
      return 'bg-emerald-500 dark:bg-emerald-600 border-emerald-600 dark:border-emerald-500';
    }
    return 'bg-emerald-600 dark:bg-emerald-500 border-emerald-700 dark:border-emerald-400';
  };

  return (
    <div className="bg-white dark:bg-[#202020] rounded-2xl border border-stone-200/80 dark:border-[#2e2e2e] p-6 shadow-xs space-y-4 transition-colors">
      <div className="flex items-center justify-between pb-3 border-b border-stone-100 dark:border-[#2a2a2a]">
        <div className="space-y-0.5">
          <h3 className="font-serif font-bold text-base text-stone-900 dark:text-[#f0f0f0] flex items-center space-x-2">
            <Calendar className="w-5 h-5 text-emerald-600 dark:text-emerald-400" />
            <span>에세이 작성 잔디 히트맵 (Consistency Heatmap)</span>
          </h3>
          <p className="text-xs text-stone-500 dark:text-stone-400">
            최근 16주간의 에세이 작성 기록입니다. 색이 짙을수록 더 많은 영어 단어를 작성했습니다.
          </p>
        </div>
      </div>

      <div className="overflow-x-auto pb-2">
        <div className="inline-block min-w-full">
          {/* Month Header */}
          <div className="flex text-[10px] text-stone-400 font-sans mb-1.5 pl-6">
            {weeks.map((_, colIdx) => {
              const label = monthLabels.find((l) => l.colIndex === colIdx);
              return (
                <div key={colIdx} className="w-3.5 mr-1 text-center shrink-0">
                  {label ? label.text : ''}
                </div>
              );
            })}
          </div>

          {/* Days Grid */}
          <div className="flex items-start">
            {/* Day of Week Labels */}
            <div className="flex flex-col text-[9px] text-stone-400 pr-2 space-y-1 select-none font-sans shrink-0">
              <span className="h-3.5 leading-[14px]">일</span>
              <span className="h-3.5 leading-[14px] opacity-0">월</span>
              <span className="h-3.5 leading-[14px]">화</span>
              <span className="h-3.5 leading-[14px] opacity-0">수</span>
              <span className="h-3.5 leading-[14px]">목</span>
              <span className="h-3.5 leading-[14px] opacity-0">금</span>
              <span className="h-3.5 leading-[14px]">토</span>
            </div>

            {/* Weeks Columns */}
            <div className="flex space-x-1">
              {weeks.map((col, cIdx) => (
                <div key={cIdx} className="flex flex-col space-y-1">
                  {col.map((day) => {
                    const act = day.activity;
                    const tooltipText = act && act.word_count > 0
                      ? `${day.dateStr}: ${act.essay_count}편, ${act.word_count}단어${act.best_band != null ? ` (최고 Band ${act.best_band.toFixed(1)})` : ''}`
                      : `${day.dateStr}: 에세이 없음`;

                    return (
                      <div
                        key={day.dateStr}
                        title={tooltipText}
                        className={`w-3.5 h-3.5 rounded-[3px] border transition-transform hover:scale-125 cursor-pointer ${getColorClass(
                          act
                        )}`}
                      />
                    );
                  })}
                </div>
              ))}
            </div>
          </div>

          {/* Legend */}
          <div className="flex items-center justify-end space-x-1.5 text-[11px] text-stone-400 font-sans mt-3">
            <span>적음</span>
            <div className="w-3 h-3 rounded-xs bg-stone-100 dark:bg-[#262626] border border-stone-200/50 dark:border-[#303030]" />
            <div className="w-3 h-3 rounded-xs bg-emerald-200 dark:bg-emerald-900/60" />
            <div className="w-3 h-3 rounded-xs bg-emerald-400 dark:bg-emerald-700" />
            <div className="w-3 h-3 rounded-xs bg-emerald-500 dark:bg-emerald-600" />
            <div className="w-3 h-3 rounded-xs bg-emerald-600 dark:bg-emerald-500" />
            <span>많음</span>
          </div>
        </div>
      </div>
    </div>
  );
};
