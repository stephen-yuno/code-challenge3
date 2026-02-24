The Chargeback Avalanche: Build Verdant Goods' Dispute Prevention API
Scenario
Verdant Goods, a rapidly growing sustainable home products e-commerce platform operating across Brazil, Mexico, and Colombia, is hemorrhaging money. In the last 90 days, their chargeback rate has spiked from 0.4% to 2.8% — well above the 1% threshold where acquirers threaten to terminate merchant accounts. The client success team at Yuno has escalated this to engineering: Verdant Goods needs tooling to identify high-risk orders before they ship and analyze patterns in their dispute history to prevent future chargebacks.

The merchant's operations team currently has no systematic way to flag suspicious orders. By the time they receive a chargeback notification (sometimes 60-90 days after the original transaction), the product has already shipped, and they've lost both the merchandise and the payment. Even worse, excessive chargebacks result in penalty fees from their acquirer and jeopardize their ability to accept card payments entirely.

You've been tasked with building a backend service and API that can:

Accept transaction data and return a real-time risk assessment
Ingest their historical chargeback data and surface actionable insights about what patterns correlate with disputes
This is a high-priority client deliverable. Verdant Goods' CEO will be demoing your solution to their board next week to prove they're taking corrective action.

Domain Background
Before diving into the requirements, here are the key payments concepts you need to understand:

Chargeback
A chargeback (also called a "dispute") occurs when a cardholder contacts their bank to reverse a transaction. Common reasons include:

Fraud: "I didn't make this purchase" (the card was stolen or the cardholder is lying)
Product not received: Customer claims the item never arrived
Product not as described: Item was defective, wrong size, or misrepresented
Duplicate charge: Merchant accidentally charged the customer twice
Subscription cancellation disputes: Customer claims they canceled but was still charged
When a chargeback is filed, the merchant typically loses the transaction amount, pays a chargeback fee ($15-$100), and the product (if already shipped). High chargeback rates (>1%) can result in the merchant being placed in monitoring programs, facing higher processing fees, or even losing their ability to accept card payments.

Chargeback Rate
Calculated as: (number of chargebacks / number of transactions) × 100. Acquirers and card networks (Visa, Mastercard) closely monitor this metric. Rates above 0.9-1% trigger penalties.

Acquirer
The financial institution or payment processor that enables a merchant to accept card payments. The acquirer has a direct relationship with the card networks and bears some risk when merchants have excessive chargebacks. If a merchant's chargeback rate gets too high, the acquirer may terminate the relationship to protect themselves.

Authorization
The initial approval of a transaction. When a customer enters their card details and clicks "pay," an authorization request is sent to the card issuer (the customer's bank) asking: "Does this cardholder have enough funds/credit, and is this transaction legitimate?" The issuer responds with approve or decline.

Reason Code
A standardized code indicating why a chargeback was filed (e.g., "10.4 - Fraud - Card-Absent Environment" or "13.1 - Merchandise/Services Not Received"). Each card network has its own reason code taxonomy.

Dispute Evidence
Documentation a merchant can submit to fight a chargeback (e.g., tracking numbers, signed delivery confirmations, customer communication logs, proof of prior transactions with the same customer). Merchants have a limited time window (usually 7-14 days) to respond.

Functional Requirements
Build a backend service that solves Verdant Goods' chargeback crisis. Your solution should:

Requirement 1: Real-Time Risk Scoring API
Create an API endpoint that accepts transaction details and returns a chargeback risk score (0-100, where 100 = extremely high risk) along with specific risk factors detected.

The endpoint should analyze:

Velocity checks: How many transactions has this email/card/IP address made in the last 24 hours? Fraudsters often test stolen cards rapidly.
Geolocation mismatches: Does the customer's billing country differ from their IP geolocation or shipping country? (Cross-border fraud is common.)
High-risk product categories: Verdant Goods sells electronics, apparel, and home goods. Electronics have higher fraud rates.
Transaction amount anomalies: Is this purchase significantly larger than the customer's previous orders or the merchant's average order value?
New customer behavior: First-time customers with no purchase history present higher risk than repeat customers with clean records.
Email/domain patterns: Disposable email domains (e.g., temp-mail.org, guerrillamail.com) or emails with random character strings are red flags.
The API should return:

A numeric risk score
A risk level label (e.g., "LOW", "MEDIUM", "HIGH", "CRITICAL")
A list of detected risk factors with explanations (e.g., "Billing country (BR) differs from shipping country (CO)")
A recommended action (e.g., "Approve", "Manual Review", "Reject")
Acceptance Criteria:

The API can be called with transaction data and returns a structured response in <500ms
The risk scoring logic is deterministic and explainable (not a black-box ML model)
At least 5 distinct risk signals are evaluated
The response clearly indicates why a transaction is flagged
Requirement 2: Chargeback Pattern Analysis
Create an API endpoint or service method that ingests historical chargeback data and produces aggregate insights to help Verdant Goods understand what's driving their disputes.

The analysis should surface:

Chargeback rate by country: Which of their three markets (Brazil, Mexico, Colombia) has the highest dispute rate?
Chargeback rate by product category: Are electronics being disputed more than apparel or home goods?
Reason code distribution: What percentage of chargebacks are fraud vs. "item not received" vs. "not as described"?
Time-to-chargeback analysis: What's the average number of days between the transaction date and the chargeback filing date? (This helps Verdant Goods understand their dispute lag.)
Repeat offenders: Identify email addresses or card BINs (first 6 digits of a card number, identifying the issuing bank) with multiple chargebacks.
Acceptance Criteria:

The service can process a dataset of historical chargebacks and return structured insights
At least 5 different analysis dimensions are provided (country, category, reason code, timing, repeat patterns)
Results are aggregated and formatted in a way that a non-technical business user could understand (e.g., percentages, top-N lists, averages)
The analysis clearly highlights Verdant Goods' biggest problems (e.g., "68% of chargebacks are from Brazil" or "Electronics have a 4.2% chargeback rate vs. 0.8% for apparel")
Requirement 3 (Stretch Goal): Batch Risk Screening
Extend your solution to support bulk risk assessment. Verdant Goods wants to run their daily pending shipments (200-500 orders) through the risk engine each morning before they print shipping labels.

Create an endpoint or command that:

Accepts a batch of transactions (e.g., a JSON array or CSV upload)
Processes each transaction through the risk scoring logic
Returns a consolidated report showing which orders should be manually reviewed or rejected before shipping
This is a stretch goal — partial implementation is welcomed. For example, you might build the batch processing logic but skip advanced features like progress tracking or parallel processing.

Requirement 4 (Stretch Goal): Fraud Rule Configuration
Add a way for Verdant Goods to customize risk thresholds and rules without modifying code. For example:

"Flag any transaction over $500 from a first-time customer as HIGH risk"
"Auto-reject any transaction where billing and shipping countries differ AND the email domain is on the disposable list"
This could be implemented as:

A configuration file (JSON/YAML) that defines rules
An API endpoint to register/update rules
A simple rules engine that evaluates conditions
This is a stretch goal — partial implementation is welcomed. Even a basic rule configuration mechanism demonstrates architectural thinking.

Test Data
Your solution should work with realistic test data. You are expected to generate this data (use AI tools, scripts, or whatever method you prefer). Your test dataset should include:

For the Risk Scoring API:
At least 50 sample transactions with diverse characteristics:

Mix of countries: Brazil (BR), Mexico (MX), Colombia (CO)
Mix of product categories: electronics, apparel, home goods
Range of transaction amounts: $15 - $850 USD equivalent
Mix of customer types: first-time buyers, repeat customers (simulate by reusing email addresses)
Some obviously suspicious patterns:
Same email making 10+ transactions in 24 hours
Billing country ≠ shipping country
Very high transaction amounts for first-time customers
Disposable email domains
Some clearly legitimate patterns:
Repeat customer from same country, similar order values
Local transactions (billing, shipping, IP geo all match)
For the Chargeback Analysis:
At least 200 historical chargeback records with:

Transaction date and chargeback filed date (with realistic lags: 20-120 days)
Country, product category, transaction amount
Chargeback reason codes (invent a simple taxonomy like: FRAUD, NOT_RECEIVED, NOT_AS_DESCRIBED, DUPLICATE, OTHER)
Customer email and card BIN (6-digit number)
Ensure the data shows clear patterns (e.g., Brazil has higher fraud, electronics have higher not-as-described disputes, a few repeat offender emails)
Include a README section explaining how to load or seed your test data.

What Success Looks Like
A reviewer should be able to:

Start your service (with clear setup instructions in the README)
Call the risk scoring API with a sample transaction and receive a risk score with explanations
Trigger the chargeback analysis and see aggregate insights that clearly identify patterns
Understand your design decisions from your architecture documentation
(Stretch) Test the batch screening or rule configuration features if you implemented them
The solution should feel production-ready in its core functionality (requirements 1-2), even if stretch goals are only partially implemented.

Deliverables Summary
See the deliverables checklist for the exact artifacts you need to submit.

Deliverables
-
A working backend service exposing the risk scoring API (Requirement 1)
-
A working implementation of the chargeback pattern analysis feature (Requirement 2)
-
Test data files or generation scripts (transactions + chargebacks) as described in the Test Data section
-
A README with setup instructions, API documentation, architecture decisions, and notes on what you completed (including stretch goal status)
-
A short demo script or example API calls showing the solution in action (can be a shell script, Postman collection, or step-by-step commands in the README)
Evaluation Criteria
Risk Scoring API: Correctness and completeness — evaluates at least 5 risk signals, returns structured scores with explanations, handles edge cases
25pts
Chargeback Pattern Analysis: Depth and actionability — surfaces at least 5 insight dimensions, clearly highlights Verdant Goods' biggest problems, results are business-readable
25pts
Code quality and architecture: Well-organized, modular, follows backend best practices (separation of concerns, error handling, input validation), appropriate use of frameworks/libraries
20pts
Test data quality: Realistic, diverse, demonstrates both obvious and subtle risk patterns, sufficient volume for meaningful analysis
10pts
Documentation and demo: Clear README with setup steps, API usage examples, architecture explanation, and demo script that makes it easy for a reviewer to test the solution
10pts
Stretch goals and polish: Batch screening, rule configuration, additional insights, error handling, performance optimizations, or other creative enhancements beyond the core requirements
10pts
Total
100pts