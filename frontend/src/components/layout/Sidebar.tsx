import React, { useState } from 'react';
import { EssayListItem, ESSAY_TYPE_LABELS } from '../../types/essay';
import {
  Search,
  Trash2,
  CheckCircle2,
  Check,
  RotateCcw
} from 'lucide-react';

interface SidebarProps {
  essays: EssayListItem[];
  currentEssayId: string | null;
  onSelectEssay: (id: string) => void;
  onDeleteEssay: (id: string) => void;
  onToggleComplete?: (id: string) => void;
  streak: number;
}

export const Sidebar: React.FC<SidebarProps> = ({
  essays,
  currentEssayId,
  onSelectEssay,
  onDeleteEssay,
  onToggleComplete,
  streak,
}) => {
  const [searchQuery, setSearchQuery] = useState('');

  const filteredEssays = essays.filter((e) => {
    const q = searchQuery.toLowerCase();
    return (
      e.date.includes(q) ||
      e.prompt.toLowerCase().includes(q) ||
      (e.preview && e.preview.toLowerCase().includes(q))
    );
  });

  return (
    <aside className="w-72 border-r border-[#e9e8e4] dark:border-[#2a2a2a] bg-[#f7f6f3] dark:bg-[#1f1f1f] flex flex-col h-[calc(100vh-3.5rem)] select-none transition-colors">
      {/* Search & Header */}
      <div className="p-3 border-b border-[#e9e8e4] dark:border-[#2a2a2a] space-y-2">
        <div className="flex items-center justify-between text-xs text-[#787774] dark:text-[#a0a0a0] font-medium px-1">
          <span>에세이 목록 ({essays.length})</span>
          <span className="text-[11px] text-amber-700 dark:text-amber-300 bg-amber-100/70 dark:bg-amber-950/50 px-2 py-0.5 rounded font-semibold border border-amber-200/50 dark:border-amber-800/40">
            {streak}일 스트릭 🔥
          </span>
        </div>
        <div className="relative">
          <Search className="w-3.5 h-3.5 text-[#9ca3af] dark:text-[#777777] absolute left-2.5 top-2.5" />
          <input
            type="text"
            placeholder="주제·본문 검색..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-8 pr-3 py-1.5 bg-white dark:bg-[#282828] border border-[#e2e1db] dark:border-[#383838] rounded-md text-xs placeholder:text-[#a8a7a1] dark:placeholder:text-[#666666] text-[#37352f] dark:text-[#e0e0e0] outline-none focus:border-[#787774] dark:focus:border-[#666666] transition-colors"
          />
        </div>
      </div>

      {/* Essay List */}
      <div className="flex-1 overflow-y-auto p-2 space-y-1">
        {filteredEssays.length === 0 ? (
          <div className="text-center py-10 px-4 text-xs text-[#787774] dark:text-[#888888] whitespace-pre-line">
            {searchQuery ? '일치하는 에세이가 없습니다.' : '아직 에세이가 없습니다.\n첫 주제를 골라보세요!'}
          </div>
        ) : (
          filteredEssays.map((essay) => {
            const isSelected = essay.id === currentEssayId;
            return (
              <div
                key={essay.id}
                onClick={() => onSelectEssay(essay.id)}
                className={`group relative p-2.5 rounded-lg text-left transition-all cursor-pointer border ${
                  isSelected
                    ? 'bg-white dark:bg-[#2c2c2c] border-[#dedad0] dark:border-[#444444] shadow-xs'
                    : 'border-transparent hover:bg-[#efeee9]/80 dark:hover:bg-[#282828] text-[#55534e] dark:text-[#b0b0b0]'
                }`}
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center space-x-1.5 text-[11px] text-[#787774] dark:text-[#909090]">
                    <span className="font-semibold text-[#37352f] dark:text-[#e0e0e0]">{essay.date}</span>
                    <span className="px-1.5 rounded bg-stone-200/70 dark:bg-[#333333] text-stone-600 dark:text-stone-300 text-[10px]">
                      {ESSAY_TYPE_LABELS[essay.essay_type]}
                    </span>
                    {essay.revision_of && (
                      <RotateCcw className="w-3 h-3 text-amber-600 dark:text-amber-400" aria-label="고쳐 쓴 에세이" />
                    )}
                    {essay.is_completed && (
                      <span className="text-[10px] bg-emerald-100 dark:bg-emerald-950/80 text-emerald-700 dark:text-emerald-300 px-1 rounded border border-emerald-300/50 dark:border-emerald-700/50 flex items-center">
                        <Check className="w-2.5 h-2.5" />
                      </span>
                    )}
                  </div>
                  <div className="flex items-center space-x-1">
                    {essay.overall_band != null ? (
                      <span className="text-[10px] tabular-nums text-stone-400 dark:text-stone-500" title="AI 추정 점수 (참고용)">
                        {essay.overall_band.toFixed(1)}
                      </span>
                    ) : (
                      <span className="text-[10px] text-stone-400 dark:text-stone-500">미첨삭</span>
                    )}
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        onToggleComplete?.(essay.id);
                      }}
                      className={`p-0.5 rounded transition-all ${
                        essay.is_completed
                          ? 'text-emerald-600 dark:text-emerald-400'
                          : 'text-stone-300 dark:text-stone-600 hover:text-emerald-600 dark:hover:text-emerald-400 opacity-0 group-hover:opacity-100'
                      }`}
                      title={essay.is_completed ? '완료 취소' : '완료로 표시'}
                    >
                      <CheckCircle2 className="w-3.5 h-3.5" />
                    </button>
                  </div>
                </div>

                <div className="text-xs font-medium text-[#37352f] dark:text-[#e0e0e0] mt-1 line-clamp-2 font-serif">
                  {essay.prompt}
                </div>

                <div className="flex items-center justify-between text-[10px] text-[#a8a7a1] dark:text-[#707070] mt-1.5">
                  <span>
                    {essay.word_count} 단어
                    {essay.writing_seconds > 0 && ` · ${Math.max(1, Math.round(essay.writing_seconds / 60))}분`}
                  </span>
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      if (confirm('이 에세이를 삭제할까요? 첨삭 기록도 함께 지워집니다. (Anki 카드는 지워지지 않습니다)')) {
                        onDeleteEssay(essay.id);
                      }
                    }}
                    className="opacity-0 group-hover:opacity-100 hover:text-red-600 dark:hover:text-red-400 p-1 transition-opacity"
                    title="에세이 삭제"
                  >
                    <Trash2 className="w-3 h-3" />
                  </button>
                </div>
              </div>
            );
          })
        )}
      </div>
    </aside>
  );
};
