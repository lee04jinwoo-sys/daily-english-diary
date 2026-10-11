import React from 'react';
import { SuggestionItem, CardType } from '../../types/essay';
import { BookmarkPlus } from 'lucide-react';

interface SuggestionCardProps {
  suggestion: SuggestionItem;
  isActive: boolean;
  onSelect: () => void;
  /** The learner's whole sentence with this fix applied (sentence cards must be complete sentences). */
  sentenceForCard: string;
  onOpenAnkiModal: (cardType: CardType, text: string, context?: string) => void;
}

export const SuggestionCard: React.FC<SuggestionCardProps> = ({
  suggestion,
  isActive,
  onSelect,
  sentenceForCard,
  onOpenAnkiModal,
}) => {
  const getCategoryBadge = () => {
    if (suggestion.tier === 'accuracy') {
      return {
        bg: 'bg-rose-50 dark:bg-rose-950/40 text-rose-700 dark:text-rose-300 border-rose-200 dark:border-rose-800/60',
        label: '필수 교정',
        dot: 'bg-rose-500',
      };
    }
    if (suggestion.tier === 'idiom') {
      return {
        bg: 'bg-amber-50 dark:bg-amber-950/40 text-amber-800 dark:text-amber-300 border-amber-200 dark:border-amber-800/60',
        label: '원어민 표현',
        dot: 'bg-amber-500',
      };
    }
    if (suggestion.tier === 'style') {
      return {
        bg: 'bg-sky-50 dark:bg-sky-950/40 text-sky-700 dark:text-sky-300 border-sky-200 dark:border-sky-800/60',
        label: '스타일 팁',
        dot: 'bg-sky-500',
      };
    }

    switch (suggestion.category) {
      case 'Grammar':
      case 'Spelling':
        return {
          bg: 'bg-rose-50 dark:bg-rose-950/40 text-rose-700 dark:text-rose-300 border-rose-200 dark:border-rose-800/60',
          label: '필수 교정',
          dot: 'bg-rose-500',
        };
      case 'Vocabulary':
      case 'Natural Expression':
        return {
          bg: 'bg-amber-50 dark:bg-amber-950/40 text-amber-800 dark:text-amber-300 border-amber-200 dark:border-amber-800/60',
          label: '원어민 표현',
          dot: 'bg-amber-500',
        };
      default:
        return {
          bg: 'bg-sky-50 dark:bg-sky-950/40 text-sky-700 dark:text-sky-300 border-sky-200 dark:border-sky-800/60',
          label: '스타일 팁',
          dot: 'bg-sky-500',
        };
    }
  };

  const badge = getCategoryBadge();

  const getCardStyle = () => {
    if (!isActive) {
      return 'bg-white/80 dark:bg-[#242424] hover:bg-white dark:hover:bg-[#2a2a2a] border-[#e9e8e4] dark:border-[#333333] hover:border-stone-300 dark:hover:border-stone-600 shadow-xs';
    }

    const tier = suggestion.tier || 'accuracy';
    if (tier === 'accuracy') {
      return 'bg-rose-50/40 dark:bg-rose-950/25 border-rose-400 dark:border-rose-500/80 shadow-md ring-2 ring-rose-400/30 dark:ring-rose-500/40';
    }
    if (tier === 'idiom') {
      return 'bg-amber-50/40 dark:bg-amber-950/25 border-amber-400 dark:border-amber-500/80 shadow-md ring-2 ring-amber-400/30 dark:ring-amber-500/40';
    }
    return 'bg-sky-50/40 dark:bg-sky-950/25 border-sky-400 dark:border-sky-500/80 shadow-md ring-2 ring-sky-400/30 dark:ring-sky-500/40';
  };

  return (
    <div
      onClick={onSelect}
      className={`p-3.5 rounded-xl border transition-all cursor-pointer ${getCardStyle()}`}
    >
      {/* Category Header */}
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center space-x-1.5">
          <span className={`inline-flex items-center px-2 py-0.5 rounded-md text-[11px] font-semibold border ${badge.bg}`}>
            <span className={`w-1.5 h-1.5 rounded-full ${badge.dot} mr-1.5`}></span>
            {badge.label}
          </span>
          {suggestion.subcategory && (
            <span className="text-[11px] text-[#787774] dark:text-[#999999] font-medium">
              {suggestion.subcategory}
            </span>
          )}
        </div>
      </div>

      {/* Before & After Phrasing */}
      <div className="bg-[#faf9f6] dark:bg-[#1e1e1e] border border-[#ebe9e1] dark:border-[#383838] rounded-lg p-2.5 mb-2.5 space-y-1.5 text-xs">
        <div className="flex items-center space-x-2 text-stone-500 dark:text-stone-400">
          <span className="text-[10px] uppercase font-bold text-stone-400 dark:text-stone-500 w-10">원문</span>
          <span className="line-through decoration-red-400 decoration-1 text-stone-600 dark:text-stone-300 font-serif">
            {suggestion.original_phrase}
          </span>
        </div>
        <div className="flex items-center space-x-2 text-emerald-800 dark:text-emerald-300 font-semibold">
          <span className="text-[10px] uppercase font-bold text-emerald-600 dark:text-emerald-400 w-10">추천</span>
          <span className="text-emerald-700 dark:text-emerald-300 font-serif bg-emerald-100/60 dark:bg-emerald-950/60 px-1.5 py-0.5 rounded">
            {suggestion.suggested_phrase}
          </span>
        </div>
      </div>

      {/* Korean Explanation */}
      <div className="text-xs text-[#55534e] dark:text-[#c5c5c5] leading-relaxed mb-3 bg-stone-50/50 dark:bg-[#1a1a1a] p-2 rounded-md border border-stone-100 dark:border-[#2f2f2f] font-sans">
        💡 {suggestion.explanation}
      </div>

      {/* Action Buttons */}
      <div className="flex items-center justify-between pt-1 border-t border-[#f0eee6] dark:border-[#2f2f2f]">
        {/* Anki Export Actions */}
        <div className="flex items-center space-x-1">
          <button
            onClick={(e) => {
              e.stopPropagation();
              onOpenAnkiModal('sentence', sentenceForCard, suggestion.explanation);
            }}
            className="flex items-center space-x-1 text-[11px] text-[#55534e] dark:text-[#a0a0a0] hover:text-blue-700 dark:hover:text-blue-300 hover:bg-blue-50 dark:hover:bg-blue-950/50 px-2 py-1 rounded transition-colors"
            title={`교정된 문장을 Anki 문장 덱에 추가: ${sentenceForCard}`}
          >
            <BookmarkPlus className="w-3 h-3 text-blue-600 dark:text-blue-400" />
            <span>문장 Anki</span>
          </button>
          
          <button
            onClick={(e) => {
              e.stopPropagation();
              onOpenAnkiModal('vocab', suggestion.suggested_phrase, suggestion.explanation);
            }}
            className="flex items-center space-x-1 text-[11px] text-[#55534e] dark:text-[#a0a0a0] hover:text-emerald-700 dark:hover:text-emerald-300 hover:bg-emerald-50 dark:hover:bg-emerald-950/50 px-2 py-1 rounded transition-colors"
            title="이 표현을 Anki 단어 덱에 추가"
          >
            <BookmarkPlus className="w-3 h-3 text-emerald-600 dark:text-emerald-400" />
            <span>단어 Anki</span>
          </button>
        </div>

      </div>
    </div>
  );
};
