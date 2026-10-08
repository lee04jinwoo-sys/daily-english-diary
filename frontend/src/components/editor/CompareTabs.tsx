import React from 'react';

interface CompareTabsProps {
  activeTab: 'editor' | 'sentence' | 'native';
  onTabChange: (tab: 'editor' | 'sentence' | 'native') => void;
}

export const CompareTabs: React.FC<CompareTabsProps> = ({
  activeTab,
  onTabChange,
}) => {
  return (
    <div className="flex items-center space-x-1.5 p-1 bg-[#f0eee6] dark:bg-[#252525] rounded-xl border border-[#e5e3da] dark:border-[#333333]">
      <button
        onClick={() => onTabChange('editor')}
        className={`px-3 py-1.5 rounded-lg text-xs transition-all whitespace-nowrap ${
          activeTab === 'editor'
            ? 'bg-white dark:bg-[#333333] text-[#222222] dark:text-[#f0f0f0] font-semibold shadow-xs'
            : 'text-[#787774] dark:text-[#a0a0a0] hover:text-[#37352f] dark:hover:text-white'
        }`}
      >
        ✍️ 작성 & 첨삭
      </button>

      <button
        onClick={() => onTabChange('sentence')}
        className={`px-3 py-1.5 rounded-lg text-xs transition-all whitespace-nowrap ${
          activeTab === 'sentence'
            ? 'bg-blue-600 dark:bg-blue-500 text-white font-semibold shadow-xs'
            : 'text-[#787774] dark:text-[#a0a0a0] hover:text-blue-700 dark:hover:text-blue-300'
        }`}
      >
        ✨ 문장별 1:1 학습 & Anki
      </button>

      <button
        onClick={() => onTabChange('native')}
        className={`px-3 py-1.5 rounded-lg text-xs transition-all whitespace-nowrap ${
          activeTab === 'native'
            ? 'bg-indigo-600 dark:bg-indigo-500 text-white font-semibold shadow-xs'
            : 'text-[#787774] dark:text-[#a0a0a0] hover:text-indigo-700 dark:hover:text-indigo-300'
        }`}
      >
        📖 원어민 패러프레이징 본문
      </button>
    </div>
  );
};
