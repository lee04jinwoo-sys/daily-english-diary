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
import { DailyTrendItem } from '../../types/diary';
import { PenTool } from 'lucide-react';

interface VolumeChartProps {
  data: DailyTrendItem[];
}

export const VolumeChart: React.FC<VolumeChartProps> = ({ data }) => {
  if (!data || data.length === 0) return null;

  const chartData = data.map((d) => {
    const parts = d.date.split('-');
    const label = parts.length === 3 ? `${parts[1]}/${parts[2]}` : d.date;
    return {
      ...d,
      displayDate: label,
    };
  });

  return (
    <div className="bg-white dark:bg-[#202020] rounded-2xl border border-stone-200/80 dark:border-[#2e2e2e] p-6 shadow-xs space-y-4 transition-colors">
      <div className="flex items-center justify-between pb-3 border-b border-stone-100 dark:border-[#2a2a2a]">
        <div className="space-y-0.5">
          <h3 className="font-serif font-bold text-base text-stone-900 dark:text-[#f0f0f0] flex items-center space-x-2">
            <PenTool className="w-5 h-5 text-indigo-600 dark:text-indigo-400" />
            <span>일자별 작성 볼륨 (단어 수 & 문장 수)</span>
          </h3>
          <p className="text-xs text-stone-500 dark:text-stone-400">
            작성한 단어 수(보라 실선, 좌측 축)와 문장 수(청록 실선, 우측 축)의 일자별 변화 추이입니다.
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
            {/* Left Y Axis: Word Count */}
            <YAxis
              yAxisId="left"
              tick={{ fontSize: 11, fill: '#888888' }}
              tickLine={false}
              axisLine={false}
              unit=" 단어"
            />
            {/* Right Y Axis: Sentence Count */}
            <YAxis
              yAxisId="right"
              orientation="right"
              tick={{ fontSize: 11, fill: '#888888' }}
              tickLine={false}
              axisLine={false}
              unit=" 문장"
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
              labelStyle={{ fontWeight: 'bold', color: '#c7d2fe', marginBottom: '4px' }}
              formatter={(value: any, name: any) => {
                if (name === '단어 수') return [`${value} 단어`, name];
                if (name === '문장 수') return [`${value} 문장`, name];
                return [value, name];
              }}
            />
            <Legend
              wrapperStyle={{ fontSize: '11px', paddingTop: '10px' }}
              iconType="circle"
              iconSize={8}
            />
            {/* 1. Word Count: Indigo Solid Line */}
            <Line
              yAxisId="left"
              type="monotone"
              dataKey="word_count"
              name="단어 수"
              stroke="#6366f1"
              strokeWidth={3}
              dot={{ r: 5, fill: '#6366f1' }}
              activeDot={{ r: 7, stroke: '#ffffff', strokeWidth: 2 }}
            />
            {/* 2. Sentence Count: Cyan Solid Line */}
            <Line
              yAxisId="right"
              type="monotone"
              dataKey="sentence_count"
              name="문장 수"
              stroke="#06b6d4"
              strokeWidth={3}
              dot={{ r: 5, fill: '#06b6d4' }}
              activeDot={{ r: 7, stroke: '#ffffff', strokeWidth: 2 }}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
};
