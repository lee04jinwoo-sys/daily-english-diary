import { describe, expect, it } from 'vitest';
import { loadThemePref, nextThemePref, resolveTheme, saveThemePref } from './theme';

const memory = (init: Record<string, string> = {}) => {
  const data = { ...init };
  return {
    data,
    getItem: (k: string) => (k in data ? data[k] : null),
    setItem: (k: string, v: string) => { data[k] = v; },
    removeItem: (k: string) => { delete data[k]; },
  };
};

describe('theme preference', () => {
  it('follows the system when nothing was chosen', () => {
    expect(loadThemePref(memory())).toBe('system');
  });

  it('ignores the old "theme" key: it was written on every visit, not chosen by the user', () => {
    expect(loadThemePref(memory({ theme: 'dark' }))).toBe('system');
    expect(loadThemePref(memory({ theme: 'light' }))).toBe('system');
  });

  it('keeps an explicit choice', () => {
    const s = memory();
    saveThemePref('dark', s);
    expect(loadThemePref(s)).toBe('dark');
    saveThemePref('light', s);
    expect(loadThemePref(s)).toBe('light');
  });

  it('choosing "system" again removes the stored choice', () => {
    const s = memory();
    saveThemePref('dark', s);
    saveThemePref('system', s);
    expect(loadThemePref(s)).toBe('system');
    expect(Object.keys(s.data)).toEqual([]);
  });

  it('treats an unknown stored value as no choice', () => {
    expect(loadThemePref(memory({ theme_pref: 'purple' }))).toBe('system');
  });

  it('survives storage that throws (private mode)', () => {
    const broken = { getItem: () => { throw new Error('no'); }, setItem: () => { throw new Error('no'); }, removeItem: () => { throw new Error('no'); } };
    expect(loadThemePref(broken)).toBe('system');
    expect(() => saveThemePref('dark', broken)).not.toThrow();
  });
});

describe('resolveTheme', () => {
  it('uses the system setting only in system mode', () => {
    expect(resolveTheme('system', true)).toBe('dark');
    expect(resolveTheme('system', false)).toBe('light');
    expect(resolveTheme('light', true)).toBe('light');
    expect(resolveTheme('dark', false)).toBe('dark');
  });
});

describe('nextThemePref', () => {
  it('cycles system -> light -> dark -> system', () => {
    expect(nextThemePref('system')).toBe('light');
    expect(nextThemePref('light')).toBe('dark');
    expect(nextThemePref('dark')).toBe('system');
  });
});
