# RustChain Machine Census

A public page listing the physical machines that attest on RustChain (Proof of Antiquity), plus a list of machines whose owners had them verified by a maintainer.

- Live page: https://rustchain.org/census/
- Page: [`index.html`](index.html), a single static file with no build step and no external scripts, fonts or CDNs
- Verified list: [`machines.json`](machines.json), curated by maintainers
- Submission form: [`.github/ISSUE_TEMPLATE/census-submission.yml`](../.github/ISSUE_TEMPLATE/census-submission.yml)
- Tests: [`tests/test_census_page.py`](../tests/test_census_page.py)

**Listing is free and earns no RTC. The census is a preservation record.** Nothing here pays out, so nothing here is worth farming. Keep it that way: do not attach rewards to census listings.

## What the page shows

**Machines attesting now** comes from `GET /api/miners` on the same origin (the `{"miners": [...], "pagination": {...}}` envelope or a bare array). Each machine is grouped into one era:

| Era | Matches (family / arch / hardware type) |
|---|---|
| Vintage PowerPC | PowerPC, G3/G4/G5, IBM POWER |
| Retro x86 | `retro`/`vintage`, Pentium, 386/486, Core 2, Nehalem, K6, Athlon |
| Exotic | SPARC, MIPS, 68k, Amiga, classic ARM (ARM2-ARM11, StrongARM, XScale, Cortex-A8/A9) |
| Modern | everything else |

For each live machine the page shows **only** the device family and arch, hardware type, an era label, the antiquity multiplier, the day it first attested, and a coarse "seen" time. It never reads or shows the miner/wallet id, and the node does not send IPs to this endpoint. Rows are sorted by era label and multiplier rather than in API order. The data is already public through `/api/miners` and the explorer, so this is not a confidentiality boundary. The census simply doesn't add identifying detail.

These live entries are classified by the node from the hardware attestation. **No person has checked them.** An era with no machines says so plainly ("No G4/G5 machines attesting right now. Own one? Get it on the census."). If `/api/miners` fails, the page says the data is unavailable instead of showing zeros.

**Verified machines** are rendered from `machines.json`.

## Verifying a submission (maintainers)

Submissions arrive as issues with the `census` label (from the form above). Before adding one:

1. **Photo check.** One photo must show all three together: the machine, its serial plate, and a sheet of paper with `RTC CENSUS <github handle> <date>` handwritten.
   - The handle matches the issue author, and the date is within a few days of the issue date.
   - The handwriting is on real paper in the same scene, not pasted in. Check lighting, shadows and perspective.
   - Reverse-image search the photo. Stock photos, eBay listings and museum photos are rejections.
   - The model on the serial plate matches the claimed model and year.
2. **Dedup by serial.** Search earlier `census` issues and `machines.json` (`serial_last4` + `model`) for the same serial. One machine gets one entry; a machine that changes owners keeps its entry, with the new owner's name if they want it.
3. **It actually attests.** If the submitter gave a miner ID, confirm it appears in `/api/miners` and that the node's classification (family/arch) is consistent with the photo. A "G4" photo whose miner attests as `aarch64` is a rejection, or at least a conversation. Never copy the miner ID into `machines.json` or into a public comment beyond what the submitter already posted.
4. **ROM clustering for retro machines.** For 68k, PowerPC and Amiga machines, check the miner's ROM report against the known emulator ROM database and the clustering server ([`node/rom_fingerprint_db.py`](../node/rom_fingerprint_db.py), [`node/rom_clustering_server.py`](../node/rom_clustering_server.py)). A known-emulator ROM hash, or one shared by several "different" machines, means emulation. Reject it.
5. **Verified tier.** Steps 1 to 4 pass, so add the entry with `"tier": "verified"` and `"method": "photo"`.
6. **Gold tier.** Gold needs both of these:
   - the machine is **still attesting 60 days** after it was verified (check the miner, not the issue), and
   - an **in-person check**, for example at a vintage computer festival (VCF Midwest, VCF East, KansasFest), a club meetup or a partner museum. The maintainer or a named, trusted volunteer sees the machine running and the serial plate.

   Record it with `"tier": "gold"`, `"method": "in_person"` and `"event": "<event name and year>"`.

When rejecting, say why, kindly. Most failures are honest mistakes, like a missing serial plate in the photo.

## Adding an entry to `machines.json`

`machines.json` ships with an empty list. Add one object per machine:

```json
{
  "schema": 1,
  "machines": [
    {
      "model": "Power Mac G4 (Mirrored Drive Doors)",
      "year": 2002,
      "cpu": "Dual PowerPC G4 7455, 1.25 GHz",
      "photo": "https://github.com/user-attachments/assets/<id>",
      "photo_alt": "Silver Power Mac G4 tower on a workbench, side panel open",
      "display_name": "Example Owner",
      "running": "since March 2026",
      "story": "Rescued from a school surplus sale; new PRAM battery and capacitors.",
      "verified": "2026-10-08",
      "method": "photo",
      "event": "",
      "tier": "verified",
      "serial_last4": "AB12",
      "issue": 1234
    }
  ]
}
```

| Field | Required | Shown on page | Notes |
|---|---|---|---|
| `model` | yes | yes | Entries without a model are skipped. |
| `year` | no | yes | Number or string. |
| `cpu` | no | yes | |
| `photo` | no | yes | Must be an `https://` URL or `photos/<file>`. Anything else is ignored. Use a photo the owner is happy to have public; **crop out the handwritten code sheet and the serial plate** unless the owner asks otherwise. |
| `photo_alt` | no | as alt text | Describe the photo. If missing, the page uses "Photo of the <model>". |
| `display_name` | no | yes | **Opt-in only.** Blank, or anything the owner did not ask for, means "an anonymous owner". Do not default it to the GitHub handle. |
| `running` | no | yes | Free text from the form. |
| `story` | no | yes | Shortened to 600 characters. |
| `verified` | yes | yes | `YYYY-MM-DD`. |
| `method` | yes | yes | `photo`, shown as "photo + handwritten code", or `in_person`, shown as "in person at <event>". |
| `event` | for `in_person` | yes | For example `VCF Midwest 2026`. |
| `tier` | yes | as a badge | `verified` or `gold`. |
| `serial_last4` | no | no | For dedup only. Never store the full serial. |
| `issue` | no | no | The submission issue number, for maintainers. |

Every string is rendered as text (`textContent`), never as HTML, so markup in a field shows up as literal characters. Validate the file before committing: `python3 -m json.tool census/machines.json`.

## Privacy

- No wallets, miner IDs or IP addresses ever appear on the census page or in `machines.json`.
- Display names are opt-in. The default is anonymous.
- Submission issues are public. The form tells submitters this and lets them cover all but the last 4 characters of the serial.
- **Removal on request:** if an owner asks, either in an issue or by contacting a maintainer, remove their entry from `machines.json` and redeploy. Don't ask for a reason. If they want, also hide or close their submission issue.

## Deploying

The page is static. On node 1 it lives in `/var/www/rustchain-census/` and nginx serves it at `/census/` on the rustchain.org server block (`location ^~ /census/ { alias /var/www/rustchain-census/; }`). It uses `^~` so the static-asset regex locations don't capture `/census/*.png`, and it has no `add_header`, so the server's CSP and HSTS headers still apply. The page works within the existing CSP: inline script, same-origin `connect-src`, and `img-src https:` for photos.

To update only the verified list, copy the new `machines.json` to `/var/www/rustchain-census/machines.json`. No reload is needed.
