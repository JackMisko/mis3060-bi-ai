# Prompt Engineering Comparison

## Strategy 1 - Zero-Shot

### Prompt
"What are the most important metrics for measuring credit risk in a consumer loan portfolio?"
### First 150 Words
"Credit risk in a consumer loan portfolio is usually assessed through a handful of metric families that each answer a different question, and a mature risk framework leans on all of them together rather than any single number. The most direct family is loss and delinquency performance: the default rate, the delinquency rate (often broken into aging buckets like 30/60/90+ days past due), the cure rate (what share of delinquent loans return to current), and roll rates (the probability a loan in one status moves to a worse one over the next period). These are the closest thing to a direct read on realized and emerging credit losses, and tracking them over time — not just as a snapshot — is what reveals whether risk is stable, improving, or building. Net charge-off rate (losses actually written off, net of recoveries, as a percentage of outstanding balances) is the standard way"
### What did this strategy do well?
This strategy was quick and relatively efficient. The response isn't too bad for the shortened prompt. The main advantage of this strategy is a quick insertion of a prompt.

## Strategy 2 - Role-assigned 

### Prompt
“You are a senior credit risk analyst at a consumer lending company presenting to a quarterly portfolio review committee made up of lending executives and risk managers. Explain the most important metrics for measuring credit risk in a consumer loan portfolio, including what each metric reveals about portfolio health and why it matters for management decision-making.”
### First 150 Words
"The core idea I'd lead with is that no single metric tells you whether a consumer loan portfolio is healthy; you need a small set of metrics that answer different questions, because a portfolio can look fine on one and be deteriorating on another. I'd organize the presentation around four families.

The first is realized and emerging loss performance — default rate, delinquency rate broken into aging buckets (30/60/90+ days past due), cure rate (the share of delinquent loans that return to current), and net charge-off rate expressed as a percentage of outstanding balances rather than loan count. This family answers "what is happening right now." It matters to the committee because it's the most direct read on credit losses, but I'd caution that default rate alone is a lagging indicator — by the time a loan defaults, the damage is largely done. Delinquency and especially the cure rate are the earlier signal: a declining cure rate quarter over quarter"
### What did this strategy do well?
This strategy was more in depth then the previous, the answer that Claude gave was more intricat and detailed in laying out the thought process and way of answering this question. The downside was that it takes longer to create a prompt and scenario to create this detailed response.

## Strategy 3 - Few-Shot

### Prompt
"Example format:

Metric: Customer Churn Rate

What it measures: The percentage of customers who stop using a company’s service during a given period.

Why it matters: A rising churn rate can indicate declining customer satisfaction or competitive pressure.

How management uses it: Management can track churn over time and investigate which customer segments are leaving most often.


Now answer this question using the same format for each metric:
What are the most important metrics for measuring credit risk in a consumer loan portfolio?

Include the key metrics a lender would typically monitor, such as delinquency, default, charge-offs, borrower quality, concentration risk, and any other important measures."
### First 150 Words
"Metric: Delinquency Rate

What it measures: The percentage of loans in the portfolio that are past due on a scheduled payment, typically broken into aging buckets such as 30, 60, and 90+ days past due.

Why it matters: It's the earliest visible sign of borrower stress — loans don't go straight to default, they pass through delinquency first, so a rising delinquency rate (especially in the early buckets) often precedes a rise in default by a quarter or more.

How management uses it: Risk teams track delinquency by aging bucket and by segment to catch deterioration early, and use it to decide whether to tighten underwriting or adjust collections resourcing before losses actually materialize.

Metric: Default Rate

What it measures: The percentage of loans that have deteriorated to the point where the lender considers them unlikely to be repaid under original terms, typically after a sustained period of non-payment (often"
### What did this strategy do well?
This strategy can lay out some pieces of the puzzle, but it doesn't offer much insight of the big picture. It analyzes each metric individually without offering an analysis of the main question. 

## Conclusion
The zero-shot strategy was the fastest and easiest to use, but its response stayed fairly broad and did not tailor the answer to a specific business audience. The role-assigned strategy produced the most useful output for a BI analyst because it organized the metrics around management questions such as current losses, future risk, concentration, and profitability, which makes the analysis more actionable for decision-making. The few-shot strategy created the clearest and most consistent format, making individual metrics easy to understand and compare, but it focused more on each metric separately than on the overall portfolio picture. Overall, the role-assigned approach was strongest because it added business context and explained how the metrics would actually be used in a portfolio review.
