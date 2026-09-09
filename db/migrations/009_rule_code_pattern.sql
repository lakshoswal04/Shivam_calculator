-- 009 - Allow a route/variant segment in rule codes
--
-- The original pattern permitted one segment plus a number (ABC-001). Real
-- rule sets need to distinguish a route AND a variant within it -- the listed
-- and unlisted limbs of a preferential issue are different rules from
-- different instruments. PREF-L-001 / PREF-U-001 carries that distinction in
-- the identifier; PREFL001 hides it. This widens the pattern by one optional
-- segment and nothing else.

BEGIN;

ALTER TABLE legal.legal_rules DROP CONSTRAINT rule_code_shape;
ALTER TABLE legal.legal_rules ADD CONSTRAINT rule_code_shape
  CHECK (rule_code ~ '^[A-Z][A-Z0-9]{1,15}(-[A-Z0-9]{1,6})?-[0-9]{3,5}$');

COMMIT;

-- rollback:
--   ALTER TABLE legal.legal_rules DROP CONSTRAINT rule_code_shape;
--   ALTER TABLE legal.legal_rules ADD CONSTRAINT rule_code_shape
--     CHECK (rule_code ~ '^[A-Z][A-Z0-9]{1,15}-[0-9]{3,5}$');
