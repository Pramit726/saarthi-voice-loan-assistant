# Refined Technical Requirements for a Doubt-Aware Phone-First Personal-Loan Pre-Application

**Six consolidated requirements, evaluation criteria, and research scope**  
Research hackathon requirements draft | 3 September 2026

> **Central technical problem.** How can a phone-first conversational loan form recognize that a borrower has asked a contextual doubt or made a correction, preserve and safely update the structured application state while resolving that event from approved product facts, and resume the correct field without storing the off-path utterance as an answer?

## 1. Core research requirements

### TR-1: Intent understanding

**Technical requirement.** For every recognized user turn, the system shall determine whether the borrower is answering the pending field, asking a contextual doubt, correcting information, issuing a control command, combining multiple acts, or providing an ambiguous response. A non-answer shall not be committed as a field value.

**Meaning in this product.** When asked for income, the utterance *“Rs. 32,000, but does that include incentives?”* must be treated as an answer plus a doubt. The value remains provisional until the doubt is resolved and the borrower confirms what should be included.

**Acceptance evidence.** Measure per-class precision and recall, target-field accuracy, value-extraction accuracy, non-answer write rate, and appropriate clarification rate. Clear questions and control commands must never be stored as form values.

### TR-2: State manager

**Technical requirement.** The system shall maintain the active field and confirmed form values while a doubt, correction, interruption, or retry is handled. A correction shall modify only its intended field. After the event, the system shall resume the correct unfinished field, and obsolete results shall not modify the newer state.

**Meaning in this product.** If monthly income is pending and the borrower asks what take-home income means, the assistant temporarily answers that question and then returns to monthly income. If the borrower says *“Actually, make the tenure 18 months,”* only tenure changes before the income question resumes.

**Acceptance evidence.** Measure pending-field accuracy, exact-resumption accuracy, correction-target accuracy, unintended field-mutation rate, completed-field preservation, and stale-result re-entry.

### TR-3: Grounded contextual explanation - safety-critical

**Technical requirement.** Every product-specific statement about a loan term, fee, rate, amount, condition, or process shall be supported by a versioned approved fact record or a deterministic calculation. If support is absent or insufficient, the system shall state that it cannot confirm the answer rather than speculate.

**Meaning in this product.** When the borrower asks about a prepayment charge, the assistant answers from the approved fact sheet, explains only the available facts, or abstains. It must not import a fee or condition from general financial knowledge.

**Acceptance evidence.** Measure retrieval accuracy, supported-claim rate, factual accuracy, unsupported-claim rate, correct-abstention rate, and source-attribution coverage. Unsupported product facts are a zero-tolerance failure on the curated test set.

## 2. Voice proof and interaction reliability

### TR-4: Faithful controlled financial speech

**Technical requirement.** The system shall preserve the exact identity and relationship of requested amount, deductions, net disbursal, EMI, tenure, and total repayment when converting them into speech. The spoken explanation and written draft shall come from the same structured records and calculations.

**Meaning in this product.** A requested amount of Rs. 75,000, deductions of Rs. 2,655, and net disbursal of Rs. 72,345 must remain distinct. Rime should receive short, listener-oriented sentences with suitable grouping, pauses, and targeted repetition rather than one dense list of numbers.

**Acceptance evidence.** Measure exact number preservation, amount-label association, spoken-written agreement, pronunciation correctness, and intelligibility under the selected phone-audio condition.

Faster synthesized banking-product descriptions reduced comprehension for native and non-native listeners in a controlled study [1]. This supports testing pace and grouping, but does not prescribe one universal speaking rate.

### TR-5: User-control prioritization and cancellation - safety-critical

**Technical requirement.** Commands such as *stop*, *pause*, *repeat*, *go back*, and *send me the facts* shall take priority over field extraction at every stage. Stop or pause shall halt queued speech, cancel or fence pending work, and prevent obsolete output from later changing the conversation or form state.

**Meaning in this product.** If the borrower interrupts a cost summary to ask about the processing fee, the remaining summary audio stops, the pending summary is not replayed later, and the question is handled without losing the current state.

**Acceptance evidence.** Measure command-recognition success, stop latency, queued-audio cancellation, state preservation after barge-in, and stale-result re-entry. A control command must never be stored as a field answer.

## 3. Product safety boundary

### TR-6: Neutral and draft-only completion - safety-critical

**Technical requirement.** The assistant shall explain approved facts without recommending acceptance, creating urgency, concealing disadvantages, cross-selling, or optimizing for conversion. The prototype shall terminate only in a reviewable draft and written fact sheet, without capabilities for real submission, approval, signature, KYC, mandate creation, or disbursal.

**Meaning in this product.** The borrower may continue, pause, ask questions, request the written facts, or decline with equal ease. The assistant never describes an offer as good for the borrower or suggests that acceptance is urgent.

**Acceptance evidence.** A scenario suite checks for recommendations, pressure, urgency, cost omission, asymmetric treatment of decline, unauthorized submission, and use of sensitive data. Any explicit pressure, hidden cost, or real transaction is a release-blocking failure.

#### Hard safety invariants

- No unsupported loan fact and no silent alteration of a confirmed value.
- No real application submission, mandate, signature, approval, or disbursal.
- Stop and pause override field collection, generation, and playback.
- No recommendation, urgency, hidden cost, cross-selling, or conversion objective.
- Spoken facts, calculations, and the written draft remain mutually consistent.

The written fact sheet remains authoritative. RBI's Key Facts Statement requirements call for key loan facts in language understood by the borrower, including APR and the amortisation schedule, before contract execution [2]. Voice supports comprehension but does not replace formal disclosure.

## 4. Compact evaluation plan

| ID | Primary measurements | Minimum fixture families |
|---|---|---|
| TR-1 | Per-class precision and recall, target-field accuracy, non-answer write rate | Answers, doubts, corrections, controls, mixed and ambiguous turns |
| TR-2 | Pending-field and exact-resumption accuracy, unintended mutation and stale-result rates | Doubts and corrections at every field, including repeated interruptions |
| TR-3 | Supported-claim rate, factual accuracy, abstention quality, attribution coverage | Answerable, partially supported, conflicting, and absent facts |
| TR-4 | Number preservation, amount-label association, written-audio agreement, intelligibility | Amounts, fees, GST, EMI, tenure, percentages, dates, and similar values |
| TR-5 | Command success, stop latency, audio cancellation, state preservation | Commands during listening, reasoning, synthesis, and playback |
| TR-6 | Pressure, urgency, omission, recommendation, submission, and privacy violations | Acceptance, hesitation, decline, repeated questions, and adversarial prompts |

The first evaluation set can be synthetic and deterministic. Each conversation trace should define the expected turn type, target field, state before and after the turn, allowed facts, spoken values, and terminal action. Numerical success thresholds should be selected after credible baselines have been implemented and measured.

> **Definition of technical success.** A borrower can leave the expected answer path to ask a question or make a correction; the assistant understands the event, preserves the form, answers only from approved facts, and resumes or revises the intended field. Financial values remain clear and consistent, and the borrower can stop or decline without pressure.

## References

1. Caroline Jones, Lynn Berry, and Catherine J. Stevens. *Synthesized Speech Intelligibility and Persuasion: Speech Rate and Non-Native Listeners.* Computer Speech & Language, 21(4):641-651, 2007. [doi:10.1016/j.csl.2007.03.001](https://doi.org/10.1016/j.csl.2007.03.001).
2. Reserve Bank of India. *Key Facts Statement (KFS) for Loans & Advances.* RBI/2024-25/18, DOR.STR.REC.13/13.03.00/2024-25, 15 April 2024. [rbi.org.in](https://www.rbi.org.in/).

