# Synthetic Data Notes

The claims data is fully synthetic, with complete and consistent recording, modeled on how a modern claims system is meant to be used. Everything is generated: no real claim, person, vehicle or note text is used. Claim numbers start with 9 so they are easy to recognize as synthetic.

The data lives in Neon as 13 tables: `header`, `exposures`, `money`, `activities`, `notes`, `coverages`, `contact_roles`, `matters`, `negotiations`, `vehicles`, `incidents`, `users` and `change_log`. Column definitions are in [data-dictionary.md](data-dictionary.md). The generator is not part of this repository.

## How the data is structured

These are rules the generator follows. You can rely on them, and you can use them as data-quality checks.

- **Money.** `net_amount` and `original_amount` equal `amount`. Payments are always positive. A void is a voided row plus a replacement. A closed exposure's reserves net to exactly what was paid.
- **Limits.** Every exposure has a coverage row with a limit. `limit_reached` is computed (`paid_to_date >= coverage_limit`), and paid never exceeds the limit.
- **Users.** Every user has a title, a department and a team group.
- **Activities.** A completed activity has `close_date` set and `>= create_time`. An open one has `close_date` NULL. Each activity is created once.
- **Claims.** `lob` and `loss_type` are always set. Every claim has at least one exposure. Segment is always a real one. A claim is closed if and only if all its exposures are closed, and `close_date` is the last exposure close.
- **Dates.** loss <= reported <= opened <= assigned. Matter filing >= loss, and service >= filing. Demands and offers are dated when they happened. Note `authoring_date` equals `create_time`.
- **Vehicles.** Every vehicle has a `vehicles` row (VIN with a valid check digit, year, make, model, style) and an `incidents` row with `first_point_of_impact` (only values from the standard collision-point list), `vehicle_direction`, `damage_description`, severity and `est_repair_cost`. Impact points match the cause (rear-ended means the insured's front and the other party's rear). Every claim header has `loss_description`. Vehicle exposures carry `incident_id`.
- **Work steps.** Each step is an activity with the date it was done and a note authored by whoever closed it. The liability decision (`header.insured_fault_pct`) comes before the first liability payment. Police report, statements, witness and scene inspection come before the decision. Quote and review quote come before the first payment. `subro_check` follows the decision and drives the subrogation referral (recovery only when the insured is not 100% at fault). Total losses get a salvage notice and a salvage status activity that closes when the salvage sells. PIP and BI claims get medical-report and treatment follow-up activities.
- **Notes.** Every note has a topic, an author with title and department, and (when it documents one) the activity it belongs to.
- **History.** Every table has `bean_version` (1 plus the number of changes since the row was created) and `update_time` (when it last changed). `change_log` lists each change: table, row, column, old and new value, who and when. A row is created at version 1 and each later edit is a logged change: claim and exposure assignment, the liability decision, each payment (`paid_to_date`), closing, approval of a payment or reserve, check issue and clearing, voids, activity completion, the repair estimate and service of a suit. Notes, coverages, vehicles, negotiations, attorney roles and users are never edited, so they stay at version 1. The generator's self-check replays the log and reproduces every current value, and each change's old value equals the previous new value.

## Assumptions made for this data

PIP income-loss, loss-of-services, funeral and survivor limits, `recovery_category` values, `check_status` values, and the fictional firms, vendors and providers.

## Deliberately left out

Reopens, reassignments, fault ratings, and litigation beyond one suit per exposure.
