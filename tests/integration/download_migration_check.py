"""Run only against the approved integration database; verify additive upgrade."""
import sys
sys.path.insert(0, '/app/services/download')
from modules.shared.integration import database_engine
from sqlalchemy import text
from integration_migrations import upgrade

engine=database_engine('download')
def snapshot():
    with engine.connect() as c:
        assert c.scalar(text('SELECT current_database()')) == 'smsprsm_integration'
        return {table: c.scalar(text(f'SELECT count(*) FROM {table}')) for table in (
            'download.document_download_jobs','download.forensic_audit_logs','identity.platform_users')}
before=snapshot()
upgrade(engine); upgrade(engine)
after=snapshot()
assert before == after, (before,after)
print('PASS: repeatable download migration preserved existing records:',after)
