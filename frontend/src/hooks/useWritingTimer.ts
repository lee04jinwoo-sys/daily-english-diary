import { useCallback, useEffect, useRef, useState } from 'react';
import { api } from '../api/client';

/** Typing pause after which the timer stops. Thinking pauses shorter than this still count. */
export const IDLE_LIMIT_MS = 2 * 60 * 1000;
const PERSIST_EVERY_S = 30;

/**
 * Active writing time for one essay.
 * Starts on the first keystroke, keeps running while the last keystroke is within IDLE_LIMIT_MS,
 * and resumes on the next keystroke. The server keeps the max value, so a stale save is harmless.
 */
export function useWritingTimer(essayId: string, initialSeconds: number) {
  const [seconds, setSeconds] = useState(initialSeconds);
  const [isRunning, setIsRunning] = useState(false);
  const secondsRef = useRef(initialSeconds);
  const savedRef = useRef(initialSeconds);
  const lastInputAtRef = useRef(0);
  const runningRef = useRef(false);

  const persist = useCallback(
    (keepalive = false) => {
      const value = secondsRef.current;
      if (value <= savedRef.current) return;
      const previous = savedRef.current;
      savedRef.current = value;
      api.updateEssay(essayId, { writing_seconds: value }, keepalive).catch(() => {
        savedRef.current = previous; // retry on the next tick / idle / unmount
      });
    },
    [essayId]
  );

  const markActivity = useCallback(() => {
    lastInputAtRef.current = Date.now();
    runningRef.current = true;
    setIsRunning(true);
  }, []);

  useEffect(() => {
    const id = setInterval(() => {
      const active = lastInputAtRef.current > 0 && Date.now() - lastInputAtRef.current < IDLE_LIMIT_MS;
      if (active) {
        secondsRef.current += 1;
        setSeconds(secondsRef.current);
        if (secondsRef.current - savedRef.current >= PERSIST_EVERY_S) persist();
      } else if (runningRef.current) {
        runningRef.current = false; // just went idle: stop and save what we have
        setIsRunning(false);
        persist();
      }
    }, 1000);

    const onUnload = () => persist(true);
    window.addEventListener('beforeunload', onUnload);
    return () => {
      clearInterval(id);
      window.removeEventListener('beforeunload', onUnload);
      persist(true); // switching essays or closing the editor
    };
  }, [persist]);

  return { seconds, isRunning, hasStarted: lastInputAtRef.current > 0 || seconds > 0, markActivity };
}

export function formatDuration(totalSeconds: number): string {
  const h = Math.floor(totalSeconds / 3600);
  const m = Math.floor((totalSeconds % 3600) / 60);
  const s = totalSeconds % 60;
  const mm = String(m).padStart(h > 0 ? 2 : 1, '0');
  const ss = String(s).padStart(2, '0');
  return h > 0 ? `${h}:${mm}:${ss}` : `${mm}:${ss}`;
}
