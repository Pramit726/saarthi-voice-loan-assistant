# Saarthi: Doubt-Aware Phone-First Personal-Loan Pre-Application

**Document type:** User story and product scope  
**Target user:** Anita, a first-time or financially less-confident borrower  
**Primary setting:** A phone-first voice journey demonstrated through the browser; production PSTN telephony is outside scope
**Primary experience:** Voice-first guidance with a written review alongside it

## 1. Overview

Saarthi helps a borrower complete a safe, reviewable personal-loan pre-application by voice. It asks one question at a time, explains unfamiliar terms when asked, and returns to the correct unfinished question after a doubt or correction.

The focused user-problem pair is:

> We want to improve independent completion of a personal-loan pre-application for borrowers who need clarification when unfamiliar financial terms and a long sequence of questions create doubts.

This is a **draft-only pre-application**. Saarthi does not approve a loan, recommend borrowing, choose a lender, submit an application, or make an eligibility decision.

## 2. User story

Anita wants to understand a personal-loan product and prepare her information without navigating a rigid form or waiting for a human agent. While answering a question, she may ask what a term means, request a calculation, correct an earlier answer, or ask to repeat the question.

Saarthi should let her do this naturally and should preserve the draft while she does it. After resolving the doubt, it should continue from the exact question that was unfinished rather than restarting, skipping a field, or silently changing unrelated information.

### 2.1 A contextual doubt

Saarthi asks: “What is your monthly income?”

Anita asks: “What does take-home income mean?”

Saarthi explains the term in plain language, using only the approved product information. It then asks for the monthly income again and records the answer only after Anita confirms it.

### 2.2 An interruption and correction

Near the end of the conversation, Anita says: “Stop. I meant eighteen months, not twelve. Also, what is the processing fee?”

The expected experience is observable:

1. The current spoken response stops promptly.
2. The processing-fee doubt is answered clearly.
3. Only the intended tenure is changed.
4. The updated eighteen-month summary is shown and spoken for review.
5. The old twelve-month response does not return later.
6. Anita can review the written draft before deciding what to do next.

## 3. User pain and supporting evidence

| Pain point | Why it matters to the user | Evidence |
|---|---|---|
| Loan costs and terms can be misunderstood. | A borrower may not understand interest rates, processing fees, APR, repayment consequences, or collection practices. | An India-focused Dvara Research-CGAP convening reported these information gaps, especially for new-to-credit customers [1]. |
| Long and complex disclosures receive limited attention. | A borrower may miss an important cost even when it appears in a multipage contract. | CGAP documented complex terms, incomplete cost disclosure, and experiments showing that the presentation of costs and key facts affects attention and borrowing decisions [2]. |
| Discovering fees late can cause abandonment. | Unexpected processing fees, prepayment penalties, or bundled products can undermine trust during the journey. | A commercial survey of 3,614 personal-loan borrowers across six Indian cities reported that fewer than 41% felt fully informed before signing; among mid-journey abandoners, 54% cited discovery of these costs or bundled products as the principal trigger [3]. |
| A realistic loan journey contains several linked concepts. | Amount, tenure, rate, EMI, interest, fees, disbursal, and total cost must remain understandable and consistent. | TVS Credit's published application process and Saathi product journey provide a realistic scope and vocabulary reference, not evidence of TVS-specific failure rates [4, 5]. |
| Phone remains a meaningful borrowing channel. | Some borrowers begin the journey through a call and need support within that channel. | Home Credit India's lender-run survey of approximately 1,842 borrowers across 17 Indian cities reported that 19% initiated borrowing through telecalling in 2023 [6]. |
| Spoken delivery can affect financial comprehension. | Dense or fast delivery can make linked amounts and conditions difficult to follow. | In a controlled study of 160 listeners hearing synthesized banking-product descriptions, faster speech reduced comprehension for native and non-native English listeners [7]. |

**Evidence boundary.** These sources establish loan-term complexity, cost confusion, fee-related abandonment, a meaningful minority phone channel, and an effect of speech rate on banking-message comprehension. They do not establish how often borrowers interrupt a phone pre-application with a field-level doubt or prove that Saarthi reduces real-world abandonment. Those remain focused product hypotheses to be evaluated.

## 4. Why voice is necessary

Voice is central because the difficult moment is not simply entering a value. It is the natural exchange that follows an unexpected doubt:

> “What does that mean?” → explanation → “Okay, record this answer.”

Voice lets the borrower interrupt, clarify, correct, and resume without moving between a form and a separate help channel. It is useful for the selected phone-first situation, which is supported as a meaningful minority channel by the Home Credit India survey [6].

Spoken delivery itself must still be tested. Jones, Berry, and Stevens found lower comprehension at the faster tested speaking rate for native and non-native listeners hearing synthesized banking-product descriptions [7]. This supports deliberate pacing, pauses, number grouping, and targeted repetition, but does not prescribe one universal speaking rate.

The removal test is decisive: if speech is removed, the product becomes an ordinary sequential form with a help button. The defining interaction—interrupting a question, resolving a doubt, and resuming the same draft—largely disappears. Therefore voice is not decoration; it is the product’s primary interaction medium.

## 5. What Saarthi provides

| Conventional form or rigid phone menu | Saarthi experience |
|---|---|
| Presents a fixed sequence of fields. | Asks one clear question at a time. |
| Treats a doubt as an off-topic detour. | Allows a contextual question at the moment it arises. |
| Makes correction cumbersome. | Lets the borrower correct the current or an earlier answer. |
| May leave the user unsure what was recorded. | Reads back important values and shows a written draft for review. |
| Pushes the user toward completion. | Remains neutral and draft-only; the borrower controls the next step. |

## 6. End-to-end user journey

The bounded journey is:

**Start by phone → answer one question → ask a doubt or make a correction → receive a plain-language explanation → resume the same question → review the draft → stop or continue by choice.**

The visual overview is available as [Figure 1: Doubt-aware voice-agent workflow](figure1_doubt_aware_voice_agent_workflow_300dpi.pdf).

## 7. Product experience flow

### Normal path

1. Saarthi welcomes the borrower and explains that it is preparing a reviewable draft.
2. It asks for one item at a time.
3. The borrower answers in ordinary language.
4. Saarthi normalizes bounded natural descriptions, confirms inferred or fuzzy matches, and continues.
5. The borrower can review the accumulated draft at any time.

### Doubt or correction path

1. The borrower interrupts with a question, correction, repeat request, or request to go back.
2. Saarthi acknowledges the request and keeps the current draft safe.
3. It answers a product question in plain language or applies the requested correction after confirmation.
4. It returns to the unfinished question or the appropriate earlier item.
5. It presents the updated draft so the borrower can check what changed.

## 8. Product scope

### Included

- Phone-first, one-question-at-a-time personal-loan pre-application guidance.
- Plain-language explanations of approved product terms.
- Questions, doubts, corrections, repeat, pause, stop, and resume.
- Reviewable written draft and spoken summary.
- Neutral guidance with no recommendation or pressure.
- A clear handoff or support path when the user is not satisfied.
- Bounded natural-language handling for employment type and loan purpose, plus conservative Indian-city validation.

### Not included

- Loan approval, eligibility adjudication, underwriting, or credit scoring.
- Selection of a lender or recommendation of an amount or tenure.
- Binding submission, payment, mandate creation, or identity verification.
- Personal financial advice.
- Claims beyond the approved product information.
- Hindi, multilingual, or code-switched voice output.
- Production PSTN telephony, lender submission, or external geocoding.

RBI's Key Facts Statement circular requires key loan facts to be presented in simple language understood by the borrower, including APR and the amortisation schedule, and explained before contract execution [8]. Saarthi's voice interaction therefore supports comprehension but does not replace the authoritative written disclosure.

## 9. Meaning of success

The prototype succeeds when a reviewer can observe that:

- a borrower can answer normal questions without losing the draft;
- a contextual doubt receives a relevant, understandable answer;
- an interruption or correction does not cause an obsolete response to reappear;
- the conversation resumes at the correct point;
- important financial values remain consistent between speech and the written review;
- the borrower remains in control and no application is submitted automatically.

## 10. Demo preparation

Use a small synthetic product fact sheet and a reviewable draft. The demonstration should include:

- one normal answer path;
- one unfamiliar term or product-cost doubt; and
- one correction or interruption that changes an earlier answer.

The audience should be able to follow the borrower’s experience without needing to understand the implementation. Detailed test fixtures and measurement procedures are maintained separately in [`TEST_PLAN.md`](TEST_PLAN.md).

## 11. Demo acceptance test

At the tenure question, the borrower says:

> “Stop. I meant eighteen months, not twelve. Also, what is the processing fee?”

The demonstration passes when the audience can observe that:

- the current speech stops promptly;
- the processing-fee question receives an understandable answer;
- only the tenure changes from twelve to eighteen months;
- the conversation resumes or presents the correct updated review;
- the spoken summary matches the written draft;
- the obsolete twelve-month response does not return; and
- no application is submitted or borrowing decision is recommended.

The normal completion path and detailed acceptance scenarios are documented in [`TEST_PLAN.md`](TEST_PLAN.md).

### Final user-facing outcome

The audience should be able to see one compact story: a borrower leaves the expected answer path, resolves a doubt, corrects an earlier answer, and resumes the draft safely. That is the product being demonstrated.

## References

[1] Amulya Neelam, Eric Duflos, Jayshree Venkatesan, and Sarah Stanley. *A Convening on Emerging Customer Risks in Digital Lending in India.* Dvara Research Foundation and Consultative Group to Assist the Poor, August 2021. dvararesearch.com.

[2] Rafe Mazer and Kate McKee. *Consumer Protection in Digital Credit.* CGAP Focus Note No. 108, August 2017. cgap.org.

[3] Ayush Mathur. *The Transparency Gap: How Personal Loan Decision Journeys Are Exposing India's Lending Trust Deficit.* Ken Research, 8 June 2026. kenresearch.com.

[4] TVS Credit Services Limited. *Personal Loan Application Process.* Accessed 2 September 2026. tvscredit.com.

[5] TVS Credit Services Limited. *TVS Credit Saathi* official Google Play listing. Accessed 2 September 2026. play.google.com.

[6] Home Credit India. *How India Borrows Survey 2023.* Survey of approximately 1,842 borrowers across 17 Indian cities, 2023. homecredit.co.in.

[7] Caroline Jones, Lynn Berry, and Catherine J. Stevens. *Synthesized Speech Intelligibility and Persuasion: Speech Rate and Non-Native Listeners.* Computer Speech & Language, 21(4):641-651, 2007. [doi:10.1016/j.csl.2007.03.001](https://doi.org/10.1016/j.csl.2007.03.001).

[8] Reserve Bank of India. *Key Facts Statement (KFS) for Loans & Advances.* RBI/2024-25/18, DOR.STR.REC.13/13.03.00/2024-25, 15 April 2024. rbi.org.in.
