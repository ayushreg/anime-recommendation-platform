"""Linking a public list on another tracker, read-only.

Kura stores a username and nothing else. There is no password field, no token,
no OAuth callback, and no code path anywhere in this router that writes to a
provider. Unlinking deletes the row and leaves everything it imported alone,
because by then those ratings are yours and live here.
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth import require_user
from app.database import get_db
from app.models import LinkedAccount, User
from app.schemas import (
    ImportResultOut,
    LinkAccountIn,
    LinkedAccountOut,
    SyncResultOut,
)
from app.services import events, ingest, live
from app.services.flags import enabled
from app.services.importer import apply_entries

router = APIRouter(prefix="/api/connect", tags=["connect"])

# A MAL sync can still fail for reasons neither end controls. When it does,
# offer the path that cannot fail rather than dead-ending.
MAL_FALLBACK_HINT = (
    " If this keeps happening, the MyAnimeList XML export import further down "
    "this page does the same job from a file."
)


def _require_flag() -> None:
    if not enabled("live_data", default=True):
        raise HTTPException(
            status_code=404,
            detail="Live data is switched off on this instance.",
        )


def _out(account: LinkedAccount) -> LinkedAccountOut:
    return LinkedAccountOut(
        id=account.id,
        provider=account.provider,
        provider_label=live.PROVIDER_LABELS.get(account.provider, account.provider),
        external_username=account.external_username,
        auto_sync=bool(account.auto_sync),
        last_synced_at=account.last_synced_at,
        last_status=account.last_status,
        last_detail=account.last_detail,
        last_matched=int(account.last_matched or 0),
        last_skipped=int(account.last_skipped or 0),
    )


def sync_account(db: Session, account: LinkedAccount) -> ImportResultOut:
    """Pull the linked list and fold it into this vault.

    Records the outcome on the account either way, so a failed sync leaves an
    explanation on the settings page instead of vanishing.
    """
    fetcher = live.PROVIDER_FETCHERS[account.provider]
    try:
        entries = fetcher(account.external_username)
    except live.LiveUnavailable as exc:
        message = str(exc)
        if account.provider == "mal":
            message += MAL_FALLBACK_HINT
        account.last_status = "error"
        account.last_detail = message[:400]
        account.last_synced_at = datetime.now(timezone.utc)
        db.commit()
        raise HTTPException(status_code=503, detail=message) from exc

    # The offline dump is a subset of every anime ever made, so a real list
    # always names titles this vault has never seen. Fetch those by the ids the
    # list just handed us, otherwise a third of somebody's shelf silently
    # vanishes and the sync looks broken.
    added = 0
    try:
        added = ingest.backfill_missing(db, [e.get("mal_id") for e in entries])
    except live.LiveUnavailable:
        # Backfill is a bonus, not the job. A list that matches against the
        # existing catalog is still worth importing.
        added = 0

    # Their list is the source of truth for a linked account, so a re-sync
    # overwrites scores Kura already holds for the same title.
    result = apply_entries(db, account.user_id, entries, overwrite=True)

    account.last_status = "ok"
    account.last_detail = f"{result.matched} matched, {result.skipped} with no catalog match"
    account.last_synced_at = datetime.now(timezone.utc)
    account.last_matched = result.matched
    account.last_skipped = result.skipped
    db.commit()
    return result


@router.get("/accounts", response_model=list[LinkedAccountOut])
def list_accounts(user: User = Depends(require_user), db: Session = Depends(get_db)):
    rows = db.query(LinkedAccount).filter(LinkedAccount.user_id == user.id).all()
    return [_out(a) for a in rows]


@router.post("/accounts", response_model=SyncResultOut)
def link_account(
    payload: LinkAccountIn,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    """Link a username and pull it once, so success is visible immediately."""
    _require_flag()
    username = payload.username.strip()
    if not username:
        raise HTTPException(status_code=400, detail="That username is empty")

    account = (
        db.query(LinkedAccount)
        .filter(LinkedAccount.user_id == user.id, LinkedAccount.provider == payload.provider)
        .first()
    )
    if not account:
        account = LinkedAccount(user_id=user.id, provider=payload.provider)
        db.add(account)
    account.external_username = username
    account.auto_sync = bool(payload.auto_sync)
    db.commit()

    result = sync_account(db, account)
    events.record(
        db,
        user_id=user.id,
        kind="account_linked",
        detail=f"{live.PROVIDER_LABELS.get(payload.provider)} as {username}",
        persist=False,
    )
    db.commit()
    return SyncResultOut(account=_out(account), result=result)


@router.post("/accounts/{provider}/sync", response_model=SyncResultOut)
def sync_now(
    provider: str,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    _require_flag()
    account = (
        db.query(LinkedAccount)
        .filter(LinkedAccount.user_id == user.id, LinkedAccount.provider == provider)
        .first()
    )
    if not account:
        raise HTTPException(status_code=404, detail="No account linked for that provider")
    result = sync_account(db, account)
    return SyncResultOut(account=_out(account), result=result)


@router.delete("/accounts/{provider}", status_code=204)
def unlink(
    provider: str,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    account = (
        db.query(LinkedAccount)
        .filter(LinkedAccount.user_id == user.id, LinkedAccount.provider == provider)
        .first()
    )
    if account:
        db.delete(account)
        db.commit()
    return None
