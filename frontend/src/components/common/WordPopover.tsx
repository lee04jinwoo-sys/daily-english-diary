import React, { useState, useEffect, useRef } from 'react';
import { api } from '../../api/client';
import { 
  Volume2, 
  BookmarkPlus, 
  X, 
  Loader2,
  Check
} from 'lucide-react';

interface WordPopoverProps {
  word: string;
  context?: string;
  position: { x: number; y: number } | null;
  onClose: () => void;
  onShowToast: (msg: string) => void;
}

interface WordData {
  word: string;
  phonetic: string;
  pos: string;
  meaning: string;
  explanation: string;
  synonyms: string;
  example: string;
}

export const WordPopover: React.FC<WordPopoverProps> = ({
  word,
  context = '',
  position,
  onClose,
  onShowToast,
}) => {
  const [loading, setLoading] = useState(false);
  const [data, setData] = useState<WordData | null>(null);
  const [isSavingAnki, setIsSavingAnki] = useState(false);
  const [isSaved, setIsSaved] = useState(false);
  const popoverRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!word || !position) return;

    let isMounted = true;
    setLoading(true);
    setData(null);
    setIsSaved(false);

    api.lookupWord(word, context)
      .then((res) => {
        if (isMounted) {
          setData(res);
          setLoading(false);
          // Check if word or idiom is already in Anki
          api.checkExistingCards({ sentences: [], words: [res.word, word] })
            .then((checkRes) => {
              if (isMounted && checkRes.existing_words && checkRes.existing_words.length > 0) {
                setIsSaved(true);
              }
            })
            .catch(() => {});
        }
      })
      .catch((err) => {
        if (isMounted) {
          setData({
            word,
            phonetic: '',
            pos: 'word',
            meaning: '뜻을 불러오지 못했습니다.',
            explanation: err.message,
            synonyms: '',
            example: '',
          });
          setLoading(false);
        }
      });

    return () => {
      isMounted = false;
    };
  }, [word, context, position]);

  // Click outside to close
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (popoverRef.current && !popoverRef.current.contains(e.target as Node)) {
        onClose();
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [onClose]);

  if (!word || !position) return null;

  const handlePlayAudio = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (!window.speechSynthesis) return;
    window.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(data?.word || word);
    utterance.lang = 'en-US';
    utterance.rate = 0.95;
    window.speechSynthesis.speak(utterance);
  };

  // Direct 1-Click Vocab Anki Save (no deletion: existing Anki cards are never removed from here)
  const handleDirectSaveVocab = async () => {
    if (!data) return;
    setIsSavingAnki(true);
    try {
      if (isSaved) {
        onShowToast(`"${data.word}"은(는) 이미 Anki에 있습니다.`);
      } else {
        const res = await api.addVocabCard({
          word: data.word,
          meaning: data.meaning,
          pos: data.pos,
          synonyms: data.synonyms,
          example: data.example,
          explanation: data.explanation,
        });

        if (res.success) {
          setIsSaved(true);
          onShowToast(res.duplicate ? '이미 등록된 단어입니다.' : `"${data.word}" 단어가 Anki에 저장되었습니다! 🎉`);
          setTimeout(() => {
            onClose();
          }, 800);
        } else {
          onShowToast('Anki 앱이 켜져 있는지 확인해주세요! (상단 헤더 확인)');
        }
      }
    } catch (e: any) {
      onShowToast(`처리 실패: ${e.message}`);
    } finally {
      setIsSavingAnki(false);
    }
  };

  // Smart flip positioning so popover NEVER overflows below or above screen
  const popoverWidth = 320;
  const popoverHeight = 270;
  const leftPos = Math.min(Math.max(16, position.x - popoverWidth / 2), window.innerWidth - popoverWidth - 24);
  const fitsBelow = position.y + 16 + popoverHeight <= window.innerHeight;
  const topPos = fitsBelow ? position.y + 12 : Math.max(16, position.y - popoverHeight - 12);

  return (
    <div
      ref={popoverRef}
      style={{ top: `${topPos}px`, left: `${leftPos}px` }}
      className="fixed z-50 w-80 bg-white dark:bg-[#202020] rounded-2xl border border-stone-200 dark:border-[#383838] shadow-2xl p-4 animate-in fade-in zoom-in-95 duration-150 transition-colors"
    >
      {/* Header */}
      <div className="flex items-center justify-between pb-2.5 border-b border-stone-100 dark:border-[#2e2e2e]">
        <div className="flex items-center space-x-2">
          <span className="font-serif text-base font-bold text-stone-900 dark:text-white">
            {data?.word || word}
          </span>

          <button
            onClick={handlePlayAudio}
            className="p-1 text-stone-500 hover:text-blue-600 dark:text-stone-400 dark:hover:text-blue-400 rounded-md hover:bg-stone-100 dark:hover:bg-[#2c2c2c] transition-colors"
            title="발음 듣기"
          >
            <Volume2 className="w-3.5 h-3.5" />
          </button>

          {data?.pos && (
            <span className="text-[10px] uppercase font-bold text-blue-700 dark:text-blue-300 bg-blue-50 dark:bg-blue-950/60 px-1.5 py-0.5 rounded border border-blue-200/60 dark:border-blue-800/60">
              {data.pos}
            </span>
          )}
        </div>

        <button
          onClick={onClose}
          className="text-stone-400 hover:text-stone-700 dark:text-stone-500 dark:hover:text-stone-200 p-1 rounded-md transition-colors"
        >
          <X className="w-3.5 h-3.5" />
        </button>
      </div>

      {/* Body */}
      {loading ? (
        <div className="py-6 flex flex-col items-center justify-center space-y-2 text-stone-400 dark:text-stone-500">
          <Loader2 className="w-5 h-5 animate-spin text-blue-500" />
          <span className="text-xs">실시간 단어 사전 분석 중...</span>
        </div>
      ) : data ? (
        <div className="py-3 space-y-2.5 text-xs">
          {/* Meaning */}
          <div className="flex items-start space-x-2">
            <span className="text-[10px] uppercase font-bold text-stone-400 dark:text-stone-500 shrink-0 w-8 mt-0.5">
              뜻
            </span>
            <span className="font-semibold text-stone-900 dark:text-stone-100 leading-snug">
              {data.meaning}
            </span>
          </div>

          {/* Explanation / Nuance */}
          {data.explanation && (
            <div className="flex items-start space-x-2 bg-stone-50 dark:bg-[#1a1a1a] p-2 rounded-lg border border-stone-100 dark:border-[#2d2d2d] text-stone-600 dark:text-stone-300 text-[11px] leading-relaxed">
              <span className="shrink-0">💡</span>
              <span>{data.explanation}</span>
            </div>
          )}

          {/* Synonyms */}
          {data.synonyms && (
            <div className="flex items-start space-x-2 text-stone-500 dark:text-stone-400 text-[11px]">
              <span className="text-[10px] uppercase font-bold text-stone-400 dark:text-stone-500 shrink-0 w-8">
                유의어
              </span>
              <span>{data.synonyms}</span>
            </div>
          )}

          {/* Example */}
          {data.example && (
            <div className="flex items-start space-x-2 text-[11px] text-stone-500 dark:text-stone-400 italic">
              <span className="text-[10px] uppercase font-bold text-stone-400 dark:text-stone-500 shrink-0 w-8 not-italic">
                예문
              </span>
              <span>"{data.example}"</span>
            </div>
          )}
        </div>
      ) : null}

      {/* Footer - DIRECT 1-CLICK ANKI */}
      <div className="pt-2.5 border-t border-stone-100 dark:border-[#2e2e2e] flex items-center justify-between">
        <span className="text-[10px] text-stone-400 dark:text-stone-500">
          Shadowing Player 호환
        </span>

        <button
          onClick={handleDirectSaveVocab}
          disabled={isSavingAnki || loading || !data}
          className={`flex items-center space-x-1 text-xs font-semibold px-3 py-1.5 rounded-lg shadow-xs transition-all active:scale-95 ${
            isSaved
              ? 'bg-emerald-700 text-white'
              : 'bg-emerald-600 hover:bg-emerald-700 text-white'
          }`}
        >
          {isSavingAnki ? (
            <Loader2 className="w-3.5 h-3.5 animate-spin" />
          ) : isSaved ? (
            <Check className="w-3.5 h-3.5" />
          ) : (
            <BookmarkPlus className="w-3.5 h-3.5" />
          )}
          <span>{isSavingAnki ? 'Anki 전송 중...' : isSaved ? 'Anki 등록됨 ✓' : '⭐ Anki 단어장에 저장'}</span>
        </button>
      </div>
    </div>
  );
};
