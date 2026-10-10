import React, { useCallback, useEffect, useState } from 'react';
import { api } from '../../api/client';
import { Topic, ESSAY_TYPE_LABELS, CATEGORY_LABELS } from '../../types/essay';
import { Shuffle, PenLine, Loader2, Lightbulb } from 'lucide-react';

interface TopicPickerProps {
  onStart: (topic: Topic | null, customPrompt?: string) => void;
}

export const TopicPicker: React.FC<TopicPickerProps> = ({ onStart }) => {
  const [topic, setTopic] = useState<Topic | null>(null);
  const [skipped, setSkipped] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [customPrompt, setCustomPrompt] = useState('');

  const fetchTopic = useCallback(async (exclude: string[]) => {
    setLoading(true);
    setError(null);
    try {
      setTopic(await api.suggestTopic(exclude));
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchTopic([]);
  }, [fetchTopic]);

  const handleReroll = () => {
    if (!topic) return;
    const next = [...skipped, topic.id];
    setSkipped(next);
    fetchTopic(next);
  };

  return (
    <div className="flex-1 overflow-y-auto px-6 py-12">
      <div className="max-w-2xl mx-auto space-y-8">
        <div className="space-y-1">
          <h1 className="font-serif font-bold text-2xl text-stone-900 dark:text-stone-100">오늘의 에세이</h1>
          <p className="text-xs text-stone-500 dark:text-stone-400">
            아직 쓰지 않은 주제 중에서 고릅니다. 직전 에세이와 다른 유형이 나오고, 일반 · 내 분야 · 시사를 5 : 3 : 2 비율로 섞습니다.
          </p>
        </div>

        {/* Suggested topic */}
        <div className="bg-white dark:bg-[#222222] rounded-2xl border border-[#e9e8e4] dark:border-[#333333] shadow-xs p-6 space-y-5">
          {loading && !topic ? (
            <div className="flex items-center justify-center py-10 text-stone-400">
              <Loader2 className="w-5 h-5 animate-spin" />
            </div>
          ) : error ? (
            <div className="text-xs text-red-600 dark:text-red-400">주제를 불러오지 못했습니다: {error}</div>
          ) : topic ? (
            <>
              <div className="flex items-center gap-1.5 text-[11px] font-semibold">
                <span className="px-2 py-0.5 rounded-md bg-indigo-50 dark:bg-indigo-950/50 text-indigo-700 dark:text-indigo-300 border border-indigo-200/70 dark:border-indigo-800/50">
                  {ESSAY_TYPE_LABELS[topic.type]}
                </span>
                <span className="px-2 py-0.5 rounded-md bg-stone-100 dark:bg-[#2a2a2a] text-stone-600 dark:text-stone-300 border border-stone-200 dark:border-[#383838]">
                  {CATEGORY_LABELS[topic.category]}
                </span>
              </div>
              <p className={`font-serif text-lg leading-relaxed text-[#1c1b18] dark:text-[#f0f0f0] transition-opacity ${loading ? 'opacity-40' : ''}`}>
                {topic.prompt}
              </p>
              <div className="flex items-center justify-end gap-2">
                <button
                  onClick={handleReroll}
                  disabled={loading}
                  className="flex items-center space-x-1.5 px-3 py-2 text-xs font-medium rounded-lg border border-stone-200 dark:border-[#3a3a3a] text-stone-700 dark:text-stone-300 hover:bg-stone-50 dark:hover:bg-[#2c2c2c] transition-colors disabled:opacity-50"
                >
                  <Shuffle className="w-3.5 h-3.5" />
                  <span>다른 주제</span>
                </button>
                <button
                  onClick={() => onStart(topic)}
                  disabled={loading}
                  className="flex items-center space-x-1.5 px-4 py-2 bg-[#2c2b28] hover:bg-[#1c1b18] dark:bg-[#e6e6e6] dark:hover:bg-white dark:text-[#191919] text-white text-xs font-semibold rounded-lg shadow-xs transition-all active:scale-95 disabled:opacity-50"
                >
                  <PenLine className="w-3.5 h-3.5" />
                  <span>이 주제로 쓰기</span>
                </button>
              </div>
            </>
          ) : null}
        </div>

        {/* Free topic */}
        <div className="bg-[#f7f6f3] dark:bg-[#1f1f1f] rounded-2xl border border-dashed border-stone-300 dark:border-[#3a3a3a] p-6 space-y-3">
          <div className="flex items-center space-x-1.5 text-xs font-semibold text-stone-700 dark:text-stone-300">
            <Lightbulb className="w-3.5 h-3.5 text-amber-500" />
            <span>내 주제로 쓰기</span>
          </div>
          <textarea
            value={customPrompt}
            onChange={(e) => setCustomPrompt(e.target.value)}
            rows={2}
            placeholder="답하고 싶은 질문을 영어나 한국어로 적어보세요. (예: Is a quant career worth more than a startup career?)"
            className="w-full bg-white dark:bg-[#252525] border border-stone-200 dark:border-[#383838] rounded-lg p-3 text-sm font-serif text-[#2c2b28] dark:text-[#e4e4e4] placeholder:text-stone-400 dark:placeholder:text-[#666666] placeholder:font-sans outline-none focus:border-stone-400 dark:focus:border-[#555555] resize-none"
          />
          <div className="flex justify-end">
            <button
              onClick={() => onStart(null, customPrompt.trim())}
              disabled={customPrompt.trim().length < 3}
              className="flex items-center space-x-1.5 px-4 py-2 bg-amber-600 hover:bg-amber-700 text-white text-xs font-semibold rounded-lg shadow-xs transition-all active:scale-95 disabled:opacity-40 disabled:cursor-not-allowed"
            >
              <PenLine className="w-3.5 h-3.5" />
              <span>이 질문으로 쓰기</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
