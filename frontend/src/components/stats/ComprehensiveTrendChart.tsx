import React from 'react';
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  Legend,
  CartesianGrid,
} from 'recharts';
import { DailyTrendItem } from '../../types/essay';
import { LineChart as LineChartIcon } from 'lucide-react';

interface ComprehensiveTrendChartProps {
  data: DailyTrendItem[];
}

export const ComprehensiveTrendChart: React.FC<ComprehensiveTrendChartProps> = ({ data }) => {
  if (!data || data.length === 0) {
    return (
      <div className="bg-white dark:bg-[#202020] rounded-2xl border border-stone-200/80 dark:border-[#2e2e2e] p-8 text-center text-xs text-stone-400">
        표시할 추이 데이터가 없습니다.
      </div>
    );
  }

  const chartData = data.map((d) => {
    const parts = d.date.split('-');
    const label = parts.length === 3 ? `${parts[1]}/${parts[2]}` : d.date;
    return {
      ...d,
      displayDate: label,
      words: d.word_count,
      sentences: d.sentence_count,
      density: d.error_density ?? 0,
      accuracyDensity: d.accuracy_density ?? 0,
      idiomDensity: d.idiom_density ?? 0,
      styleDensity: d.style_density ?? 0,
      nciVal: d.nci ?? 85,
    };
  });

  return (
    <div className="bg-white dark:bg-[#202020] rounded-2xl border border-stone-200/80 dark:border-[#2e2e2e] p-6 shadow-xs space-y-4 transition-colors">
      <div className="flex items-center justify-between pb-3 border-b border-stone-100 dark:border-[#2a2a2a]">
        <div className="space-y-0.5">
          <h3 className="font-serif font-bold text-base text-stone-900 dark:text-[#f0f0f0] flex items-center space-x-2">
            <LineChartIcon className="w-5 h-5 text-indigo-600 dark:text-indigo-400" />
            <span>일자별 종합 학습 지표 (Volume, Sentences, NCI & Error Density)</span>
          </h3>
          <p className="text-xs text-stone-500 dark:text-stone-400">
            단어 수(보라), 문장 일치율(초록), 문장 수(파랑), 전체 오류 밀도(빨강)의 시계열 변화를 하나의 차트에서 비교합니다.
          </p>
        </div>
      </div>

      <div className="w-full h-80 pt-2">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={chartData} margin={{ top: 10, right: 20, left: -10, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#88888825" vertical={false} />
            <XAxis
              dataKey="displayDate"
              tick={{ fontSize: 11, fill: '#888888' }}
              tickLine={false}
              axisLine={{ stroke: '#88888840' }}
            />
            {/* Left Y-Axis: Word count (0 to ~500) */}
            <YAxis
              yAxisId="volume"
              orientation="left"
              tick={{ fontSize: 11, fill: '#888888' }}
              tickLine={false}
              axisLine={false}
              unit="w"
            />
            {/* Right Y-Axis: Rates, NCI %, and Counts (0 to 100) */}
            <YAxis
              yAxisId="metrics"
              orientation="right"
              domain={[0, 100]}
              tick={{ fontSize: 11, fill: '#888888' }}
              tickLine={false}
              axisLine={false}
            />
            <Tooltip
              contentStyle={{
                backgroundColor: 'rgba(25, 25, 25, 0.94)',
                borderRadius: '12px',
                border: '1px solid rgba(255, 255, 255, 0.15)',
                color: '#ffffff',
                fontSize: '12px',
                boxShadow: '0 10px 25px -5px rgba(0, 0, 0, 0.3)',
              }}
              labelStyle={{ fontWeight: 'bold', color: '#818cf8', marginBottom: '6px' }}
              formatter={(value: any, name: any, item: any) => {
                if (name === '단어 수') return [`${value} 단어`, name];
                if (name === '교정 없이 유지된 비율') return [`${value}%`, name];
                if (name === '문장 수') return [`${value} 문장`, name];
                if (name === '오류 밀도' || name === '오류 밀도 (전체)') {
                  const p = item.payload;
                  return [
                    `${value}건 / 100단어 (정확도: ${p.accuracyDensity}, 표현: ${p.idiomDensity}, 스타일: ${p.styleDensity})`,
                    name,
                  ];
                }
                return [value, name];
              }}
            />
            <Legend
              wrapperStyle={{ fontSize: '11px', paddingTop: '10px' }}
              iconType="circle"
              iconSize={8}
            />
            {/* 1. 단어 수: Indigo Solid Line */}
            <Line
              yAxisId="volume"
              type="monotone"
              dataKey="words"
              name="단어 수"
              stroke="#6366f1"
              strokeWidth={2.5}
              dot={{ r: 4, fill: '#6366f1' }}
              activeDot={{ r: 6, stroke: '#ffffff', strokeWidth: 2 }}
            />
            {/* 2. 교정 없이 유지된 비율 (NCI %): Emerald Solid Line */}
            <Line
              yAxisId="metrics"
              type="monotone"
              dataKey="nciVal"
              name="교정 없이 유지된 비율"
              stroke="#10b981"
              strokeWidth={2.5}
              dot={{ r: 4, fill: '#10b981' }}
              activeDot={{ r: 6, stroke: '#ffffff', strokeWidth: 2 }}
            />
            {/* 3. 문장 수: Blue Solid Line */}
            <Line
              yAxisId="metrics"
              type="monotone"
              dataKey="sentences"
              name="문장 수"
              stroke="#3b82f6"
              strokeWidth={2.5}
              dot={{ r: 4, fill: '#3b82f6' }}
              activeDot={{ r: 6, stroke: '#ffffff', strokeWidth: 2 }}
            />
            {/* 4. 오류 밀도: Rose Red Solid Line */}
            <Line
              yAxisId="metrics"
              type="monotone"
              dataKey="density"
              name="오류 밀도"
              stroke="#f43f5e"
              strokeWidth={2.5}
              dot={{ r: 4, fill: '#f43f5e' }}
              activeDot={{ r: 6, stroke: '#ffffff', strokeWidth: 2 }}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
};
