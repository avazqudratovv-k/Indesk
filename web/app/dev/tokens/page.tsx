import { colorGroups, reportPaperTokens } from "./tokens-data";
import styles from "./page.module.css";

// Dev-only test page for ROADMAP 1.3. Remove or hide it before deploy.
function Palette({ title, theme }: { title: string; theme: "light" | "dark" | "dk" }) {
  const attrs = theme === "dk" ? { className: `${styles.panel} dk` } : { className: styles.panel, "data-theme": theme };
  return (
    <section {...attrs} aria-label={title}>
      <h2 className={styles.h2}>{title}</h2>
      {colorGroups.map((group) => (
        <div key={group.title} className={styles.group}>
          <h3 className={styles.h3}>{group.title}</h3>
          <ul className={styles.list}>
            {group.tokens.map((token) => (
              <li key={token} className={styles.item}>
                <span className={styles.swatch} style={{ background: `var(--${token})` }} />
                <code className={styles.name}>--{token}</code>
              </li>
            ))}
          </ul>
        </div>
      ))}
      <div className={styles.group}>
        <h3 className={styles.h3}>Primary button, shadow, text</h3>
        <button type="button" className={styles.primary}>Try with an example</button>
        <div className={styles.shadowBox}>--shadow</div>
        <p className={styles.sample}>Onest text. 한국어 텍스트. <code>JetBrains Mono 0123</code></p>
      </div>
    </section>
  );
}

export default function TokensPage() {
  return (
    <main className={styles.page}>
      <h1 className={styles.h1}>Design tokens</h1>
      <p className={styles.lede}>Every color from DESIGN.md in Nocturne (light), Midnight (dark) and the always-dark panel.</p>
      <div className={styles.panels}>
        <Palette title="Nocturne (light)" theme="light" />
        <Palette title="Midnight (dark)" theme="dark" />
        <Palette title="Always-dark panel (.dk)" theme="dk" />
      </div>
      <section className={styles.group} aria-label="Report paper">
        <h2 className={styles.h2}>Report paper (same in both themes)</h2>
        <ul className={styles.list}>
          {reportPaperTokens.map((token) => (
            <li key={token} className={styles.item}>
              <span className={styles.swatch} style={{ background: `var(--${token})` }} />
              <code className={styles.name}>--{token}</code>
            </li>
          ))}
        </ul>
      </section>
    </main>
  );
}
