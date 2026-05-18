// SPDX-License-Identifier: MIT

const DECIMALS = 6n;
const TOKEN_SCALE = 10n ** DECIMALS;
const MAX_UINT256 = (1n << 256n) - 1n;
const MAX_WHOLE_TOKENS = MAX_UINT256 / TOKEN_SCALE;

function assertTokenAmountString(value) {
  const amount = String(value).trim();

  if (amount.length === 0) {
    throw new Error("Token amount is required");
  }
  if (amount.startsWith("-")) {
    throw new Error("Token amount must be non-negative");
  }
  if (!/^\d+(\.\d+)?$/.test(amount)) {
    throw new Error("Invalid token amount format");
  }

  return amount;
}

function parseTokenAmount(value) {
  const amount = assertTokenAmountString(value);
  const [wholePart, fractionalPart = ""] = amount.split(".");

  if (fractionalPart.length > Number(DECIMALS)) {
    throw new Error(`Token amount supports at most ${DECIMALS} decimal places`);
  }

  const normalizedWhole = wholePart.replace(/^0+(?=\d)/, "");
  if (
    normalizedWhole.length > MAX_WHOLE_TOKENS.toString().length ||
    BigInt(normalizedWhole) > MAX_WHOLE_TOKENS
  ) {
    throw new Error("Token amount exceeds uint256 range");
  }

  const fractional = fractionalPart.padEnd(Number(DECIMALS), "0");
  const atomicAmount =
    BigInt(normalizedWhole) * TOKEN_SCALE + BigInt(fractional);

  if (atomicAmount > MAX_UINT256) {
    throw new Error("Token amount exceeds uint256 range");
  }

  return atomicAmount;
}

function formatTokenAmount(value) {
  const amount = BigInt(value);
  const whole = amount / TOKEN_SCALE;
  const fractional = amount % TOKEN_SCALE;
  const wholeFormatted = whole.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ",");

  if (fractional === 0n) {
    return wholeFormatted;
  }

  const fractionalFormatted = fractional
    .toString()
    .padStart(Number(DECIMALS), "0")
    .replace(/0+$/, "");

  return `${wholeFormatted}.${fractionalFormatted}`;
}

module.exports = {
  DECIMALS,
  TOKEN_SCALE,
  MAX_UINT256,
  parseTokenAmount,
  formatTokenAmount,
};
