-- All the exposures of one claim, with limit and amount paid.
-- Cookbook query 2 in docs/data-dictionary.md. Change 900001 to look at another claim.
SELECT e.exposure_pk, e.exposure_type, e.coverage_subtype, e.state,
       c.deductible, e.coverage_limit, e.paid_to_date, e.limit_reached
FROM exposures e
JOIN coverages c USING (coverage_id)
WHERE e.claim_id = 900001;
