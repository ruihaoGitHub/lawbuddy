"use client";

import styles from "./quick-actions.module.scss";

type Props = {
  onSelect: (text: string) => void;
};

const QUICK_ACTIONS = [
  "公司突然把我开了",
  "公司逼我自己辞职",
  "工资一直拖着不给",
  "上班了但一直没签合同",
  "我不确定属于哪种情况",
];

export function QuickActions(props: Props) {
  const { onSelect } = props;

  return (
    <div className={styles.wrapper}>
      <div className={styles.list}>
        {QUICK_ACTIONS.map((text) => (
          <button
            key={text}
            type="button"
            className={styles.button}
            onClick={() => onSelect(text)}
          >
            {text}
          </button>
        ))}
      </div>
    </div>
  );
}