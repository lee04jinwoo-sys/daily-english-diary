import React from 'react';
import { ResponsiveContainer, PieChart, Pie, Cell, Tooltip } from 'recharts';
import { PieChart as PieChartIcon } from 'lucide-react';

interface ErrorCategoryChartProps {
  categoryCounts: Record<string, number>;
}

const CATEGORY_COLORS: Record<string, string> = {
  Grammar: '#ef4444',
  Spelling: '#f97316',
  Clarity: '#8b5cf6',
  'Natural Expression': '#3b82f6',
  Vocabulary: '#10b981',
};

const DEFAULT_COLOR = '#6b7280';

export const ErrorCategoryChart: React.FC<ErrorCategoryChartProps> = ({ categoryCounts }) => {
  // Aggregate subcategories like "Grammar:관사" into main categories
  const aggregated: Record<string, number> = {};
  Object.entries(categoryCounts).forEach(([rawCat, count]) => {
    const mainCat = rawCat.split(':')[0].trim();
    aggregated[mainCat] = (aggregated[mainCat] || 0) + count;
  });

  const total = Object.values(aggregated).reduce((a, b) => a + b, 0);

  const chartData = Object.entries(aggregated).map(([name, value]) => ({
    name,
    value,
    percentage: total > 0 ? Math.round((value / total) * 100) : 0,
    color: CATEGORY_COLORS[name] || DEFAULT_COLOR,
  }));

  if (total === 0) {
    return (
      <div className="bg-white dark:bg-[#202020] rounded-2xl border border-stone-200/80 dark:border-[#2e2e2e] p-8 text-center text-xs text-stone-400">
        아직 기록된 첨삭 에러 데이터가 없습니다.
      </div>
    );
  }

  return (
    <div className="bg-white dark:bg-[#202020] rounded-2xl border border-stone-200/80 dark:border-[#2e2e2e] p-6 shadow-xs space-y-4 transition-colors">
      <div className="flex items-center justify-between pb-3 border-b border-stone-100 dark:border-[#2a2a2a]">
        <div className="space-y-0.5">
          <h3 className="font-serif font-bold text-base text-stone-900 dark:text-[#f0f0f0] flex items-center space-x-2">
            <PieChartIcon className="w-5 h-5 text-purple-600 dark:text-purple-400" />
            <span>첨삭 피드백 유형별 비중 (Error Distribution)</span>
          </h3>
          <p className="text-xs text-stone-500 dark:text-stone-400">
            총 {total}건의 피드백 중 문법, 철자, 어휘, 자연스러움의 비율입니다.
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 items-center pt-2">
        {/* Donut Chart */}
        <div className="w-full h-52 relative flex items-center justify-center">
          <ResponsiveContainer width="100%" height="100%">
            <PieChart>
              <Pie
                data={chartData}
                cx="50%"
                cy="50%"
                innerRadius={50}
                outerRadius={80}
                paddingAngle={4}
                dataKey="value"
              >
                {chartData.map((entry, index) => (
                  <Cell key={`cell-${index}`} fill={entry.color} />
                ))}
              </Pie>
              <Tooltip
                contentStyle={{
                  backgroundColor: 'rgba(25, 25, 25, 0.92)',
                  borderRadius: '12px',
                  border: '1px solid rgba(255, 255, 255, 0.15)',
                  color: '#ffffff',
                  fontSize: '12px',
                }}
                formatter={(val: any, name: any) => [`${val}건`, name]}
              />
            </PieChart>
          </ResponsiveContainer>

          {/* Center Stat */}
          <div className="absolute flex flex-col items-center justify-center pointer-events-none">
            <span className="text-xl font-bold font-mono text-stone-900 dark:text-white">
              {total}
            </span>
            <span className="text-[10px] text-stone-400 dark:text-stone-500 font-sans">
              총 피드백
            </span>
          </div>
        </div>

        {/* Categories Bar Breakdown */}
        <div className="space-y-3">
          {chartData.map((item) => (
            <div key={item.name} className="space-y-1">
              <div className="flex items-center justify-between text-xs font-medium text-stone-700 dark:text-stone-300">
                <span className="flex items-center space-x-2">
                  <span
                    className="w-2.5 h-2.5 rounded-full shrink-0"
                    style={{ backgroundColor: item.color }}
                  />
                  <span>{item.name}</span>
                </span>
                <span className="text-stone-500 dark:text-stone-400 font-sans">
                  {item.value}건 ({item.percentage}%)
                </span>
              </div>
              <div className="w-full h-2 bg-stone-100 dark:bg-[#1a1a1a] rounded-full overflow-hidden">
                <div
                  className="h-full rounded-full transition-all duration-500"
                  style={{ width: `${item.percentage}%`, backgroundColor: item.color }}
                />
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};
