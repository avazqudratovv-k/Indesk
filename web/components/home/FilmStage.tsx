import { Fragment, type CSSProperties } from "react";
import { useTranslations } from "next-intl";
import { agentColor, agentIds, type AgentId } from "./agents";
import { film, threadX } from "./film-data";
import styles from "./HomeFilm.module.css";

type Vars = CSSProperties & Record<`--${string}`, string | number>;

const spriteDelay = (index: number) => `${(-0.45 * index).toFixed(2)}s`;
const cx = (...names: string[]) => names.map((name) => styles[name]).join(" ");

// The 8:5 stage of the demo film. Purely visual: the screen-reader text lives in HomeFilm.
// PLACEHOLDER content: see film-data.ts and home.film.placeholderClaims in the message files.
export default function FilmStage({ verified, total }: { verified: number; total: number }) {
  const t = useTranslations("home.film");
  return (
    <div className={styles.film}>
      {film.files.map((file, i) => (
        <div key={file.kind} className={cx("abs", "file", `ff${i}`)} style={{ "--i": i, "--agent": file.color } as Vars}>
          <div className={cx("fileCard", `hl${i}`)}>
            <div className={styles.fileTab}>{file.kind}</div>
            <div className={styles.fileLines}>
              <i />
              <i />
              <i />
            </div>
          </div>
          <i className={styles.pin} />
        </div>
      ))}
      <div className={cx("abs", "live")}>
        <span className={styles.liveDot} />
        {t("live")}
      </div>
      <div className={cx("abs", "case", "fcase")}>{t("caseLabel", { no: film.caseNo })}</div>
      <div className={cx("abs", "question", "fq")}>
        <b className={styles.qMark}>?</b>
        <span className={styles.qClip}>
          <span className={cx("ftype")}>{t("question")}</span>
        </span>
        <i className={cx("caret", "fcaret")} />
      </div>
      <svg className={styles.threads} viewBox="0 0 640 400" preserveAspectRatio="none" aria-hidden="true">
        {threadX.map((x, i) => (
          <path
            key={x}
            className={cx("thread", `fth${i}`)}
            d={`M340 52 C340 100 ${x} 96 ${x} 138`}
            stroke={agentColor[agentIds[i]]}
            pathLength={100}
          />
        ))}
      </svg>

      <div className={cx("abs", "workCard", "fc0k")} style={{ "--i": 0, "--agent": agentColor.owl } as Vars}>
        <div className={styles.cardHead}>{t("agents.owl")}</div>
        <div className={styles.cardMono}>{film.owl.field}</div>
        <div className={styles.cardBig}>
          {film.owl.value[0]}
          <br />
          {film.owl.value[1]}
        </div>
        <div className={styles.meter}>
          <div className={styles.fconf} />
        </div>
        <div className={styles.cardNote}>{film.owl.confidence}</div>
      </div>
      <div className={cx("abs", "workCard", "fc1k")} style={{ "--i": 1, "--agent": agentColor.chameleon } as Vars}>
        <div className={styles.cardHead}>{t("agents.chameleon")}</div>
        <div className={styles.shot}>
          {[
            ["0.781cqw", "2.188cqw", "#6b6250"],
            ["3.125cqw", "3.438cqw", "#5c5444"],
            ["5.469cqw", "5.625cqw", "#8a7f66"],
            ["7.812cqw", "4.375cqw", "#5c5444"],
          ].map(([x, h, c]) => (
            <i key={x} style={{ "--x": x, "--h": h, "--c": c } as Vars} />
          ))}
          <b style={{ left: "0.312cqw", top: "0.312cqw", width: "3.75cqw", height: "1.25cqw" }} />
          <b style={{ left: "7.188cqw", top: "2.188cqw", width: "2.5cqw", height: "3.75cqw" }} />
        </div>
        <div className={styles.quotes}>
          {film.vision.quotes.map(([label, value]) => (
            <div key={label}>
              {label} <b>{value}</b>
            </div>
          ))}
          <span className={styles.good}>{film.vision.confidence}</span>
        </div>
      </div>
      <div className={cx("abs", "workCard", "fc2k")} style={{ "--i": 2, "--agent": agentColor.beaver } as Vars}>
        <div className={styles.cardHead}>{t("agents.beaver")}</div>
        <div className={styles.code}>
          {film.data.codeStart}
          <span className={styles.str}>{film.data.codeArg}</span>
          {film.data.codeEnd}
          <br />
          {film.data.codeLine2}
        </div>
        <div className={styles.bars}>
          <i className={styles.fb0} style={{ height: "1.875cqw", background: "var(--rule2)" }} />
          <i className={styles.fb1} style={{ height: "3.125cqw", background: "var(--ink2)" }} />
          <i className={styles.fb2} style={{ height: "5cqw", background: "var(--c-bea)" }} />
        </div>
        <div className={styles.cardMono} style={{ padding: "0.469cqw 0.781cqw" }}>
          {film.data.summary}
        </div>
      </div>
      <div className={cx("abs", "workCard", "fc3k")} style={{ "--i": 3, "--agent": agentColor.hound } as Vars}>
        <div className={styles.cardHead}>{t("agents.hound")}</div>
        <div className={styles.cardMono} style={{ padding: "0.625cqw 0.781cqw 0" }}>
          {film.retrieval.source}
        </div>
        <div className={styles.snippet}>
          {[94, 100, 72, 88, 50].map((width, i) => (
            <i key={i} className={i === 1 || i === 2 ? styles.mark : undefined} style={{ width: `${width}%` }} />
          ))}
        </div>
        <div className={cx("cardNote", "good")}>{film.retrieval.score}</div>
      </div>
      <div className={cx("abs", "workCard", "fc4k")} style={{ "--i": 4, "--agent": agentColor.cat } as Vars}>
        <div className={styles.cardHead}>{t("agents.cat")}</div>
        <div className={styles.checks}>
          <div className={styles.check}>
            <b>✓</b>
            <span>{t("placeholderClaims.a")}</span>
          </div>
          <div className={styles.check}>
            <b>✓</b>
            <span>{t("placeholderClaims.b")}</span>
          </div>
          <div className={cx("check", "checkBad", "shake")}>
            <b>✗</b>
            <span>{t("placeholderClaims.c")}</span>
          </div>
        </div>
      </div>

      {agentIds.map((id: AgentId, i) => {
        const vars = { "--i": i, "--agent": agentColor[id] } as Vars;
        return (
          <Fragment key={id}>
            <div className={cx("abs", "animal", `fm${i}`)} style={vars}>
              <span className={styles.hvs} aria-hidden="true">
                {/* Sprite sheet of 24 frames; a plain img (not next/image) because it is stepped with CSS. Low priority: it is not needed for first paint. */}
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img src={`/home/sprite-${id}.webp`} alt="" width={4224} height={176} loading="lazy" decoding="async" fetchPriority="low" style={{ "--d": spriteDelay(i) } as Vars} />
              </span>
            </div>
            <div className={cx("abs", "ring", `fr${i}`)} style={vars} />
            <div className={cx("abs", "animalLabel", `fm${i}`)} style={vars}>
              {t(`agents.${id}`)}
            </div>
          </Fragment>
        );
      })}

      <div className={cx("abs", "dim", "fdim")} />
      <div className={cx("abs", "report", "frep")}>
        <div className={styles.reportHead}>
          <span className={styles.reportTitle}>{t("report.title")}</span>
          <span className={styles.reportMeta}>{t("report.meta", { no: film.caseNo, agents: film.agentCount })}</span>
        </div>
        <div className={styles.rows}>
          {film.reportRows.map((row) => (
            <div key={row.label} className={styles.row} style={{ "--c": row.color, "--w": `${row.width}%` } as Vars}>
              <b />
              <i />
              <span>{row.label}</span>
            </div>
          ))}
          <div className={cx("row", "rowBad")} style={{ "--w": `${film.flaggedRow.width}%` } as Vars}>
            <b />
            <i />
            <span>{film.flaggedRow.label}</span>
            <svg className={styles.scribble} viewBox="0 0 300 40" preserveAspectRatio="none" aria-hidden="true">
              <path className={styles.circ} d="M30 22C10 8 90 -2 170 4S296 12 290 26 200 40 120 38 8 36 30 22z" pathLength={100} />
            </svg>
          </div>
        </div>
        <div className={cx("abs", "stamp", "fstamp")}>{t("report.stamp", { verified, total })}</div>
        <div className={cx("abs", "download", "fdl")}>↓ {t("report.download")}</div>
      </div>
    </div>
  );
}
