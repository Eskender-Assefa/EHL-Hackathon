"""Provision a restricted role in the explicitly configured development database."""
from psycopg import sql
import bmwdb

ROLE='bmw_demo_app'
READ_TABLES=['schema_migrations','brands','models','model_groups','group_members','markets','market_aliases',
 'categories','features','attributes','variants','source_trim_labels','datasets','source_assets','dataset_versions',
 'source_records','evidence_locations','ingestion_runs','validation_issues','scenarios','configurator_sessions',
 'configurator_session_options','reviewed_option_mappings','feedback_records','feedback_tags','evidence_items',
 'processing_runs','problem_proposals','problem_evidence','requirements','requirement_versions',
 'requirement_evidence','pm_decisions','audit_events']
INSERT_TABLES=['problem_proposals','problem_evidence','requirements','requirement_versions','requirement_evidence','pm_decisions','audit_events']

def configure(conn):
    with conn.transaction():
        prior=conn.execute('SELECT rolsuper,rolcreatedb,rolcreaterole FROM pg_roles WHERE rolname=%s',(ROLE,)).fetchone()
        if prior and any(prior):raise ValueError('Existing role is privileged; choose an isolated role instead')
        if not prior:conn.execute(sql.SQL('CREATE ROLE {} LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE').format(sql.Identifier(ROLE)))
        db=conn.execute('SELECT current_database()').fetchone()[0]
        schema=conn.execute('SELECT current_schema()').fetchone()[0]
        conn.execute(sql.SQL('GRANT CONNECT ON DATABASE {} TO {}').format(sql.Identifier(db),sql.Identifier(ROLE)))
        conn.execute(sql.SQL('REVOKE CREATE ON SCHEMA {} FROM PUBLIC').format(sql.Identifier(schema)))
        conn.execute(sql.SQL('GRANT USAGE ON SCHEMA {} TO {}').format(sql.Identifier(schema),sql.Identifier(ROLE)))
        for table in READ_TABLES:
            conn.execute(sql.SQL('GRANT SELECT ON {} TO {}').format(sql.Identifier(table),sql.Identifier(ROLE)))
        for table in INSERT_TABLES:
            conn.execute(sql.SQL('GRANT INSERT ON {} TO {}').format(sql.Identifier(table),sql.Identifier(ROLE)))
        conn.execute(sql.SQL('GRANT UPDATE ON requirements TO {}').format(sql.Identifier(ROLE)))
        for table in ['problem_proposals','requirements','pm_decisions','audit_events']:
            seq=conn.execute('SELECT pg_get_serial_sequence(%s,%s)',(table,'id')).fetchone()[0]
            if seq:conn.execute(sql.SQL('GRANT USAGE ON SEQUENCE {} TO {}').format(sql.Identifier(*seq.split('.')),sql.Identifier(ROLE)))
        conn.execute(sql.SQL('REVOKE UPDATE,DELETE,TRUNCATE ON audit_events FROM {}').format(sql.Identifier(ROLE)))
    print('Restricted development role configured. No credentials printed.')

if __name__=='__main__':
    with bmwdb.connect() as conn:configure(conn)
