// SPDX-License-Identifier: MIT
// Deterministic animation envelope for newly created Beacon Atlas contracts.

export const CONTRACT_PULSE_DURATION_SECONDS = 2.4;

function clamp(value, min, max) {
  return Math.min(max, Math.max(min, value));
}

export function contractPulseFrame(elapsedSeconds, baseOpacity = 0.3) {
  const elapsed = Number.isFinite(elapsedSeconds) ? Math.max(0, elapsedSeconds) : 0;
  const opacity = Number.isFinite(baseOpacity) ? clamp(baseOpacity, 0, 1) : 0.3;
  const progress = clamp(elapsed / CONTRACT_PULSE_DURATION_SECONDS, 0, 1);

  // Three bright beats make a new connection noticeable, while the envelope
  // guarantees that the temporary additive line fades completely and can be
  // disposed after a bounded lifetime.
  const wave = Math.cos(progress * Math.PI * 3) ** 2;
  const envelope = (1 - progress) ** 1.5;
  const intensity = wave * envelope;
  const peakOpacity = clamp(opacity + 0.55, 0.35, 1);

  return {
    glowOpacity: peakOpacity * intensity,
    glowScale: 1 + Math.sin(progress * Math.PI) * 0.08 + intensity * 0.04,
    done: elapsed >= CONTRACT_PULSE_DURATION_SECONDS,
  };
}
