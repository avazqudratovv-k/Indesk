import styles from "./ChoiceGroup.module.css";

export type Choice = { value: string; label: string };

type ChoiceGroupProps = {
  title: string;
  hint: string;
  choices: Choice[];
  selected: string;
  onPick: (value: string) => void;
};

// A row of toggle buttons for one custom-plan setting (the board's pill groups).
export default function ChoiceGroup({ title, hint, choices, selected, onPick }: ChoiceGroupProps) {
  return (
    <div role="group" aria-label={title} className={styles.group}>
      <div className={styles.head}>
        <b className={styles.title}>{title}</b>
        <span className={styles.hint}>{hint}</span>
      </div>
      <div className={styles.row}>
        {choices.map((choice) => (
          <button
            key={choice.value}
            type="button"
            aria-pressed={choice.value === selected}
            className={styles.pill}
            onClick={() => onPick(choice.value)}
          >
            {choice.label}
          </button>
        ))}
      </div>
    </div>
  );
}
