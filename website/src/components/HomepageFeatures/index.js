import clsx from 'clsx';
import Heading from '@theme/Heading';
import styles from './styles.module.css';

const FeatureList = [
  {
    title: 'Proof-of-Antiquity',
    icon: '🕰️',
    description: (
      <>
        Old machines outmine new ones. A PowerPC G4 earns <strong>2.5×</strong> a
        modern x86 — antiquity is the moat. The hardware everyone else threw away
        is the hardware that wins here.
      </>
    ),
  },
  {
    title: '1 CPU = 1 Vote',
    icon: '⚖️',
    description: (
      <>
        Every real CPU is one honest vote, proven by hardware fingerprinting —
        clock-skew, cache-timing, and SIMD identity that VMs and emulators
        can&apos;t fake. Fake machines earn a billionth of real ones.
      </>
    ),
  },
  {
    title: 'Vintage Hardware Wins',
    icon: '🖥️',
    description: (
      <>
        PowerPC, SPARC, MIPS, 68k, POWER8 and more — <strong>15+ CPU
        architectures</strong> across G4/G5 Macs, Amigas, and datacenter iron,
        all attesting to one Proof-of-Antiquity chain.
      </>
    ),
  },
];

function Feature({icon, title, description}) {
  return (
    <div className={clsx('col col--4')}>
      <div className="text--center">
        <span className={styles.featureIcon} role="img" aria-label={title}>
          {icon}
        </span>
      </div>
      <div className="text--center padding-horiz--md">
        <Heading as="h3">{title}</Heading>
        <p>{description}</p>
      </div>
    </div>
  );
}

export default function HomepageFeatures() {
  return (
    <section className={styles.features}>
      <div className="container">
        <div className="row">
          {FeatureList.map((props, idx) => (
            <Feature key={idx} {...props} />
          ))}
        </div>
      </div>
    </section>
  );
}
