-- 001 - Extensions, schemas and enumerated domains
-- Separation of concerns (brief §31): company FACTS, LAW, CALCULATIONS,
-- ASSESSMENT RESULTS and SOURCE DOCUMENTS live in distinct namespaces so a
-- company fact can never be written into a legal table.

BEGIN;

CREATE EXTENSION IF NOT EXISTS pgcrypto;    -- gen_random_uuid()
CREATE EXTENSION IF NOT EXISTS btree_gist;  -- exclusion constraints on daterange + uuid

CREATE SCHEMA IF NOT EXISTS legal;    -- source documents, provisions, rules
CREATE SCHEMA IF NOT EXISTS company;  -- company facts
CREATE SCHEMA IF NOT EXISTS calc;     -- formulas
CREATE SCHEMA IF NOT EXISTS assess;   -- assessment results
CREATE SCHEMA IF NOT EXISTS audit;    -- change log

COMMENT ON SCHEMA legal   IS 'Law: source documents, provisions, rules. Never contains company facts.';
COMMENT ON SCHEMA company IS 'Company facts supplied as input to the rule engine.';
COMMENT ON SCHEMA calc    IS 'Calculation formulas, versioned independently of legal rules.';
COMMENT ON SCHEMA assess  IS 'Assessment runs and their pinned rule/calculation versions.';
COMMENT ON SCHEMA audit   IS 'Append-only change history.';

CREATE TYPE legal.authority AS ENUM ('MCA','SEBI','NSE','BSE','RBI','OTHER','UNKNOWN');

CREATE TYPE legal.document_type AS ENUM (
  'ACT','RULE','NOTIFICATION','CIRCULAR','FORM','INSTRUCTION_KIT','AMENDMENT',
  'REGULATION','MASTER_CIRCULAR','GUIDANCE','FAQ',
  'CHECKLIST','CORPORATE_ACTION_REQUIREMENT','FILING_REQUIREMENT','LISTING_REQUIREMENT',
  'XBRL_REQUIREMENT','COMPLIANCE_CALENDAR','NOTICE','CONTAINER','UNKNOWN');

-- P0 primary law .. P4 general web (brief §18).
CREATE TYPE legal.source_priority AS ENUM ('P0','P1','P2','P3','P4');

-- Whether a document's text already incorporates later amendments. Text that
-- does not may be read for reference but must not source a production rule.
CREATE TYPE legal.consolidation_status AS ENUM
  ('CONSOLIDATED','AS_ENACTED','REFERENCE_ONLY','UNKNOWN');

CREATE TYPE legal.provision_type AS ENUM (
  'CHAPTER','PART','SCHEDULE','ANNEXURE',
  'SECTION','RULE','REGULATION','PARAGRAPH','ITEM','QUESTION',
  'SUB_SECTION','SUB_RULE','SUB_REGULATION','CLAUSE','SUB_CLAUSE',
  'PROVISO','EXPLANATION');

CREATE TYPE legal.instrument_kind AS ENUM
  ('ACT','RULES','REGULATIONS','CIRCULAR','CHECKLIST','FAQ','UNKNOWN');

CREATE TYPE legal.issue_type AS ENUM (
  'RIGHTS','PREFERENTIAL','PRIVATE_PLACEMENT','BONUS','ESOP','SWEAT_EQUITY',
  'PUBLIC_ISSUE','FPO','QIP','CONVERSION','WARRANTS','OTHER','GENERAL','UNKNOWN');

CREATE TYPE legal.company_type AS ENUM (
  'PRIVATE','PUBLIC','LISTED','UNLISTED','SME','MAIN_BOARD','SECTION_8','NIDHI',
  'GOVERNMENT','ANY','UNKNOWN');

CREATE TYPE legal.listed_status AS ENUM ('LISTED','UNLISTED','BOTH','UNKNOWN');

CREATE TYPE legal.security_type AS ENUM (
  'EQUITY_SHARES','PREFERENCE_SHARES','CONVERTIBLE_SECURITIES','WARRANTS',
  'DEBENTURES','NON_CONVERTIBLE','ESOP_OPTIONS','SWEAT_EQUITY',
  'DEPOSITORY_RECEIPTS','ANY','UNKNOWN');

CREATE TYPE legal.exchange AS ENUM ('NSE','BSE','MSEI','ANY','NONE');

-- Rule outcomes (brief §24). REVIEW_REQUIRED is a first-class result: the
-- engine says "a human must decide" instead of guessing.
CREATE TYPE legal.rule_result AS ENUM
  ('PASS','WARNING','BLOCK','NOT_APPLICABLE','REVIEW_REQUIRED');

CREATE TYPE legal.severity AS ENUM ('INFO','WARNING','BLOCK');

-- AI may propose; only a human may approve (brief §19, §26).
CREATE TYPE legal.review_status AS ENUM
  ('PENDING','IN_REVIEW','APPROVED','REJECTED','NEEDS_INFO','SUPERSEDED');

CREATE TYPE legal.approval_type AS ENUM (
  'BOARD','SHAREHOLDER_ORDINARY','SHAREHOLDER_SPECIAL','POSTAL_BALLOT',
  'STOCK_EXCHANGE_IN_PRINCIPLE','STOCK_EXCHANGE_TRADING','STOCK_EXCHANGE_LISTING',
  'SEBI','RBI','ROC','AUDIT_COMMITTEE','OTHER');

CREATE TYPE legal.day_type AS ENUM ('CALENDAR','WORKING','TRADING');

CREATE TYPE legal.deadline_direction AS ENUM ('BEFORE','AFTER','ON');

CREATE TYPE legal.compliance_stage AS ENUM
  ('PRE_ISSUE','PRE_ALLOTMENT','ALLOTMENT','POST_ALLOTMENT','LISTING','TRADING','ONGOING');

CREATE TYPE legal.requirement_necessity AS ENUM ('MANDATORY','CONDITIONAL','OPTIONAL');

CREATE TYPE legal.conflict_status AS ENUM
  ('OPEN','UNDER_REVIEW','RESOLVED','NOT_A_CONFLICT');

CREATE TYPE legal.doc_scope AS ENUM ('COMPANY','REIT_INVIT','OTHER');

COMMIT;

-- rollback:
--   DROP SCHEMA IF EXISTS audit, assess, calc, company, legal CASCADE;
