export type ThemePref = 'system' | 'light' | 'dark';

type Store = Pick<Storage, 'getItem' | 'setItem' | 'removeItem'>;

/** Only an explicit choice is stored. The old 'theme' key is ignored: it was written on every visit. */
export const THEME_KEY = 'theme_pref';
export const DARK_QUERY = '(prefers-color-scheme: dark)';

export function loadThemePref(store: Store = localStorage): ThemePref {
  try {
    const v = store.getItem(THEME_KEY);
    return v === 'light' || v === 'dark' ? v : 'system';
  } catch {
    return 'system';
  }
}

export function saveThemePref(pref: ThemePref, store: Store = localStorage): void {
  try {
    if (pref === 'system') store.removeItem(THEME_KEY);
    else store.setItem(THEME_KEY, pref);
  } catch {
    // private mode etc.: the choice lasts for this page only
  }
}

export function resolveTheme(pref: ThemePref, systemDark: boolean): 'light' | 'dark' {
  return pref === 'system' ? (systemDark ? 'dark' : 'light') : pref;
}

export function nextThemePref(pref: ThemePref): ThemePref {
  return pref === 'system' ? 'light' : pref === 'light' ? 'dark' : 'system';
}
