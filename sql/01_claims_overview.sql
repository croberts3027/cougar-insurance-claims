-- Indemnity paid per claim, largest first.
-- Adapted from cookbook query 3 in docs/data-dictionary.md (LIMIT removed).
-- Summing indemnity_paid over all rows gives 138789173.80, the check value in docs/claims-primer.md.
SELECT claim_id, SUM(amount) AS indemnity_paid
FROM money
WHERE subtype = 'Payment' AND status = 'submitted' AND cost_type = 'COUGAR_indemnity'
GROUP BY claim_id
ORDER BY indemnity_paid DESC;
