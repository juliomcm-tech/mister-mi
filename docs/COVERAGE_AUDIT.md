# Public source coverage audit — 19 November 2026

The original collector read only rendered `.grd.tip` rows. OLBG's public
Svelte page data already contains more tips than its first display. Reading the
same response's literal `data:{tips:[...]}` recovers those rows without another
request, authentication, or an unofficial data endpoint.

Snapshot collected from the five configured public sport pages on 2026-11-19,
then compared with the same saved responses and a 15:46 UTC evaluation time:

| Sport | Initial display rows | Public underlying rows | Normalized before | Normalized after | Today's normalized before/after |
| --- | ---: | ---: | ---: | ---: | ---: |
| Football | 20 | 100 | 20 | 99 | 2 / 2 |
| Tennis | 7 | 11 | 5 | 5 | 4 / 4 |
| Basketball | 18 | 32 | 18 | 18 | 10 / 10 |
| Ice hockey | 20 | 38 | 20 | 26 | 11 / 11 |
| American football | 20 | 21 | 20 | 21 | 0 / 0 |
| **Total** | **85** | **202** | **83** | **169** | **27 / 27** |

The extra raw rows for today's date are expired: basketball 14, hockey 3,
and tennis 2. They cannot become current opportunities. Four tennis records
are expired across all dates. Overall, 21 expired rows and 12 unsupported
market rows are excluded before model qualification, leaving 169 normalized
records. The unchanged current-day qualification result is **one** OLBG signal
and **zero** independently confirmed selections. This change improves collection
coverage; it does not establish that more suitable games exist today.

The single qualified OLBG signal in this snapshot is Alexander Zverev versus
Arthur Fils, 19:30 UTC, with 19/21 winner tips. This is a dated audit observation,
not a current recommendation, calibrated probability, or independently confirmed
prediction. No production success rate can be inferred from these counts.

## Public pagination evidence

The page's visibly available **Load More Tips** button is implemented by the
public Svelte route asset `/_app/immutable/nodes/110.DvpO6Iv4.js`. Its handler
increases the visible slice by `tipsListOtherPagesLimit`, bounded by the existing
array's length. It does not fetch the next results page. The same component
uses `tip.expired` to separate active and expired events. The collector now reads
the complete array supplied to that button and honors the explicit expiry flag.

No explicit today-only URL or calendar query was exposed in the inspected
sport-page links or forms. Public league links are available and could provide
additional coverage in a later bounded expansion. Neither the initial display
nor the expanded array demonstrates coverage of every daily fixture worldwide.
An all-sports overview response was also inspected: 84 underlying versus 22
display rows, with many unsupported sports and overlapping events. It was not
added as an independent source.

## Parser safeguards and validation

- Only inline Svelte page data with the observed `data:{tips:[...]}` structure
  is read. The parser accepts JSON values plus bare object keys, handles escaped
  strings, and never executes JavaScript. Unsupported expressions or malformed
  payloads fall back to rendered HTML. Payload size and row count are bounded.
- Event links must use HTTPS and the exact `www.olbg.com` host and a supported
  sport path. Kickoff epochs and integer vote counts are required and validated.
  `confidence` is not substituted for the observed vote ratio. Tennis rows with
  a null league remain usable.
- HTML and underlying records are deduplicated by event, kickoff, market,
  selection, segment and country. Votes are never summed. Expired, cancelled,
  or postponed public records invalidate matching rendered rows, including
  when the cancelled record has incomplete voting data.
- Raw counts include the underlying rows before filtering and any genuinely
  additional rendered rows. The initial display is not counted a second time.
- Current Lisbon date, kickoff guard, source thresholds, and independent-source
  requirements remain in the analysis layer and were not relaxed.

Validation: 57 Python tests passed, including 16 OLBG coverage regressions covering
hidden rows, deduplication, explicit cancellation, unsafe literals, malformed
votes/dates/hosts, market scope, null tennis leagues and Lisbon midnight.

This audit used only allowed public OLBG pages and their linked static assets.
It did not retry blocked prediction sites through another network or access path.
