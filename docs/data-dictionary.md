# Synthetic Claims Database: Data Dictionary

Nov 20, 2026

A complete guide to the 13 tables in the Neon Postgres database `neondb` (project "Cougar Insurance Claims", schema `public`). Written for someone who has never seen this data and has never worked in insurance.

|  |  |
| --- | --- |
| **What it is** | 20,000 **synthetic** (fake) insurance claims: 85% auto, 15% homeowner property. Every claim, person, vehicle, firm and note is generated. None of it is real. |
| **Size** | 13 tables, about 2.34 million rows, 467 MB. |
| **Time span** | Losses from 2024-01-01 to 2026-09-24. The data is frozen at an "as-of" moment of **2026-10-07 12:00:00**. Nothing is dated after it. |
| **Source** | CSV files made by a synthetic claims generator (seed 7), loaded into Neon one table per file. This document describes the database. |
| **Modeled on** | How a modern claims system is meant to be used, with complete and consistent record keeping. Real claim data is usually messier. |

**In this document:** 1 Start here, 2 Insurance vocabulary, 3 How the tables connect, 4 Conventions and gotchas, 5 Table catalog, 6 Column dictionary (every column of every table), 7 Code lists, 8 The change log in depth, 9 A worked example, 10 Query cookbook, 11 What the data guarantees and leaves out.

## 1. Start here: the 60-second picture

An insurance **claim** starts when a policyholder reports a loss: a fender bender, a hailstorm, a burst pipe. The insurance company opens a file, decides what its policy covers, pays for the damage, and closes the file. This database records that whole life for 20,000 claims.

Four ideas explain almost everything:

1. **One claim, many exposures.** A claim is the event ("I hit a deer"). An **exposure** is one coverage's piece of that event ("collision damage to my car", "rental car", "tow"). A claim has 1 to 8 exposures. Money, work items and notes usually attach to an exposure.
2. **Everything points back to `claim_id`.** Every table except `users` has a `claim_id` column. Start at `header` (one row per claim) and join outward.
3. **Money is a ledger of events.** The `money` table does not hold a balance. It holds one row per reserve change, payment and recovery. You add rows up to get totals (section 10 shows how).
4. **Nothing is overwritten without a trace.** Tables show the *current* value of each row. `change_log` records every edit (who, when, old value, new value), so you can see how a claim looked at any past moment.

**If you only read three sections:** section 3 (how tables connect), section 4 (gotchas), section 10 (queries you can copy).

How the tables relate (`──<` means "one to many"):

```
 header (claim) ──< exposures ──< money (reserves, payments, recoveries)
      │                  │    └──< activities (tasks), notes (adjuster text)
      │                  ├── coverages (limit + deductible)
      │                  ├── incidents ── vehicles (auto only)
      │                  └──< contact_roles (attorney), negotiations, matters (lawsuit)
      └── activities, notes, money, vehicles... also carry claim_id directly

 change_log = the edit history of header, exposures, money, activities, incidents, matters
 users      = the people whose names appear in the *_name columns
```

## 2. Insurance vocabulary

You do not need to be an adjuster. These are all the terms the column definitions rely on.

| Term | Plain-English meaning | Where you see it |
| --- | --- | --- |
| **Policyholder / insured** | The customer who bought the insurance. | `incidents.role = 'insured'`, `exposures."LossPartyName" = "Insured's loss"` |
| **Claimant / third party** | A person who is *not* the customer but is making a claim against the customer (the other driver, an injured guest). | `role = 'third_party'`, `"LossPartyName" = 'Third-party liability'` |
| **Loss** | The bad event: crash, hail, theft, fire, leak. | `header.loss_date`, `loss_cause`, `loss_description` |
| **FNOL** (First Notice of Loss) | The first report of the loss, usually a phone call. | note topic `First notice of loss`; `header.reported_date` |
| **Adjuster** | The employee who investigates and settles a claim. | every `*_name` column; `users` |
| **Claim** | The file for one loss. | `header` |
| **Coverage** | A specific protection in the policy (collision, rental, bodily injury...). | `coverages`, `coverage_subtype` |
| **Exposure** | One coverage's part of a claim; the unit that gets money and a closing date. | `exposures` |
| **Limit** | The most the policy will pay under a coverage. | `coverage_limit`, `exposure_limit` |
| **Deductible** | The first dollars of a loss the policyholder pays themselves. | `coverages.deductible` |
| **Indemnity** | Money paid to cover the loss itself (repair bill, medical bill, settlement). | `cost_type = 'COUGAR_indemnity'` |
| **Expense** | Money the insurer spends to handle the claim, not to cover the loss: inspections and reports (`aoexpense`) and legal fees (`dccexpense`). | `cost_type` |
| **Reserve** | The insurer's running estimate of how much a claim will cost in total. A forecast, not a payment. | `money.subtype = 'Reserve'` |
| **Payment** | Money actually sent out (by check). | `money.subtype = 'Payment'` |
| **Void** | Cancel a payment (for example a lost check) and re-issue it. | `money.status = 'voided'` |
| **Recovery** | Money the insurer gets back after paying. | `money.subtype = 'Recovery'` |
| **Subrogation** | Getting back what you paid from the party that caused the loss, usually their insurer. | `recovery_category = 'subrogation'` |
| **Salvage** | Selling a wrecked car for scrap value after paying it off as a total loss. | `recovery_category = 'salvage'` |
| **Total loss** | The car costs more to fix than it is worth, so the insurer pays its value instead. | `incidents.total_loss` |
| **ACV** (Actual Cash Value) | What the car was worth just before the loss. | `incidents.vehicle_acv` |
| **Liability decision / fault** | Deciding who caused an accident and by what percentage. | `header.insured_fault_pct` |
| **PIP** (Personal Injury Protection) | No-fault coverage that pays the policyholder's own medical bills, lost income and similar costs. | `exposure_type = 'PIPDamages'`, `pip_*` coverage codes |
| **BI** (Bodily Injury) | Coverage for injuries the insured caused to *other* people. | `exposure_type = 'BodilyInjuryDamage'` |
| **UM / UIM** | Uninsured / underinsured motorist coverage: pays the policyholder when an at-fault driver has no or too little insurance. | `uim_bid`, `udim_bid` |
| **PD** (Property Damage) | Damage to things (a car, a house, a fence) as opposed to people. | `apd_*`, `dwl_pd`, `os_pd`, `pli_pd` |
| **Demand / offer** | In an injury claim, the claimant's lawyer *demands* a sum and the insurer *offers* a sum until they agree. | `negotiations` |
| **Matter / suit** | A lawsuit. "Matter" is the claim system's word for it. | `matters` |
| **Service** | Formally delivering the lawsuit papers to the defendant. | `matters.service_date` |
| **Activity / diary** | A to-do task on a claim ("get police report", "check back in 30 days"). | `activities` |
| **Segment** | A label that sorts a claim by complexity so it is routed to the right team. | `exposures."SegmentName"` |
| **Team / group** | The adjuster team that works a claim. Names start with `#`. | `assigned_group`, `users."group"` |
| **Bean version** | A counter the claim system keeps on each row to detect edits. | `bean_version` on every table |

## 3. How the tables connect

### 3.1 Keys

Every table has a single-column primary key (a unique ID) **except `contact_roles`**, which has none (one row per attorney assignment, identified by `exposure_ref`). Each ID type counts up from its own block of numbers, so an ID tells you what it is:

| ID column | Table | Starts at | Count |
| --- | --- | --- | --- |
| `claim_id` | header | 900001 | 20,000 |
| `exposure_pk` | exposures | 9000001 | 31,535 |
| `coverage_id` | coverages | 9100001 | 31,535 |
| `matter_id` | matters | 9200001 | 263 |
| `negotiation_id` | negotiations | 9300001 | 1,634 |
| `user_id` | users | 9400001 | 90 |
| `vehicle_id` | vehicles | 9500001 | 24,856 |
| `incident_id` | incidents | 9600001 | 24,856 |
| `txn_id` | money | 90000001 | 133,526 |
| `act_pk` | activities | 95000001 | 298,247 |
| `note_id` | notes | 97000001 | 298,013 |
| `change_id` | change\_log | 9700001 | 1,475,475 |

`change_log.event_id` starts at 9800001. `claim_number` is a separate, human-facing number: `claim_id + 8,100,000`.

### 3.2 Join map

The database has **no foreign-key constraints** (only primary keys), so nothing stops you joining on the wrong column. Use this table. All 21 relationships below were tested: there are **zero orphan rows** in any of them.

| From table | Column | To table | Column | Notes |
| --- | --- | --- | --- | --- |
| exposures, money, activities, notes, vehicles, incidents, coverages, matters, negotiations, contact\_roles, change\_log | `claim_id` | header | `claim_id` | many-to-one |
| money, activities, notes, matters, negotiations, contact\_roles | `exposure_ref` | exposures | `exposure_pk` | many-to-one. **Empty on claim-level activities and notes**, so use `LEFT JOIN` |
| exposures | `coverage_id` | coverages | `coverage_id` | one-to-one |
| exposures | `incident_id` | incidents | `incident_id` | many-to-one. Empty for injury and property exposures |
| incidents | `vehicle_id` | vehicles | `vehicle_id` | one-to-one |
| notes | `activity_ref` | activities | `act_pk` | many-to-one. Empty for notes not tied to a task |
| change\_log | `table_name` + `row_id` | the table named | its key (see section 8) | polymorphic: `row_id` means a different key depending on `table_name` |
| header, exposures, money, activities, notes, change\_log | `*_name` columns (`assigned_name`, `created_by_name`, `author_name`, `changed_by`, ...) | users | `name` | joins on the **name text**, not on `user_id` |

### 3.3 Cardinalities worth knowing

- 1 claim has 1 to 8 exposures (average 1.6). 13,451 claims have exactly one.
- 1 exposure has 1 to 15 money rows (average 4.2) and exactly one `coverages` row.
- An auto claim has 1 insured vehicle and sometimes 1 third-party vehicle (7,864 claims). Property claims have no vehicles or incidents.
- An injury exposure may have one attorney (`contact_roles`), several demand/offer lines (`negotiations`) and at most one lawsuit (`matters`).

## 4. Conventions and gotchas

**Types.** Only five Postgres types are used: `integer`, `numeric` (exact decimal, used for all dollar amounts), `boolean`, `timestamp` (`timestamp without time zone`) and `text`. Every column in section 6 shows its type.

**Time.** All timestamps are naive: no time zone, no daylight-saving adjustment. `header.loss_date` always has time `00:00:00` (it is a date stored as a timestamp). Subtract two timestamps to get an interval; use `extract(epoch from ...) / 86400` for days.

**Empty values are `NULL`.** There are no empty strings. A `NULL` nearly always has a meaning (for example a `close_date` that is `NULL` means "not closed yet"). Section 6 shows how often each column is empty.

**Booleans** are real Postgres booleans (`true` / `false`).

**Money.** US dollars, two decimals, type `numeric`. Reserve rows can be negative (they are *changes*). Payments and recoveries are positive.

**Identifier quoting.** Three columns need double quotes in SQL:

| Column | Why |
| --- | --- |
| `exposures."SegmentName"` | capital letters (Postgres lower-cases unquoted names) |
| `exposures."LossPartyName"` | capital letters |
| `users."group"` | `group` is a reserved word |

Every other table and column name is lower case with underscores.

**Names, not IDs, link people.** `assigned_name`, `created_by_name`, `closed_by_name`, `author_name` and `changed_by` hold the person's name as text. Join them to `users.name` (unique). There is no user ID in those tables.

**Redundant columns exist on purpose.** `money.exposure_type` and `money.coverage_subtype` repeat the exposure's values; `exposures.coverage_limit` repeats `coverages.exposure_limit`; `header.loss_type` repeats `header.lob` in upper case; `matters.file_date` and `filing_date` are identical; `money.net_amount` and `original_amount` equal `amount`. They were kept because real claim extracts have them.

**Always-empty columns.** `exposures.reopen_date` and `coverages.incident_limit` are empty on every row, which is why Postgres stores them as `text`. `activities.retired` is always `0`.

**Add indexes before heavy analysis.** The tables have primary keys but no other indexes, so a filter on `claim_id` in a big table (`change_log`, `activities`, `notes`) scans the whole table. This is fine for occasional queries. For repeated use, run for example `CREATE INDEX ON change_log (claim_id);`.

**It is synthetic.** Names, firms, cities, vehicles, VINs, plates and note text are invented. Utah city names and the court name are real place names only. Patterns are cleaner than real life (section 11).

## 5. Table catalog

| Table | One row is... | Rows | Primary key |
| --- | --- | --- | --- |
| `header` | a **claim** | 20,000 | `claim_id` |
| `exposures` | an **exposure**: one coverage's share of a claim | 31,535 | `exposure_pk` |
| `coverages` | the **coverage, limit and deductible** behind one exposure | 31,535 | `coverage_id` |
| `money` | a **financial transaction** (reserve change, payment, recovery) | 133,526 | `txn_id` |
| `activities` | a **task** (diary, review, decision, inspection) | 298,247 | `act_pk` |
| `notes` | an **adjuster note** | 298,013 | `note_id` |
| `vehicles` | a **vehicle** in an auto loss | 24,856 | `vehicle_id` |
| `incidents` | what happened to **one vehicle** (impact, damage) | 24,856 | `incident_id` |
| `contact_roles` | an **attorney** on an injury exposure | 789 | none |
| `negotiations` | a **demand or offer** on an injury exposure | 1,634 | `negotiation_id` |
| `matters` | a **lawsuit** | 263 | `matter_id` |
| `users` | a **person** (adjuster, supervisor, intake, system) | 90 | `user_id` |
| `change_log` | one **changed column** in one edit event | 1,475,475 | `change_id` |

Facts about the claims themselves: 16,992 auto and 3,008 property; 18,535 closed and 1,465 open (7.3%); 7,832 have a liability decision; 263 lawsuits on 260 claims; 1,634 negotiation lines; 31,535 exposures.

## 6. Column dictionary, table by table

How to read the tables below: **Type** is the Postgres type. **Empty?** says whether the column can be `NULL`: *Never* means every row has a value; a percentage is the share of rows that are `NULL` (so a high number is normal for columns that only apply to some rows). **Definition** explains the column and, for coded columns, lists the values with row counts.

Every table ends with `update_time` and `bean_version`. These two columns work the same way everywhere:

- `bean_version` counts edits to a row. `1` = never edited. It equals 1 + the number of edit events the row has in `change_log`.
- `update_time` is when the row last changed (its creation time if never edited).

### header: claims

**One row per claim.** This is the hub table: start here and join outward on `claim_id`. It holds the claim-level facts: what happened, when, where, who owns it, whether it is open, and the fault decision.

| Column | Type | Empty? | Definition |
| --- | --- | --- | --- |
| `claim_id` | integer | Never | **Primary key.** Unique ID of the claim. Every other table carries a `claim_id` column that points back here. Values run 900001 to 920000 (20,000 claims). |
| `claim_number` | integer | Never | The 7-digit claim number a person would quote on the phone. Always starts with 9. In this data set it is always `claim_id + 8,100,000` (claim 900001 is claim number 9000001). Stored as a number, not text. |
| `lob` | text | Never | Line of business: `auto` (16,992 claims) or `pr` (property, meaning a homeowner claim; 3,008 claims). |
| `loss_type` | text | Never | Upper-case code for the same thing as `lob`: `AUTO` or `PR`. Redundant with `lob`; use either. |
| `claim_state` | text | Never | `open` (1,465 claims) or `closed` (18,535). A claim is `closed` only when every one of its exposures is closed. |
| `loss_date` | timestamp | Never | The day the loss happened (accident, storm, theft, fire, and so on). The time is always 00:00:00. Range 2024-01-01 to 2026-09-24. |
| `reported_date` | timestamp | Never | When the loss was reported to the insurer. On or after `loss_date`. |
| `claim_opened` | timestamp | Never | When the claim record was created in the claim system, a few minutes after `reported_date`. |
| `close_date` | timestamp | 7.3% | When the claim was closed. Empty while the claim is open. Equals the latest `close_date` of the claim's exposures. |
| `assigned_name` | text | Never | Name of the adjuster who owns the claim. Matches `users.name` (join on the name; there is no user-ID column here). 44 different people. |
| `assigned_title` | text | Never | The owner's job title. Five values: `Claims Adjuster`, `Inside Property Adjuster`, `Claims Assistant`, `Specialty Adjuster`, `Property Adjuster`. |
| `assigned_group` | text | Never | The team the claim is assigned to (names start with `#`, for example `#Express Care Team`). Always the team of the claim's first exposure (the one with the lowest `exposure_pk`). 11 teams; see the code lists. |
| `assignment_date` | timestamp | Never | When the claim was assigned to its owner, a few minutes after `claim_opened`. |
| `loss_cause` | text | Never | Short phrase for what caused the loss, for example `hail`, `theft`, `rear-end collision`, `burst pipe`, `lockout`. 29 values; see the code lists. |
| `loss_city` | text | Never | City where the loss happened. Ten Utah cities (Logan, St. George, Lehi, Cedar City, Provo, Sandy, Layton, Salt Lake City, Ogden, Orem), each about 10% of claims. |
| `loss_description` | text | Never | One- or two-sentence narrative of what happened, written the way the insured might report it. 3,663 distinct texts, 52 to 163 characters. |
| `insured_fault_pct` | integer | 60.8% | The insured driver's share of the blame, 0 to 100, set by the **liability decision**. Empty (12,168 claims) when no decision applies (no other party, comprehensive, tow, property) or the decision is not yet made. Decided claims: 5,237 at `100` (insured fully at fault), 1,765 at `0` (not at fault), 830 in between (shared fault). |
| `update_time` | timestamp | Never | When the row last changed. Equals the creation time if the row never changed. For `header` it is the claim-closing time on closed claims. |
| `bean_version` | integer | Never | Change counter. `1` means the row has never changed since it was created. It goes up by one for each later change event, so it equals 1 + the number of change events recorded for this row in `change_log`. On this table the value is 2 to 4: every claim is assigned (version 2), many get a liability decision, and closed claims get a closing change. |

### exposures: one coverage's share of a claim

**One row per exposure.** An exposure is one coverage's claim on a claim: for a car accident you might have a collision exposure (fix my car), a rental exposure (rent me a car), a tow exposure, and an injury exposure. Each has its own adjuster, limit, money and closing date. A claim has 1 to 8.

| Column | Type | Empty? | Definition |
| --- | --- | --- | --- |
| `exposure_pk` | integer | Never | **Primary key.** Unique ID of the exposure. Other tables call it `exposure_ref` when they point here. |
| `claim_id` | integer | Never | The claim this exposure belongs to. Joins to `header.claim_id`. A claim has 1 to 8 exposures (average 1.6; 13,451 claims have exactly one). |
| `exposure_type` | text | Never | Broad kind of exposure: `VehicleDamage` (19,899), `PropertyDamage` (3,892), `TowOnly` (3,578), `PIPDamages` (2,572), `BodilyInjuryDamage` (1,594). |
| `coverage_subtype` | text | Never | The specific coverage being claimed against, as a code such as `coll_vd` (collision) or `abi_bid` (auto bodily injury). 20 codes; see the coverage code list. |
| `state` | text | Never | `open` (1,831) or `closed` (29,704). |
| `create_time` | timestamp | Never | When the exposure was created. The first exposure of a claim is created when the claim opens; others (rental, tow, injury) follow days or weeks later. |
| `assignment_date` | timestamp | Never | When the exposure was assigned to its adjuster, shortly after `create_time`. |
| `close_date` | timestamp | 5.8% | When the exposure closed (after its last financial transaction). Empty while open (5.8% of rows). |
| `reopen_date` | text | Always | Always empty. Reopened exposures are not modeled. (Stored as `text` only because the column has no values to infer a type from.) |
| `assigned_name` | text | Never | Adjuster handling this exposure. Matches `users.name`. May differ from the claim owner in `header.assigned_name`. |
| `assigned_title` | text | Never | That person's job title (a label, not a key). |
| `assigned_group` | text | Never | Team handling this exposure (18 teams, for example `#Auto PIP Team`, `#Total Loss Team`, `#Bodily Injury - Litigation`). |
| `"SegmentName"` | text | Never | **Quoted identifier (capital letters).** The claim *segment*, a workflow label for how complex the exposure is and who should handle it, for example `Auto Fast Track`, `Auto Complex Injury`, `Property Large Loss`. 11 values; see the code lists. |
| `"LossPartyName"` | text | Never | **Quoted identifier.** Whose loss this is: `Insured's loss` (23,796; the policyholder is the one who was harmed or damaged) or `Third-party liability` (7,739; the insured damaged or hurt someone else, so the insurer pays that other party). |
| `coverage_id` | integer | Never | The coverage row behind this exposure. Joins to `coverages.coverage_id`. One-to-one. |
| `coverage_limit` | numeric | Never | The most the policy will pay on this exposure, in dollars. Same value as `coverages.exposure_limit`, repeated here for convenience. |
| `paid_to_date` | numeric | Never | Indemnity paid so far on this exposure, in dollars: the sum of its submitted (not voided) indemnity payments in `money`. Expense payments are not included. Verified equal to that sum on all 31,535 rows. |
| `limit_reached` | boolean | Never | `true` when something has been paid and `paid_to_date` has reached `coverage_limit` (2,402 exposures). Payments never go above the limit. |
| `incident_id` | integer | 25.6% | For vehicle-damage and tow exposures: the vehicle incident this exposure is about. Joins to `incidents.incident_id`. Empty (25.6%) for injury and property exposures. |
| `update_time` | timestamp | Never | When the row last changed. Equals the creation time if the row never changed. For a closed exposure it is the closing time. |
| `bean_version` | integer | Never | Change counter. `1` means the row has never changed since it was created. It goes up by one for each later change event, so it equals 1 + the number of change events recorded for this row in `change_log`. Values 2 to 9: assignment, each payment, and closing all add a version. |

### coverages: the limit and deductible behind an exposure

**One row per exposure** (one-to-one with `exposures` through `coverage_id`). Holds the policy terms that apply: the limit and the deductible.

| Column | Type | Empty? | Definition |
| --- | --- | --- | --- |
| `coverage_id` | integer | Never | **Primary key.** Unique ID of the coverage row. Joins to `exposures.coverage_id`. There is exactly one coverages row per exposure. |
| `claim_id` | integer | Never | The claim this coverage belongs to. Joins to `header.claim_id`. |
| `coverage_subtype` | text | Never | Coverage code, same codes as `exposures.coverage_subtype`. |
| `exposure_limit` | numeric | Never | The limit for this coverage, in dollars (100 to 900,000). For collision and comprehensive it is the vehicle's actual cash value; for dwelling it is the insured dwelling amount; for injury coverages it is the policy limit. |
| `incident_limit` | text | Always | Always empty. A per-incident limit is not modeled. (Stored as `text` only because there are no values to infer a type from.) |
| `deductible` | integer | Never | The deductible in dollars: the part of a loss the policyholder pays first. Collision and comprehensive: `250`, `500` or `1000`. Dwelling, other structures and personal property: `1000` or `2500`. Every other coverage (liability, injury, PIP, rental, tow, loss of use): `0` (16,242 rows). |
| `update_time` | timestamp | Never | When the row was created. Rows in this table are never edited, so this is also the last-change time. Same as the creation time of the exposure. |
| `bean_version` | integer | Never | Always `1`. Rows in this table are never edited after creation, so the counter never moves. |

### money: reserves, payments and recoveries

**One row per financial transaction.** This is the claim ledger. Nothing here is a balance; you sum rows to get totals. How to read it:

- **Reserve** rows say how much the insurer expects to spend. Each row is a *change* to the reserve (positive raises it, negative lowers it). The current reserve of an exposure is the sum of its `Reserve` rows.
- **Payment** rows are money actually paid. Total paid = sum of `Payment` rows with `status = 'submitted'`.
- **Outstanding reserve** = reserve minus paid. On a closed exposure it is exactly zero for every cost type (checked on all closed exposures).
- **Recovery** rows are money received back (subrogation or salvage); **RecoveryReserve** rows are the expected recovery.
- **Voids:** a voided payment stays in the table with `status = 'voided'`, and a new submitted payment for the same amount replaces it. Counting `voided` rows as payments would double count. All 792 voided payments have a matching replacement.

| Column | Type | Empty? | Definition |
| --- | --- | --- | --- |
| `txn_id` | integer | Never | **Primary key.** Unique ID of the financial transaction. |
| `claim_id` | integer | Never | The claim the transaction belongs to. Joins to `header.claim_id`. |
| `exposure_ref` | integer | Never | The exposure the transaction belongs to. Joins to `exposures.exposure_pk`. Never empty: every transaction is on an exposure. |
| `exposure_type` | text | Never | The exposure's `exposure_type`, repeated here so you do not have to join. |
| `coverage_subtype` | text | Never | The exposure's coverage code, repeated here. |
| `subtype` | text | Never | What kind of transaction this is. `Reserve` (73,489): a change to the money set aside. `Payment` (52,277): money paid out. `RecoveryReserve` (5,252): money the insurer expects to get back. `Recovery` (2,508): money actually received back. |
| `status` | text | Never | `submitted` (132,734): in effect. `voided` (792): a payment that was cancelled. Every voided payment is followed by a replacement payment for the same amount, so count only `submitted` rows to avoid double counting. |
| `cost_type` | text | Never | Which bucket the money belongs to. `COUGAR_indemnity` (107,900): the loss itself. `aoexpense` (24,410): adjusting expense, small fees to run the claim (inspections, reports). `dccexpense` (1,216): defense and cost containment, i.e. legal fees. |
| `cost_category` | text | Never | A second label that always goes with `cost_type`: `indemnity` for `COUGAR_indemnity`, `COUGAR_otherphysdam` for `aoexpense`, `COUGAR_legalLiability` for `dccexpense`. Carries no extra information. |
| `payment_type` | text | 60.8% | Payments only (empty on 60.8% of rows): `final` (39,884) closes out the exposure's payments, `partial` (7,765) is a payment along the way, `supplement` (4,628) is an additional payment after an earlier one. |
| `recovery_category` | text | 94.2% | Recovery and recovery-reserve rows only (empty on 94.2% of rows): `subrogation` (money collected from the at-fault party's insurer) or `salvage` (money from selling a total-loss vehicle). |
| `create_time` | timestamp | Never | When the transaction was created. |
| `submit_date` | timestamp | Never | When the transaction took effect. Equals `create_time` unless it needed a supervisor's approval, in which case it is a few hours later. |
| `amount` | numeric | Never | Dollar amount. Payments, recoveries and recovery reserves are positive (a recovery reserve can also be negative when an expected recovery is reduced). Reserve rows are *changes*: positive raises the reserve, negative lowers it (range -205,652.92 to +352,980.27). |
| `net_amount` | numeric | Never | Always equal to `amount` in this data set. (In a real claim system it would be the amount after deductions.) |
| `original_amount` | numeric | Never | Always equal to `amount` in this data set. (In a real system it would be the amount before later adjustment.) |
| `check_issue_date` | timestamp | 60.8% | Payments only: when the check was issued. Empty on non-payment rows (60.8%). |
| `check_clear_date` | timestamp | 61.7% | Payments only: when the check cleared the bank. Empty if the check has not cleared yet, was voided, or the row is not a payment (61.7%). |
| `check_status` | text | 60.8% | Payments only: `cleared` (51,135), `issued` (350, not yet cleared) or `voided` (792). |
| `created_by_name` | text | Never | Person who created the transaction. Matches `users.name`. |
| `created_by_title` | text | Never | Their job title. |
| `created_by_dept` | text | Never | Their department. |
| `update_time` | timestamp | Never | When the row last changed. Equals the creation time if the row never changed. Changes on approval, check issue, check clearing and voiding. |
| `bean_version` | integer | Never | Change counter. `1` means the row has never changed since it was created. It goes up by one for each later change event, so it equals 1 + the number of change events recorded for this row in `change_log`. Values 1 to 4: approval, check issue and check clearing each add a version. |

### activities: tasks

**One row per task (activity).** Activities are the claim's to-do list: required steps (verify coverage, get the police report), approvals, and diary reminders. Each is created, then completed (or still open). 55.6% are claim-level (`exposure_ref` empty); the rest belong to one exposure.

| Column | Type | Empty? | Definition |
| --- | --- | --- | --- |
| `act_pk` | integer | Never | **Primary key.** Unique ID of the activity (a task). |
| `claim_id` | integer | Never | The claim the activity belongs to. Joins to `header.claim_id`. |
| `exposure_ref` | integer | 55.6% | The exposure the activity is about. Joins to `exposures.exposure_pk`. Empty (55.6%) for claim-level activities such as `Review New Claim`. |
| `create_time` | timestamp | Never | When the activity was created (when the task was assigned or scheduled). |
| `close_date` | timestamp | 0.3% | When the activity was completed. Empty while open (877 rows, all on open claims). Always on or after `create_time`. |
| `subject` | text | Never | Standard task title for the activity pattern, for example `Verify coverage`, `Get police report`, `Review and approve new payment`. 33 values. |
| `description` | text | Never | The task's own text. Identical to `subject` except for `General reminder (diary)` tasks, whose description is one of `Diary: confirm repair status`, `Diary: follow up on outstanding documents` or `Diary: review reserves`. |
| `status` | text | Never | `complete` (297,370) or `open` (877). |
| `retired` | integer | Never | Always `0`. Present for compatibility with the source system's layout; ignore it. |
| `pattern_code` | text | Never | The machine name of the activity template, one-to-one with `subject`. 33 values; see the activity list. Prefer this column when filtering. |
| `opened_by_name` | text | Never | Who created the activity. `System User` (the automation) created 163,822 of them. |
| `opened_by_title` | text | Never | Their title (`Automated Process` for the system user). |
| `opened_by_dept` | text | Never | Their department (`Claims Operations` for the system user). |
| `closed_by_name` | text | 0.3% | Who completed it. Empty while open. Matches `users.name`. |
| `closed_by_title` | text | 0.3% | Their title. |
| `closed_by_dept` | text | 0.3% | Their department. |
| `update_time` | timestamp | Never | When the row last changed. Equals the creation time if the row never changed. For a completed activity it is the completion time. |
| `bean_version` | integer | Never | Change counter. `1` means the row has never changed since it was created. It goes up by one for each later change event, so it equals 1 + the number of change events recorded for this row in `change_log`. `1` for open activities (877), `2` for completed ones (completion is the only edit). |

### notes: adjuster notes

**One row per note.** The free-text record adjusters write as they work. The `body` column is the only long text field in the database; it is generated from templates, so it is consistent with the structured data but repetitive (118,379 distinct bodies in 298,013 notes). About 56% of notes are tied to an exposure and about 72% to the activity they document.

| Column | Type | Empty? | Definition |
| --- | --- | --- | --- |
| `note_id` | integer | Never | **Primary key.** Unique ID of the note. |
| `claim_id` | integer | Never | The claim the note is about. Joins to `header.claim_id`. |
| `exposure_ref` | integer | 44.1% | The exposure the note is about. Joins to `exposures.exposure_pk`. Empty (44.1%) for claim-level notes. |
| `exposure_type` | text | 44.1% | That exposure's `exposure_type`. Empty whenever `exposure_ref` is empty. |
| `coverage_subtype` | text | 44.1% | That exposure's coverage code. Empty whenever `exposure_ref` is empty. |
| `activity_ref` | integer | 27.6% | The activity this note documents (for example the note written when `Verify coverage` was completed). Joins to `activities.act_pk`. Empty (27.6%) for notes not tied to an activity. |
| `activity_subject` | text | 27.6% | The `subject` of that activity. Empty whenever `activity_ref` is empty. |
| `authoring_date` | timestamp | Never | When the note was written. Always equal to `create_time`. |
| `create_time` | timestamp | Never | When the note was created. |
| `topic` | text | Never | Category of the note. 13 values: `General`, `Investigation`, `First notice of loss`, `Coverage`, `PIP`, `Property`, `Subrogation`, `Bodily Injury`, `Auto Glas/Roadside` (spelled this way in the data), `Rental`, `Salvage`, `Negotiation`, `Legal`. Never empty. |
| `subject` | text | Never | Short note title, for example `FNOL`, `Coverage verified`, `Estimate received`. 51 values. |
| `body` | text | Never | The note text, 23 to 639 characters. Generated from templates and consistent with the claim's other data (amounts, dates, impact point, fault). This is the only free-text column worth searching. |
| `author_dept` | text | Never | Author's department. |
| `author_title` | text | Never | Author's job title. |
| `author_name` | text | Never | Author's name. Matches `users.name`. |
| `update_time` | timestamp | Never | When the row was created. Rows in this table are never edited, so this is also the last-change time. |
| `bean_version` | integer | Never | Always `1`. Rows in this table are never edited after creation, so the counter never moves. |

### vehicles

**One row per vehicle in an auto loss**, one-to-one with `incidents`. Property claims have none.

| Column | Type | Empty? | Definition |
| --- | --- | --- | --- |
| `vehicle_id` | integer | Never | **Primary key.** Unique ID of the vehicle. One vehicle per incident (`incidents.vehicle_id`). |
| `claim_id` | integer | Never | The claim the vehicle is part of. Joins to `header.claim_id`. Only auto claims have vehicles (16,992 claims). |
| `role` | text | Never | `insured` (16,992: the policyholder's vehicle) or `third_party` (7,864: the other party's vehicle in a multi-vehicle collision). At most one of each per claim. |
| `vin` | text | Never | 17-character Vehicle Identification Number with a valid check digit. Synthetic (starts with `9SY`). Unique. |
| `year` | integer | Never | Model year, 2004 to 2026. Skews new (most vehicles are 2018 or later). 2004 has 1,008 vehicles against 150 for 2005, so read 2004 as "2004 or older". |
| `make` | text | Never | Manufacturer. 13 values (Toyota, Honda, Ford, Chevrolet, Tesla, Hyundai, Jeep, Ram, Subaru, Mazda, Nissan, Dodge, Harley-Davidson). |
| `model` | text | Never | Model name. 19 values (for example `F-150`, `Camry`, `Model 3`). |
| `style` | text | Never | Body style: `Passenger car` (16,914), `Pickup` (6,155), `Van` (1,516), `Motorcycle` (271). |
| `color` | text | Never | Color. Eight values, roughly equal shares. |
| `license_plate` | text | Never | Synthetic plate in the form `A12 3BC`. |
| `plate_state` | text | Never | State of registration: `UT` (23,169), `AZ`, `ID`, `NV`, `WY`, `CO`. |
| `update_time` | timestamp | Never | When the row was created. Rows in this table are never edited, so this is also the last-change time. Same as the claim's `claim_opened`. |
| `bean_version` | integer | Never | Always `1`. Rows in this table are never edited after creation, so the counter never moves. |

### incidents: what happened to each vehicle

**One row per vehicle in an auto loss** (one-to-one with `vehicles`): where it was hit, what it was doing, how bad the damage is, what the repair costs. Vehicle-damage and tow exposures point here through `exposures.incident_id`.

| Column | Type | Empty? | Definition |
| --- | --- | --- | --- |
| `incident_id` | integer | Never | **Primary key.** Unique ID of the incident (what happened to one vehicle). Joins to `exposures.incident_id`. |
| `claim_id` | integer | Never | The claim. Joins to `header.claim_id`. |
| `vehicle_id` | integer | Never | The vehicle involved. Joins to `vehicles.vehicle_id`. One-to-one. |
| `role` | text | Never | `insured` or `third_party`. Same as `vehicles.role`. |
| `loss_party` | text | Never | `Insured's loss` or `Third-party liability`. Same idea as `exposures."LossPartyName"`. |
| `first_point_of_impact` | text | Never | Where on the vehicle it was first hit. Always one of a fixed list of 15 values (bumper, fender, door, quarter panel, rollover, and so on), plus `Non-collision (comprehensive loss)` for hail, theft, vandalism, fire and glass, and `No Damage` for breakdowns and roadside calls. See the code lists. |
| `vehicle_direction` | text | 22.6% | What the vehicle was doing, for example `Going straight`, `Backing up`, `Merging/changing lanes`. Empty (22.6%) when parked or when the loss was not a collision. |
| `vehicle_parked` | boolean | Never | `true` if the vehicle was parked at the time of the loss (4,345). A parked vehicle has no direction. |
| `vehicle_towed` | boolean | Never | `true` if the vehicle had to be towed (7,559). Roadside labor (lockout, flat tire, out of fuel) is not a tow. A towed vehicle is never drivable. |
| `total_loss` | boolean | Never | `true` if the vehicle was declared a total loss (1,244): repair would cost about as much as the car is worth. Same as `damage_severity = 'total_loss'`. |
| `damage_severity` | text | Never | `none` (2,192), `minor` (10,141), `moderate` (7,004), `severe` (4,275), `total_loss` (1,244). Set by comparing the repair estimate with the vehicle's value. |
| `damage_description` | text | Never | Plain-language description of the damage that matches the impact point and severity. 66 distinct texts. |
| `drivable` | boolean | Never | `true` if the vehicle could be driven after the loss (15,532). |
| `airbags_deployed` | boolean | Never | `true` if airbags deployed (1,822). Only on severe collisions. |
| `est_repair_cost` | numeric | 28.6% | The repair estimate in dollars (for a total loss, close to the vehicle's value). Empty (28.6%) when there is no damage or the estimate has not been received yet (the `quote` activity is not complete). |
| `vehicle_acv` | numeric | Never | The vehicle's **actual cash value** in dollars: what the car was worth just before the loss, from its age and model (2,500 to 47,000). |
| `update_time` | timestamp | Never | When the row last changed. Equals the creation time if the row never changed. Changes when the estimate arrives. |
| `bean_version` | integer | Never | Change counter. `1` means the row has never changed since it was created. It goes up by one for each later change event, so it equals 1 + the number of change events recorded for this row in `change_log`. `1` (7,101) if no estimate was logged, `2` (17,755) once the estimate was received. |

### contact\_roles: attorneys

**One row per attorney** assigned to a bodily-injury exposure. Exists only for represented claimants (789 rows, 774 claims). **This is the only table with no primary key.**

| Column | Type | Empty? | Definition |
| --- | --- | --- | --- |
| `claim_id` | integer | Never | The claim. Joins to `header.claim_id`. |
| `exposure_ref` | integer | Never | The injury exposure the attorney represents the claimant on. Joins to `exposures.exposure_pk`. One row per exposure (789 rows, 789 distinct exposures). |
| `role` | text | Never | Always `plaintiff_attorney`: a lawyer representing the injured person against the insured. |
| `firm` | text | Never | The law firm. Six fictional firms, 114 to 148 rows each. |
| `assigned_date` | timestamp | Never | When the attorney became involved. |
| `update_time` | timestamp | Never | When the row was created. Rows in this table are never edited, so this is also the last-change time. Same as `assigned_date`. |
| `bean_version` | integer | Never | Always `1`. Rows in this table are never edited after creation, so the counter never moves. |

### negotiations: demands and offers

**One row per demand or offer** on a represented bodily-injury exposure, in date order. A typical sequence is demand, offer, demand, offer, ...

| Column | Type | Empty? | Definition |
| --- | --- | --- | --- |
| `negotiation_id` | integer | Never | **Primary key.** Unique ID of the negotiation line. |
| `claim_id` | integer | Never | The claim. Joins to `header.claim_id`. |
| `exposure_ref` | integer | Never | The represented bodily-injury exposure being negotiated. Joins to `exposures.exposure_pk`. |
| `negotiation_date` | timestamp | Never | When the demand or offer was made. |
| `created_time` | timestamp | Never | When the line was entered. Equal to `negotiation_date`. |
| `line_type` | text | Never | `demand` (699: the claimant's attorney asks for money) or `offer` (935: the insurer offers money). |
| `party` | text | Never | Who made it: `claimant attorney` for demands, `insurer` for offers. |
| `amount` | numeric | Never | Dollars demanded or offered (0 to 328,900). A demand never exceeds the exposure's `coverage_limit` (checked on all 699). The last offer is often, but not always, the amount finally paid: it differs from `exposures.paid_to_date` on 109 of the 511 exposures that have offers. |
| `update_time` | timestamp | Never | When the row was created. Rows in this table are never edited, so this is also the last-change time. |
| `bean_version` | integer | Never | Always `1`. Rows in this table are never edited after creation, so the counter never moves. |

### matters: lawsuits

**One row per lawsuit.** A suit is filed on a bodily-injury exposure that has an attorney (263 suits, 260 claims, all filed by the as-of date). The matter is entered at filing and edited once, when it is served.

| Column | Type | Empty? | Definition |
| --- | --- | --- | --- |
| `matter_id` | integer | Never | **Primary key.** Unique ID of the lawsuit (a *matter* in claim-system language). |
| `claim_id` | integer | Never | The claim. Joins to `header.claim_id`. 263 suits on 260 claims. |
| `exposure_ref` | integer | Never | The bodily-injury exposure that is in suit. Joins to `exposures.exposure_pk`. One suit per exposure. |
| `file_date` | timestamp | Never | Date the suit was filed. Same as `filing_date`. |
| `filing_date` | timestamp | Never | Date the suit was filed (duplicate of `file_date`). |
| `service_date` | timestamp | Never | Date the suit papers were served on the insured, 3 to 30 days after filing. |
| `court` | text | Never | Always `Third District Court`. |
| `created_time` | timestamp | Never | When the matter was entered. Equals the filing date. |
| `update_time` | timestamp | Never | When the matter row last changed, which is the service date (service is the only edit). |
| `bean_version` | integer | Never | Always `2`: created at filing (version 1), then updated when served (version 2). |

### users: people

**One row per person** who appears in any `*_name` column: adjusters, supervisors, intake specialists, and one automated user (`System User`). Link to other tables **by name**.

| Column | Type | Empty? | Definition |
| --- | --- | --- | --- |
| `user_id` | integer | Never | **Primary key.** Unique ID of the person. Note that other tables refer to people by **name**, not by this ID. |
| `name` | text | Never | The person's (fictional) name. Unique. This is the value that appears in every `*_name` column elsewhere. |
| `title` | text | Never | Job title: `Claims Adjuster`, `Casualty Claims Adjuster`, `Casualty Claims Examiner`, `Inside Property Adjuster`, `Property Adjuster`, `Claims Intake Specialist`, `Salvage Specialist`, `Subrogation Specialist`, `Specialty Adjuster`, `Claims Supervisor`, `Claims Assistant`, `PIP Claim Assistant`, `Automated Process`. |
| `dept` | text | Never | Department: `Claims` (40), `Casualty Claims` (24), `Property Claims` (20), `Claims Intake` (5), `Claims Operations` (1, the automation). |
| `"group"` | text | Never | **Reserved word; write it as `"group"`.** The team the person belongs to (for example `#Auto PIP Team`). Supervisors are in `Claims Supervisors`, intake staff in `Claims Intake`, the automated user in `Claims Operations`. |
| `update_time` | timestamp | Never | When the row was created. Rows in this table are never edited, so this is also the last-change time. A fixed date, 2023-12-01 08:00, before the first claim. |
| `bean_version` | integer | Never | Always `1`. Rows in this table are never edited after creation, so the counter never moves. |

### change\_log: history of edits

**One row per changed column in one edit event.** Every table shows only the current value of each row. This table keeps the past: what changed, from what, to what, when and by whom. A row's first version is its creation (the row itself), so only later versions appear here. Section 8 explains how to use it.

| Column | Type | Empty? | Definition |
| --- | --- | --- | --- |
| `change_id` | integer | Never | **Primary key.** Unique ID of this log line. One line per changed column. |
| `event_id` | integer | Never | Groups the lines that changed together. One event is one new version of one row (for example the three columns set when a claim is assigned). 594,322 events. |
| `table_name` | text | Never | Which table the changed row lives in: `activities` (892,110 lines), `money` (265,404), `exposures` (195,041), `header` (104,902), `incidents` (17,755), `matters` (263). The other tables are never edited. |
| `row_id` | integer | Never | Key of the changed row **in the table named by `table_name`**: `claim_id` for `header`, `exposure_pk` for `exposures`, `txn_id` for `money`, `act_pk` for `activities`, `incident_id` for `incidents`, `matter_id` for `matters`. The meaning of this column depends on `table_name`. |
| `claim_id` | integer | Never | The claim the changed row belongs to, repeated so a claim's whole history comes from one filter. |
| `bean_version` | integer | Never | The row's version number after this change. The first change is version 2. |
| `changed_at` | timestamp | Never | When the change happened. |
| `changed_by` | text | Never | Who made it: `System User` for automatic changes (assignment, check issue and clearing), otherwise a person's name from `users.name`. |
| `change_event` | text | Never | What happened, 13 values: see the change-event table. Each event name always changes the same table and columns. |
| `column_name` | text | Never | Which column changed. Names match the real columns of the table in `table_name`. |
| `old_value` | text | 68.3% | The value before the change, as text. Empty (68.3%) when the column had no value before (first assignment, first close date). |
| `new_value` | text | Never | The value after the change, as text. Timestamps are `YYYY-MM-DD HH:MM:SS`, amounts have two decimals, booleans are `True` or `False`. Cast it if you need a number or date. |

## 7. Code lists: what the coded values mean

Counts are rows in the table named.

### 7.1 Coverage codes (`coverage_subtype`, in `exposures`, `coverages`, `money`, `notes`)

| Code | Meaning | Exposure type | Exposures |
| --- | --- | --- | --- |
| `coll_vd` | **Collision.** Repair of the insured's own vehicle after a crash. | VehicleDamage | 6,900 |
| `comp_vd` | **Comprehensive.** The insured's own vehicle damaged by something other than a crash: hail, theft, glass, fire, animal. | VehicleDamage | 5,130 |
| `rental_vd` | **Rental car** while the insured's car is repaired. | VehicleDamage | 2,108 |
| `apd_vd` | **Auto property damage liability, vehicle.** The insured hurt someone else's vehicle; the insurer pays that driver. | VehicleDamage | 5,761 |
| `apd_pd` | Auto property damage liability, *other property* (a fence, a building). | PropertyDamage | 203 |
| `towlabor_towlabor` | **Towing and roadside labor** (tow, lockout, flat tire, fuel delivery). | TowOnly | 3,578 |
| `pip_medical_cougar` | **PIP medical** expense. | PIPDamages | 2,343 |
| `pip_income_loss_cougar` | PIP lost income. | PIPDamages | 135 |
| `pip_loss_srvce_cougar` | PIP loss of services (paying for household help the injured person can no longer do). | PIPDamages | 78 |
| `pip_funeral_cougar` | PIP funeral expense. | PIPDamages | 9 |
| `pip_survivor_cougar` | PIP survivor benefit. | PIPDamages | 7 |
| `abi_bid` | **Auto bodily injury liability.** The insured hurt another person; the insurer pays them. | BodilyInjuryDamage | 1,439 |
| `uim_bid` | Underinsured motorist bodily injury. | BodilyInjuryDamage | 44 |
| `udim_bid` | Uninsured / underinsured motorist bodily injury. | BodilyInjuryDamage | 31 |
| `pli_bi` | Personal liability, bodily injury (home policy: a guest is hurt). | BodilyInjuryDamage | 80 |
| `dwl_pd` | **Dwelling:** the house itself. | PropertyDamage | 2,414 |
| `ppd_ppd` | Personal property: belongings inside the home. | PropertyDamage | 744 |
| `lu_lud` | Loss of use: living costs while the home is unlivable. | PropertyDamage | 170 |
| `os_pd` | Other structures (garage, shed, fence on the property). | PropertyDamage | 105 |
| `pli_pd` | Personal liability, property damage (the insured damaged a neighbor's property). | PropertyDamage | 256 |

Each coverage code appears under exactly one exposure type, so `exposure_type` is a coarser grouping of `coverage_subtype`.

### 7.2 Exposure types (`exposure_type`)

| Value | Meaning | Exposures |
| --- | --- | --- |
| `VehicleDamage` | Anything about a car's repair or replacement, including rental and the other driver's car. | 19,899 |
| `PropertyDamage` | Damage to a home, belongings or someone else's property. | 3,892 |
| `TowOnly` | Towing and roadside service. | 3,578 |
| `PIPDamages` | PIP injury benefits to the policyholder side. | 2,572 |
| `BodilyInjuryDamage` | Injury claims by other people. | 1,594 |

### 7.3 Segments (`exposures."SegmentName"`)

A segment is the claim system's complexity label. (`Permisions` is spelled that way in the data.)

| Segment | Line | Exposures |
| --- | --- | --- |
| `Auto Fast Track` | auto | 14,138 |
| `Auto Liability No Injury` | auto | 5,964 |
| `Towing & Roadside` | auto | 3,578 |
| `Auto (PIP) non-Complex Injury` | auto | 2,556 |
| `Auto (BI) non-Complex Injury` | auto | 1,414 |
| `Auto Complex Injury` | auto | 100 |
| `Sensitive (Special Permisions)` | auto | 16 |
| `Property No Liability` | property | 3,275 |
| `Property Liability PD Only` | property | 256 |
| `Property Large Loss` | property | 158 |
| `Property non-Complex Injury` | property | 80 |

### 7.4 Teams (`assigned_group`)

Team names start with `#`. `header` uses 11 teams (always the team of the claim's first exposure, the one with the lowest `exposure_pk`); `exposures` uses 18.

| Team | Exposures | Claims (in `header`) |
| --- | --- | --- |
| `#Auto Liability No Injury Team` | 5,964 | 4,968 |
| `#Cougar Care Team (Repairable)` | 4,385 | 2,961 |
| `#Cougar NON-DRP Team (Repairable)` | 4,332 | 2,989 |
| `#Express Care Team` | 4,177 | 2,880 |
| `#Auto - Tow` | 3,578 | 2,192 |
| `#Auto PIP Team` | 2,556 | not a claim-owner team |
| `#Total Loss Team` | 1,244 | 1,002 |
| `#Home Exterior Damage Team` | 1,170 | 952 |
| `#Home Interior Damage Team` | 1,157 | 950 |
| `#Home Fire/Smoke Damage Claims Team` | 768 | 512 |
| `#Bodily Injury - BI/UM - No Attorney - Minor` | 728 | not a claim-owner team |
| `#Bodily Injury - BI/UM - Attorney - Minor` | 479 | not a claim-owner team |
| `#Home Contents Only/Theft` | 338 | 338 |
| `#Bodily Injury - Litigation` | 263 | not a claim-owner team |
| `#Home Condo/Townhome & Liability Claims Team` | 256 | 256 |
| `#Bodily Injury - BI/UM - Complex` | 67 | not a claim-owner team |
| `#Bodily Injury - UIM` | 57 | not a claim-owner team |
| `#Bodily Injury - Home or Fatality` | 16 | not a claim-owner team |

`users."group"` also lists `#Salvage Recovery` and `#Subro: Out-Bound Undisputed` (people who create recovery transactions) plus `Claims Supervisors`, `Claims Intake` and `Claims Operations`. No claim or exposure is assigned to those.

### 7.5 Causes of loss (`header.loss_cause`)

| Line | Causes (claims) |
| --- | --- |
| Auto, collisions | `rear-ended another vehicle` (2,395), `unsafe lane change` (2,015), `intersection collision` (934), `failed to yield at intersection` (884), `animal strike` (882), `rear-end collision` (670), `parked vehicle struck` (626), `single-vehicle collision` (620), `rollover` (596), `backed into object` (590), `head-on collision` (340) |
| Auto, non-collision (comprehensive) | `theft` (858), `vandalism` (855), `hail` (850), `glass break` (845), `fire` (840) |
| Auto, roadside | `flat tire` (600), `lockout` (549), `disabled vehicle` (523), `out of fuel` (520) |
| Property | `fire` (427), `burst pipe` (331), `hail` (327), `wind` (318), `freezing` (313), `tree fall` (307), `appliance leak` (306), `burglary` (177), `theft` (161), `damage to neighbor property` (141), `guest injury` (115), `major water loss` (85) |

`fire`, `hail` and `theft` occur on both auto and property claims, so filter on `lob` when you count them (for example `fire` is 840 auto + 427 property = 1,267 claims). There are 29 distinct values in all. Note: animal strike is listed with the collisions because the vehicle has a recorded point of impact, but it is paid under comprehensive coverage (comp\_vd, 882 exposures), as are theft, vandalism, hail, glass break and fire on auto claims.

### 7.6 Activity patterns (`activities.pattern_code` and `subject`)

`pattern_code` is the machine name; `subject` is the title people see. They are one-to-one. (`interview_claimant`'s subject is spelled `statment` in the data.)

| Group | `pattern_code` : `subject` (rows) |
| --- | --- |
| Intake and review | `COUGAR_Review_New_Claim`: Review New Claim (20,000). `COUGAR_Verify_Coverage`: Verify coverage (20,000). `COUGAR_Complete_Hours`: Complete 8 hour contact (20,000). `COUGAR_Complete_Investigation`: Complete investigation (20,000). `COUGAR_Review_New_Exposure`: Review New Exposure (31,535). `iso_matches`: ISO matches found (5,973). `follow_up_insured`: Follow Up with insured (2,969). |
| Diaries (reminders) | `30_day_diary` (12,254), `60_day_diary` (6,318), `90_day_diary` (4,421), `general_reminder`: General reminder (diary) (14,818) |
| Approvals and checks | `approve_payment`: Review and approve new payment (20,729). `approve_reserve_change`: Review and approve reserve change (7,769). `COUGAR_Void_Check_Complete`: Void Check Complete (792). |
| Liability | `COUGAR_Fault_Analysis`: No fault analysis (5,761). `determine_claim_decision`: Determine claim decision (7,864). |
| Evidence gathering | `police_report`: Get police report (4,677). `get_statement_insured driver`: Obtain recorded statement from insured driver (6,663). `interview_claimant`: Obtain recorded statement from claimant driver (5,154). `witness_statement`: Get a statement from witness (1,347). `vehicle_inspection`: Get vehicle inspected (5,147). `scene_inspection`: Get accident scene inspected (665). `property_inspection`: Get property inspected (2,414). |
| Estimates | `quote`: Get quote for repairs/replacement (20,205). `review_quote`: Review and approve quote for repairs/replacement (20,138). |
| Injury | `new_bill`: Review new bill received (8,904). `initial_med_report`: Get initial medical report (2,572). `medical_report_claimant`: Get claimant medical reports (1,510). `follow_up_treatment`: Follow up on treatment status (7,196). |
| Recovery | `subro_check`: Determine if opportunity for recovery (6,811). `COUGAR_New_Subro`: New Subrogation Referral (1,623). `COUGAR_Salvage_Notice`: Notify salvage carrier of vehicle (1,009). `salvage_vehicle`: Salvage Vehicle Status (1,009). |

### 7.7 Note topics (`notes.topic`)

`General` (140,011), `Investigation` (51,346), `First notice of loss` (20,000), `Coverage` (19,934), `PIP` (18,707), `Property` (15,707), `Subrogation` (10,015), `Bodily Injury` (7,413), `Auto Glas/Roadside` (6,979), `Rental` (4,081), `Salvage` (1,923), `Negotiation` (1,634), `Legal` (263).

### 7.8 Points of impact and directions (`incidents`)

`first_point_of_impact` (24,856 incidents): `Front bumper, grille, hood & radiator` (6,146), `Non-collision (comprehensive loss)` (4,248), `Rear bumper, rear body panel, trunk lid/ liftgate` (3,724), `No Damage` (2,192), `Right fender - side & wheel area` (1,294), `Left quarter panel` (1,251), `Left fender - side & wheel area` (1,216), `Right quarter panel` (1,154), `Left fender - front (headlamp area)` (928), `Right fender - front (headlamp area)` (874), `Rollover` (596), `Right front door` (334), `Right rear door` (306), `Left rear door` (300), `Left front door` (293).

`vehicle_direction` (empty on 5,622 incidents): `Going straight` (6,642), `Going through intersection` (3,636), `Stopped in traffic lane` (3,065), `Merging/changing lanes` (2,015), `Negotiating curve` (1,216), `Stopped on shoulder of road` (921), `Entering parking space` (626), `Backing up` (590), `Disabled in traffic lane` (523).

### 7.9 Money value combinations

Only these combinations of `subtype`, `status`, `cost_type`, `payment_type` and `recovery_category` exist:

| `subtype` | `status` | `cost_type` | `payment_type` | `recovery_category` | Rows |
| --- | --- | --- | --- | --- | --- |
| Reserve | submitted | COUGAR\_indemnity | (empty) | (empty) | 60,937 |
| Reserve | submitted | aoexpense | (empty) | (empty) | 12,131 |
| Reserve | submitted | dccexpense | (empty) | (empty) | 421 |
| Payment | submitted | COUGAR\_indemnity | final / partial / supplement | (empty) | 27,196 / 6,860 / 4,570 |
| Payment | submitted | aoexpense | final | (empty) | 12,082 |
| Payment | submitted | dccexpense | partial | (empty) | 777 |
| Payment | voided | COUGAR\_indemnity | final / partial / supplement | (empty) | 409 / 110 / 58 |
| Payment | voided | aoexpense | final | (empty) | 197 |
| Payment | voided | dccexpense | partial | (empty) | 18 |
| RecoveryReserve | submitted | COUGAR\_indemnity | (empty) | subrogation / salvage | 3,327 / 1,925 |
| Recovery | submitted | COUGAR\_indemnity | (empty) | subrogation / salvage | 1,594 / 914 |

Expense payments (`aoexpense`, `dccexpense`) appear only as payments and reserves, never as recoveries.

## 8. The change log in depth

### 8.1 What it is

`change_log` is an audit trail. Whenever a row in `header`, `exposures`, `money`, `activities`, `incidents` or `matters` is edited after creation, one line is written per changed column. The row itself always shows only the latest value.

Vocabulary: an **event** is one edit to one row (it can change several columns at once); the lines of one event share an `event_id`. After the event, the row's `bean_version` goes up by one, and that new number is stored on each line as `change_log.bean_version`.

`table_name` plus `row_id` identify the edited row:

| `table_name` | `row_id` is the... | Lines |
| --- | --- | --- |
| `header` | `header.claim_id` | 104,902 |
| `exposures` | `exposures.exposure_pk` | 195,041 |
| `money` | `money.txn_id` | 265,404 |
| `activities` | `activities.act_pk` | 892,110 |
| `incidents` | `incidents.incident_id` | 17,755 |
| `matters` | `matters.matter_id` | 263 |

Tables that are never edited have no lines and stay at version 1: `notes`, `coverages`, `vehicles`, `negotiations`, `contact_roles`, `users`.

### 8.2 The 13 change events

| `change_event` | Table | Columns changed | Made by | Lines |
| --- | --- | --- | --- | --- |
| `claim_assigned` | header | `assigned_name`, `assigned_group`, `assignment_date` | System User | 60,000 |
| `liability_decision` | header | `insured_fault_pct` | claim owner | 7,832 |
| `claim_closed` | header | `claim_state`, `close_date` | claim owner | 37,070 |
| `exposure_assigned` | exposures | `assigned_name`, `assigned_group`, `assignment_date` | System User | 94,605 |
| `payment_recorded` | exposures | `paid_to_date`, and `limit_reached` when the limit is hit | person who created the payment | 41,028 |
| `exposure_closed` | exposures | `state`, `close_date` | the exposure's adjuster | 59,408 |
| `approved` | money | `status` (`submitting` to `submitted`), `submit_date` | supervisor who approved | 56,996 |
| `check_issued` | money | `check_issue_date`, `check_status` (to `issued`) | System User | 104,554 |
| `check_cleared` | money | `check_status` (`issued` to `cleared`), `check_clear_date` | System User | 102,270 |
| `payment_voided` | money | `status` (`submitted` to `voided`), `check_status` (`issued` to `voided`) | a supervisor | 1,584 |
| `activity_completed` | activities | `status`, `close_date`, `closed_by_name` | person who completed it | 892,110 |
| `estimate_received` | incidents | `est_repair_cost` | person who completed the quote task | 17,755 |
| `suit_served` | matters | `service_date` | claim owner | 263 |

Things to know:

- Claims and exposures are created *unassigned* and assigned minutes later, so the "before" value of the first assignment is `NULL`.
- A payment that needs approval is created with `status = 'submitting'` and becomes `submitted` on approval. The `money` table shows only `submitted` / `voided`; the earlier `submitting` state exists only in `old_value`.
- Only the edits listed above are modeled. Reassignments, reopens, corrections and note edits are not.
- Columns that merely repeat another logged column (for example `assigned_title`, `closed_by_title`, `created_by_*`) are not logged separately.

### 8.3 Using the log

- **Find rows that changed:** `bean_version > 1`. **See how they changed:** look them up in `change_log`.
- **A claim's complete history in one query:** `WHERE claim_id = 900001 ORDER BY changed_at, change_id` (the log carries `claim_id` for exactly this reason).
- **Value as of a past date:** take the latest log line for that row and column at or before the date and read `new_value`; if there is none, the value had not been set yet (see the cookbook, query 9).
- **Consistency:** each line's `old_value` equals the previous line's `new_value` for the same row and column, and replaying the log reproduces every current value (this was checked when the data was generated).

## 9. Worked example: one claim from start to finish

Claim `900001` (claim number 9000001) is a simple, complete example. Each step names the table it comes from, so you can run the lookups yourself with the queries in section 10.

| Step | What happened | Table and values |
| --- | --- | --- |
| 1. The loss | On 2024-03-04 a rock struck the windshield of the insured's Red 2026 Nissan Altima on Redwood Road in Lehi. | `header`: `lob = auto`, `loss_cause = glass break`, `loss_city = Lehi`, `loss_date = 2024-03-04`. `vehicles` + `incidents`: the vehicle, `first_point_of_impact = Non-collision (comprehensive loss)`, `damage_severity = minor`, `vehicle_acv = 26,000`. |
| 2. Reported and opened | The insured phoned it in at 09:13:28 on 2024-03-05. The claim was created at 09:16:44. | `header.reported_date`, `claim_opened`. First note: topic `First notice of loss`, subject `FNOL`. |
| 3. Assigned | At 09:39:21 the system assigned it to Kendall Eastwick on `#Cougar Care Team (Repairable)`. | `header.assigned_name`, `assigned_group`. `change_log` event `claim_assigned` (3 lines), bringing `bean_version` to 2. |
| 4. Coverage and exposure | Coverage was verified and one exposure was set up: comprehensive (`comp_vd`), limit 26,000, deductible 1,000. | `exposures` row 9000001 (`exposure_type = VehicleDamage`). `coverages` row 9100001 (`exposure_limit = 26,000`, `deductible = 1,000`). Exposure assigned to Blake Castellan (event `exposure_assigned`). |
| 5. Estimate | The shop's estimate arrived on 2024-03-19: **2,230.48**. | `activities` pattern `quote` completed (event `activity_completed`). `incidents.est_repair_cost = 2,230.48` (event `estimate_received`). A `review_quote` task approved it on 2024-03-24. |
| 6. Reserve | On 2024-03-05 an indemnity reserve of **1,407.58** was set; on 2024-04-12 it was reduced by **-177.10**, to 1,230.48. A 45.00 expense reserve covered a small fee. | `money`: `subtype = Reserve`, `cost_type = COUGAR_indemnity` (two rows, 1,407.58 and -177.10) and `aoexpense` (45.00). |
| 7. Payment | A final payment of **1,230.48** was created on 2024-04-06 (the estimate 2,230.48 minus the 1,000 deductible). It needed approval; Tatum Sutter approved it, a check was issued 2024-04-07 and cleared 2024-04-12. A 45.00 expense payment was made on 2024-03-10. | `money`: `subtype = Payment`, `payment_type = final`, `check_status = cleared`. `change_log` events `approved`, `check_issued`, `check_cleared` (version 1 to 4). `exposures.paid_to_date = 1,230.48` (event `payment_recorded`). |
| 8. Close | On 2024-04-12 at 19:51:28 the exposure closed, then the claim. | `exposures.state = closed`, `close_date`; `header.claim_state = closed`, `close_date` (event `claim_closed`), final `header.bean_version = 3`. |

Notice that the reserve rows add up to the paid amount: 1,407.58 + (-177.10) = 1,230.48. That is the rule for every closed exposure (section 11).

Totals for this claim: 1 exposure, 1 coverage row, 1 vehicle, 1 incident, 5 money rows, 11 activities, 10 notes, and 55 change-log lines (header 5, exposures 6, incidents 1, money 10, activities 33).

For a claim with a lawsuit, look at claim `900062`: four exposures (collision, third-party vehicle, PIP medical, and an open auto bodily-injury exposure 9000097 with a $25,000 limit), one attorney in `contact_roles` (Wasatch Front Trial Attorneys), a demand of $25,000 in `negotiations`, and a lawsuit in `matters` (filed 2026-06-11, served 2026-06-30).

## 10. Query cookbook

Every query below was run against the live database. They use only columns described in section 6.

**1. One claim at a glance**

```sql
SELECT claim_id, claim_number, lob, claim_state, loss_date, loss_cause, loss_city,
       assigned_name, assigned_group, insured_fault_pct, close_date
FROM header
WHERE claim_id = 900001;
```

**2. All the exposures of a claim, with limit and amount paid**

```sql
SELECT e.exposure_pk, e.exposure_type, e.coverage_subtype, e.state,
       c.deductible, e.coverage_limit, e.paid_to_date, e.limit_reached
FROM exposures e
JOIN coverages c USING (coverage_id)
WHERE e.claim_id = 900001;
```

**3. Total indemnity paid per claim (largest first)**

```sql
SELECT claim_id, SUM(amount) AS indemnity_paid
FROM money
WHERE subtype = 'Payment' AND status = 'submitted' AND cost_type = 'COUGAR_indemnity'
GROUP BY claim_id
ORDER BY indemnity_paid DESC
LIMIT 10;
```

**4. Outstanding reserve on open exposures (reserve minus paid, indemnity only)**

```sql
SELECT e.exposure_pk, e.claim_id, e.coverage_subtype,
       COALESCE(SUM(m.amount) FILTER (WHERE m.subtype = 'Reserve'), 0) AS reserve,
       COALESCE(SUM(m.amount) FILTER (WHERE m.subtype = 'Payment' AND m.status = 'submitted'), 0) AS paid,
       COALESCE(SUM(m.amount) FILTER (WHERE m.subtype = 'Reserve'), 0)
     - COALESCE(SUM(m.amount) FILTER (WHERE m.subtype = 'Payment' AND m.status = 'submitted'), 0) AS outstanding
FROM exposures e
JOIN money m ON m.exposure_ref = e.exposure_pk AND m.cost_type = 'COUGAR_indemnity'
WHERE e.state = 'open'
GROUP BY e.exposure_pk, e.claim_id, e.coverage_subtype
ORDER BY outstanding DESC
LIMIT 10;
```

**5. Open claims by team**

```sql
SELECT assigned_group, COUNT(*) AS open_claims
FROM header
WHERE claim_state = 'open'
GROUP BY assigned_group
ORDER BY open_claims DESC;
```

**6. Average days from claim opening to closing, by line of business**

```sql
SELECT lob,
       ROUND(AVG(EXTRACT(EPOCH FROM (close_date - claim_opened)) / 86400)::numeric, 1) AS avg_days_to_close
FROM header
WHERE claim_state = 'closed'
GROUP BY lob;
```

**7. Total-loss vehicles with year, make, model and value**

```sql
SELECT h.claim_id, v.year, v.make, v.model, i.vehicle_acv, i.est_repair_cost
FROM header h
JOIN incidents i ON i.claim_id = h.claim_id AND i.role = 'insured'
JOIN vehicles v ON v.vehicle_id = i.vehicle_id
WHERE i.total_loss
ORDER BY i.vehicle_acv DESC
LIMIT 10;
```

**8. Lawsuits with the plaintiff's law firm and the number of demands**

```sql
SELECT m.matter_id, m.claim_id, m.filing_date, m.service_date, cr.firm,
       COUNT(n.negotiation_id) FILTER (WHERE n.line_type = 'demand') AS demands
FROM matters m
LEFT JOIN contact_roles cr ON cr.exposure_ref = m.exposure_ref
LEFT JOIN negotiations n ON n.exposure_ref = m.exposure_ref
GROUP BY m.matter_id, m.claim_id, m.filing_date, m.service_date, cr.firm
ORDER BY m.filing_date
LIMIT 10;
```

**9. The value of a column as of a past date (who owned claim 900001 at 09:30 vs 09:40 on 2024-03-05?)**

```sql
SELECT t.as_of,
       COALESCE((SELECT l.new_value
                 FROM change_log l
                 WHERE l.table_name = 'header' AND l.row_id = 900001 AND l.column_name = 'assigned_name'
                   AND l.changed_at <= t.as_of
                 ORDER BY l.changed_at DESC, l.change_id DESC
                 LIMIT 1), '(unassigned)') AS owner
FROM (VALUES ('2024-03-05 09:30:00'::timestamp), ('2024-03-05 09:40:00'::timestamp)) AS t(as_of);
```

**10. A claim's story: tasks and notes in time order**

```sql
SELECT create_time AS at, 'task' AS kind, subject AS what, status AS detail
FROM activities WHERE claim_id = 900001
UNION ALL
SELECT create_time, 'note', subject, LEFT(body, 80)
FROM notes WHERE claim_id = 900001
ORDER BY at, kind;
```

**11. Subrogation and salvage recovered, against indemnity paid, per claim**

```sql
SELECT claim_id,
       SUM(amount) FILTER (WHERE subtype = 'Payment' AND status = 'submitted' AND cost_type = 'COUGAR_indemnity') AS paid,
       SUM(amount) FILTER (WHERE subtype = 'Recovery' AND recovery_category = 'subrogation') AS subrogation_recovered,
       SUM(amount) FILTER (WHERE subtype = 'Recovery' AND recovery_category = 'salvage') AS salvage_recovered
FROM money
GROUP BY claim_id
HAVING SUM(amount) FILTER (WHERE subtype = 'Recovery') > 0
ORDER BY subrogation_recovered DESC NULLS LAST
LIMIT 10;
```

**12. Search the note text**

```sql
SELECT claim_id, topic, subject, LEFT(body, 100) AS excerpt
FROM notes
WHERE body ILIKE '%hail%'
LIMIT 10;
```

**13. Claims with shared fault (insured partly to blame)**

```sql
SELECT claim_id, loss_cause, insured_fault_pct
FROM header
WHERE insured_fault_pct > 0 AND insured_fault_pct < 100
ORDER BY claim_id
LIMIT 10;
```

**14. Everything that was edited on a claim, in order**

```sql
SELECT changed_at, table_name, row_id, change_event, column_name, old_value, new_value, changed_by
FROM change_log
WHERE claim_id = 900001
ORDER BY changed_at, change_id
LIMIT 20;
```

## 11. What the data guarantees and what it leaves out

### 11.1 Rules the data follows (all verified in Neon)

- **Joins are complete.** All 21 join relationships in section 3.2 have zero orphans.
- **Dates are in order.** `reported_date >= loss_date`; `claim_opened >= reported_date` (by up to 15 minutes); no timestamp is after 2026-10-07 12:00:00; an activity's `close_date` is on or after its `create_time`; a lawsuit is served 3 to 30 days after filing.
- **Claim state matches exposures.** A claim is `closed` exactly when all its exposures are closed, and its `close_date` is the latest exposure `close_date` (checked on all 18,535 closed claims). Open activities exist only on open claims.
- **Limits hold.** `paid_to_date` never exceeds `coverage_limit`; `exposures.coverage_limit` equals `coverages.exposure_limit`.
- **`paid_to_date` equals the ledger.** For every exposure it equals the sum of its submitted indemnity payments in `money`.
- **Closed exposures have no leftover reserve.** For every closed exposure and every cost type, the reserve rows sum to exactly what was paid.
- **Voids are replaced.** Every voided payment has a submitted payment of the same amount on the same exposure and cost type.
- **Money is simple.** `net_amount = original_amount = amount` on every row. Payments and recoveries are positive.
- **Vehicle logic is consistent.** A towed vehicle is never drivable. A parked vehicle has no `vehicle_direction`. Airbags deploy only on `severe` or `total_loss` damage. `total_loss` is true exactly when `damage_severity = 'total_loss'`. Every VIN starts with `9SY` and is 17 characters.
- **Negotiations stay in bounds.** No demand is above its exposure's coverage limit.
- **Versions add up.** Each row's `bean_version` is 1 + its number of change events.

### 11.2 What the data does not model

- **Not modeled:** reopened claims or exposures, reassignments to another adjuster, a fault rating beyond the percentage, more than one lawsuit per exposure, more than one third-party vehicle per claim, claimant and driver names, litigation beyond a filing date and a service date, and the policy itself (there is no policy table; only the coverage limit and deductible per exposure).
- **Not edited:** `notes`, `coverages`, `vehicles`, `negotiations`, `contact_roles` and `users` are written once and never change.
- **Invented values:** PIP income-loss, loss-of-services, funeral and survivor limits, `recovery_category` and `check_status` values, and all firms, repair shops, providers, contractors, streets and people.
- **Rates were tuned.** Shares such as the 7% open claims, the 14.7% of claims with a BI or PIP exposure, and about 260 lawsuits were set by generator parameters, so they illustrate a claim system rather than measure any real book of business.
- **The final offer is not always the payment.** The last `offer` on an exposure equals `paid_to_date` for most but not all exposures (it differs on 109 of the 511 exposures that have offers).
- **Some values are very uniform.** Cities (about 10% each), colors and several fault percentages are close to evenly spread, which real data is not.

### 11.3 How the data was made

A synthetic claims generator produced the data (20,000 claims, seed 7). The generator is not part of this repository. The CSV files it wrote carry the same column names as the Neon tables.
