# Applied Data Science Practicum: Claims Analytics Syllabus

Oct 9, 2026

## Course overview

By the end of this course, each student will have one end-to-end data science project on insurance claims data that they can put on a resume and walk an interviewer through, from the business question all the way to a deployed and monitored model.

This is a small, hands-on practicum for 4 to 6 college students studying statistics or data science. It is built around the synthetic\_20k\_v2 claims dataset (20,000 synthetic auto and property claims), so students get realistic insurance data without any privacy concerns. Each week covers one stage of the data science process, and each stage produces one piece of the final project.

The plan assumes 10 weekly sessions of about 2 hours, plus 4 to 6 hours of student work outside of class. An 8-week and a 12-week version are in the timeline section in case the schedule turns out different.

## Learning objectives

Students who finish the course will be able to do the ten things below, which line up with what a hiring manager for an entry-level data science role will ask about.

1. Turn a vague business request into a clear analytics problem with a target, a success metric, and a decision the model supports.
2. Write SQL to pull, join, aggregate, and quality-check claims data.
3. Explore data to find patterns, data quality problems, and target leakage before modeling.
4. Build features using only information that would be known at the moment the model is used.
5. Train and compare a simple baseline against tree-based models (decision trees, random forests, gradient boosting) and choose metrics that fit the business problem.
6. Use NLP to turn claim text into features and models.
7. Explain model results with tools like SHAP and translate them into business impact.
8. Package a model so it can score new claims in a repeatable batch process.
9. Monitor a model for data drift and performance decay, and decide when it needs retraining.
10. Present technical work to both business and technical audiences, and tell the project story in an interview.

## Course format and tools

Each student builds their own project on a shared dataset, and pairs up with a classmate for weekly code review. Individual projects matter here because the goal is a resume project each student can speak to end to end, which is hard to do when one teammate did all the modeling. The code review pairs still give them practice working on a team.

Each 2-hour session follows the same rhythm:

- **Stand-up (15 min):** each student gives a 2-minute update on what they did, what they found, and where they are stuck. This gives everyone a presentation rep every single week.
- **Lesson (45 min):** one concept, taught with claims examples.
- **Lab (45 min):** hands-on work in their own repo, with the mentor walking around.
- **Wrap-up (15 min):** walk through the assignment and answer questions.

| Purpose | Tool | Why this one |
| --- | --- | --- |
| Language | Python 3.11+, pandas, scikit-learn | Industry default for data science |
| SQL | DuckDB | Runs SQL directly on CSV or Parquet files with no server to set up |
| Coding environment | VS Code with Jupyter notebooks | Free, and what most teams use |
| Version control | Git and GitHub | Each student's repo becomes their portfolio link |
| Tree-based models | scikit-learn, LightGBM or XGBoost | Gradient boosting is the workhorse for tabular data |
| Explainability | SHAP | Standard way to explain tree models to stakeholders |
| NLP | scikit-learn TF-IDF, sentence-transformers (optional) | Starts simple, with room to go further |
| Experiment tracking | MLflow | Logs runs, metrics, and model versions |
| Deployment demo | Batch scoring script, plus Streamlit or FastAPI | Shows both batch and on-demand scoring |
| Monitoring | Evidently or hand-built PSI checks | Makes drift visible without heavy setup |

## The dataset and project menu

Seven business questions fit synthetic\_20k\_v2, so each student can have their own. Total loss and fault are the best fits for this course because they use both tree-based models and text, and the attorney question suits a stronger student because the positive class is small.

The data follows how a modern claims system extract is laid out: 20,000 auto (85%) and property (15%) claims with loss dates from January 2024 to September 2026, an as-of date of October 7, 2026, and about 7% of claims still open. It comes as 13 related tables, including the claim header, exposures, financial transactions, activities, about 298,000 adjuster notes, vehicle incidents, attorney and lawsuit records, and a change log with the full edit history of each row. That gives the SQL week plenty of real joining without being overwhelming.

| Business question | Target from the data | Model type | Rows to model | Who uses it and why |
| --- | --- | --- | --- | --- |
| Will this vehicle be a total loss? | `total_loss` on the insured vehicle in `incidents.csv` | Classification | About 17,000 insured vehicles | Total loss team: moving total losses to salvage early cuts storage and rental costs |
| How much will this claim cost? | Sum of submitted payments in `money.csv` | Regression | Up to 20,000 claims, mostly closed | Reserving and actuarial: better early reserves |
| Which claims will become large losses? | Total paid in the top 5% or 10% | Classification | Up to 20,000 claims | Claims managers: route complex claims to senior adjusters early |
| Will this claim involve an injury? | Claim has a BI or PIP exposure (14.7% of claims) | Classification | 20,000 claims | Intake: send injury claims to the right team from day one |
| Will an injured party hire an attorney? | An attorney in `contact_roles.csv` on a BI exposure | Classification with imbalanced classes | About 1,540 BI claims, 789 represented exposures | Casualty managers: settle early, before representation raises costs |
| Who was at fault? | `insured_fault_pct` grouped as not at fault, shared, or at fault | Multi-class classification, heavy on NLP | 7,832 claims with a liability decision | Liability adjusters and recovery team: faster decisions and earlier subrogation referrals |
| How long will this claim stay open? | Days from report to close, with about 7% still open | Survival analysis | 20,000 claims | Claims operations: staffing and setting customer expectations |

Fraud or SIU referral is off the menu because the data has no fraud or SIU flag. Lawsuits (263) are too rare to model on their own, but they make a good stretch goal on the attorney project.

One rule applies to every project: the model scores claims **as of a fixed point**, usually first notice of loss, and may only use information known at that moment. This data makes the rule easy to teach and also easy to break:

- The change log records when every assignment, liability decision, payment, estimate and closing happened, so students can rebuild what each claim looked like on any date. That is the right way to build leakage-safe features.
- The adjuster notes are generated from templates that repeat the claim's amounts, fault percentage and dates. Any note written after the scoring point can give away the answer, so text features should use the loss description and only the notes written before the scoring point.
- `damage_severity`, `total_loss` and `damage_description` are filled in from the first version of the incident row, but in real life they come from the repair estimate. The change log will not catch this one, so treat them as unknown at first notice. Towed, drivable and airbags deployed are fair to use.

## Deliverables

Every week produces one piece of the final project, and by week 10 those pieces add up to a GitHub repo, a model card, and a presentation the student can show an employer.

| Week | Deliverable | What good looks like |
| --- | --- | --- |
| 1 | Problem statement (one page) | Names the decision, the user, the target, the success metric, and the scoring point |
| 2 | SQL notebook and data quality log | 10 or more queries that answer real business questions, plus a list of data issues found |
| 3 | EDA report | 5 findings with charts, each tied back to the business question |
| 4 | Feature table and feature dictionary | Every feature documented with its source and why it is safe from leakage |
| 5 | Model comparison | Baseline vs. tree models on the same time-based split, with the chosen metric explained |
| 6 | Text model and combined model | Shows whether the text adds value on top of the structured features |
| 7 | Model card and midpoint readout | 5-minute talk plus a one-page summary of what the model does, how well, and its limits |
| 8 | Batch scoring pipeline | One command scores new claims from raw data to predictions |
| 9 | Monitoring report | Drift and performance checks on a later time period, with a retraining recommendation |
| 10 | Final presentation, repo README, resume bullets | 15-minute talk, a clean README, and 2 to 3 resume bullets with numbers |

## Timeline at a glance

The course moves through five phases over 10 weeks, and each phase ends with a checkpoint students need to clear before moving on.

&#91;embedded content: course timeline · 5 phases, 4 checkpoints, 3 talks\]

Presentation practice runs the whole length of the course instead of being saved for the end, so by week 10 each student has given about a dozen short talks.

**8-week version:** combine weeks 3 and 4 (EDA and features) and weeks 8 and 9 (deployment and monitoring), and move the storytelling lesson into week 7.

**12-week version:** add an advanced modeling week after week 6 (large language models on claim notes, or survival models for claim duration) and a dry-run week before the finals where students present to an outside guest and revise.

## Week-by-week plan

Each week lists its goal, what to teach, what students do in the lab, and the assignment due before the next session.

### Week 1: Defining the business problem

**Goal:** students understand how a claim moves through an insurance company and turn a business request into a problem a model can solve.

- **Teach:** the claim lifecycle (first notice of loss, assignment, investigation, reserving, payments, settlement or litigation, closure, reopening); basic insurance terms (frequency, severity, loss ratio, reserves); how to frame a problem: decision, user, target, metric, and scoring point.
- **Lab:** set up Python, VS Code, Git, and a GitHub repo from a starter template. Each student picks a question from the project menu.
- **Assignment:** one-page problem statement.
- **Career tie-in:** most projects fail because the problem was framed wrong, not because the model was weak. Practice asking stakeholders "what will you do differently with this?"

### Week 2: Exploring the data with SQL

**Goal:** students can get answers out of the data with SQL and find data quality issues early.

- **Teach:** loading the 13 CSV files into DuckDB and joining them on the documented keys; SELECT, WHERE, GROUP BY, and left joins; CTEs; window functions (ROW\_NUMBER, LAG, running totals); the money rules (count only submitted payments, since every voided payment is followed by a replacement); data quality checks for duplicates, nulls, impossible dates, and negative payments. The synthetic data passes its own consistency checks, so give students a copy with a few planted problems to find.
- **Lab:** answer business questions in SQL, like claim counts and average paid by month and line of business, report lag, the share of payments voided, and salvage vs. subrogation recoveries.
- **Assignment:** SQL notebook with 10 or more queries and a data quality log.
- **Career tie-in:** SQL shows up in nearly every data job interview, and window functions are the usual separator.

### Week 3: Exploratory data analysis

**Goal:** students understand their target and their data well enough to avoid the common traps.

- **Teach:** distributions and skew (claim costs are heavily right-skewed); missing data patterns; relationships between features and the target; target leakage and how to spot it; why claims data needs a time-based train and test split instead of a random one.
- **Lab:** profile the target and top candidate features, then mark every field as known or not known at the scoring point.
- **Assignment:** EDA report with 5 findings, each with a chart and a "so what" for the business.
- **Career tie-in:** a good chart with one clear sentence beats ten charts with no point.

### Week 4: Feature engineering

**Goal:** students build a clean, leakage-safe feature table they can model on.

- **Teach:** date features (report lag, day of week, season, vehicle age); encoding categories (one-hot, target encoding and its risks); rebuilding each claim as it looked at the scoring point with the change log; handling missing values; scikit-learn pipelines so the same steps run in training and scoring.
- **Lab:** build the feature table in SQL or pandas and freeze the time periods, for example training on 2024 losses, validating on January to June 2025, testing on July to December 2025, and holding 2026 back for monitoring.
- **Assignment:** feature table and feature dictionary.
- **Career tie-in:** in industry, better features usually beat fancier models.

### Week 5: Tree-based models

**Goal:** students train, tune, and compare models and pick metrics that match the business problem.

- **Teach:** start with a logistic or linear regression baseline; decision trees and why they overfit; random forests; gradient boosting with LightGBM or XGBoost; cross-validation and hyperparameter tuning; metrics (ROC AUC, precision-recall AUC, lift, and calibration for classification; MAE and RMSE for regression); class imbalance; logging runs in MLflow.
- **Lab:** train all models on the same split and fill in a comparison table.
- **Assignment:** model comparison with a short write-up on which model to carry forward and why.
- **Career tie-in:** always compare to a simple baseline. If gradient boosting only beats logistic regression by a little, the simpler model may be the better choice.

### Week 6: NLP on claim text

**Goal:** students turn free text into useful signal and test whether it improves their model.

- **Teach:** text cleaning and tokenizing; bag of words and TF-IDF; a TF-IDF plus logistic regression text classifier; a quick look at embeddings and sentence-transformers; combining text features with structured features; where large language models fit and their risks (cost, consistency, privacy, explaining the output).
- **Lab:** build a text-only model on the loss description and notes written before the scoring point, then add text features to the week 5 model and compare. Because the notes come from templates, expect text to score higher than it would on real notes.
- **Assignment:** text model and combined model, with a note on whether the text was worth it.
- **Career tie-in:** a lot of business value is locked up in notes, emails, and documents. Knowing the simple methods first makes students better at judging when an LLM is actually needed.

### Week 7: Interpreting and evaluating the model

**Goal:** students can explain what their model does, how much it is worth, and where it falls short.

- **Teach:** SHAP values and partial dependence plots; error analysis (which claims does the model get wrong?); picking a threshold based on cost and capacity, for example "if adjusters can review 200 claims a week, which 200?"; translating lift into dollars or hours saved; fairness and regulation in insurance, including avoiding unfair discrimination and why companies keep model documentation; writing a model card.
- **Lab:** produce SHAP plots and a capacity-based threshold analysis.
- **Assignment:** model card draft and a 5-minute midpoint readout, presented in class with peer feedback.
- **Career tie-in:** being able to say "here is what this model can't do" builds trust faster than any accuracy number.

### Week 8: Deploying the model

**Goal:** students turn notebook code into something that can score new claims reliably.

- **Teach:** batch scoring vs. real-time scoring and why most claims models run in batch; moving code from notebooks into scripts and functions; saving and loading the pipeline; registering a model version in MLflow; environment files for reproducibility; a quick look at Docker and cloud platforms; simple tests (does the output have the right shape, are scores between 0 and 1?).
- **Lab:** build a score.py that takes raw claims and writes predictions. Optionally wrap it in a small Streamlit app or FastAPI endpoint.
- **Assignment:** working batch scoring pipeline that a classmate can run from the README.
- **Career tie-in:** a model nobody can run has no business value. Code that a teammate can run is a big step up from code that only runs on your laptop.

### Week 9: Monitoring the model and telling the story

**Goal:** students understand what happens after deployment and start building their final presentation.

- **Teach:** treat 2026 losses as production; data drift with the population stability index (PSI); performance drift; the delayed-label problem (claim outcomes can take months or years to be known, so you watch inputs and early proxies); retraining triggers; creating drift on purpose in a copy of the data, since a generator with fixed settings produces little on its own; what a monitoring dashboard should show. Second half: storytelling for presentations, including leading with the recommendation, one message per slide, and preparing for tough questions.
- **Lab:** run monitoring checks on the held-out period, then outline the final deck.
- **Assignment:** monitoring report and a full draft of the final deck. Do a dry run with the code review partner.
- **Career tie-in:** interviewers love asking "how would you know if your model stopped working?" Most new graduates have no answer.

### Week 10: Final presentations

**Goal:** students present their project with confidence and leave with a portfolio piece.

- **Format:** 15 minutes each to a mixed audience (ideally a business stakeholder plus a technical guest), plus 5 minutes of questions. Suggested structure: business problem, data, approach, results in business terms, deployment and monitoring plan, limitations, and next steps.
- **Wrap-up:** finish the repo README, write 2 to 3 resume bullets with numbers, and practice a 60-second version of the project for interviews.
- **Career tie-in:** the 60-second version is what they will use most, in interviews, at career fairs, and in networking conversations.

## Career topics worth weaving in

These are the skills that usually separate new hires who ramp up fast from those who struggle, and most are rarely taught in school. None needs its own session; each fits into 10 to 15 minutes of a week where it naturally comes up.

| Topic | Why it matters | Where it fits |
| --- | --- | --- |
| Asking good questions of stakeholders | Requirements are almost always vague at first | Week 1 |
| Domain knowledge | Knowing the business is what turns a modeler into a trusted partner | Week 1, then ongoing |
| Git, pull requests, and code review | Every team uses them, and few graduates are comfortable with them | Weekly code review pairs |
| Data quality and lineage | Real data is never clean, and knowing where a number came from saves days | Week 2 |
| Causal thinking and A/B testing | A model that predicts well does not prove an intervention will work | Week 7 |
| Translating results into dollars and hours | Leaders decide on business impact, not on AUC | Week 7 |
| Responsible modeling and regulation | Insurance models face real rules on fairness and documentation | Week 7 |
| Writing reproducible, testable code | Separates a notebook from something a team can rely on | Week 8 |
| Cloud and data platforms | Most jobs use Azure, AWS, Databricks, or Snowflake | Week 8, as an overview |
| Using AI coding assistants well | Speeds up work, but the output still needs checking and understanding | Any lab |
| Scoping and estimating work | Saying "I can have a first cut by Friday" and hitting it builds trust | Week 9 |
| Interview storytelling | Turning the project into a clear 60-second answer and STAR stories | Week 10 |
| Career paths | Data analyst, data scientist, ML engineer, analytics engineer, and actuarial roles differ a lot | Week 10, ideally with a guest panel |

Guest speakers make several of these land better than a lecture would. A claims adjuster or manager in week 1, an actuary in week 5 or 7, and an ML engineer in week 8 would each take only 20 to 30 minutes.
