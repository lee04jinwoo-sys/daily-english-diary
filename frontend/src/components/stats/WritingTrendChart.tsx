import React from 'react';
import { ResponsiveContainer, LineChart, Line, XAxis, YAxis, Tooltip, Legend, CartesianGrid } from 'recharts';
import { ESSAY_TYPE_LABELS, WritingSignal, WritingTrendItem } from '../../types/essay';
import { Gauge } from 'lucide-react';

interface WritingTrendChartProps {
  data: WritingTrendItem[];
}

// Must match backend/app/services/stats_service.py writing_signal().
const SIGNALS: Record<WritingSignal, { label: string; hint: string; className: string }> = {
  improving: {
    label: '실력 향상',
    hint: '더 빨라졌거나 오류가 줄었고, 다른 쪽은 나빠지지 않았습니다.',
    className: 'bg-emerald-50 text-emerald-700 border-emerald-200 dark:bg-emerald-950/30 dark:text-emerald-300 dark:border-emerald-900/50',
  },
  rushed: {
    label: '서두름',
    hint: '빨라졌지만 필수 교정도 늘었습니다. 속도보다 정확도를 먼저 챙기세요.',
    className: 'bg-amber-50 text-amber-700 border-amber-200 dark:bg-amber-950/30 dark:text-amber-300 dark:border-amber-900/50',
  },
  careful: {
    label: '신중해짐',
    hint: '느려졌지만 필수 교정이 줄었습니다.',
    className: 'bg-sky-50 text-sky-700 border-sky-200 dark:bg-sky-950/30 dark:text-sky-300 dark:border-sky-900/50',
  },
  declining: {
    label: '오류 증가',
    hint: '빨라지지 않았는데 필수 교정이 늘었습니다.',
    className: 'bg-rose-50 text-rose-700 border-rose-200 dark:bg-rose-950/30 dark:text-rose-300 dark:border-rose-900/50',
  },
  slower: {
    label: '느려짐',
    hint: '정확도는 비슷한데 속도가 줄었습니다.',
    className: 'bg-stone-100 text-stone-600 border-stone-200 dark:bg-[#262626] dark:text-stone-300 dark:border-[#333333]',
  },
  steady: {
    label: '비슷함',
    hint: '속도와 정확도 모두 직전 글들과 비슷합니다.',
    className: 'bg-stone-100 text-stone-600 border-stone-200 dark:bg-[#262626] dark:text-stone-300 dark:border-[#333333]',
  },
};

export const WritingTrendChart: React.FC<WritingTrendChartProps> = ({ data }) => {
  const chartData = data.map((d, i) => {
    const [, m, day] = d.date.split('-');
    return { ...d, label: `${i + 1} (${m}/${day})` };
  });

  return (
    <div className="bg-white dark:bg-[#202020] rounded-2xl border border-stone-200/80 dark:border-[#2e2e2e] p-6 shadow-xs space-y-4 transition-colors">
      <div className="pb-3 border-b border-stone-100 dark:border-[#2a2a2a] space-y-0.5">
        <h3 className="font-serif font-bold text-base text-stone-900 dark:text-[#f0f0f0] flex items-center space-x-2">
          <Gauge className="w-5 h-5 text-emerald-600 dark:text-emerald-400" />
          <span>쓰기 속도와 정확도</span>
        </h3>
        <p className="text-xs text-stone-500 dark:text-stone-400">
          속도(분당 단어)와 필수 교정 밀도(100단어당)를 함께 봅니다. 빨라졌는데 교정이 늘면 서두른 것이고, 둘 다 좋아지면 실력이 는 것입니다.
          각 글은 직전 3편(고쳐 쓰기 제외) 평균과 비교하며, 속도 ±10%·교정 밀도 ±15% 안의 변화는 비슷한 것으로 봅니다.
        </p>
      </div>

      {chartData.length === 0 ? (
        <div className="py-8 text-center text-xs text-stone-400 dark:text-stone-500">
          쓰기 시간이 기록되고 첨삭받은 에세이가 생기면 여기에 표시됩니다.
        </div>
      ) : (
        <>
          <div className="w-full h-64 pt-2">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={chartData} margin={{ top: 10, right: 0, left: -10, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#88888825" vertical={false} />
                <XAxis dataKey="label" tick={{ fontSize: 11, fill: '#888888' }} tickLine={false} axisLine={{ stroke: '#88888840' }} />
                <YAxis yAxisId="wpm" tick={{ fontSize: 11, fill: '#10b981' }} tickLine={false} axisLine={false} />
                <YAxis yAxisId="acc" orientation="right" tick={{ fontSize: 11, fill: '#f43f5e' }} tickLine={false} axisLine={false} />
                <Tooltip
                  contentStyle={{
                    backgroundColor: 'rgba(25, 25, 25, 0.94)',
                    borderRadius: '12px',
                    border: '1px solid rgba(255, 255, 255, 0.15)',
                    color: '#ffffff',
                    fontSize: '12px',
                  }}
                  labelFormatter={(_, payload) => {
                    const item = payload?.[0]?.payload as WritingTrendItem | undefined;
                    if (!item) return '';
                    const rev = item.is_revision ? ' · 고쳐 쓰기' : '';
                    return `${item.date} · ${ESSAY_TYPE_LABELS[item.essay_type]}${rev} · ${item.word_count}단어 / ${item.minutes}분`;
                  }}
                />
                <Legend wrapperStyle={{ fontSize: '11px', paddingTop: '10px' }} iconType="circle" iconSize={8} />
                <Line yAxisId="wpm" type="monotone" dataKey="wpm" name="분당 단어 (WPM)" stroke="#10b981" strokeWidth={2.5} dot={{ r: 4, fill: '#10b981' }} />
                <Line yAxisId="acc" type="monotone" dataKey="accuracy_density" name="필수 교정 / 100단어" stroke="#f43f5e" strokeWidth={2} dot={{ r: 3, fill: '#f43f5e' }} />
              </LineChart>
            </ResponsiveContainer>
          </div>

          <div className="pt-2 border-t border-stone-100 dark:border-[#2a2a2a] space-y-1.5">
            {[...chartData].reverse().map((d) => {
              const sig = d.signal ? SIGNALS[d.signal] : null;
              return (
                <div key={d.essay_id} className="flex items-center justify-between gap-3 text-xs">
                  <span className="text-stone-500 dark:text-stone-400 tabular-nums shrink-0">
                    {d.label}
                    {d.is_revision ? ' · 고쳐 쓰기' : ''}
                  </span>
                  <span className="text-stone-700 dark:text-stone-300 tabular-nums">
                    {d.wpm.toFixed(1)} wpm · 필수 교정 {d.accuracy_density.toFixed(1)}/100
                  </span>
                  {sig ? (
                    <span title={sig.hint} className={`shrink-0 px-2 py-0.5 rounded-md border text-[11px] font-semibold ${sig.className}`}>
                      {sig.label}
                    </span>
                  ) : (
                    <span className="shrink-0 text-[11px] text-stone-400 dark:text-stone-500">기준 없음 (첫 기록)</span>
                  )}
                </div>
              );
            })}
          </div>
        </>
      )}
    </div>
  );
};
