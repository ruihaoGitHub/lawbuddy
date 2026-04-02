"use client";

import styles from "./welcome-panel.module.scss";

type Props = {
  onSelect: (text: string) => void;
};

const SCENES = [
  {
    title: "被解雇 / 辞退",
    desc: "突然被通知不用来了",
    value: "我被公司突然辞退了，不知道这种情况该怎么维权，你能帮我分析一下吗？",
    color: "orange",
  },
  {
    title: "工资被拖欠",
    desc: "发工资了但一直不给",
    value: "公司一直拖欠我的工资，到现在都没有发，我想知道该怎么处理。",
    color: "yellow",
  },
  {
    title: "没签劳动合同",
    desc: "入职一直没让我签合同",
    value: "我已经入职一段时间了，但公司一直没有和我签劳动合同，这种情况我该怎么办？",
    color: "purple",
  },
  {
    title: "工伤问题",
    desc: "工作时受伤或生病",
    value: "我在工作期间受伤了，想了解工伤认定和后续维权应该怎么做。",
    color: "green",
  },
  {
    title: "被逼主动辞职",
    desc: "老板暗示我自己走",
    value: "公司在逼我主动辞职，但没有明确辞退我，我想知道这种情况该怎么应对。",
    color: "pink",
  },
  {
    title: "社保问题",
    desc: "没缴或少缴社保",
    value: "我怀疑公司没有正常给我缴纳社保，或者存在少缴的情况，我可以怎么维权？",
    color: "blue",
  },
] as const;

export default function WelcomePanel({ onSelect }: Props) {
  return (
    <section className={styles.wrapper} aria-label="welcome guide">
      <div className={styles.hero}>
        <div className={styles.heroCard}>
          <div className={styles.heroBrand}>
            <div className={styles.heroIcon} aria-hidden="true">
              劳
            </div>
            <div className={styles.heroMeta}>
              <div className={styles.brand}>劳小权</div>
              <div className={styles.tagline}>你身边懂法律的朋友</div>
            </div>
          </div>

          <div className={styles.heroTitle}>先别慌，把你的情况告诉我</div>

          <div className={styles.desc}>
            劳动合同、工资拖欠、社保、工伤、被辞退这些问题都可以直接问。
            你只需要把发生了什么说清楚，我会帮你梳理风险和可行的维权方向。
          </div>
        </div>
      </div>

      <div className={styles.content}>
        <div className={styles.sectionTitle}>你可以直接选择一个常见问题：</div>

        <div className={styles.chips}>
          {SCENES.map((item) => (
            <button
              key={item.title}
              type="button"
              className={`${styles.sceneChip} ${styles[item.color]}`}
              onClick={() => onSelect(item.value)}
            >
              <span className={styles.sceneTitle}>{item.title}</span>
              <span className={styles.sceneDesc}>{item.desc}</span>
            </button>
          ))}
        </div>
      </div>
    </section>
  );
}
