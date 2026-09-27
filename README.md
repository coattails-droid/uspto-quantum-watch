# USPTO quantum watch

A daily check of newly **published** US patent applications and newly **granted** patents that are about quantum technology. When it finds some, it opens an issue here and assigns you. A mail summary follows.

This is the same process as [uspto-nanotech-watch](https://github.com/coattails-droid/uspto-nanotech-watch), aimed at quantum computing, quantum communication, and quantum sensing rather than nanomaterials.

## What it watches

- CPC `G06N 10`: quantum computing (circuits, qubit hardware, algorithms, error correction, quantum software).
- CPC `H04B 10/70`: photonic quantum communication.
- CPC `H04L 9/085`: quantum key distribution.
- Titles that say qubit, quantum computer, quantum gate, quantum annealing, quantum error correction, quantum key distribution, quantum sensor, or quantum communication.

It does not treat "post-quantum" classical cryptography, quantum dots, or quantum-efficiency chip patents as hits. Those dots still show up on the nanotech watch when they are in CPC `B82`.

The Patent Office does not publish most filings on the day they are filed. Utility applications usually appear about 18 months later. Provisionals are not published. Each run looks at the last 4 days of grants and publications.

## What runs

**Quantum class alerts** runs every day at 8:30am US Eastern Daylight Time (12:30 UTC). It needs no AI. It files one issue and assigns you. The email follows a minute or two later. After the clocks change in November, this same schedule is 7:30am Eastern until it is shifted.

The daily job reviews candidates itself. Copilot is not required. It keeps CPC `G06N 10`, `H04B 10/70`, and `H04L 9/085`, plus titles that name a qubit, quantum computer, quantum key distribution, quantum sensor, or quantum communication. Post-quantum cryptography and quantum-dot optics are set aside.

## The API key

USPTO requires a free API key, and GitHub does not share secrets between repositories. Paste the same `USPTO_API_KEY` you already use on uspto-nanotech-watch:

1. This repository, **Settings → Secrets and variables → Actions → New repository secret**.
2. Name it exactly `USPTO_API_KEY`.
3. **Actions → Quantum class alerts → Run workflow**.

Until that secret exists, the class-alert workflow files a single setup issue.

## Files

- [`.github/workflows/quantum-class-alerts.yml`](.github/workflows/quantum-class-alerts.yml) files the daily issue.
- [`.github/workflows/quantum-patent-watch.md`](.github/workflows/quantum-patent-watch.md) is the agent's instructions.
- [`.github/workflows/quantum-patent-watch.lock.yml`](.github/workflows/quantum-patent-watch.lock.yml) is the compiled Actions workflow. Regenerate it with `gh aw compile` after frontmatter changes.
- [`scripts/uspto_recent.py`](scripts/uspto_recent.py) fetches the candidate list.
