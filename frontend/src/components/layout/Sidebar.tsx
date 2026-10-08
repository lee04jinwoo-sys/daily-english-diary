import React, { useState } from 'react';
import { DiaryListItem } from '../../types/diary';
import { 
  Search, 
  Trash2, 
  Calendar,
  CheckCircle2,
  Check
} from 'lucide-react';

interface SidebarProps {
  diaries: DiaryListItem[];
  currentDate: string;
  onSelectDate: (date: string) => void;
  onDeleteDiary: (date: string) => void;
  onToggleComplete?: (date: string) => void;
  streak: number;
}

export const Sidebar: React.FC<SidebarProps> = ({
  diaries,
  currentDate,
  onSelectDate,
  onDeleteDiary,
  onToggleComplete,
  streak,
}) => {
  const [searchQuery, setSearchQuery] = useState('');

  const filteredDiaries = diaries.filter((d) => {
    const q = searchQuery.toLowerCase();
    return (
      d.date.includes(q) ||
      (d.title && d.title.toLowerCase().includes(q)) ||
      (d.preview && d.preview.toLowerCase().includes(q))
    );
  });

  return (
    <aside className="w-72 border-r border-[#e9e8e4] dark:border-[#2a2a2a] bg-[#f7f6f3] dark:bg-[#1f1f1f] flex flex-col h-[calc(100vh-3.5rem)] select-none transition-colors">
      {/* Search & Header */}
      <div className="p-3 border-b border-[#e9e8e4] dark:border-[#2a2a2a] space-y-2">
        <div className="flex items-center justify-between text-xs text-[#787774] dark:text-[#a0a0a0] font-medium px-1">
          <span>일기 목록 ({diaries.length})</span>
          <span className="text-[11px] text-amber-700 dark:text-amber-300 bg-amber-100/70 dark:bg-amber-950/50 px-2 py-0.5 rounded font-semibold border border-amber-200/50 dark:border-amber-800/40">
            {streak}일 스트릭 🔥
          </span>
        </div>
        <div className="relative">
          <Search className="w-3.5 h-3.5 text-[#9ca3af] dark:text-[#777777] absolute left-2.5 top-2.5" />
          <input
            type="text"
            placeholder="일기 검색..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-8 pr-3 py-1.5 bg-white dark:bg-[#282828] border border-[#e2e1db] dark:border-[#383838] rounded-md text-xs placeholder:text-[#a8a7a1] dark:placeholder:text-[#666666] text-[#37352f] dark:text-[#e0e0e0] outline-none focus:border-[#787774] dark:focus:border-[#666666] transition-colors"
          />
        </div>
      </div>

      {/* Diary List */}
      <div className="flex-1 overflow-y-auto p-2 space-y-1">
        {filteredDiaries.length === 0 ? (
          <div className="text-center py-10 px-4 text-xs text-[#787774] dark:text-[#888888]">
            {searchQuery ? '일치하는 일기가 없습니다.' : '작성된 일기가 없습니다.\n오늘의 첫 일기를 써보세요!'}
          </div>
        ) : (
          filteredDiaries.map((diary) => {
            const isSelected = diary.date === currentDate;
            return (
              <div
                key={diary.date}
                onClick={() => onSelectDate(diary.date)}
                className={`group relative p-2.5 rounded-lg text-left transition-all cursor-pointer border ${
                  isSelected
                    ? 'bg-white dark:bg-[#2c2c2c] border-[#dedad0] dark:border-[#444444] shadow-xs'
                    : 'border-transparent hover:bg-[#efeee9]/80 dark:hover:bg-[#282828] text-[#55534e] dark:text-[#b0b0b0]'
                }`}
              >
                <div className="flex items-start justify-between">
                  <div className="flex items-center space-x-1.5 text-xs font-semibold text-[#37352f] dark:text-[#f0f0f0]">
                    <Calendar className="w-3.5 h-3.5 text-[#787774] dark:text-[#888888]" />
                    <span>{diary.date}</span>
                    {diary.is_completed ? (
                      <span className="text-[10px] bg-emerald-100 dark:bg-emerald-950/80 text-emerald-700 dark:text-emerald-300 px-1.5 py-0.2 rounded font-medium border border-emerald-300/50 dark:border-emerald-700/50 flex items-center space-x-0.5">
                        <Check className="w-2.5 h-2.5" />
                        <span>완료</span>
                      </span>
                    ) : diary.is_draft ? (
                      <span className="text-[10px] bg-stone-200 dark:bg-stone-800 text-stone-600 dark:text-stone-400 px-1 rounded font-normal">
                        임시
                      </span>
                    ) : null}
                  </div>
                  <div className="flex items-center space-x-1">
                    {diary.word_count !== undefined && !diary.is_draft && (
                      <span className="text-[10px] font-medium text-stone-600 dark:text-stone-300 bg-stone-100 dark:bg-stone-800/60 px-1.5 py-0.2 rounded border border-stone-200 dark:border-stone-700/50 font-sans">
                        {diary.word_count}단어
                      </span>
                    )}
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        onToggleComplete?.(diary.date);
                      }}
                      className={`p-0.5 rounded transition-all ${
                        diary.is_completed
                          ? 'text-emerald-600 dark:text-emerald-400'
                          : 'text-stone-300 dark:text-stone-600 hover:text-emerald-600 dark:hover:text-emerald-400 opacity-0 group-hover:opacity-100'
                      }`}
                      title={diary.is_completed ? '완료 취소' : '완료로 표시'}
                    >
                      <CheckCircle2 className="w-3.5 h-3.5" />
                    </button>
                  </div>
                </div>

                <div className="text-xs font-medium text-[#37352f] dark:text-[#e0e0e0] mt-1 line-clamp-1">
                  {diary.title || '제목 없음'}
                </div>

                <div className="text-[11px] text-[#787774] dark:text-[#909090] line-clamp-1 mt-0.5 font-sans">
                  {diary.preview || '내용 없음'}
                </div>

                <div className="flex items-center justify-between text-[10px] text-[#a8a7a1] dark:text-[#707070] mt-2">
                  <span>{diary.word_count} 단어</span>
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      if (confirm(`${diary.date} 일기를 정말 삭제하시겠습니까?`)) {
                        onDeleteDiary(diary.date);
                      }
                    }}
                    className="opacity-0 group-hover:opacity-100 hover:text-red-600 dark:hover:text-red-400 p-1 transition-opacity"
                    title="일기 삭제"
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
