# Share Why You Starred RustChain

**Bounty Pool: 300 RTC** — 3 RTC per accepted testimonial, plus a community shoutout.

We want to hear from the people who starred the repo. Tell us what made you
hit that button — the vintage-hardware angle, Proof of Antiquity, the
governance model, the miners, the memes, whatever it was.

## How to submit

1. Fork the repo and star it (if you haven't already).
2. Copy `TEMPLATE.json` in this directory to a new file named after your
   GitHub handle, e.g. `community/testimonials/your-github-handle.json`.
3. Fill in the fields (see below).
4. Open a pull request titled `[Testimonial] <your-github-handle>`.

Once merged, the `rtc-reward` workflow picks up new files under
`community/testimonials/` the same way it does for `community/machines/`
submissions, and 3 RTC is sent to the wallet address you provide.

## Fields

| Field | Description |
| --- | --- |
| `github_handle` | Your GitHub username. |
| `wallet` | RTC wallet address to receive the 3 RTC reward. |
| `starred_date` | Date (YYYY-MM-DD) you starred the repo. |
| `reason` | 1-3 sentences on why you starred RustChain. |
| `favorite_feature` | Optional. The feature/RIP that stood out to you. |

## Rules

- One submission per GitHub account.
- The GitHub account must have starred `Scottcjn/Rustchain` at the time of
  submission.
- Submissions are reviewed for authenticity before merge; spam or
  copy-pasted entries will be closed without reward.
- Accepted testimonials may be featured in the README or project docs as a
  community shoutout.
