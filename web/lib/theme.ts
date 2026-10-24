export type Theme = "light" | "dark";

export const themeStorageKey = "indesk-theme";

// Runs in <head> before first paint (no flash). Saved choice wins; otherwise follow the system.
export const themeInitScript = `(function(){try{var t=localStorage.getItem("${themeStorageKey}");if(t!=="light"&&t!=="dark"){t=matchMedia("(prefers-color-scheme: dark)").matches?"dark":"light"}document.documentElement.setAttribute("data-theme",t)}catch(e){}})()`;
