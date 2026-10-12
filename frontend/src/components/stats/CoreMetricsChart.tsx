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
import { EssayTrendItem } from '../../types/essay';
import { Sparkles } from 'lucide-react';

interface CoreMetricsChartProps {
  data: EssayTrendItem[];
}

export const CoreMetricsChart: React.FC<CoreMetricsChartProps> = ({ data }) => {
  if (!data || data.length === 0) return null;

  const chartData = data.map((d) => {
    const label = `${d.number}번`;
    return {
      ...d,
      displayDate: label,
      nciVal: d.nci ?? 85,
      accuracyDensity: d.accuracy_density ?? 0,
      idiomDensity: d.idiom_density ?? 0,
      styleDensity: d.style_density ?? 0,
      totalDensity: d.error_density ?? 0,
    };
  });

  return (
    <div className="bg-white dark:bg-[#202020] rounded-2xl border border-stone-200/80 dark:border-[#2e2e2e] p-6 shadow-xs space-y-4 transition-colors">
      <div className="flex items-center justify-between pb-3 border-b border-stone-100 dark:border-[#2a2a2a]">
        <div className="space-y-0.5">
          <h3 className="font-serif font-bold text-base text-stone-900 dark:text-[#f0f0f0] flex items-center space-x-2">
            <Sparkles className="w-5 h-5 text-emerald-600 dark:text-emerald-400" />
            <span>교정 없이 유지된 비율 & 3대 오류 밀도 추이</span>
          </h3>
          <p className="text-xs text-stone-500 dark:text-stone-400">
            교정 없이 유지된 비율(초록, 좌측 축)과 100단어당 오류 유형별 밀도(문법/정확도: 빨강, 표현/콜로케이션: 주황, 스타일: 하늘색, 우측 축)입니다.
          </p>
        </div>
      </div>

      <div className="w-full h-72 pt-2">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={chartData} margin={{ top: 10, right: 20, left: -10, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#88888825" vertical={false} />
            <XAxis
              dataKey="displayDate"
              tick={{ fontSize: 11, fill: '#888888' }}
              tickLine={false}
              axisLine={{ stroke: '#88888840' }}
            />
            {/* Left Y Axis: Native Conformance Index (%) */}
            <YAxis
              yAxisId="left"
              domain={[60, 100]}
              tick={{ fontSize: 11, fill: '#888888' }}
              tickLine={false}
              axisLine={false}
              unit="%"
            />
            {/* Right Y Axis: Error Density (건 / 100단어) */}
            <YAxis
              yAxisId="right"
              orientation="right"
              domain={[0, (dataMax: number) => Math.max(4.0, Math.ceil(dataMax + 1))]}
              tick={{ fontSize: 11, fill: '#888888' }}
              tickLine={false}
              axisLine={false}
              unit="건"
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
              labelStyle={{ fontWeight: 'bold', color: '#e0e7ff', marginBottom: '4px' }}
              formatter={(value: any, name: any) => {
                if (name === '교정 없이 유지된 비율') return [`${value}%`, name];
                if (
                  name === '문법/정확도 오류' ||
                  name === '원어민 표현 제안' ||
                  name === '스타일 팁'
                ) {
                  return [`${value}건 / 100단어`, name];
                }
                return [value, name];
              }}
            />
            <Legend
              wrapperStyle={{ fontSize: '11px', paddingTop: '10px' }}
              iconType="circle"
              iconSize={8}
            />
            {/* 1. Native Conformance Index (NCI %): Emerald */}
            <Line
              yAxisId="left"
              type="monotone"
              dataKey="nciVal"
              name="교정 없이 유지된 비율"
              stroke="#10b981"
              strokeWidth={3}
              dot={{ r: 4, fill: '#10b981' }}
              activeDot={{ r: 6, stroke: '#ffffff', strokeWidth: 2 }}
            />
            {/* 2. Accuracy Error Density: Red */}
            <Line
              yAxisId="right"
              type="monotone"
              dataKey="accuracyDensity"
              name="문법/정확도 오류"
              stroke="#ef4444"
              strokeWidth={2.5}
              dot={{ r: 4, fill: '#ef4444' }}
              activeDot={{ r: 6, stroke: '#ffffff', strokeWidth: 2 }}
            />
            {/* 3. Idiom Density: Amber */}
            <Line
              yAxisId="right"
              type="monotone"
              dataKey="idiomDensity"
              name="원어민 표현 제안"
              stroke="#f59e0b"
              strokeWidth={2.5}
              dot={{ r: 4, fill: '#f59e0b' }}
              activeDot={{ r: 6, stroke: '#ffffff', strokeWidth: 2 }}
            />
            {/* 4. Style Density: Sky Blue */}
            <Line
              yAxisId="right"
              type="monotone"
              dataKey="styleDensity"
              name="스타일 팁"
              stroke="#38bdf8"
              strokeWidth={2}
              strokeDasharray="4 3"
              dot={{ r: 3, fill: '#38bdf8' }}
              activeDot={{ r: 5, stroke: '#ffffff', strokeWidth: 2 }}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
};
