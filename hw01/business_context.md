# Business Context Exploration

## Question 1 

### Question
“Wildcat’s borrower data includes credit score, debt-to-income ratio, and annual income, and borrowers in Default have noticeably lower average credit scores than borrowers with Current loans. How should a consumer lender use these three attributes together when evaluating credit risk, rather than relying too heavily on any one metric?”

### Response
"Credit score, debt-to-income ratio, and annual income each measure a different aspect of borrower risk, so they are most useful when considered together. Credit score reflects past repayment behavior, DTI measures current financial strain, and income shows a borrower’s overall capacity to repay. Using only one metric can be misleading because, for example, a borrower may have a strong credit score but still have an unusually high DTI. A combined risk model or scorecard can provide a more complete picture and help determine whether factors such as credit score still predict default after accounting for income and DTI."

### Follow Up Question
Which of these three variables would you expect to be the strongest predictor of default?

## Question 2

### Question 
"“Wildcat’s portfolio is concentrated in Home Improvement and Auto loans, while Business loans are less common but have much larger average loan balances. In a quarterly portfolio review, what would a lending committee typically want to monitor across Auto, Personal, Home Improvement, Education, and Business in order to identify concentration risk and changes in portfolio performance?”

### Response 
"portfolio committee typically looks at both concentration risk and performance trends across loan purposes. It is important to compare each category’s share of total loan count with its share of total dollar exposure, since a smaller category like Business loans can still represent a large portion of the portfolio’s risk because of larger balances. The committee would also monitor default, delinquency, and payoff rates over time, especially for signs that performance is worsening from quarter to quarter. In addition, borrower quality measures such as credit score, DTI, and income for new loans can help identify weakening underwriting standards before they show up in default rates. For Wildcat, this means paying close attention to Business loans even if Auto and Home Improvement make up more of the total loan count."

### Follow Up Question 
Why can dollar exposure be more important than loan count when evaluating concentration risk?

## Question 3 

### Question
"Wildcat classifies loans as Current, Paid Off, Delinquent, or Default, with substantially more Delinquent loans than Defaulted loans. What is the practical difference between delinquency and default in consumer lending, and how should Wildcat interpret movement between these four status categories when assessing the health of its loan portfolio?”

### Response 
"Delinquency means a borrower has missed payments, while default usually means the lender has determined that the loan is unlikely to be repaid under its original terms. In Wildcat’s data, the four statuses can be viewed as a progression: Current loans may become Delinquent, delinquent loans may either return to Current or move into Default, and Paid Off represents a successful exit. Because delinquency is an earlier warning sign, it is normal for there to be more delinquent loans than defaulted loans at a given time. A portfolio committee should therefore focus not only on the number of loans in each status, but also on how loans move between statuses over time, especially cure rates and movement from delinquency into default."

### Follow Up Question
Why is the delinquency rate often considered a leading indicator of future defaults?
