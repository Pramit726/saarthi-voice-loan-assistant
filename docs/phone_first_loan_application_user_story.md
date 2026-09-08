# Saarthi: Doubt-Aware Phone-First Personal-Loan Pre-Application

**Document type:** User story and product scope  
**Target user:** Anita, a first-time or financially less-confident borrower  
**Primary setting:** An inbound phone conversation  
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
| Loan terms such as EMI, APR, fees, and take-home income are unfamiliar. | A borrower may not know what answer is being requested or may abandon the process. | Consumer financial-literacy research reports difficulty understanding financial products and terminology [1, 2]. |
| Long, sequential application journeys create friction. | Repeated fields and unclear next steps make completion harder, especially on a phone. | Digital-finance usability research identifies complexity and lack of understandable guidance as barriers to access [3]. |
| A borrower may need to ask a question while a field is active. | A rigid menu or form forces the user to leave the path, lose context, or wait for a separate support channel. | Voice-interface research treats turn-taking, repair, and clarification as central interaction problems [4]. |
| Amounts, fees, dates, and tenure must remain consistent after a correction. | An incorrect or stale summary can undermine trust and lead to an unintended decision. | Research on spoken information shows that speech rate and presentation affect comprehension of financial information [5]. |
| Users need control before any consequential action. | A borrower should be able to review, pause, correct, or stop without pressure. | Responsible-finance guidance emphasizes transparency, informed choice, and meaningful user control [6]. |

## 4. Why voice is necessary

Voice is central because the difficult moment is not simply entering a value. It is the natural exchange that follows an unexpected doubt:

> “What does that mean?” → explanation → “Okay, record this answer.”

Voice lets the borrower interrupt, clarify, correct, and resume without moving between a form and a separate help channel. It is useful for phone-first access, hands-busy situations, and users who find dense written forms difficult to navigate.

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
4. Saarthi confirms uncertain or important values and continues.
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

### Not included

- Loan approval, eligibility adjudication, underwriting, or credit scoring.
- Selection of a lender or recommendation of an amount or tenure.
- Binding submission, payment, mandate creation, or identity verification.
- Personal financial advice.
- Claims beyond the approved product information.

## 9. Meaning of success

The prototype succeeds when a reviewer can observe that:

- a borrower can answer normal questions without losing the draft;
- a contextual doubt receives a relevant, understandable answer;
- an interruption or correction does not cause an obsolete response to reappear;
- the conversation resumes at the correct point;
- important financial values remain consistent between speech and the written review;
- the borrower remains in control and no application is submitted automatically.

## 10. Demo preparation

Prepare a small synthetic product fact sheet and a fixed, reviewable draft. The demonstration should use a short path with a name, requested amount, tenure, income, and existing repayments. Include one unfamiliar term and one deliberate correction so that the defining interaction is visible within a few minutes.

The demo should show the user-facing result, not require the audience to understand internal implementation details. A trace or dashboard may be shown afterward as supporting evidence.

## 11. Demo acceptance test

### Test A: normal completion path

The borrower answers the questions for name, requested amount, tenure, monthly income, and existing repayments.

**Pass when:** Saarthi asks one clear question at a time, the answers appear in the draft, and the final spoken summary matches the written review.

### Test B: doubt and correction path

At the tenure question, the borrower says:

> “Stop. I meant eighteen months, not twelve. Also, what is the processing fee?”

**Pass when:**

- the twelve-month response stops rather than continuing over the user;
- Saarthi answers the processing-fee question in understandable language;
- only the tenure changes from twelve to eighteen months;
- the borrower is asked to review or confirm the changed value;
- the updated summary is consistent in speech and text;
- no obsolete twelve-month response or stale result appears afterward;
- no loan application, recommendation, or financial commitment is made.

### Final user-facing outcome

The audience should be able to see one compact story: a borrower leaves the expected answer path, resolves a doubt, corrects an earlier answer, and resumes the draft safely. That is the product being demonstrated.

## References

[1] Organisation for Economic Co-operation and Development, *OECD/INFE 2023 International Survey of Adult Financial Literacy*.  
[2] Consumer Financial Protection Bureau, consumer research on financial well-being and understanding financial products.  
[3] World Bank, *Global Findex Database 2021* and research on digital financial inclusion.  
[4] McTear, M., Calleijas, Z., and Griol, D., *The Conversational Interface*, Springer, 2016.  
[5] Research on synthesized speech intelligibility, speech rate, and persuasion in banking contexts.  
[6] Reserve Bank of India, digital lending and customer-protection guidance.
