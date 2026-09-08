// SPDX-License-Identifier: MIT

const MASTER_LEVEL = 0.045;
const MAX_TRANSIENTS = 6;
const HOVER_COOLDOWN_MS = 120;

let audioContext = null;
let masterGain = null;
let ambientNodes = [];
let soundControl = null;
let soundEnabled = false;
let soundSupported = true;
let activeTransients = 0;
let lastHoverAt = 0;
let suspendTimer = null;
let delegatedEventsBound = false;

function audioContextConstructor() {
  return globalThis.AudioContext || globalThis.webkitAudioContext || null;
}

function setParam(param, value, time) {
  if (typeof param.setValueAtTime === 'function') {
    param.setValueAtTime(value, time);
  } else {
    param.value = value;
  }
}

function buildAudioGraph() {
  if (audioContext && audioContext.state !== 'closed') return audioContext;

  const AudioContextClass = audioContextConstructor();
  if (!AudioContextClass) {
    soundSupported = false;
    updateControl();
    return null;
  }

  audioContext = new AudioContextClass();
  masterGain = audioContext.createGain();
  setParam(masterGain.gain, 0, audioContext.currentTime);
  masterGain.connect(audioContext.destination);

  const lowPass = audioContext.createBiquadFilter();
  lowPass.type = 'lowpass';
  setParam(lowPass.frequency, 180, audioContext.currentTime);
  setParam(lowPass.Q, 0.7, audioContext.currentTime);
  lowPass.connect(masterGain);

  ambientNodes = [
    { frequency: 55, level: 0.32, type: 'sine' },
    { frequency: 82.5, level: 0.12, type: 'triangle' },
  ].map(({ frequency, level, type }) => {
    const oscillator = audioContext.createOscillator();
    const gain = audioContext.createGain();
    oscillator.type = type;
    setParam(oscillator.frequency, frequency, audioContext.currentTime);
    setParam(gain.gain, level, audioContext.currentTime);
    oscillator.connect(gain);
    gain.connect(lowPass);
    oscillator.start();
    return { oscillator, gain };
  });

  return audioContext;
}

function updateControl() {
  if (!soundControl) return;

  if (!soundSupported) {
    soundControl.textContent = '[SOUND N/A]';
    soundControl.disabled = true;
    soundControl.setAttribute('aria-label', 'Sound is not supported by this browser');
    soundControl.setAttribute('aria-pressed', 'false');
    return;
  }

  soundControl.disabled = false;
  soundControl.textContent = soundEnabled ? '[SOUND ON]' : '[SOUND OFF]';
  soundControl.setAttribute('aria-label', soundEnabled ? 'Mute Beacon Atlas sound' : 'Enable Beacon Atlas sound');
  soundControl.setAttribute('aria-pressed', String(soundEnabled));
  soundControl.classList.toggle('is-active', soundEnabled);
}

function fadeMaster(target, seconds) {
  if (!audioContext || !masterGain) return;
  const now = audioContext.currentTime;
  const gain = masterGain.gain;
  gain.cancelScheduledValues?.(now);
  setParam(gain, gain.value, now);
  gain.linearRampToValueAtTime?.(target, now + seconds);
  if (typeof gain.linearRampToValueAtTime !== 'function') gain.value = target;
}

export async function setSoundEnabled(enabled) {
  if (!enabled) {
    soundEnabled = false;
    fadeMaster(0, 0.18);
    updateControl();

    clearTimeout(suspendTimer);
    suspendTimer = setTimeout(() => {
      if (!soundEnabled && audioContext?.state === 'running') audioContext.suspend();
    }, 220);
    return false;
  }

  const context = buildAudioGraph();
  if (!context) return false;

  clearTimeout(suspendTimer);
  try {
    if (context.state === 'suspended') await context.resume();
  } catch (error) {
    console.warn('[sound] Browser blocked audio activation:', error.message);
    soundEnabled = false;
    updateControl();
    return false;
  }

  soundEnabled = context.state !== 'closed';
  fadeMaster(MASTER_LEVEL, 0.25);
  updateControl();
  return soundEnabled;
}

function playTone(frequency, duration, level, waveform = 'sine') {
  if (!soundEnabled || audioContext?.state !== 'running' || !masterGain) return false;
  if (activeTransients >= MAX_TRANSIENTS) return false;

  const oscillator = audioContext.createOscillator();
  const gain = audioContext.createGain();
  const now = audioContext.currentTime;
  oscillator.type = waveform;
  setParam(oscillator.frequency, frequency, now);
  setParam(gain.gain, 0.0001, now);
  gain.gain.exponentialRampToValueAtTime?.(level, now + 0.01);
  gain.gain.exponentialRampToValueAtTime?.(0.0001, now + duration);
  oscillator.connect(gain);
  gain.connect(masterGain);

  activeTransients += 1;
  oscillator.addEventListener('ended', () => {
    oscillator.disconnect();
    gain.disconnect();
    activeTransients = Math.max(0, activeTransients - 1);
  }, { once: true });
  oscillator.start(now);
  oscillator.stop(now + duration + 0.02);
  return true;
}

export function playHoverTone() {
  const now = performance.now();
  if (now - lastHoverAt < HOVER_COOLDOWN_MS) return false;
  lastHoverAt = now;
  return playTone(720, 0.045, 0.12, 'sine');
}

export function playClickTone(kind = 'default') {
  const frequencies = {
    agent: 520,
    city: 390,
    close: 220,
    toggle: 660,
    default: 460,
  };
  return playTone(frequencies[kind] || frequencies.default, 0.09, 0.2, 'triangle');
}

function bindDelegatedFeedback() {
  if (delegatedEventsBound || !globalThis.document?.addEventListener) return;
  delegatedEventsBound = true;
  const selector = 'a, button, [role="button"], .panel-dot, .bounty-card, .contract-new-btn';

  document.addEventListener('pointerover', (event) => {
    const target = event.target.closest?.(selector);
    if (!target || target.contains(event.relatedTarget) || target === soundControl) return;
    playHoverTone();
  });

  document.addEventListener('click', (event) => {
    const target = event.target.closest?.(selector);
    if (target && target !== soundControl) playClickTone();
  });
}

export function initSoundControls(control) {
  soundControl = control;
  updateControl();
  bindDelegatedFeedback();

  if (!control) return;
  control.addEventListener('click', async () => {
    const activated = await setSoundEnabled(!soundEnabled);
    if (activated) playClickTone('toggle');
  });
  globalThis.window?.addEventListener('pagehide', disposeSound, { once: true });
}

export function disposeSound() {
  clearTimeout(suspendTimer);
  soundEnabled = false;
  ambientNodes.forEach(({ oscillator, gain }) => {
    try { oscillator.stop(); } catch {}
    oscillator.disconnect();
    gain.disconnect();
  });
  ambientNodes = [];
  masterGain?.disconnect();
  masterGain = null;
  if (audioContext && audioContext.state !== 'closed') audioContext.close();
  audioContext = null;
  activeTransients = 0;
  updateControl();
}
