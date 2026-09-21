"""Check shared RDS identities using two independently initialized app instances.

Creates one random test account and sessions, then removes only those test records.
Run in the configured gateway: python tests/integration/shared_auth.py
"""
import secrets
import uuid
from sqlalchemy import text
from modules.shared.integration import database_engine
from modules.shared.auth.postgres import PostgresAuthService
from modules.shared.auth.models import RegisterRequest


def main():
    engine=database_engine('identity')
    with engine.connect() as c:
        assert c.execute(text('SELECT current_database()')).scalar_one() == 'smsprsm_integration'
        assert c.execute(text('SELECT ssl FROM pg_stat_ssl WHERE pid=pg_backend_pid()')).scalar_one()
        assert c.execute(text('SELECT count(*) FROM platform_users')).scalar_one() > 0
    first, second=PostgresAuthService(), PostgresAuthService()
    email=f'shared-auth-{uuid.uuid4().hex}@example.test'
    password=secrets.token_urlsafe(24)
    account=None
    try:
        account=first.register(RegisterRequest(email=email,password=password,role='user'))
        assert second.get_user(account.id).email == email
        print('PASS account created by one instance is visible to an already-running second instance')
        token=second.authenticate(email,password,'user').access_token
        assert first.decode_token(token)['sub'] == account.id
        print('PASS shared account login and session validation across instances')
        first.revoke_token(token)
        try:
            second.decode_token(token)
        except ValueError:
            pass
        else:
            raise AssertionError('Revoked session accepted by second instance')
        print('PASS cross-instance session revocation')
        restarted=PostgresAuthService()
        assert restarted.authenticate(email,password,'user').role == 'user'
        print('PASS account survives application-instance restart')
    finally:
        if account:
            with engine.begin() as c:
                c.execute(text('DELETE FROM auth_tokens WHERE user_id=:id'),{'id':account.id})
                c.execute(text('DELETE FROM platform_users WHERE id=:id AND email=:email'),{'id':account.id,'email':email})
            print('PASS temporary test account and sessions cleaned up')


if __name__ == '__main__':
    main()
