-- Negative tests for the schema's safety guarantees.
-- Each case MUST raise; a case that succeeds means a guarantee is broken.
\set ON_ERROR_STOP 1
\pset pager off

BEGIN;

INSERT INTO legal.legal_sources
 (document_key,authority,document_type,title,file_name,local_file_path,file_type,
  file_size_bytes,file_hash,source_priority,consolidation_status,as_amended_upto,
  human_review_required)
VALUES ('t-p0','SEBI','REGULATION','Test P0','t.pdf','t.pdf','pdf',100,
        repeat('a',64),'P0','CONSOLIDATED','2024-01-01',false),
       ('t-p4','OTHER','UNKNOWN','Test P4 blog','b.pdf','b.pdf','pdf',100,
        repeat('b',64),'P4','UNKNOWN',NULL,false),
       ('t-ref','MCA','ACT','As-enacted Act','a.pdf','a.pdf','pdf',100,
        repeat('c',64),'P0','REFERENCE_ONLY',NULL,false);
INSERT INTO legal.legal_rules (rule_code,title,authority,issue_type)
VALUES ('PREF-001','Test rule','SEBI','PREFERENTIAL');

CREATE FUNCTION pg_temp.must_fail(label text, stmt text) RETURNS void
LANGUAGE plpgsql AS $$
BEGIN
    BEGIN
        EXECUTE stmt;
        RAISE WARNING 'BROKEN  %  <-- statement SUCCEEDED but must have failed', label;
    EXCEPTION WHEN others THEN
        RAISE NOTICE 'ok      %  (% )', label, left(replace(SQLERRM, E'\n', ' '), 76);
    END;
END $$;

CREATE FUNCTION pg_temp.mk(vno int, extra text DEFAULT '', src text DEFAULT 't-p0') RETURNS text
LANGUAGE sql AS $$
 SELECT format($f$
   INSERT INTO legal.legal_rule_versions
    (rule_id,version_no,issue_type,trigger_expr,requirement,result_if_fail,severity,
     source_id,source_reference,effective_from %s)
   SELECT r.rule_id,%s,'PREFERENTIAL','x','y','BLOCK','BLOCK',s.source_id,'reg.164','2020-01-01' %s
   FROM legal.legal_rules r, legal.legal_sources s
   WHERE r.rule_code='PREF-001' AND s.document_key='%s' $f$,
   CASE WHEN extra='' THEN '' ELSE ','||split_part(extra,'|',1) END, vno,
   CASE WHEN extra='' THEN '' ELSE ','||split_part(extra,'|',2) END, src);
$$;

-- Baseline: a valid PENDING version must insert cleanly.
\echo ''
\echo '--- schema safety guarantees ---'
DO $$ BEGIN EXECUTE pg_temp.mk(1, 'effective_to|''2024-05-01'''); 
  RAISE NOTICE 'ok      baseline valid version inserted';
END $$;

SELECT pg_temp.must_fail('overlapping rule versions rejected (§17)',
        pg_temp.mk(2, 'effective_to|NULL'));   -- 2023-01-01.. overlaps 2020..2024-05
SELECT pg_temp.must_fail('APPROVED without reviewer rejected (§19)',
        pg_temp.mk(3, 'legal_review_status,human_review_required|''APPROVED'',false'));
SELECT pg_temp.must_fail('APPROVED on P4 source rejected (§18)',
        pg_temp.mk(4, 'legal_review_status,human_review_required,reviewer_id,reviewed_at|''APPROVED'',false,''lawyer'',now()', 't-p4'));
SELECT pg_temp.must_fail('APPROVED on REFERENCE_ONLY source rejected (amendment safety)',
        pg_temp.mk(5, 'legal_review_status,human_review_required,reviewer_id,reviewed_at|''APPROVED'',false,''lawyer'',now()', 't-ref'));
SELECT pg_temp.must_fail('effective_to before effective_from rejected',
        pg_temp.mk(6, 'effective_to|''2019-01-01'''));
SELECT pg_temp.must_fail('malformed condition AST rejected (§10)', $$
   INSERT INTO legal.legal_conditions (rule_version_id,expr_json,expr_text)
   SELECT rule_version_id,'{"op":"eq","field":"company.listed"}'::jsonb,'no value'
   FROM legal.legal_rule_versions WHERE version_no=1 $$);
SELECT pg_temp.must_fail('unknown condition operator rejected (§10)', $$
   INSERT INTO legal.legal_conditions (rule_version_id,expr_json,expr_text)
   SELECT rule_version_id,'{"op":"REGEX","field":"a","value":"b"}'::jsonb,'bad op'
   FROM legal.legal_rule_versions WHERE version_no=1 $$);
-- company.* is now tenant-scoped, so this fixture must supply org_id and set
-- the tenant, or the test would pass on a NOT NULL violation instead of on
-- the capital constraint it is actually asserting.
INSERT INTO auth.organisations (org_id, name, slug)
VALUES ('33333333-3333-3333-3333-333333333333','Constraint Test Org','constraint-test');
SET LOCAL app.current_org = '33333333-3333-3333-3333-333333333333';

SELECT pg_temp.must_fail('paid-up capital above authorised rejected', $$
   WITH c AS (INSERT INTO company.companies (org_id,name)
              VALUES ('33333333-3333-3333-3333-333333333333','T Ltd') RETURNING company_id)
   INSERT INTO company.capital_snapshots
    (org_id,company_id,as_of_date,authorised_capital,issued_capital,subscribed_capital,
     paid_up_capital,face_value,shares_issued)
   SELECT '33333333-3333-3333-3333-333333333333',company_id,'2024-01-01',
          5000000,9000000,9000000,9000000,10,900000 FROM c $$);

-- Positive control: a valid snapshot must still insert, proving the failure
-- above came from the capital ordering and not from tenancy plumbing.
DO $$
DECLARE cid uuid;
BEGIN
  INSERT INTO company.companies (org_id,name)
  VALUES ('33333333-3333-3333-3333-333333333333','Valid Ltd') RETURNING company_id INTO cid;
  INSERT INTO company.capital_snapshots
   (org_id,company_id,as_of_date,authorised_capital,issued_capital,subscribed_capital,
    paid_up_capital,face_value,shares_issued)
  VALUES ('33333333-3333-3333-3333-333333333333',cid,'2024-01-01',
          50000000,35000000,35000000,35000000,10,3500000);
  RAISE NOTICE 'ok      valid capital snapshot accepted (control for the test above)';
END $$;
SELECT pg_temp.must_fail('duplicate rule_code rejected', $$
   INSERT INTO legal.legal_rules (rule_code,title,authority,issue_type)
   VALUES ('PREF-001','dup','SEBI','PREFERENTIAL') $$);
SELECT pg_temp.must_fail('duplicate file_hash rejected (§2)', $$
   INSERT INTO legal.legal_sources
    (document_key,authority,document_type,title,file_name,local_file_path,file_type,
     file_size_bytes,file_hash,source_priority)
   VALUES ('dup','SEBI','REGULATION','dup','d.pdf','d.pdf','pdf',1,repeat('a',64),'P0') $$);

-- Positive: a valid AST must be accepted.
\echo ''
\echo '--- positive checks ---'
DO $$ BEGIN
  INSERT INTO legal.legal_conditions (rule_version_id,expr_json,expr_text)
  SELECT rule_version_id,
    '{"op":"AND","args":[{"op":"eq","field":"company.listed","value":true},
                         {"op":"in","field":"issue.type","value":["PREFERENTIAL"]}]}'::jsonb,
    'company.listed = true AND issue.type in (PREFERENTIAL)'
  FROM legal.legal_rule_versions WHERE version_no=1;
  RAISE NOTICE 'ok      well-formed nested AST accepted';
END $$;

SELECT 'deadline: 15 calendar days after allotment' AS check,
       legal.compute_deadline('2024-03-15',15,'DAYS','CALENDAR','AFTER') AS result,
       (legal.compute_deadline('2024-03-15',15,'DAYS','CALENDAR','AFTER')='2024-03-30') AS correct;
SELECT '7 working days after 2024-03-15 (Fri)' AS check,
       legal.compute_deadline('2024-03-15',7,'DAYS','WORKING','AFTER') AS result,
       (legal.compute_deadline('2024-03-15',7,'DAYS','WORKING','AFTER')='2024-03-26') AS correct;

-- The production gate must be empty: nothing here was ever human-approved.
SELECT 'rules visible to engine (must be 0)' AS check, count(*) AS n
FROM legal.v_active_rule_versions;

ROLLBACK;
