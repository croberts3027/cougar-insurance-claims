# Insurance Claims Primer for the Synthetic Claims Data

Nov 23, 2026

This guide gives you the business background you need before you open the data. You do **not** need to know anything about insurance. By the end you should be able to explain, in plain words, what each number in the synthetic claims data represents and why it exists.

**Who it is for.** College students who will analyze the synthetic claims data (20,000 fake auto and homeowner insurance claims, 2024 to October 2026) for a class project.

**What you will be able to do after reading it**

- Explain what a claim is, and how one moves from "something bad happened" to a closed file.
- Read every table and column in business terms: who did what, when, and why that row exists.
- Tell reserves, payments, expenses and recoveries apart, and add them up correctly.
- Compute the standard claims metrics (severity, cycle time, litigation rate and more) and know what "normal" looks like in this data.
- Avoid the common traps that make claims analyses wrong.
- Know which parts of the data are realistic and which are simplified or invented.

**How it fits with the data dictionary.** This guide explains the *business*. The companion [Synthetic Claims Database: Data Dictionary](data-dictionary.md) explains the *tables*: every column, its type, how often it is empty, and how tables join. Read this guide first, keep the dictionary open while you query. Names in `table.column` form (for example `money.subtype`) point to the dictionary.

**Suggested reading order**

1. Sections 1 to 3: what insurance is, who is involved, what a policy covers.
2. Section 4: the claim lifecycle. This is the spine of the whole data set.
3. Sections 5 to 8: money, fault and injuries, recoveries, how a claims department works.
4. Sections 9 to 11: reading the numbers, traps, and what is synthetic. Read these before you start your analysis.
5. Section 12 (practice questions) and section 13 (glossary) for reference.

**About the numbers quoted here.** Every figure comes from the 20,000-claim data set as it stood at its "as-of" moment, **2026-10-07 12:00**. They describe *this synthetic data*, not the insurance industry. Where something is a real-world rule rather than a feature of the data, the text says so.

## 1. Insurance in five minutes

### 1.1 The basic idea: sharing risk

Most people will never have a house fire, but a few will, and the loss could ruin them. Insurance lets a large group of people each pay a small, certain amount so that the few who suffer a big loss are paid back. The company running the pool is the **insurer**. The money each person pays is the **premium**. The contract between them is the **policy**. The person buying it is the **policyholder** (also called the **insured**).

This works because of the *law of large numbers*: for one person a fire is unpredictable, but across 100,000 homes the number of fires in a year is quite predictable. The insurer's job is to estimate that, charge enough premium to pay the losses and its own costs, and keep its promises when losses happen.

### 1.2 The vocabulary of a policy

| Term | What it means | Everyday analogy |
| --- | --- | --- |
| **Policy** | The contract that says what is covered, for how long, and up to how much. | A warranty contract |
| **Premium** | The price of the policy (for example paid every six months). | The warranty's price |
| **Peril** | A cause of loss the policy covers (fire, hail, collision, theft). | The things the warranty covers |
| **Coverage** | A specific protection within the policy (collision, rental car, dwelling...). | One line in the contract |
| **Limit** | The most the insurer will pay under a coverage. | A cap on the warranty |
| **Deductible** | The first part of a loss you pay yourself. | A co-pay |
| **Exclusion** | Something the policy says it will not cover. | Fine print |
| **Claim** | A request to the insurer to pay for a loss under the policy. | Filing a warranty claim |

This data covers only the **claims** side. There are no policies or premiums in it (section 11 explains why that matters).

### 1.3 Where the money goes

Think of the insurer as a business with money coming in and going out:

- **In:** premiums, plus investment income on money held until claims are paid.
- **Out:** **losses** (the money paid to or for people with claims), **loss adjustment expense** (the cost of handling and defending claims: adjusters, inspections, lawyers) and **operating expenses** (sales, pricing, salaries, buildings).

Two ratios summarize how a book of business is doing. They are not computable from this data (no premium), but they explain why claims numbers matter:

| Ratio | Formula | Example |
| --- | --- | --- |
| **Loss ratio** | losses (plus claim handling cost) ÷ premium earned | $780,000 of claim costs on $1,200,000 of premium = 65% |
| **Combined ratio** | loss ratio + expense ratio (operating expenses ÷ premium) | 65% + 30% = 95%. Under 100% means an underwriting profit |

Every dollar in the `money` table is a piece of the numerator of a loss ratio.

### 1.4 Frequency and severity

Actuaries (the insurer's statisticians) break expected loss into two parts:

- **Frequency:** how often claims happen (for example 6 claims per 100 cars per year).
- **Severity:** how much a claim costs on average (for example $5,000).

**Expected loss per policy = frequency × severity** (6% × $5,000 = $300 per car per year). This is the starting point for setting the price. When you analyze the claims data you are mostly studying severity, cycle time and how claims are handled, because there are no policy counts to compute true frequency.

### 1.5 Where claims fit in the company

| Department | What it does |
| --- | --- |
| **Underwriting** | Decides who to insure and on what terms. |
| **Actuarial** | Prices policies and estimates how much money to hold for unpaid claims (reserves). |
| **Claims** | Investigates losses, decides what is owed, and pays. *This is where your data comes from.* |
| **Legal / Special investigations** | Defends lawsuits; investigates suspected fraud. |
| **Finance** | Records premiums, claim payments and reserves in the company's books. |

Claims is called the "moment of truth": it is where the promise sold as insurance is either kept or broken, so how fast and how fairly claims are handled matters to customers and regulators.

### 1.6 Personal lines: the two kinds of insurance in this data

Insurance for individuals and families is called **personal lines**. This data has two:

- **Personal auto** (`header.lob = 'auto'`, 16,992 claims, 85%): covers the policyholder's car and the harm they cause to others while driving.
- **Homeowners / property** (`header.lob = 'pr'`, 3,008 claims, 15%): covers the house, belongings, and the harm the owner causes to others on their property.

(Insurance for businesses is **commercial lines** and works similarly with bigger numbers. It is not in this data.)

## 2. The cast: everyone involved in a claim

A claim is a small drama with many actors. Knowing who is who tells you what a name, title or department column in the data means.

### 2.1 Customers and outsiders

| Role | Who they are | Where they show up in the data |
| --- | --- | --- |
| **Policyholder / insured** | The customer who bought the policy. | The "insured" vehicle (`vehicles.role = 'insured'`) and `exposures."LossPartyName" = "Insured's loss"` |
| **Claimant** | A person making a claim *against* the policyholder's policy because the policyholder hurt them or damaged their property. | `"LossPartyName" = 'Third-party liability'`; the "third party" vehicle (`role = 'third_party'`) |
| **Plaintiff attorney** | A lawyer hired by an injured claimant to negotiate with the insurer or sue. | `contact_roles` (`role = 'plaintiff_attorney'`, `firm`) |
| **Repair shop / body shop** | Gives the repair estimate and fixes the car. Named in note text (for example "Beehive Collision"). | `incidents.est_repair_cost`; `notes.body` |
| **Medical provider** | Treats injured people and sends the bills (clinics, physical therapy, imaging). | Injury activities such as `new_bill`; note text |
| **Police** | Writes the accident report used to decide fault. | The `police_report` activity |
| **Other driver's insurer** | Pays back part of the loss when its customer caused the accident. | Recoveries with `recovery_category = 'subrogation'` |
| **Salvage buyer** | Buys the wreck of a total-loss car. | Recoveries with `recovery_category = 'salvage'` |
| **Contractor** | Repairs a damaged house. | Property notes |
| **Court** | Where lawsuits are filed. | `matters.court` (always "Third District Court") |

Repair shops, providers, firms, agencies and contractors are fictional. Only the court and the cities are real Utah names.

### 2.2 The insurer's people

Every person in the data is in `users` (90 people, all fictional). Their `title` tells you what they do:

| Title (`users.title`) | What the job is | People |
| --- | --- | --- |
| **Claims Intake Specialist** | Takes the first phone call (the first notice of loss) and opens the claim. Writes the first note. | 5 |
| **Claims Adjuster** | The main role: investigates car claims, decides what is owed, negotiates repair costs, pays. | 16 |
| **Claims Assistant** | Handles simple, routine work such as towing and roadside claims. | 4 |
| **PIP Claim Assistant** | Processes the injury medical bills for no-fault (PIP) coverage. | 4 |
| **Specialty Adjuster** | Handles specialized auto cases, here the total-loss team. | 4 |
| **Casualty Claims Adjuster** | Handles bodily injury claims (injuries to other people). "Casualty" is the insurance word for liability-to-people claims. | 12 |
| **Casualty Claims Examiner** | A more senior casualty role for complex injury claims, fatalities and lawsuits. | 12 |
| **Inside Property Adjuster** | Handles home claims mainly from the office (phone, photos, estimates) rather than visiting the house. | 12 |
| **Property Adjuster** | Handles home claims that need more investigation, such as fire or condo claims. | 8 |
| **Subrogation Specialist** | Collects money back from the party (or insurer) that caused the loss. | 4 |
| **Salvage Specialist** | Sells total-loss vehicles. | 4 |
| **Claims Supervisor** | Manages a group of adjusters and **approves large payments and reserve changes**. | 4 |
| **Automated Process** | The computer ("System User"): opens tasks, assigns claims, issues and clears checks. | 1 |

An **adjuster** is the employee who investigates a claim, decides how much the insurer owes under the policy, and settles it. (An *independent* adjuster works for hire; the people here are staff adjusters.)

### 2.3 How people appear in the tables

- Columns ending in `_name` (`assigned_name`, `created_by_name`, `closed_by_name`, `author_name`, `changed_by`) hold the person's name. Join to `users.name`.
- `System User` appears whenever the computer did the work: assigning claims, issuing and clearing checks, creating many tasks. About 55% of all activities (163,822 of 298,247) were opened by it.
- `assigned_group` is the **team**, a pool of adjusters working a type of claim (names start with `#`). Section 8 explains the teams.
- A claim has one **owner** (`header.assigned_name`) but each exposure can have its own adjuster (`exposures.assigned_name`). On a car accident the claim owner may be a general adjuster while a casualty adjuster handles the injury.

## 3. What a policy covers

A policy is a bundle of separate coverages. A claim is checked against each one, and each coverage that applies becomes its own **exposure** (section 4). That is why the data has coverage codes such as `coll_vd` and `abi_bid`: they name the line of the policy being used. Every coverage has a **limit** (the most it will pay) and some have a **deductible** (the part you pay first).

### 3.1 First-party and third-party coverages

This is the most important split in insurance.

|  | **First-party** | **Third-party (liability)** |
| --- | --- | --- |
| Whose loss? | The policyholder's own: their car, their house, their medical bills. | Someone *else's*, caused by the policyholder. |
| Who gets the money? | The policyholder (or the shop or contractor who repairs it). | The other person (or their shop, doctor or insurer). |
| Is fault relevant? | Usually not. Your collision coverage pays whoever caused the crash. | Yes. The insurer pays only for what the policyholder is legally responsible for. |
| Examples here | Collision, comprehensive, rental, tow, PIP, dwelling, personal property | Auto property damage liability, bodily injury liability, personal liability |
| In the data | `exposures."LossPartyName" = "Insured's loss"` | `"LossPartyName" = 'Third-party liability'` |

### 3.2 Auto coverages in the data

| Code (`coverage_subtype`) | In plain English | Example | Limit used in this data | Deductible |
| --- | --- | --- | --- | --- |
| `coll_vd` **Collision** | Repairs your own car after it hits something or is hit (another car, a pole, a rollover). | You back into a pole. | The car's actual cash value (ACV) | $250, $500 or $1,000 |
| `comp_vd` **Comprehensive** | Repairs your car after non-crash damage. | Hail, theft, vandalism, a cracked windshield, fire, hitting a deer. | The car's ACV | $250, $500 or $1,000 |
| `rental_vd` **Rental** | A rental car while yours is being fixed. | A week of rental after a crash. | $900, $1,200 or $1,500 total | none |
| `towlabor_towlabor` **Towing and roadside** | A tow or roadside help. | Flat tire, lockout, out of fuel, tow. | $100 or $250 | none |
| `apd_vd` **Property damage liability: vehicle** | Pays for the *other* driver's car when you caused the crash. | You rear-end someone. | $25,000, $50,000 or $100,000 | none |
| `apd_pd` **Property damage liability: other** | Pays for other property you damaged. | You hit a fence or a building. | $25,000, $50,000 or $100,000 | none |
| `abi_bid` **Bodily injury liability** | Pays *other people's* injuries when you caused the crash (medical bills, pain and suffering, lost wages). | The driver you hit has whiplash. | $25,000 to $500,000 | none |
| `uim_bid`, `udim_bid` **Uninsured / underinsured motorist** | Your own insurer pays *your* injuries when the at-fault driver has no insurance or too little. | A driver with no insurance injures you. | $25,000 to $250,000 | none |
| `pip_medical_cougar` **PIP medical** | "Personal injury protection": pays *your own* medical bills after a crash, no matter who was at fault. | Your ER visit and physical therapy. | $3,000, $5,000 or $10,000 | none |
| `pip_income_loss_cougar`, `pip_loss_srvce_cougar`, `pip_funeral_cougar`, `pip_survivor_cougar` **Other PIP** | PIP also pays lost income, household help you cannot do, funeral costs and survivor benefits. | You miss two weeks of work. | $13,000 / $7,300 / $1,500 / $5,000 | none |

The `_vd` suffix means *vehicle damage*; `_pd` *property damage*; `_bid` *bodily injury damage*.

One point that confuses people: auto **liability** limits are often quoted in a "split" like 25/50/25 (per person, per accident, property). This data uses a **single limit per exposure** instead, which is a simplification.

### 3.3 Homeowner coverages in the data

| Code | In plain English | Example | Limit used in this data | Deductible |
| --- | --- | --- | --- | --- |
| `dwl_pd` **Dwelling** | Repairs or rebuilds the house itself. | A burst pipe floods the kitchen; fire damages the roof. | The insured amount of the house: $100,000 to $900,000 (median $221,000) | $1,000 or $2,500 |
| `os_pd` **Other structures** | Garage, shed, fence. | A tree falls on the shed. | 10% of the dwelling amount | $1,000 or $2,500 |
| `ppd_ppd` **Personal property** | Belongings inside the home. | Furniture ruined by water; a burglary. | 50% of the dwelling amount | $1,000 or $2,500 |
| `lu_lud` **Loss of use** | Living costs while the home cannot be lived in. | Hotel after a fire. | 20% of the dwelling amount | none |
| `pli_pd` **Personal liability: property** | Pays for damage the owner (or family) caused to someone else's property. | A child's ball breaks a neighbor's window. | $100,000 or $300,000 | none |
| `pli_bi` **Personal liability: injury** | Pays if a guest or passer-by is hurt on your property. | A guest slips on your steps. | $100,000 or $300,000 | none |

### 3.4 Limits and deductibles: the arithmetic

The amount the insurer pays on an exposure follows a simple recipe:

**Payment = (covered loss − deductible), capped at the limit.** For liability coverages the covered loss is also reduced to the policyholder's share of fault.

Four worked examples:

1. **Collision or comprehensive.** Claim `900001`: a rock cracked a windshield. The repair estimate was **$2,230.48**, the deductible was **$1,000**, so the insurer paid **$1,230.48**. In the data, for 88.6% of collision and comprehensive exposures that have both an estimate and a payment, `incidents.est_repair_cost` minus `coverages.deductible` equals `exposures.paid_to_date` to within two cents.
2. **Total loss.** Claim `900003`: a 2023 Hyundai Elantra valued (ACV) at **$14,000** was wrecked beyond economic repair. The insurer settled the vehicle at about $13,811, subtracted the **$500** deductible, and paid **$13,310.76**. Total loss is explained in section 7.
3. **Limit cap.** A bodily injury exposure with a **$25,000** limit and $60,000 of damages pays at most **$25,000**. The data flags this with `exposures.limit_reached = true`. It happens on 5.9% of auto bodily-injury exposures, 16.5% of PIP medical, 11.3% of rental and 44.9% of towing exposures (the tow limit is only $100 or $250).
4. **Shared fault.** The other driver's car needs **$8,000** of repairs and the policyholder is **70% at fault**. The insurer owes 70% of $8,000 = **$5,600**. In the data this shows up as `apd_vd` payments that rise with `header.insured_fault_pct`: on average $742 at 30% fault but $3,962 at 100%.

A home example (not a specific claim): dwelling limit $250,000, hail damage $18,000, deductible $2,500: the insurer pays **$15,500**.

### 3.5 Is it covered? Coverage verification

Before paying anything the insurer checks that (1) the policy was in force on the **loss date**, (2) the cause of loss is covered, and (3) the person or property is eligible. In the data this is the `COUGAR_Verify_Coverage` activity (one per claim, 20,000 in all, finished in a median of 0.65 days) and a note with topic `Coverage`. In real life some claims are denied here; this data does **not** model denials (see section 11), but about 12% of non-injury exposures end with **no payment**, usually because the loss was smaller than the deductible or the claim was closed without a payment.

## 4. The claim lifecycle: from loss to closed file

Every row in the database is a footprint of one step in this process. Learn the steps and the tables will make sense.

A claim moves through these stages. Not every claim does every stage: a lockout claim skips fault and injuries; a windshield claim skips most of the middle. The timings are the **medians in this data**.

&#91;embedded content: claim lifecycle · 12 steps and an injury detour\]

Read left to right, row by row. Injury claims take the dashed detour before payment; the table below gives each step's footprint in the data.

| # | Stage | What happens | Who | Footprint in the data | Typical timing here |
| --- | --- | --- | --- | --- | --- |
| 1 | **The loss** | Something happens: a crash, hail, a burst pipe, a theft. | Policyholder | `header.loss_date`, `loss_cause`, `loss_city`, `loss_description` | n/a |
| 2 | **Report** (the *first notice of loss*, FNOL) | The customer phones in. An intake specialist records it and opens the claim. | Intake Specialist | `reported_date`, `claim_opened`; first note (topic `First notice of loss`); task `COUGAR_Review_New_Claim` | Reported a median 2.4 days after the loss (auto) or 3.6 (property). The claim opens 1 to 15 minutes after the report |
| 3 | **Assign** | The system assigns the claim to an owner on the right team. | System User, adjuster | `assignment_date`, `assigned_name`, `assigned_group`; `change_log` event `claim_assigned` | Median 32 minutes after the report |
| 4 | **Verify coverage and make contact** | Check the policy was active and covers the cause. Speak to the customer. | Adjuster | Tasks `COUGAR_Verify_Coverage`, `COUGAR_Complete_Hours`; notes with topic `Coverage` | Coverage in about 0.65 days; first contact in about 4 hours |
| 5 | **Set up exposures** | Create one **exposure** for each coverage that applies (collision, rental, tow, injury...), each with its limit and deductible. | Adjuster | `exposures`, `coverages`; task `COUGAR_Review_New_Exposure` | The first within minutes; others (rental, injury) days or weeks later |
| 6 | **Investigate** | Collect evidence: police report, driver and witness statements, inspections, a check of past-claim databases (ISO). | Adjuster | Tasks `police_report`, statements, `vehicle_inspection`, `scene_inspection`, `iso_matches`, `COUGAR_Complete_Investigation`; notes topic `Investigation` | Investigation completes in about 5 days |
| 7 | **Decide fault** (collisions with another party) | Decide who was responsible and by what percentage. | Adjuster | `header.insured_fault_pct`; task `determine_claim_decision`; `change_log` event `liability_decision` | About 9 days |
| 8 | **Evaluate the damage** | Get a repair estimate, review it, decide repair or total loss. | Adjuster, repair shop | Tasks `quote`, `review_quote`; `incidents.est_repair_cost`, `damage_severity`, `total_loss` | Estimate about 8 days, review about 5 more |
| 9 | **Set the reserve** | Estimate what the exposure will cost, and revise it as facts change. | Adjuster; supervisor if over $5,000 | `money` rows with `subtype = 'Reserve'` | First reserve within about two hours of creating the exposure |
| 10 | **Pay** | Record payments, get approval, issue checks. | Adjuster; supervisor for $1,000 or more | `money` rows with `subtype = 'Payment'`; `check_*` columns; `exposures.paid_to_date` | First payment a median 26 days after the exposure is created |
| 11 | **Injury path** (if injured people) | Medical bills, maybe an attorney, demands and offers, maybe a lawsuit (section 6). | Casualty adjuster or examiner | PIP and bodily-injury exposures; `contact_roles`, `negotiations`, `matters`; `dccexpense` | PIP median 148 days; lawsuits average about 520 days |
| 12 | **Recover** | Collect from the at-fault party (subrogation) or sell the wreck (salvage). | Subrogation and salvage specialists | `money` rows with `subtype = 'Recovery'` | A median 67 days after the last payment |
| 13 | **Close** | After the last transaction, reserves are trued up to what was paid; the exposure closes; the claim closes when its last exposure does. | Adjuster | `exposures.state` and `close_date`; `header.claim_state` and `close_date`; `change_log` events `exposure_closed`, `claim_closed` | An exposure closes 2 to 6 days after its last transaction. Claims close in a median **34.6 days** (auto) or **64.2** (property) |

What is **not** in the data: reopening a closed claim, denying a claim, or moving a claim to another adjuster. Real claims do all three.

### Footprint of one average claim

To get a feel for the volume of records, here is how many rows an average claim leaves behind:

| Table | Rows per claim (average) | Why |
| --- | --- | --- |
| `header` | 1 | The claim |
| `exposures` and `coverages` | 1.6 each | One per coverage that applies |
| `money` | 6.7 | Reserves, payments, recoveries, spread across the exposures |
| `activities` | 14.9 | The task list |
| `notes` | 14.9 | The written record |
| `vehicles` and `incidents` | 1.2 (auto claims: 1.5) | Insured vehicle, sometimes the other driver's too |
| `change_log` | 73.8 | Every edit to any of the above |

## 5. Money: reserves, payments, expenses and recoveries

Most of the numbers in the data are dollars, and almost all of them live in the `money` table. It is a **ledger**: one row per event, never a running balance. To get a total you add up the right rows. This section explains the four kinds of rows so you add the right ones.

### 5.1 The four kinds of money rows (`money.subtype`)

| `subtype` | What it is | Does cash move? | Sign of `amount` | Rows |
| --- | --- | --- | --- | --- |
| **Reserve** | The insurer's *estimate* of what the exposure will cost in total. Each row is a *change* to that estimate. | No. It is a forecast. | Positive raises the estimate, negative lowers it | 73,489 |
| **Payment** | Money actually sent out (a check). | Yes, out | Positive | 52,277 |
| **RecoveryReserve** | The insurer's estimate of money it expects to get *back*. | No | Positive (can be negative when lowered) | 5,252 |
| **Recovery** | Money actually received back (section 7). | Yes, in | Positive | 2,508 |

### 5.2 Why reserves exist

When a claim is reported the insurer does not yet know what it will cost. But the company must still record on its books an estimate of what it will eventually pay for every open claim, because that is money it owes. That estimate is the **reserve**. Adjusters set it claim by claim when the exposure opens and revise it as facts arrive (an estimate comes in, treatment lasts longer, a lawsuit is filed). Actuaries use all the reserves to judge how much money the whole company must hold.

Reserves matter because they drive reported profit: reserving too low makes the company look more profitable than it is; too high does the opposite. That is why large reserve changes need a supervisor's approval (section 8).

In this data: 92.5% of exposures with an indemnity reserve have more than one reserve row (the estimate is revised, and always trued up to the amount paid when the exposure closes). The **first** reserve is within 23% below to 25% above the final amount paid for 80% of closed exposures (median ratio 1.01). That is far more accurate than real life, especially for injuries (section 11).

### 5.3 Paid, outstanding and incurred

Three totals are used constantly. Compute them per exposure (or claim) like this:

| Total | Meaning | How to compute from `money` |
| --- | --- | --- |
| **Paid** | Money already sent out. | Sum of `amount` where `subtype = 'Payment'` and `status = 'submitted'` |
| **Reserve (total)** | The current estimate of total cost. | Sum of `amount` where `subtype = 'Reserve'` |
| **Outstanding reserve** | Money still expected to be paid. | Reserve minus Paid |
| **Incurred** | Paid plus outstanding: the best estimate of the total cost. | Paid + Outstanding, which in this data equals the Reserve total |
| **Net incurred** | Incurred minus money recovered. | Incurred − sum of `Recovery` rows |

When an exposure **closes**, its outstanding reserve is exactly zero for every cost type: whatever was paid is the final cost. While it is **open**, the outstanding reserve is the insurer's remaining estimate. Example of an open one: dwelling exposure `9007495` (claim 904808) has a reserve of **$215,064.65** and nothing paid yet, so its entire amount is outstanding.

**Worked example: claim `900001`** (a windshield claim).

| Date | `subtype` | `cost_type` | `amount` | Running meaning |
| --- | --- | --- | --- | --- |
| 2024-03-05 | Reserve | indemnity | +1,407.58 | Estimate: the exposure will cost $1,407.58 |
| 2024-03-05 | Reserve | expense (`aoexpense`) | +45.00 | Estimate: a $45 inspection fee |
| 2024-03-10 | Payment | expense | 45.00 | Fee paid; expense outstanding is now $0 |
| 2024-04-06 | Payment | indemnity | 1,230.48 | Repair paid (estimate $2,230.48 minus $1,000 deductible) |
| 2024-04-12 | Reserve | indemnity | −177.10 | Estimate trimmed to the amount actually paid: 1,407.58 − 177.10 = 1,230.48 |

Totals for indemnity: reserve 1,230.48, paid 1,230.48, outstanding 0, incurred 1,230.48.

### 5.4 Indemnity versus expense

Insurers separate the money paid to cover the *loss* from the money spent to *handle* the claim.

| `cost_type` | Industry name | What it is | In this data |
| --- | --- | --- | --- |
| `COUGAR_indemnity` | **Indemnity** | Money that makes the policyholder or claimant whole: repair bills, medical bills, settlements. | 38,626 payments, **$138.8 million** |
| `aoexpense` | **Adjusting and other expense** (A&O) | Routine cost of running the claim, such as inspection or report fees. | 12,082 payments of $8.50 to $45, **$258,250** in total |
| `dccexpense` | **Defense and cost containment** (DCC) | Mostly lawyers' fees to defend lawsuits. | 777 payments of $500 to $6,000, **$2.48 million** in total |

The two expense types together are called **loss adjustment expense** (LAE). Why keep them apart? Policy limits normally apply to indemnity only, and accounting and pricing treat indemnity and expense differently. That is why `exposures.paid_to_date` counts **indemnity only**.

### 5.5 Life of a payment

1. **Created** (`create_time`). The adjuster records the payment, tagged `partial` (an installment), `supplement` (an additional payment after the first, for example the shop found more damage) or `final` (`payment_type`).
2. **Approved.** Payments of $1,000 or more need a supervisor's approval in this data (51% of indemnity payments). `submit_date` is when it took effect: a median 184 minutes after creation.
3. **Check issued** (`check_issue_date`), usually within a day of approval.
4. **Check cleared** (`check_clear_date`), a median 7 days later. `check_status` is `cleared` (51,135), `issued` (350: still outstanding as of 2026-10-07) or `voided` (792).
5. **Void and replace.** About 1.5% of payments are cancelled (a lost or wrong check). The original stays in the table with `status = 'voided'`, and a **new** payment for the same amount replaces it. If you counted both you would pay twice, so always filter on `status = 'submitted'`.

### 5.6 The whole data set in dollars

| Measure | Value |
| --- | --- |
| Indemnity paid (submitted payments) | **$138,789,173.80** |
| Adjusting and other expense paid | $258,250 |
| Defense and cost containment paid | $2,478,500 |
| Recovered (salvage and subrogation) | $7,674,571 (5.5% of indemnity paid) |
| Voided payments (not real spending) | $2,108,907 (792 rows) |

Use these as check totals: if your query for indemnity paid does not return $138,789,173.80, one of your filters is wrong.

A starter query for one claim, by cost type (see the dictionary's cookbook for more):

```sql
SELECT cost_type,
       SUM(amount) FILTER (WHERE subtype = 'Reserve') AS reserve,
       SUM(amount) FILTER (WHERE subtype = 'Payment' AND status = 'submitted') AS paid
FROM money
WHERE claim_id = 900001
GROUP BY cost_type;
```

## 6. Fault, injuries and lawsuits

Car damage is usually quick and bounded by the value of the car. Injuries and lawsuits are slow, uncertain and expensive. Understanding the difference explains most of the variation in the data.

### 6.1 Fault and the liability decision

A **liability** (third-party) coverage pays only when the policyholder was legally responsible, meaning *negligent*, for the harm. Often both drivers share the blame, so the insurer assigns a **fault percentage**. The insurer then pays only its customer's share. (Exact legal rules differ by state; this data uses a simple version.)

In the data the percentage is `header.insured_fault_pct` (0 to 100: the insured's share). It is set by the **liability decision**, the `determine_claim_decision` activity (median 8.9 days to complete), after the adjuster collects the police report, driver and witness statements and an inspection of the scene. It exists only for collisions involving another party: **7,832** claims have one.

| Decision | Claims | Share of decided |
| --- | --- | --- |
| Insured **fully at fault** (100) | 5,237 | 66.9% |
| Insured **not at fault** (0) | 1,765 | 22.5% |
| **Shared** fault (10 to 90) | 830 | 10.6% |

The cause of loss predicts fault. Read cause names from the policyholder's side:

- `rear-ended another vehicle`, `failed to yield at intersection`, `unsafe lane change`: the insured caused it, so about 91% are decided at 100% fault.
- `rear-end collision` (the insured's car was hit from behind) and `parked vehicle struck`: the other party caused it, so about 90% are decided at 0%.
- `intersection collision` and `head-on collision`: mixed. The insured is at fault in some, not at fault in others, and a few are shared.

What the decision changes in the data:

1. **Liability payments** to the other party (`apd_vd`, `apd_pd`, `abi_bid`) exist only when the insured has some fault, and are scaled by the insured's share (section 3.4).
2. **Collision payments** to the policyholder's own shop do not depend on fault: the policyholder is paid either way.
3. **Recoveries.** When the insured is not 100% at fault, the insurer tries to collect the other party's share back (subrogation, section 7).

### 6.2 Injury coverages

Three different coverages pay for injuries, depending on *whose* injury and *who* was at fault:

| Coverage | Who is hurt | Fault matters? | Limits here | Exposures | Typical size |
| --- | --- | --- | --- | --- | --- |
| **PIP** (`pip_*`) | The policyholder (and passengers), medical bills first | **No**: pays regardless of fault | $3,000 to $10,000 for medical | 2,572 | Median paid about $1,557 |
| **Bodily injury liability** (`abi_bid`, `pli_bi`) | **Other people** the policyholder hurt | **Yes** | $25,000 to $500,000 (auto) | 1,519 | Median paid about $10,498 (auto BI) |
| **Uninsured / underinsured motorist** (`uim_bid`, `udim_bid`) | The policyholder, when the at-fault driver has no or too little insurance | Other driver's fault | $25,000 to $250,000 | 75 | Median paid about $11,200 (UIM) and $23,000 (UDIM) |

PIP exists because many states, including Utah where the cities in this data are, use a **no-fault** system: each driver's own insurer pays their own medical bills up to a small limit without arguing about fault, and claims against the other driver are usually reserved for more serious injuries. That is why 16.8% of auto claims have a PIP or injury exposure.

Injury exposures stay open much longer than anything else: median **148 days** for PIP medical (treatment takes time) and **33%** of bodily-injury exposures are still open at the as-of date, versus about 3% of vehicle-damage exposures.

### 6.3 How an injury claim unfolds

1. **Injury reported.** The injury exposure is created days or weeks after the claim opens (up to about 90 days later for liability bodily injury, 150 for uninsured motorist).
2. **Records and bills.** The adjuster collects the initial medical report, treatment updates and bills (activities `initial_med_report`, `medical_report_claimant`, `follow_up_treatment`, `new_bill`).
3. **An attorney may appear.** In this data 789 of 1,594 bodily-injury exposures (49.5%) have a plaintiff attorney (`contact_roles`). Attorneys make claims larger, slower and more adversarial.
4. **Demand.** The attorney sends a **demand**: the dollar amount they want. The median demand in this data is 1.8 times the final payment.
5. **Offers.** The insurer replies with an **offer**; they go back and forth (`negotiations`: 699 demands, 935 offers).
6. **Settlement.** They agree; the insurer pays (`payment_type = 'final'`) and the claimant signs away further claims.
7. **Or a lawsuit.** If talks fail, the claimant files a lawsuit.

### 6.4 Lawsuits

A lawsuit is called a **matter** in the claim system. The steps in the data:

- **Filed**: the claimant's attorney files the complaint in court (`matters.filing_date`). The median is 288 days after the loss.
- **Served**: the papers are formally delivered to the insured (`matters.service_date`), a median 17 days after filing.
- **Defended**: the insurer hires defense lawyers, whose fees are the `dccexpense` payments (about $10,800 per litigated exposure on average).
- **Resolved**: by settlement (in this data every suit that closes ends in a payment) or trial.

Suits are rare but heavy: 263 bodily-injury exposures on 260 claims (1.3% of all claims; 16.5% of bodily-injury exposures).

| Bodily-injury exposures (auto and home) | Count | Average paid\* | Average days open\*\* |
| --- | --- | --- | --- |
| No attorney | 805 | $8,981 | 108 |
| Attorney, no lawsuit | 526 | $9,875 | 248 |
| **In a lawsuit** | 263 | **$14,811** | **519** |

\* Averages include exposures that paid $0. \*\* For open exposures, measured to the as-of date.

Complex injuries (expected loss of $75,000 or more) go to a separate team (`Auto Complex Injury` segment, 100 exposures) and suits go to `#Bodily Injury - Litigation`.

### 6.5 Where to look in the data

| Question | Table and columns |
| --- | --- |
| Who decided fault, and what? | `header.insured_fault_pct`; notes with topic `Investigation`; activity `determine_claim_decision` |
| Which injured people have lawyers? | `contact_roles` (join on `exposure_ref`) |
| What was demanded and offered? | `negotiations` (`line_type`, `amount`, `negotiation_date`) |
| Which claims are in suit? | `matters` |
| What did the lawsuit cost? | `money` where `cost_type = 'dccexpense'` |

## 7. Getting money back: subrogation, salvage and total loss

Paying a claim is not always the end of the money story. Sometimes the insurer can get part of it back. Recoveries reduce the true cost of a claim, so a careful analysis looks at **net** cost (paid minus recovered).

### 7.1 Subrogation: collecting from the party who caused the loss

**Subrogation** (from a Latin word for "substitution") means that after the insurer pays its own policyholder, it steps into the policyholder's shoes and asks the person at fault, usually that person's insurer, to reimburse it.

Example: another driver rear-ends your insured customer. The customer's collision coverage pays the repair shop right away (repair $8,000 minus a $500 deductible = $7,500), so the customer is not stuck waiting for the other driver's insurer. The insurer then sends a **subrogation referral** to the at-fault driver's insurer and collects. (In real life the customer's deductible is also recovered and refunded to them. This data does not model that.)

In the data:

- Subrogation is pursued only when the insured is **not 100% at fault** (`header.insured_fault_pct` below 100). Recovery is roughly the other party's share of the payment.
- Of the 2,137 collision exposures that were paid on claims with a fault decision under 100%, **70%** (1,496) have a subrogation recovery. The median recovery is **90%** of what the insurer paid.
- The work shows up as activities `subro_check` ("Determine if opportunity for recovery", 6,811) and `COUGAR_New_Subro` ("New Subrogation Referral", 1,623), notes with topic `Subrogation` (10,015), and money rows created by the Subrogation Specialist.
- **1,594 subrogation recoveries total $4,427,717.**

### 7.2 Total loss and salvage

A car is a **total loss** when it would cost too much to repair compared with what it is worth, so the insurer pays the car's value instead of fixing it. (Insurers use a threshold that is a high share of the car's value; the exact rule varies by company and state.) The value used is the **actual cash value (ACV)**: what the car was worth just before the loss, taking age and condition into account. It is *not* what the owner paid or what a new car costs.

Once the insurer pays, it owns the wreck, called **salvage**. It sells the wreck (for parts or scrap) and keeps the proceeds. That income is a **salvage recovery**.

In the data:

- **1,244** vehicles are total losses (`incidents.total_loss = true`, `damage_severity = 'total_loss'`): about 10% of insured vehicles with a collision or comprehensive exposure. Their estimate (`est_repair_cost`) is close to the car's value.
- Total losses are handled by the `#Total Loss Team` (Specialty Adjusters) and a Salvage Specialist. Activities `COUGAR_Salvage_Notice` and `salvage_vehicle` ("Salvage Vehicle Status", 1,009 of each) track the sale, and the status task closes when the wreck sells.
- The payment is about the ACV minus the deductible (median payment is **87%** of ACV).
- **914 salvage recoveries total $3,246,854.** The median salvage sale is **20% of the car's ACV**.
- 82% of paid total-loss exposures have a recovery.

**Worked example: claim `900003`** (a 2023 Hyundai Elantra totaled in an intersection collision, insured not at fault).

| Item | `money.subtype` | Amount |
| --- | --- | --- |
| Vehicle ACV (and the coverage limit) | n/a (`incidents.vehicle_acv`) | $14,000.00 |
| Deductible | n/a (`coverages.deductible`) | $500.00 |
| Payment to settle the car | Payment | $13,310.76 |
| Salvage recovery *booked as expected* | RecoveryReserve | $3,215.84 |
| Expected recovery lowered when the car sold for less | RecoveryReserve (negative) | −$342.19 |
| Salvage actually received | Recovery | **$2,873.65** |
| **Net indemnity cost** (paid minus recovered) |  | **$10,437.11** |

The recovery reserve works like a claim reserve in reverse: it is the estimate of money coming in, adjusted until the real recovery arrives.

### 7.3 Timing and how to read recoveries in the data

- The median recovery arrives **67 days after the last payment**, so recoveries lag, and very recent claims will show payments but no recoveries yet.
- Overall, recoveries are **$7.67 million**, or **5.5%** of indemnity paid. On exposures that have a recovery they offset about 38% of what was paid.
- `money.recovery_category` tells you which kind (`subrogation` 1,594 rows, `salvage` 914 rows). In this data an exposure has **one** kind of recovery, never both. In real claims both can happen.
- The money filters: gross paid = `subtype = 'Payment' AND status = 'submitted'`; recovered = `subtype = 'Recovery'`; net = gross minus recovered. Do **not** add `RecoveryReserve` rows to either; they are estimates.

## 8. How a claims department is organized

The data shows not only what happened to each claim but how the department worked it. This section explains the machinery behind columns such as `SegmentName`, `assigned_group` and the `activities` table.

### 8.1 Routing by segment

Not every claim deserves the same attention. A cracked windshield and a wrongful-death claim need very different handling. Claim systems therefore label each exposure with a **segment** (`exposures."SegmentName"`), a complexity category that decides which team gets it. Simple claims go on a "fast track" so they are paid quickly with little human effort; complex ones go to senior staff.

| Segment | What it is | Team that handles it | Exposures | Dollars paid | Share of dollars |
| --- | --- | --- | --- | --- | --- |
| Auto Fast Track | Routine vehicle damage: collision, comprehensive, rental | Repair-type teams; total losses to the Total Loss Team | 14,138 | $44.2M | 31.9% |
| Property No Liability | Ordinary home damage (water, wind, hail, fire, theft) | Home teams | 3,275 | $28.4M | 20.4% |
| Property Large Loss | Home loss of $100,000 or more | Home teams | **158** | **$22.5M** | **16.2%** |
| Auto Liability No Injury | Paying the other driver's car or property | Auto Liability No Injury Team | 5,964 | $20.7M | 14.9% |
| Auto (BI) non-Complex Injury | Bodily injury with an expected loss under $75,000 | Bodily injury teams | 1,414 | $12.5M | 9.0% |
| Auto (PIP) non-Complex Injury | No-fault medical benefits | Auto PIP Team | 2,556 | $4.6M | 3.3% |
| Auto Complex Injury | Bodily injury with an expected loss of $75,000 or more | BI Complex | 100 | $3.2M | 2.3% |
| Property Liability PD Only | Homeowner damaged someone else's property | Condo/Townhome and Liability team | 256 | $1.6M | 1.2% |
| Property non-Complex Injury | A guest hurt at the home | Casualty team | 80 | $0.6M | 0.4% |
| Towing & Roadside | Tow, lockout, flat tire | Auto - Tow (Claims Assistants) | 3,578 | $0.4M | 0.3% |
| Sensitive (Special Permisions) | Fatality-related PIP (funeral, survivor benefits) | Home or Fatality team | 16 | $0.04M | 0.0% |

Read the table twice: the **158** large property exposures are 0.5% of exposures but **16% of the dollars**. Claims money is concentrated in a few big claims (section 9).

### 8.2 Teams

A **team** (`assigned_group`, names start with `#`) is a pool of adjusters who work one kind of claim. The data has 18 teams for exposures. In this data each team has four people. Teams fall into families: **vehicle repair** (Cougar Care, Cougar NON-DRP, Express Care; names are internal labels), **Total Loss**, **Auto - Tow**, **Auto Liability No Injury**, **Auto PIP**, six **Bodily Injury** teams (by severity, attorney involvement and litigation), and five **Home** teams. The full list with counts is in the data dictionary (section 7.4).

A claim is owned by the adjuster handling its **first exposure** (`header.assigned_group` is always that exposure's team). Other exposures may be handled by other teams, which is how one car accident ends up with three or four adjusters.

### 8.3 The to-do engine: activities and diaries

Adjusters do not work from memory. The claim system creates **activities** (tasks) automatically when events happen, and each task is assigned, due and completed. `activities` is the data's log of that work: 298,247 tasks.

| Trigger | Task created (`pattern_code`) | Median days to complete |
| --- | --- | --- |
| Claim opens (every claim) | `COUGAR_Review_New_Claim`: review the new claim | 0.43 |
|  | `COUGAR_Verify_Coverage`: verify coverage | 0.65 |
|  | `COUGAR_Complete_Hours`: "Complete 8 hour contact" (first contact with the customer; the name suggests an 8-hour target) | 0.18 (about 4 hours) |
|  | `COUGAR_Complete_Investigation`: complete the investigation | 5.3 |
| Exposure created | `COUGAR_Review_New_Exposure` | 0.51 |
| Repair estimate needed | `quote`: get a repair quote; `review_quote`: review and approve it | 8.2; 4.6 |
| Collision with another party | `police_report`, statements, `scene_inspection`, then `determine_claim_decision` (the liability decision) | 8.9 (decision) |
| Injury bill arrives | `new_bill`: review new bill | 1.25 |
| Injury treatment ongoing | `follow_up_treatment` | 1.75 |
| Payment of $1,000 or more | `approve_payment` | 0.13 (about 3 hours) |
| Reserve change over $5,000 | `approve_reserve_change` | 0.13 |

**Diaries** are reminders to look at the claim again: `30_day_diary`, `60_day_diary`, `90_day_diary`, plus free-form `general_reminder` tasks. Open claims otherwise get forgotten, so diaries guarantee someone revisits them.

Reading the table: `create_time` to `close_date` on an activity is its turnaround time. Only 877 tasks (0.3%) are still open, and all are on open claims.

Each completed task usually leaves a **note** (`notes`, 298,013 rows) written by whoever finished it, so the file documents who knew what and when. Notes matter for hand-offs, audits and regulators. They are text, so you can search them (see the dictionary's query cookbook).

### 8.4 Authority and approvals

An adjuster can pay only up to their **authority**. Bigger decisions need a **supervisor**. In this data:

- A **payment of $1,000 or more** needs approval (51% of indemnity payments).
- A **reserve change over $5,000** needs approval.
- The `approve_payment` (20,729) and `approve_reserve_change` (7,769) tasks add up to 28,498, exactly the number of approval events in `change_log`, where a money row changes from `submitting` to `submitted`.

The approval step is why `money.submit_date` can be hours after `create_time`.

### 8.5 Speed: the first hours

The first hours of a claim are the most visible to the customer. In the data, the median time from report to assignment is **32 minutes**, the claim record is opened 1 to 15 minutes after the report (`reported_date` to `claim_opened`), and first contact with the customer is completed in about four hours.

## 9. Reading the numbers: core metrics and what normal looks like

Claims people judge a book of business with a handful of measures. This section defines each one, shows how to get it from the data, and gives the value **in this synthetic data set** so you know what a sensible answer looks like. These are not industry benchmarks.

### 9.1 Volume and mix

| Measure | Definition | Value here |
| --- | --- | --- |
| Claims | Rows in `header` | 20,000 (about 1,750 to 1,900 per loss quarter, flat) |
| Exposures per claim | Rows in `exposures` per `claim_id` | 1.58 on average; 67% of claims have one |
| Line of business | `header.lob` | 85% auto, 15% property |
| Claims with an injury exposure | PIP or bodily injury on the claim | 14.7% of claims (auto 16.8%, property 2.7%) |
| Claims **closed without payment** | Closed claims where total indemnity paid is $0 | 1,651 claims (8.3%) |
| Open claims | `claim_state = 'open'` | 1,465 (7.3%), average age 136 days |

### 9.2 Severity: how much does a claim cost?

**Severity** is the average cost of a claim. It is the most important and most misunderstood number, because claim costs are very **skewed**: most claims are small and a few are enormous.

| Claim-level indemnity paid (17,931 claims with a payment) | Value |
| --- | --- |
| Median (the typical claim) | **$2,826** |
| Mean (the average, pulled up by large claims) | **$7,740** |
| 90th percentile | $18,052 |
| 99th percentile | $82,872 |
| Largest | $380,960 |
| Share of all dollars from the **top 1%** of claims | **20.7%** |
| Share of all dollars from the **top 10%** of claims | **58.4%** |

Because the mean is nearly three times the median, **always report both**, plus percentiles. Line of business matters too: the mean paid claim is about **$5,543 for auto** and **$21,433 for property**, so mixing them hides everything.

Severity by coverage (exposures that were paid, so excluding $0):

| Coverage | Paid exposures (% of exposures) | Mean paid | Median paid | 90th percentile |
| --- | --- | --- | --- | --- |
| Collision `coll_vd` | 90.7% | $4,591 | $2,493 | $10,301 |
| Comprehensive `comp_vd` | 79.2% | $3,519 | $1,433 | $8,237 |
| Auto property damage `apd_vd` | 91.7% | $3,855 | $2,808 | $7,816 |
| Rental `rental_vd` | 93.6% | $613 | $550 | $1,052 |
| Towing `towlabor_towlabor` | 95.1% | $126 | $100 | $226 |
| PIP medical `pip_medical_cougar` | 93.8% | $1,957 | $1,557 | $3,541 |
| Bodily injury `abi_bid` | 68.9% | $15,101 | $10,498 | $30,750 |
| Dwelling `dwl_pd` | 81.5% | $24,182 | $8,492 | $61,114 |
| Personal property `ppd_ppd` | 61.7% | $5,070 | $2,780 | $12,198 |

Read it as a story: towing costs about $126, a rental about $600, a collision a few thousand dollars, a bodily-injury claim around $15,000 and a house claim about $24,000, with enormous spread in the last two.

### 9.3 Speed: cycle time

**Cycle time** is how long a claim takes. Insurers watch it because slow claims cost more to handle and upset customers.

| Measure | How to compute | Value here |
| --- | --- | --- |
| Reporting lag | `reported_date` minus `loss_date`, in days | Median 2.4 (auto), 3.6 (property). Average 6.4 and 20.3: a few are reported very late |
| Time to assign | `assignment_date` minus `reported_date` | Median 32 minutes |
| Time to first payment | First indemnity payment minus exposure `create_time` | Median 26 days, 90th percentile 63 |
| Days to close a claim | `close_date` minus `claim_opened`, closed claims | Median **34.6** (auto) and **64.2** (property); 90th percentile 146 (auto) and 112 (property) |

Days to close an **exposure** by coverage (closed exposures, median): towing 9, rental 21, comprehensive 25, collision 38, auto property damage 40, dwelling 63, **PIP medical 148** (90th percentile 223). Injury coverage is slow because treatment takes months. Auto has the longer tail because of injuries; at the median property claims close more slowly (64 days against 35), but auto has the longer tail.

### 9.4 Injury, litigation and limits

| Measure | Value here |
| --- | --- |
| Bodily-injury exposures with an attorney | 789 of 1,594 (49.5%) |
| Bodily-injury exposures in a lawsuit | 263 (16.5%); 260 claims = 1.3% of all claims |
| Demand ÷ final payment (median) | 1.8 |
| Legal expense per litigated exposure (average) | about $10,800 |
| Exposures that hit their **limit** | towing 44.9%, PIP medical 16.5%, rental 11.3%, auto bodily injury 5.9%, dwelling 2.2%, collision and comprehensive 0%. The 9 PIP funeral exposures all hit their limit, a quirk of how the data was generated |

### 9.5 Recoveries, reserves and operations

| Measure | Value here |
| --- | --- |
| Recoveries as a share of indemnity paid | 5.5% ($7.67M of $138.8M) |
| Subrogation: collision exposures (insured not 100% at fault) with a recovery | 70% |
| Salvage: median sale as a share of the car's ACV | 20% |
| **Reserve accuracy**: first reserve ÷ final paid (closed exposures) | Median 1.01; middle 80% between 0.77 and 1.25 |
| Payments voided and replaced | 1.5% |
| Payments needing supervisor approval ($1,000 or more) | 51%; median approval time 3 hours |
| Time for a check to clear | Median 7 days |

### 9.6 Open inventory

A claims department also tracks what is still open. By exposure type, the share still open at the as-of date: bodily injury **33%**, PIP 14%, property 6.5%, vehicle damage 3.4%, towing 0.4%. Injuries are why a company's open inventory stays full.

### 9.7 Starter queries

Severity by coverage:

```sql
SELECT coverage_subtype,
       COUNT(*) FILTER (WHERE paid_to_date > 0) AS paid_exposures,
       ROUND(AVG(paid_to_date) FILTER (WHERE paid_to_date > 0), 0) AS mean_paid,
       ROUND((PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY paid_to_date) FILTER (WHERE paid_to_date > 0))::numeric, 0) AS median_paid
FROM exposures
GROUP BY coverage_subtype
ORDER BY paid_exposures DESC;
```

Share of all dollars from the top 10% of claims:

```sql
WITH c AS (SELECT claim_id, SUM(paid_to_date) AS paid FROM exposures GROUP BY claim_id),
     r AS (SELECT paid, NTILE(10) OVER (ORDER BY paid DESC) AS decile FROM c)
SELECT ROUND(100 * SUM(paid) FILTER (WHERE decile = 1) / SUM(paid), 1) AS top_decile_share_pct
FROM r;
```

## 10. Traps when analyzing claims data

These mistakes are easy to make and change your conclusions. Each one has a data example.

### 10.1 Open claims are unfinished (the biggest trap)

Claims take months or years to settle, but the data stops on **2026-10-07**. Recent claims are still in progress, so their paid amounts are *incomplete*, not small. Actuaries call this the claim's **development** or **maturity**. Look at average paid per claim by when the loss happened:

| Loss quarter | Claims | Still open | Average paid per claim (all claims, including $0) |
| --- | --- | --- | --- |
| 2024-Q1 | 1,737 | 0.1% | $7,825 |
| 2025-Q1 | 1,758 | 1.5% | $8,108 |
| 2026-Q1 | 1,772 | 5.4% | $7,017 |
| 2026-Q2 | 1,863 | 14.4% | $5,813 |
| 2026-Q3 | 1,751 | **49.6%** | **$3,991** |

It would be wrong to conclude that claims became cheaper in 2026. Half of the Q3 2026 claims are still open and most injury claims have barely started. The same bias hits cycle time: if you average days-to-close for closed claims only, recent quarters look fast because only the quick ones are finished.

**What to do:** compare only mature periods (for example 2024 and 2025 losses), or compare claims at the *same age* (paid by 90 days after the loss, for instance), or use **incurred** (paid plus reserve), which already estimates the final cost.

### 10.2 Know your unit of analysis (the grain)

The data has several "grains": a *claim* (`header`), an *exposure* (`exposures`), a *transaction* (`money`), a *task* (`activities`). Mixing them silently multiplies or divides your numbers.

- Joining `header` (20,000 rows) to `money` (133,526 rows) gives 133,526 rows. If you then average a *claim* column such as `insured_fault_pct`, claims with many transactions count many times.
- "Average cost per claim" must sum to the claim level first (for example `SUM(paid_to_date)` per `claim_id`), then average.
- Counting rows after a join is not counting claims: use `COUNT(DISTINCT claim_id)`.
- Do not add `coverage_limit` across exposures and call it the claim's limit: each exposure has its own limit.

### 10.3 Money double counting

- **Voided payments** (792 rows, $2.1 million) sit beside their replacements. Always filter `status = 'submitted'`.
- **Reserve rows are changes**, not balances. Summing them gives the current estimate; looking at one row shows only the change.
- **RecoveryReserve** is an estimate; **Recovery** is cash. Do not add them.
- `exposures.paid_to_date` is **indemnity only**. Expense payments are in `money` (`aoexpense`, `dccexpense`).
- `net_amount` and `original_amount` equal `amount` here; they add no information.
- Amounts can be **negative** (reserve decreases). Check signs before taking averages.

### 10.4 Skew, outliers and mix

- Use **medians and percentiles** next to the mean (section 9.2).
- A single $380,960 dwelling claim barely changes a mean of 17,931 claims, but a *segment* average over 158 large property exposures is driven by a handful of them.
- Compare like with like: a property claim and an auto claim are different products. **Group by coverage or line first**, then compare. Averages across mixes can reverse when you split them (Simpson's paradox).

### 10.5 NULL means something

- `close_date` NULL = still open.
- `insured_fault_pct` NULL = no liability decision applies yet or at all. It is **not 0**, and `WHERE insured_fault_pct < 100` silently drops the NULLs (SQL treats NULL comparisons as unknown).
- `exposure_ref` NULL on `activities` and `notes` = a claim-level row. Use `LEFT JOIN` or you will lose those rows.
- `payment_type`, `recovery_category` and `check_*` are NULL on rows where they do not apply.

### 10.6 Time is tricky

- Measure age and elapsed time against the **as-of date (2026-10-07 12:00)**, never `now()`. Otherwise every open claim gets older every day you rerun your query.
- Timestamps have no time zone and `loss_date` is a date stored at midnight.
- In this data every report happens between 8:00 and 17:00 (section 11). Do not draw conclusions about "time of day" patterns.

### 10.7 Leakage if you build a prediction model

If you try to predict an outcome (will this claim be litigated? how much will it cost?), use only information available **at the moment of the prediction**. `paid_to_date`, `close_date`, `claim_state`, `est_repair_cost` (arrives mid-claim) and the whole `change_log` contain the future. To reconstruct what was known on a past date, replay `change_log` (the dictionary's cookbook query 9 shows how). Predicting rare events (1.3% of claims are litigated) also needs measures other than plain accuracy: a model that always says "no suit" is 98.7% accurate and useless.

### 10.8 Patterns the generator made

Because the data is generated by rules, some patterns are artifacts: fault percentages follow the cause of loss, bodily-injury demands are a fixed multiple of the payment, reserves track payments closely. Finding such a pattern tells you how the data was made, not how insurers behave. Say so in your write-up.

## 11. What is real and what is synthetic

The data was **generated by a program** (`generator/synthetic_claims.py`, seed 7), modeled on how a modern claims system is used. No real claim, person, vehicle or note appears in it, and its numbers are choices made for teaching, **not facts about any real insurer**. Know the difference before you draw conclusions.

### 11.1 What you can trust

- **The structure.** Claim, exposure, coverage, reserve, payment, recovery, activity, note and change history are the real building blocks of a claim system, and they relate the way the dictionary says.
- **The accounting identities.** Paid equals the sum of submitted payments; a closed exposure's reserves equal what was paid; every join resolves. These are guaranteed, so any query that violates them has a bug.
- **The vocabulary.** Coverage names, segments, activity types and the claim lifecycle follow real practice.

### 11.2 What is simplified or invented

| Topic | In real life | In this data |
| --- | --- | --- |
| **Policies and premium** | Every claim belongs to a policy that earned premium. | No policy or premium tables. You can study costs but cannot compute true frequency, loss ratio or profitability. |
| **Claim amounts** | Shaped by real repair costs, medical bills and court outcomes. | Drawn from skewed (log-normal) distributions per coverage: that is why you see many small and a few huge amounts. |
| **Seasonality and catastrophes** | Hail season, winter freezes and storms cluster claims in time. | Claims are spread evenly over time (472 to 681 per full month). Hail is about 5% to 7% of claims in every month. No catastrophe events. |
| **When claims are reported** | Around the clock, with peaks. | Every report is between 8:00 and 17:00, with no weekend dip. |
| **Denials and fraud** | Some claims are denied or investigated as fraud. | No denials, no fraud outcomes. Some tasks (such as ISO matches) exist, but nothing happens as a result. |
| **Reopens and reassignments** | Claims reopen, and adjusters change. | Not modeled. Once closed, a claim stays closed, and each exposure keeps one adjuster. |
| **Reserve accuracy** | Often badly off, especially for injuries. | The first reserve is close to the final payment (median ratio 1.01). Do not generalize this to real reserving. |
| **Fault** | Disputed and negotiated. | One percentage drawn by simple rules from the cause of loss. |
| **Injury claims** | Bills, liens, many offers, trials, appeals. | One demand and one to three offers, then payment; at most one suit per injury exposure. |
| **Recoveries** | Subrogation and salvage can both occur, plus deductible reimbursement. | One recovery type per exposure; deductible recovery not modeled. |
| **Policy limits** | Often split (for example 25/50/25). | A single limit per exposure. Home limits are tied to the dwelling amount. |
| **Text** | Notes are messy, abbreviated, inconsistent. | Notes are generated from templates, so they are clean and repetitive (118,379 different bodies in 298,013 notes). |
| **Names and places** | Real people, firms, cities. | Fictional people, firms, shops and providers. Ten Utah cities, each about 10% of claims. |
| **Trends** | Costs rise with inflation and repair-cost changes. | No trend is built in. Apparent declines in recent periods are mostly unfinished claims (section 10.1). |
| **Data quality** | Missing values, typos, duplicates. | Almost none, apart from a few misspellings copied from the source layout (`Permisions`, `statment`, `Glas`). |

### 11.3 Practical advice

- Report **relationships, mechanics and process** with confidence. Be modest about **levels and rates** (the exact average severity, the exact percent litigated): they came from the generator's settings.
- When you find a surprising pattern, check whether the generator could have built it in (for example fault depends on cause, demands are a multiple of the payment).
- State the **as-of date** (2026-10-07) and your **filters** with every number.

## 12. Practice questions

Use these to learn the data. Work in order: each tier builds on the last. Warm-up answers are given so you can check your queries against the database.

### 12.1 Warm-up (check values included)

| # | Question | Check value |
| --- | --- | --- |
| 1 | How many claims and exposures are there? What share of claims are auto? | 20,000 claims; 31,535 exposures; 85% auto (16,992) |
| 2 | What is the total indemnity paid on submitted payments? | $138,789,173.80 |
| 3 | How many claims are open, and what share is that? | 1,465 (7.3%) |
| 4 | Which coverage appears most often in `exposures`? | Collision `coll_vd`, 6,900 |
| 5 | What share of claims have exactly one exposure? | 13,451 claims (67.3%) |
| 6 | Which team handles the most exposures? | `#Auto Liability No Injury Team`, 5,964 |
| 7 | How many bodily-injury exposures have an attorney? In suit? | 789; 263 |
| 8 | How many payments were voided, and what are they worth? | 792; $2,108,907 |

### 12.2 Core analysis

1. **Severity.** For each coverage, compute mean and median paid (paid exposures only). Which coverages have the biggest gap between mean and median, and why?
2. **Cycle time.** Compare days-to-close for closed auto and property claims. Compare medians *and* 90th percentiles. What causes the difference in the tails?
3. **Deductibles.** For collision and comprehensive payments, test whether `est_repair_cost` minus `deductible` equals `paid_to_date`. Which exposures break the rule and what do they have in common? (Hint: total losses.)
4. **Fault and payments.** Plot average `apd_vd` payment by `insured_fault_pct`. Explain the shape using section 3.4.
5. **Subrogation.** Among collision payments where the insured is not 100% at fault, what share has a subrogation recovery? How does the recovery rate or the recovered share of paid change with `insured_fault_pct`?
6. **Reserve accuracy.** Compare each closed exposure's *first* reserve with its final paid amount. Which coverages are hardest to reserve? What does the ratio look like for bodily injury versus collision?
7. **Attorneys and suits.** Compare paid amount and days open for bodily-injury exposures with no attorney, an attorney, and a suit. Does the data prove that attorneys *cause* higher cost? What else could explain the difference?
8. **Approvals.** How long do payment approvals take? Does the payment amount matter? Which supervisors approve the most?
9. **Concentration.** Which segment produces the most dollars? Which produces the most exposures? Draw the cumulative share of dollars against the cumulative share of claims.

### 12.3 Challenge

1. **Development triangle.** Using `money.create_time` (or `change_log`), compute cumulative paid at 3, 6, 12 and 18 months after the loss for each loss quarter. Show how paid grows as claims mature, and use it to explain section 10.1.
2. **Leakage-free prediction.** Predict which bodily-injury exposures will end in a lawsuit using only information known within 30 days of the exposure's creation. Evaluate with precision and recall, not accuracy.
3. **Data quality suite.** Write checks that should always return zero (for example payments over a limit, closed claims with open exposures, voids without replacements). Run them and explain what each guarantees.
4. **Net cost.** Build net cost per claim (indemnity paid minus recoveries plus expense) and compare line of business and segment on a *net* versus *gross* basis. What changes?
5. **A null result.** Test whether adjuster workload (tasks per adjuster per week) is related to task turnaround. If you find nothing, explain why that might be a property of how the data was generated.

### 12.4 Presenting your results

- State the **unit** (claim, exposure or transaction), the **filters** and the **as-of date**.
- Give **median and mean** for money; avoid reporting only averages.
- Say whether each number includes **open** claims.
- Separate **what the data shows** from **what you infer** about insurance in general.

## 13. Glossary A to Z

The right-hand column says where the idea appears in the data (or "not in data").

| Term | Meaning | In the data |
| --- | --- | --- |
| **A&O expense** | Adjusting and other expense: routine costs of running a claim (inspection or report fees). | `cost_type = 'aoexpense'` |
| **Actual cash value (ACV)** | What a vehicle was worth just before the loss, after age and wear. | `incidents.vehicle_acv` |
| **Activity** | A task in a claim's to-do list, with a creator, a completer and dates. | `activities` |
| **Adjuster** | The employee who investigates a claim and decides what is owed. | `*_name` columns; `users` |
| **APD (auto property damage)** | Liability coverage that pays for damage you cause to other people's vehicles or property. | `apd_vd`, `apd_pd` |
| **Approval / authority** | The rule that larger payments or reserve changes need a supervisor's sign-off. | `approve_payment`, `approve_reserve_change` |
| **As-of date** | The moment the data is frozen. | 2026-10-07 12:00 |
| **Bean version** | A counter the claim system keeps on each row to track edits. | `bean_version` |
| **Bodily injury (BI)** | Coverage for injuries you cause to other people. | `exposure_type = 'BodilyInjuryDamage'` |
| **Case reserve** | A reserve an adjuster sets on one specific claim. | `Reserve` rows |
| **Casualty** | The insurance word for liability-to-people claims such as bodily injury. | Casualty teams and titles |
| **Cause of loss / peril** | What caused the damage (hail, theft, collision). | `header.loss_cause` |
| **Claim** | A request that the insurer pay for a loss under a policy. | `header` |
| **Claimant** | A person making a claim against someone else's policy. | Third-party exposures |
| **Closed without payment (CWP)** | A claim closed with nothing paid. | 1,651 claims |
| **Collision** | Coverage for repairing your own car after a crash. | `coll_vd` |
| **Combined ratio** | Loss ratio plus expense ratio; below 100% means an underwriting profit. | not in data (no premium) |
| **Comparative fault** | Sharing blame between parties by percentage. | `insured_fault_pct` |
| **Comprehensive** | Coverage for your own car damaged by something other than a crash (hail, theft, glass, fire, animals). | `comp_vd` |
| **Coverage** | One specific protection within a policy. | `coverages`, `coverage_subtype` |
| **Cycle time** | How long a claim or step takes. | Date differences |
| **DCC (defense and cost containment)** | Mostly lawyers' fees to defend lawsuits. | `cost_type = 'dccexpense'` |
| **Deductible** | The first part of a loss the policyholder pays. | `coverages.deductible` |
| **Demand** | The dollar amount an injured person's attorney asks for. | `negotiations.line_type = 'demand'` |
| **Development (maturity)** | How a claim's cost grows and settles as it ages. Immature claims look cheaper than they will be. | Section 10.1 |
| **Diary** | A reminder to look at a claim again after a set time. | `30_day_diary`, `60_day_diary`, `90_day_diary` |
| **Dwelling** | Home coverage for the house itself. | `dwl_pd` |
| **Exclusion** | Something a policy does not cover. | not in data |
| **Expense** | Money spent to handle a claim rather than to pay the loss. See LAE. | `aoexpense`, `dccexpense` |
| **Exposure** | One coverage's claim within a claim; the unit that gets limits, money and a close date. | `exposures` |
| **Fast track** | A streamlined path for simple claims. | `Auto Fast Track` segment |
| **First-party** | Coverage for the policyholder's own loss. | `"LossPartyName" = "Insured's loss"` |
| **FNOL (first notice of loss)** | The first report of a loss. | `reported_date`; note topic `First notice of loss` |
| **Frequency** | How often claims happen, relative to the number of policies. | needs policy counts (not in data) |
| **Incident** | In this data, what happened to one vehicle: impact point, damage. | `incidents` |
| **Incurred** | Paid plus outstanding reserve: the best estimate of total cost. | Sum of `Reserve` rows |
| **Indemnity** | Money paid to cover the loss itself. | `cost_type = 'COUGAR_indemnity'` |
| **Insured / policyholder** | The customer who bought the policy. | `role = 'insured'` |
| **ISO** | An industry database of past claims, used to spot prior losses and possible fraud. | task `iso_matches` |
| **LAE (loss adjustment expense)** | Cost of handling and defending claims: A&O plus DCC. | `aoexpense` + `dccexpense` |
| **Liability coverage** | Pays for harm the policyholder causes to others. | Third-party exposures |
| **Limit** | The most a coverage will pay. | `coverage_limit`, `exposure_limit` |
| **Line of business (LOB)** | A type of insurance (auto, homeowners). | `header.lob` |
| **Loss** | The event or the money lost; also the amount paid on a claim. | `loss_date`, `loss_cause` |
| **Loss of use** | Home coverage for living costs while the house is unlivable. | `lu_lud` |
| **Loss ratio** | Claim costs divided by premium earned. | not in data (no premium) |
| **Matter** | A lawsuit, in claim-system language. | `matters` |
| **Negligence** | Failing to take reasonable care, which makes someone legally responsible for harm. | The basis of `insured_fault_pct` |
| **Net incurred** | Incurred minus recoveries. | Reserve minus `Recovery` |
| **No-fault** | A system where each driver's own insurer pays their medical bills regardless of fault. | PIP coverage |
| **Note** | A text entry in the claim file. | `notes` |
| **Offer** | The dollar amount the insurer proposes to settle an injury claim. | `negotiations.line_type = 'offer'` |
| **Open / closed** | Whether the claim or exposure is still being worked. | `claim_state`, `state` |
| **Outstanding reserve** | Reserve minus paid: money still expected to be paid. | Computed |
| **Paid** | Money already sent out. | Submitted `Payment` rows |
| **PIP (personal injury protection)** | No-fault coverage paying the policyholder's own medical bills and related costs. | `pip_*` |
| **Plaintiff** | The person who files a lawsuit. | `role = 'plaintiff_attorney'` |
| **Policy** | The insurance contract. | not in data |
| **Premium** | The price of a policy. | not in data |
| **Pure premium** | Expected loss per policy: frequency times severity. | needs policy counts |
| **Recovery** | Money the insurer gets back after paying (subrogation or salvage). | `Recovery` rows |
| **Reopen** | Reactivating a closed claim. | not in data |
| **Reserve** | The insurer's estimate of what a claim will cost. A forecast, not a payment. | `Reserve` rows |
| **Salvage** | The wreck of a total-loss vehicle, sold to recover part of the payment. | `recovery_category = 'salvage'` |
| **Segment** | A complexity category that routes a claim to a team. | `exposures."SegmentName"` |
| **Service (of process)** | Formally delivering lawsuit papers to the defendant. | `matters.service_date` |
| **Settlement** | An agreement that ends a claim for an agreed payment. | `payment_type = 'final'` |
| **Severity** | The average cost of a claim. | Paid per claim |
| **Subrogation** | Collecting from the at-fault party after paying your own policyholder. | `recovery_category = 'subrogation'` |
| **Supplement** | An additional payment after an earlier one (more damage found). | `payment_type = 'supplement'` |
| **Supervisor** | The manager who approves large payments and reserve changes. | `Claims Supervisor` |
| **Third-party** | A person who is not the policyholder but is affected by the policyholder's actions. | `role = 'third_party'` |
| **Total loss** | A vehicle too costly to repair, so the insurer pays its value. | `incidents.total_loss` |
| **UM / UIM** | Uninsured / underinsured motorist coverage: your insurer pays your injuries when the at-fault driver cannot. | `uim_bid`, `udim_bid` |
| **Underwriting** | Deciding whom to insure, on what terms and at what price. | not in data |
| **Void** | Cancelling a payment (such as a lost check) so it can be reissued. | `status = 'voided'` |
