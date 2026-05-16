const { expect } = require("chai");
const {
  MAX_UINT256,
  parseTokenAmount,
  formatTokenAmount,
} = require("../scripts/token-amount");

describe("Deployment token amount helpers", function () {
  it("parses token amounts exactly into six-decimal atomic units", function () {
    expect(parseTokenAmount("1000000")).to.equal(1000000000000n);
    expect(parseTokenAmount("1.000001")).to.equal(1000001n);
    expect(parseTokenAmount("0002.5")).to.equal(2500000n);
  });

  it("rejects values that should not be coerced by JavaScript number parsing", function () {
    const invalidAmounts = [
      "",
      "-1",
      "1e309",
      "Infinity",
      "NaN",
      "0x10",
      "1_000",
      "1.0000001",
    ];

    for (const amount of invalidAmounts) {
      expect(() => parseTokenAmount(amount)).to.throw();
    }
  });

  it("rejects values outside the uint256 deployment range", function () {
    const tooLarge = (MAX_UINT256 / 1000000n + 1n).toString();

    expect(() => parseTokenAmount(tooLarge)).to.throw(/uint256/);
  });

  it("formats atomic units without losing integer precision", function () {
    const amount = parseTokenAmount("123456789123456789.123456");

    expect(formatTokenAmount(amount)).to.equal(
      "123,456,789,123,456,789.123456",
    );
  });
});
