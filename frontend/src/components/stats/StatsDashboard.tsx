import React, { useState, useMemo } from 'react';
import { StatsResponse, CardType } from '../../types/essay';
import { StreakWidget } from '../calendar/StreakWidget';
import { CoreMetricsChart } from './CoreMetricsChart';
import { VolumeChart } from './VolumeChart';
import { ErrorCategoryChart } from './ErrorCategoryChart';
import { ActivityHeatmap } from './ActivityHeatmap';
import { BandTrendChart } from './BandTrendChart';
import { 
  BarChart2, 
  AlertTriangle, 
  ArrowRight, 
  BookmarkPlus,
  CalendarDays
} from 'lucide-react';

interface StatsDashboardProps {
  stats: StatsResponse | null;
  onOpenAnkiModal: (cardType: CardType, text: string, context?: string) => void;
}

export const StatsDashboard: React.FC<StatsDashboardProps> = ({
  stats,
  onOpenAnkiModal,
}) => {
  const [period, setPeriod] = useState<'all' | '30d' | '7d'>('all');

  // Filter daily trends according to selected period
  const filteredTrends = useMemo(() => {
    const raw = stats?.daily_trends || [];
    if (period === 'all' || raw.length === 0) return raw;

    const today = new Date();
    const daysLimit = period === '7d' ? 7 : 30;
    const cutoff = new Date(today);
    cutoff.setDate(today.getDate() - daysLimit);
    const cutoffStr = cutoff.toISOString().slice(0, 10);

    return raw.filter((item) => item.date >= cutoffStr);
  }, [stats?.daily_trends, period]);

  const topSubcategories = stats?.top_subcategories || [];

  return (
    <div className="flex-1 overflow-y-auto px-6 sm:px-12 py-8 max-w-5xl mx-auto w-full space-y-7 transition-colors pb-24">
      {/* 1. Header Bar with Period Filters */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-2 border-b border-stone-200/60 dark:border-[#2b2b2b]">
        <div>
          <h1 className="font-serif font-bold text-2xl text-stone-900 dark:text-stone-100 flex items-center space-x-2.5">
            <BarChart2 className="w-6 h-6 text-blue-600 dark:text-blue-400" />
            <span>학습 분석 & 객관적 성장 지표</span>
          </h1>
          <p className="text-xs text-stone-500 dark:text-stone-400 mt-1">
            에세이별 Band 추이, 100단어당 교정 밀도, 작성 볼륨을 추적합니다.
          </p>
        </div>

        {/* Period Selector Tabs */}
        <div className="flex items-center space-x-1 p-1 bg-stone-100 dark:bg-[#252525] rounded-xl border border-stone-200/60 dark:border-[#333333] shrink-0 self-start sm:self-auto">
          <CalendarDays className="w-3.5 h-3.5 text-stone-400 ml-2 mr-1" />
          <button
            onClick={() => setPeriod('all')}
            className={`px-3 py-1 text-xs rounded-lg font-medium transition-all ${
              period === 'all'
                ? 'bg-white dark:bg-[#383838] text-stone-900 dark:text-white shadow-2xs font-semibold'
                : 'text-stone-500 dark:text-stone-400 hover:text-stone-800 dark:hover:text-stone-200'
            }`}
          >
            전체 기간
          </button>
          <button
            onClick={() => setPeriod('30d')}
            className={`px-3 py-1 text-xs rounded-lg font-medium transition-all ${
              period === '30d'
                ? 'bg-white dark:bg-[#383838] text-stone-900 dark:text-white shadow-2xs font-semibold'
                : 'text-stone-500 dark:text-stone-400 hover:text-stone-800 dark:hover:text-stone-200'
            }`}
          >
            최근 30일
          </button>
          <button
            onClick={() => setPeriod('7d')}
            className={`px-3 py-1 text-xs rounded-lg font-medium transition-all ${
              period === '7d'
                ? 'bg-white dark:bg-[#383838] text-stone-900 dark:text-white shadow-2xs font-semibold'
                : 'text-stone-500 dark:text-stone-400 hover:text-stone-800 dark:hover:text-stone-200'
            }`}
          >
            최근 7일
          </button>
        </div>
      </div>

      {/* 2. Top Metric Cards */}
      <StreakWidget stats={stats} />

      <BandTrendChart
        data={(stats?.band_trends || []).filter((b) => period === 'all' || filteredTrends.some((t) => t.date === b.date))}
        typeBands={stats?.type_bands || {}}
        avgBand={stats?.avg_band ?? null}
      />

      {/* 3. 2대 통합 꺾은선 차트 그리드 */}
      <div className="grid grid-cols-1 gap-6">
        {/* 교정 없이 유지된 비율 & 오류 밀도 통합 차트 (듀얼 Y축) */}
        <CoreMetricsChart data={filteredTrends} />

        {/* 단어 수 & 문장 수 작성 볼륨 통합 차트 (듀얼 Y축) */}
        <VolumeChart data={filteredTrends} />
      </div>

      {/* 5. Error Breakdown & Consistency Heatmap */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Error Donut Breakdown */}
        <ErrorCategoryChart categoryCounts={stats?.category_counts || {}} />

        {/* GitHub Consistency Heatmap */}
        <ActivityHeatmap dailyActivity={stats?.daily_activity || {}} />
      </div>

      {/* 6. Top Mistake Subcategories & Remedial Examples */}
      <div className="bg-white dark:bg-[#202020] rounded-2xl border border-stone-200/80 dark:border-[#2e2e2e] p-6 shadow-xs space-y-4 transition-colors">
        <div className="pb-3 border-b border-stone-100 dark:border-[#2a2a2a]">
          <h2 className="text-base font-bold text-stone-900 dark:text-[#f0f0f0] font-serif flex items-center space-x-2">
            <AlertTriangle className="w-5 h-5 text-amber-500" />
            <span>자주 틀리는 세부 문법 취약점 클리닉 (Frequent Weaknesses)</span>
          </h2>
          <p className="text-xs text-stone-500 dark:text-stone-400 mt-0.5">
            가장 빈번하게 첨삭된 패턴들을 확인하고 Anki 카드로 만들어 완벽하게 마스터해보세요.
          </p>
        </div>

        {topSubcategories.length === 0 ? (
          <div className="py-8 text-center text-xs text-stone-400 dark:text-stone-500">
            데이터가 충분히 모이면 자주 틀리는 문법 패턴이 여기에 자동으로 분석됩니다.
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-1">
            {topSubcategories.map((subcat, idx) => (
              <div
                key={idx}
                className="bg-stone-50/60 dark:bg-[#1a1a1a] border border-stone-200/60 dark:border-[#2e2e2e] rounded-xl p-4 space-y-3"
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center space-x-2">
                    <span className="text-xs font-bold text-stone-800 dark:text-stone-200 bg-stone-200/70 dark:bg-[#282828] px-2 py-0.5 rounded-md font-mono">
                      #{idx + 1}
                    </span>
                    <span className="text-xs font-bold text-stone-800 dark:text-stone-200">
                      {subcat.subcategory}
                    </span>
                  </div>
                  <span className="text-[11px] font-semibold text-amber-700 dark:text-amber-300 bg-amber-50 dark:bg-amber-950/60 px-2 py-0.5 rounded-md border border-amber-200/60 dark:border-amber-800/60">
                    {subcat.count}회 발생
                  </span>
                </div>

                {/* Examples */}
                <div className="space-y-2">
                  {subcat.examples.map((ex, exIdx) => (
                    <div
                      key={exIdx}
                      className="bg-white dark:bg-[#222222] border border-stone-200/60 dark:border-[#333333] rounded-lg p-3 text-xs space-y-1.5"
                    >
                      <div className="flex items-center space-x-2">
                        <span className="line-through text-red-500 dark:text-red-400 font-serif">
                          {ex.original}
                        </span>
                        <ArrowRight className="w-3 h-3 text-stone-400 shrink-0" />
                        <span className="text-emerald-700 dark:text-emerald-300 font-semibold font-serif">
                          {ex.suggested}
                        </span>
                      </div>
                      <div className="text-[11px] text-stone-600 dark:text-stone-400 font-sans leading-relaxed">
                        💡 {ex.explanation}
                      </div>

                      <div className="pt-1 flex justify-end">
                        <button
                          onClick={() => onOpenAnkiModal('sentence', ex.suggested, ex.explanation)}
                          className="flex items-center space-x-1 text-[11px] font-semibold text-blue-600 dark:text-blue-400 hover:bg-blue-50 dark:hover:bg-blue-950/50 px-2 py-1 rounded-md transition-colors"
                        >
                          <BookmarkPlus className="w-3.5 h-3.5" />
                          <span>Anki 카드로 만들기</span>
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};
