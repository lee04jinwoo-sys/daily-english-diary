import React, { useState, useEffect } from 'react';
import { CardType, AnkiStatus } from '../../types/essay';
import { api } from '../../api/client';
import { X, BookmarkPlus, Volume2, CheckCircle2, AlertCircle } from 'lucide-react';

interface AnkiCardModalProps {
  isOpen: boolean;
  onClose: () => void;
  cardType: CardType;
  initialText: string;
  context?: string;
  ankiStatus: AnkiStatus | null;
  onCardAdded: (message: string) => void;
}

export const AnkiCardModal: React.FC<AnkiCardModalProps> = ({
  isOpen,
  onClose,
  cardType: initialCardType,
  initialText,
  context = '',
  ankiStatus,
  onCardAdded,
}) => {
  const [cardType, setCardType] = useState<CardType>(initialCardType);
  const [deckName, setDeckName] = useState<string>('');
  const [modelName, setModelName] = useState<string>('');
  
  // Fields
  const [front, setFront] = useState('');
  const [meaning, setMeaning] = useState('');
  const [explanation, setExplanation] = useState('');
  const [example, setExample] = useState('');
  const [pos, setPos] = useState('');
  const [synonyms, setSynonyms] = useState('');

  const [isLoadingPreview, setIsLoadingPreview] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  useEffect(() => {
    if (isOpen && initialText) {
      setCardType(initialCardType);
      setFront(initialText);
      setErrorMsg(null);
      loadPreview(initialCardType, initialText, context);
    }
  }, [isOpen, initialText, initialCardType]);

  const loadPreview = async (type: CardType, text: string, ctx: string) => {
    setIsLoadingPreview(true);
    setErrorMsg(null);
    try {
      const res = await api.previewAnkiCard({
        card_type: type,
        text,
        context: ctx,
      });

      setDeckName(res.deck_name);
      setModelName(res.model_name);
      setFront(res.front || text);
      setMeaning(res.meaning || '');
      setExplanation(res.explanation || '');
      setExample(res.example || '');
      setPos(res.pos || '');
      setSynonyms(res.synonyms || '');
    } catch (err: any) {
      setErrorMsg(`AI 카드 정보 자동완성 중 오류: ${err.message}`);
    } finally {
      setIsLoadingPreview(false);
    }
  };

  const handleTypeChange = (newType: CardType) => {
    setCardType(newType);
    if (newType === 'sentence') {
      setDeckName('1. Language::1.1. English::Sentence');
      setModelName('English Sentence');
    } else {
      setDeckName('1. Language::1.1. English::Vocabulary');
      setModelName('English Vocabulary');
    }
    loadPreview(newType, front, context);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!front.trim()) {
      setErrorMsg('앞면 텍스트를 입력해주세요.');
      return;
    }

    setIsSubmitting(true);
    setErrorMsg(null);

    try {
      if (cardType === 'sentence') {
        const res = await api.addSentenceCard({
          sentence: front.trim(),
          translation: meaning.trim() || explanation.trim(),
          deck_name: deckName,
          model_name: modelName,
        });
        if (res.success) {
          onCardAdded(res.duplicate ? '이미 존재하는 문장입니다 (중복 방지)' : 'Anki 문장 카드가 성공적으로 등록되었습니다!');
          onClose();
        }
      } else {
        const res = await api.addVocabCard({
          word: front.trim(),
          meaning: meaning.trim(),
          pos: pos.trim(),
          synonyms: synonyms.trim(),
          example: example.trim(),
          explanation: explanation.trim(),
          deck_name: deckName,
          model_name: modelName,
        });
        if (res.success) {
          onCardAdded(res.duplicate ? '이미 존재하는 단어입니다 (중복 방지)' : 'Anki 단어 카드가 성공적으로 등록되었습니다!');
          onClose();
        }
      }
    } catch (err: any) {
      setErrorMsg(err.message || 'Anki 카드 등록에 실패했습니다.');
    } finally {
      setIsSubmitting(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-xs flex items-center justify-center p-4">
      <div className="bg-white dark:bg-[#222222] rounded-2xl border border-stone-200 dark:border-[#383838] shadow-2xl max-w-lg w-full overflow-hidden animate-in fade-in zoom-in-95 duration-150 transition-colors">
        {/* Header */}
        <div className="px-6 py-4 border-b border-stone-100 dark:border-[#2f2f2f] flex items-center justify-between bg-[#faf9f6] dark:bg-[#1a1a1a]">
          <div className="flex items-center space-x-2">
            <div className="p-1.5 rounded-lg bg-blue-50 dark:bg-blue-950/50 text-blue-700 dark:text-blue-300">
              <BookmarkPlus className="w-4 h-4" />
            </div>
            <div>
              <h3 className="text-sm font-bold text-stone-900 dark:text-[#f0f0f0]">Anki 플래시카드 등록</h3>
              <p className="text-[11px] text-stone-500 dark:text-stone-400">
                내용을 확인 및 수정한 후 AnkiConnect로 전송합니다 (gTTS 음성 자동 생성)
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="text-stone-400 dark:text-stone-500 hover:text-stone-700 dark:hover:text-stone-200 p-1.5 rounded-lg hover:bg-stone-100 dark:hover:bg-[#2c2c2c] transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Card Type Selector */}
        <div className="px-6 pt-4 pb-2 flex items-center space-x-2">
          <button
            type="button"
            onClick={() => handleTypeChange('sentence')}
            className={`flex-1 py-1.5 text-xs font-semibold rounded-lg border transition-all ${
              cardType === 'sentence'
                ? 'bg-blue-600 dark:bg-blue-500 border-blue-600 dark:border-blue-500 text-white shadow-xs'
                : 'bg-white dark:bg-[#2a2a2a] border-stone-200 dark:border-[#3a3a3a] text-stone-600 dark:text-stone-300 hover:bg-stone-50 dark:hover:bg-[#333333]'
            }`}
          >
            문장 카드 (English Sentence)
          </button>
          <button
            type="button"
            onClick={() => handleTypeChange('vocab')}
            className={`flex-1 py-1.5 text-xs font-semibold rounded-lg border transition-all ${
              cardType === 'vocab'
                ? 'bg-emerald-600 dark:bg-emerald-500 border-emerald-600 dark:border-emerald-500 text-white shadow-xs'
                : 'bg-white dark:bg-[#2a2a2a] border-stone-200 dark:border-[#3a3a3a] text-stone-600 dark:text-stone-300 hover:bg-stone-50 dark:hover:bg-[#333333]'
            }`}
          >
            단어/표현 카드 (English Vocabulary)
          </button>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="px-6 py-4 space-y-3.5">
          {errorMsg && (
            <div className="p-2.5 bg-red-50 dark:bg-red-950/40 border border-red-200 dark:border-red-800/60 rounded-lg text-xs text-red-700 dark:text-red-300 flex items-center space-x-1.5">
              <AlertCircle className="w-4 h-4 shrink-0 text-red-500" />
              <span>{errorMsg}</span>
            </div>
          )}

          {/* Deck Info */}
          <div className="grid grid-cols-2 gap-3 text-xs">
            <div>
              <label className="block text-[11px] font-semibold text-stone-500 dark:text-stone-400 mb-1">
                타겟 덱 (Target Deck)
              </label>
              <input
                type="text"
                value={deckName}
                onChange={(e) => setDeckName(e.target.value)}
                className="w-full px-2.5 py-1.5 bg-stone-50 dark:bg-[#1a1a1a] border border-stone-200 dark:border-[#383838] rounded-lg text-xs font-mono text-stone-700 dark:text-stone-300 outline-none focus:border-stone-400 dark:focus:border-[#555555]"
              />
            </div>
            <div>
              <label className="block text-[11px] font-semibold text-stone-500 dark:text-stone-400 mb-1">
                노트 모델 (Note Model)
              </label>
              <input
                type="text"
                value={modelName}
                onChange={(e) => setModelName(e.target.value)}
                className="w-full px-2.5 py-1.5 bg-stone-50 dark:bg-[#1a1a1a] border border-stone-200 dark:border-[#383838] rounded-lg text-xs font-mono text-stone-700 dark:text-stone-300 outline-none focus:border-stone-400 dark:focus:border-[#555555]"
              />
            </div>
          </div>

          {/* Front */}
          <div>
            <div className="flex items-center justify-between mb-1">
              <label className="text-[11px] font-semibold text-stone-700 dark:text-stone-300">
                {cardType === 'sentence' ? '앞면 (영어 문장)' : '앞면 (영어 단어/표현)'}
              </label>
              <span className="flex items-center space-x-1 text-[10px] text-stone-400 dark:text-stone-500">
                <Volume2 className="w-3 h-3" />
                <span>gTTS 음성 자동 생성</span>
              </span>
            </div>
            <textarea
              rows={2}
              value={front}
              onChange={(e) => setFront(e.target.value)}
              className="w-full px-3 py-2 bg-white dark:bg-[#1a1a1a] border border-stone-200 dark:border-[#383838] rounded-lg text-xs font-serif text-stone-900 dark:text-stone-100 outline-none focus:border-stone-400 dark:focus:border-[#555555] resize-none"
              placeholder={cardType === 'sentence' ? 'English sentence here...' : 'Word or idiom...'}
            />
          </div>

          {/* Meaning */}
          <div>
            <label className="block text-[11px] font-semibold text-stone-700 dark:text-stone-300 mb-1">
              뒷면 (한국어 뜻 / 번역)
            </label>
            <input
              type="text"
              value={meaning}
              onChange={(e) => setMeaning(e.target.value)}
              className="w-full px-3 py-1.5 bg-white dark:bg-[#1a1a1a] border border-stone-200 dark:border-[#383838] rounded-lg text-xs text-stone-900 dark:text-stone-100 outline-none focus:border-stone-400 dark:focus:border-[#555555]"
              placeholder={isLoadingPreview ? 'AI가 뜻을 분석하고 있습니다...' : '한국어 번역 또는 의미 입력'}
            />
          </div>

          {/* Vocab extra fields: POS, Synonyms, Example */}
          {cardType === 'vocab' && (
            <>
              <div className="grid grid-cols-2 gap-3 text-xs">
                <div>
                  <label className="block text-[11px] font-semibold text-stone-700 dark:text-stone-300 mb-1">
                    품사 (Part of Speech)
                  </label>
                  <input
                    type="text"
                    value={pos}
                    onChange={(e) => setPos(e.target.value)}
                    placeholder="noun, verb, idiom..."
                    className="w-full px-2.5 py-1.5 bg-white dark:bg-[#1a1a1a] border border-stone-200 dark:border-[#383838] rounded-lg text-xs text-stone-900 dark:text-stone-100 outline-none focus:border-stone-400 dark:focus:border-[#555555]"
                  />
                </div>
                <div>
                  <label className="block text-[11px] font-semibold text-stone-700 dark:text-stone-300 mb-1">
                    유의어 (Synonyms)
                  </label>
                  <input
                    type="text"
                    value={synonyms}
                    onChange={(e) => setSynonyms(e.target.value)}
                    placeholder="쉼표로 구분"
                    className="w-full px-2.5 py-1.5 bg-white dark:bg-[#1a1a1a] border border-stone-200 dark:border-[#383838] rounded-lg text-xs text-stone-900 dark:text-stone-100 outline-none focus:border-stone-400 dark:focus:border-[#555555]"
                  />
                </div>
              </div>

              <div>
                <label className="block text-[11px] font-semibold text-stone-700 dark:text-stone-300 mb-1">
                  예문 (Example Sentence)
                </label>
                <textarea
                  rows={2}
                  value={example}
                  onChange={(e) => setExample(e.target.value)}
                  placeholder="자연스러운 활용 예문..."
                  className="w-full px-3 py-1.5 bg-white dark:bg-[#1a1a1a] border border-stone-200 dark:border-[#383838] rounded-lg text-xs font-serif text-stone-900 dark:text-stone-100 outline-none focus:border-stone-400 dark:focus:border-[#555555] resize-none"
                />
              </div>
            </>
          )}

          {/* Explanation */}
          <div>
            <label className="block text-[11px] font-semibold text-stone-700 dark:text-stone-300 mb-1">
              문법 및 뉘앙스 해설 (Explanation)
            </label>
            <textarea
              rows={2}
              value={explanation}
              onChange={(e) => setExplanation(e.target.value)}
              placeholder="해설 또는 팁..."
              className="w-full px-3 py-1.5 bg-white dark:bg-[#1a1a1a] border border-stone-200 dark:border-[#383838] rounded-lg text-xs outline-none focus:border-stone-400 dark:focus:border-[#555555] resize-none text-stone-600 dark:text-stone-300"
            />
          </div>

          {/* Action Footer */}
          <div className="pt-3 border-t border-stone-100 dark:border-[#2f2f2f] flex items-center justify-between">
            <div className="flex items-center space-x-1.5 text-xs text-stone-500 dark:text-stone-400">
              {ankiStatus?.connected ? (
                <span className="flex items-center space-x-1 text-emerald-600 dark:text-emerald-400 text-[11px]">
                  <CheckCircle2 className="w-3.5 h-3.5" />
                  <span>Anki 준비 완료</span>
                </span>
              ) : (
                <span className="text-amber-600 dark:text-amber-400 text-[11px]">
                  ⚠️ Anki 데스크톱 앱이 실행되어 있어야 합니다.
                </span>
              )}
            </div>

            <div className="flex items-center space-x-2">
              <button
                type="button"
                onClick={onClose}
                className="px-3.5 py-2 text-xs font-medium text-stone-600 dark:text-stone-400 hover:bg-stone-100 dark:hover:bg-[#2c2c2c] rounded-lg transition-colors"
              >
                취소
              </button>
              <button
                type="submit"
                disabled={isSubmitting || isLoadingPreview}
                className="px-4 py-2 bg-stone-900 hover:bg-stone-800 dark:bg-stone-100 dark:hover:bg-white text-white dark:text-stone-900 text-xs font-semibold rounded-lg shadow-sm transition-all active:scale-95 disabled:opacity-50 flex items-center space-x-1.5"
              >
                {isSubmitting ? (
                  <span>Anki 전송 중...</span>
                ) : (
                  <>
                    <BookmarkPlus className="w-3.5 h-3.5" />
                    <span>Anki에 카드 등록</span>
                  </>
                )}
              </button>
            </div>
          </div>
        </form>
      </div>
    </div>
  );
};
