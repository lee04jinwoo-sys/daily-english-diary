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
import { BandTrendItem, ESSAY_TYPE_LABELS, EssayType } from '../../types/essay';
import { Scale } from 'lucide-react';

interface BandTrendChartProps {
  data: BandTrendItem[];
  typeBands: Record<string, number>;
  avgBand: number | null;
}

const SERIES: Array<{ key: keyof BandTrendItem; name: string; color: string; width: number }> = [
  { key: 'overall_band', name: '종합', color: '#6366f1', width: 3 },
  { key: 'task_response', name: '과제 수행', color: '#f43f5e', width: 1.5 },
  { key: 'coherence', name: '구성·흐름', color: '#f59e0b', width: 1.5 },
  { key: 'lexical', name: '어휘', color: '#10b981', width: 1.5 },
  { key: 'grammar', name: '문법', color: '#0ea5e9', width: 1.5 },
];

export const BandTrendChart: React.FC<BandTrendChartProps> = ({ data, typeBands, avgBand }) => {
  const chartData = data.map((d, i) => {
    const [, m, day] = d.date.split('-');
    return { ...d, label: `${i + 1} (${m}/${day})` };
  });
  const typeEntries = Object.entries(typeBands).sort((a, b) => a[1] - b[1]);

  return (
    <div className="bg-white dark:bg-[#202020] rounded-2xl border border-stone-200/80 dark:border-[#2e2e2e] p-6 shadow-xs space-y-4 transition-colors">
      <div className="flex items-start justify-between pb-3 border-b border-stone-100 dark:border-[#2a2a2a]">
        <div className="space-y-0.5">
          <h3 className="font-serif font-bold text-base text-stone-900 dark:text-[#f0f0f0] flex items-center space-x-2">
            <Scale className="w-5 h-5 text-indigo-600 dark:text-indigo-400" />
            <span>참고: 에세이별 점수 추이 (AI 추정)</span>
          </h3>
          <p className="text-xs text-stone-500 dark:text-stone-400">
            AI 채점은 같은 글에도 0.5 정도 흔들릴 수 있습니다. 한 편의 점수보다 여러 편에 걸친 방향을 보세요.
          </p>
        </div>
        {avgBand != null && (
          <div className="text-right shrink-0">
            <div className="text-[10px] text-stone-400 dark:text-stone-500">평균</div>
            <div className="text-lg font-bold tabular-nums text-indigo-700 dark:text-indigo-300">{avgBand.toFixed(1)}</div>
          </div>
        )}
      </div>

      {chartData.length === 0 ? (
        <div className="py-8 text-center text-xs text-stone-400 dark:text-stone-500">
          첨삭받은 에세이가 생기면 Band 추이가 여기에 표시됩니다.
        </div>
      ) : (
        <div className="w-full h-72 pt-2">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={chartData} margin={{ top: 10, right: 20, left: -10, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#88888825" vertical={false} />
              <XAxis dataKey="label" tick={{ fontSize: 11, fill: '#888888' }} tickLine={false} axisLine={{ stroke: '#88888840' }} />
              <YAxis domain={[4, 9]} ticks={[4, 5, 6, 7, 8, 9]} tick={{ fontSize: 11, fill: '#888888' }} tickLine={false} axisLine={false} />
              <Tooltip
                contentStyle={{
                  backgroundColor: 'rgba(25, 25, 25, 0.94)',
                  borderRadius: '12px',
                  border: '1px solid rgba(255, 255, 255, 0.15)',
                  color: '#ffffff',
                  fontSize: '12px',
                }}
                labelFormatter={(_, payload) => {
                  const item = payload?.[0]?.payload as BandTrendItem | undefined;
                  if (!item) return '';
                  const rev = item.revision_of ? ' · 고쳐 쓰기' : '';
                  return `${item.date} · ${ESSAY_TYPE_LABELS[item.essay_type]}${rev}`;
                }}
              />
              <Legend wrapperStyle={{ fontSize: '11px', paddingTop: '10px' }} iconType="circle" iconSize={8} />
              {SERIES.map((s) => (
                <Line
                  key={s.key}
                  type="monotone"
                  dataKey={s.key}
                  name={s.name}
                  stroke={s.color}
                  strokeWidth={s.width}
                  dot={{ r: s.width > 2 ? 4 : 2, fill: s.color }}
                />
              ))}
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}

      {typeEntries.length > 0 && (
        <div className="pt-2 border-t border-stone-100 dark:border-[#2a2a2a]">
          <div className="text-[11px] font-semibold text-stone-500 dark:text-stone-400 mb-2">유형별 평균 Band (낮은 순)</div>
          <div className="flex flex-wrap gap-2">
            {typeEntries.map(([type, band]) => (
              <span
                key={type}
                className="text-xs px-2.5 py-1 rounded-lg bg-stone-50 dark:bg-[#1a1a1a] border border-stone-200 dark:border-[#333333] text-stone-700 dark:text-stone-300"
              >
                {ESSAY_TYPE_LABELS[type as EssayType] ?? type}{' '}
                <span className="font-bold tabular-nums text-indigo-700 dark:text-indigo-300">{band.toFixed(1)}</span>
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};
