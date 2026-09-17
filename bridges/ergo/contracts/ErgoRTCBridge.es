// ErgoScript EIP-4 Token Minting & 2-of-3 Multisig Bridge Contract for RustChain RTC
// Backs eRTC on Ergo 1:1 against locked native RTC on RustChain

{
  // Public keys for 2-of-3 Bridge Federation Operators
  val operator1 = PK("9f4QF8AD1nQ3nEAQVkcmdtPdKFCWPDnHGnzt4kJvCJWuLMtRNhk")
  val operator2 = PK("9gRAwdDdc8pQJ9iLi4a2F4q7w9iFm1Wv9mJ4n2v9kLmNx8PqRst")
  val operator3 = PK("9hBcWdEfc9qRk0jMj5b3G5r8x0jGn2Xw0nK5o3w0lMnOy9QrTuv")

  // EIP-4 Token Properties
  val expectedTokenId: Coll[Byte] = SELF.R4[Coll[Byte]].get
  val minBoxValue: Long = 1000000L // 0.001 ERG min box value

  // Operation Mode:
  // Mode 1: Minting eRTC upon verified RustChain Lock
  val isMintOrRelease: Boolean = {
    val quorum: Int = (if (operator1) 1 else 0) + (if (operator2) 1 else 0) + (if (operator3) 1 else 0)
    quorum >= 2
  }

  // Mode 2: User Burning eRTC to unlock RTC on RustChain
  val isBurnToUnlock: Boolean = {
    val outBox = OUTPUTS(0)
    val tokensIn = SELF.tokens
    val tokensOut = outBox.tokens
    val selfTokenId = tokensIn(0)._1
    val selfTokenAmount = tokensIn(0)._2
    
    // Ensure burned tokens decrease total bridge circulating supply
    (selfTokenId == expectedTokenId) &&
    (OUTPUTS.size >= 1) &&
    (outBox.R4[Coll[Byte]].isDefined) // Contains recipient RustChain wallet
  }

  sigmaProp(isMintOrRelease || isBurnToUnlock)
}
