-- ============================================
-- Oracle XE 전용 스키마 생성
-- SYS 또는 SYSTEM 계정으로 실행
-- ============================================

-- 1. 사용자(스키마) 생성
CREATE USER bistelligence IDENTIFIED BY admin
    DEFAULT TABLESPACE users
    TEMPORARY TABLESPACE temp
    QUOTA UNLIMITED ON users;

-- 2. 권한 부여
GRANT CONNECT, RESOURCE TO bistelligence;
GRANT CREATE SESSION TO bistelligence;
GRANT CREATE TABLE TO bistelligence;
GRANT CREATE SEQUENCE TO bistelligence;
GRANT CREATE VIEW TO bistelligence;
GRANT CREATE PROCEDURE TO bistelligence;
