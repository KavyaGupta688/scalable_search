"""The integrated runtime must never silently create a local identity store."""
from unittest.mock import Mock
import pytest
from fastapi import HTTPException
from sqlalchemy.exc import OperationalError
from modules.shared.auth import dependencies, postgres


@pytest.fixture(autouse=True)
def no_implicit_identity_override(monkeypatch):
    monkeypatch.delenv('AUTH_DATABASE_URL_SYNC', raising=False)


@pytest.mark.parametrize('url', [None, '', 'invalid-url', 'sqlite:///local.db', 'mysql://user:private@host/db'])
def test_missing_or_wrong_database_fails_without_local_fallback(monkeypatch, url):
    monkeypatch.setattr(dependencies, '_auth_service', None)
    if url is None:
        monkeypatch.delenv('DATABASE_URL_SYNC', raising=False)
    else:
        monkeypatch.setenv('DATABASE_URL_SYNC', url)
    local = Mock()
    monkeypatch.setattr(dependencies, 'AuthService', local)
    with pytest.raises(HTTPException) as exc:
        dependencies.get_auth_service()
    assert exc.value.status_code == 503
    assert 'private' not in exc.value.detail
    local.assert_not_called()


def test_shared_backend_is_selected_and_reused(monkeypatch):
    monkeypatch.setattr(dependencies, '_auth_service', None)
    monkeypatch.setenv('DATABASE_URL_SYNC', 'postgresql+psycopg2://host/test')
    factory = Mock()
    monkeypatch.setattr(postgres, 'PostgresAuthService', factory)
    assert dependencies.get_auth_service() is factory.return_value
    assert dependencies.get_auth_service() is factory.return_value
    factory.assert_called_once_with()


def test_database_outage_never_switches_to_local_accounts(monkeypatch):
    monkeypatch.setattr(dependencies, '_auth_service', None)
    monkeypatch.setenv('DATABASE_URL_SYNC', 'postgresql+psycopg2://host/test')
    monkeypatch.setattr(postgres, 'PostgresAuthService', Mock(side_effect=OperationalError('', {}, Exception())))
    local=Mock()
    monkeypatch.setattr(dependencies, 'AuthService', local)
    with pytest.raises(OperationalError):
        dependencies.get_auth_service()
    assert dependencies._auth_service is None
    local.assert_not_called()


def test_explicit_shared_identity_database_works_without_module_database(monkeypatch):
    monkeypatch.setattr(dependencies, '_auth_service', None)
    monkeypatch.delenv('DATABASE_URL_SYNC', raising=False)
    monkeypatch.setenv('AUTH_DATABASE_URL_SYNC', 'postgresql+psycopg2://shared/identities')
    factory=Mock()
    monkeypatch.setattr(postgres, 'PostgresAuthService', factory)
    assert dependencies.get_auth_service() is factory.return_value


def test_identity_override_does_not_redirect_module_data(monkeypatch):
    from modules.shared import integration
    monkeypatch.setenv('AUTH_DATABASE_URL_SYNC', 'postgresql+psycopg2://shared/identities')
    monkeypatch.setenv('DATABASE_URL_SYNC', 'postgresql+psycopg2://separate/moduledata')
    factory=Mock()
    monkeypatch.setattr(integration,'create_engine',factory)
    integration.database_engine.cache_clear()
    try:
        integration.database_engine('identity')
        assert factory.call_args.args[0] == 'postgresql+psycopg2://shared/identities'
        integration.database_engine('ingestion')
        assert factory.call_args.args[0] == 'postgresql+psycopg2://separate/moduledata'
    finally:
        integration.database_engine.cache_clear()
