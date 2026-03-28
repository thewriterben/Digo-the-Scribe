"""Tests for digo.google_auth — Google OAuth2 helper."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch


class TestGetCredentials:
    """Tests for the get_credentials() function."""

    @patch("digo.google_auth.TOKEN_PATH", new_callable=lambda: MagicMock(spec=Path))
    @patch("digo.google_auth.InstalledAppFlow")
    def test_new_credentials_via_oauth_flow(self, mock_flow_cls, mock_token_path):
        """When no cached token exists, triggers the browser-based OAuth flow."""
        mock_token_path.exists.return_value = False
        mock_token_path.parent = MagicMock()

        fake_creds = MagicMock()
        fake_creds.to_json.return_value = '{"token": "abc"}'
        mock_flow_cls.from_client_secrets_file.return_value.run_local_server.return_value = (
            fake_creds
        )

        from digo.google_auth import get_credentials

        creds = get_credentials()

        assert creds is fake_creds
        mock_flow_cls.from_client_secrets_file.assert_called_once()
        mock_token_path.write_text.assert_called_once_with('{"token": "abc"}', encoding="utf-8")

    @patch("digo.google_auth.TOKEN_PATH", new_callable=lambda: MagicMock(spec=Path))
    @patch("digo.google_auth.Credentials")
    def test_loads_cached_valid_token(self, mock_creds_cls, mock_token_path):
        """When a valid cached token exists, returns it without re-auth."""
        mock_token_path.exists.return_value = True

        fake_creds = MagicMock()
        fake_creds.valid = True
        mock_creds_cls.from_authorized_user_file.return_value = fake_creds

        from digo.google_auth import get_credentials

        creds = get_credentials()

        assert creds is fake_creds
        mock_creds_cls.from_authorized_user_file.assert_called_once()

    @patch("digo.google_auth.TOKEN_PATH", new_callable=lambda: MagicMock(spec=Path))
    @patch("digo.google_auth.Request")
    @patch("digo.google_auth.Credentials")
    def test_refreshes_expired_token(self, mock_creds_cls, mock_request_cls, mock_token_path):
        """When the cached token is expired but has a refresh token, refreshes it."""
        mock_token_path.exists.return_value = True
        mock_token_path.parent = MagicMock()

        fake_creds = MagicMock()
        fake_creds.valid = False
        fake_creds.expired = True
        fake_creds.refresh_token = "refresh-token"
        fake_creds.to_json.return_value = '{"token": "refreshed"}'
        mock_creds_cls.from_authorized_user_file.return_value = fake_creds

        from digo.google_auth import get_credentials

        creds = get_credentials()

        assert creds is fake_creds
        fake_creds.refresh.assert_called_once()
        mock_token_path.write_text.assert_called_once()

    @patch("digo.google_auth.TOKEN_PATH", new_callable=lambda: MagicMock(spec=Path))
    @patch("digo.google_auth.InstalledAppFlow")
    @patch("digo.google_auth.Credentials")
    def test_reauth_when_expired_without_refresh_token(
        self, mock_creds_cls, mock_flow_cls, mock_token_path
    ):
        """When the cached token is expired and has no refresh token, re-runs OAuth flow."""
        mock_token_path.exists.return_value = True
        mock_token_path.parent = MagicMock()

        stale_creds = MagicMock()
        stale_creds.valid = False
        stale_creds.expired = True
        stale_creds.refresh_token = None
        mock_creds_cls.from_authorized_user_file.return_value = stale_creds

        new_creds = MagicMock()
        new_creds.to_json.return_value = '{"token": "new"}'
        mock_flow_cls.from_client_secrets_file.return_value.run_local_server.return_value = (
            new_creds
        )

        from digo.google_auth import get_credentials

        creds = get_credentials()

        assert creds is new_creds
        mock_flow_cls.from_client_secrets_file.assert_called_once()

    def test_scopes_include_calendar_readonly(self):
        """SCOPES list includes the Calendar read-only scope."""
        from digo.google_auth import SCOPES

        assert "https://www.googleapis.com/auth/calendar.readonly" in SCOPES

    def test_token_path_matches_config(self):
        """TOKEN_PATH is a Path derived from config.GOOGLE_TOKEN_FILE."""
        from digo import config as cfg
        from digo.google_auth import TOKEN_PATH

        assert isinstance(TOKEN_PATH, Path)
        assert str(TOKEN_PATH) == cfg.GOOGLE_TOKEN_FILE
