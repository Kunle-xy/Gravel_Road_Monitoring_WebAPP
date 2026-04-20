#!/usr/bin/env python3
"""
CLI for managing the sign-in allowlist (approved emails + domains).

Run from the FastAPI project root:
    uv run python manage_approved.py <subcommand> [...]

See APPROVED_EMAILS.md for usage examples.
"""

from __future__ import annotations

import argparse
import sys
from typing import Iterable

from sqlalchemy.exc import IntegrityError

from app.database import SessionLocal
from app.models import ApprovedDomain, ApprovedEmail, User


def _normalize_email(raw: str) -> str:
    value = (raw or "").strip().lower()
    if "@" not in value:
        raise ValueError(f"Not a valid email: {raw!r}")
    return value


def _normalize_domain(raw: str) -> str:
    value = (raw or "").strip().lower().lstrip("@")
    if not value or "." not in value:
        raise ValueError(f"Not a valid domain: {raw!r}")
    return value


def cmd_add(args: argparse.Namespace) -> int:
    email = _normalize_email(args.email)
    db = SessionLocal()
    try:
        if db.query(ApprovedEmail).filter(ApprovedEmail.email == email).first():
            print(f"already approved: {email}")
            return 0
        db.add(ApprovedEmail(email=email, note=args.note))
        db.commit()
        print(f"approved email: {email}")
        return 0
    except IntegrityError as exc:
        db.rollback()
        print(f"failed: {exc}", file=sys.stderr)
        return 1
    finally:
        db.close()


def cmd_remove(args: argparse.Namespace) -> int:
    email = _normalize_email(args.email)
    db = SessionLocal()
    try:
        row = db.query(ApprovedEmail).filter(ApprovedEmail.email == email).first()
        if not row:
            print(f"not found: {email}")
            return 0
        db.delete(row)
        db.commit()
        print(f"removed: {email}")
        return 0
    finally:
        db.close()


def cmd_add_domain(args: argparse.Namespace) -> int:
    domain = _normalize_domain(args.domain)
    db = SessionLocal()
    try:
        if db.query(ApprovedDomain).filter(ApprovedDomain.domain == domain).first():
            print(f"already approved: @{domain}")
            return 0
        db.add(ApprovedDomain(domain=domain, note=args.note))
        db.commit()
        print(f"approved domain: @{domain}")
        return 0
    finally:
        db.close()


def cmd_remove_domain(args: argparse.Namespace) -> int:
    domain = _normalize_domain(args.domain)
    db = SessionLocal()
    try:
        row = db.query(ApprovedDomain).filter(ApprovedDomain.domain == domain).first()
        if not row:
            print(f"not found: @{domain}")
            return 0
        db.delete(row)
        db.commit()
        print(f"removed: @{domain}")
        return 0
    finally:
        db.close()


def _print_rows(header: str, rows: Iterable[tuple[str, str | None, str | None]]) -> None:
    rows = list(rows)
    print(f"\n{header} ({len(rows)})")
    if not rows:
        print("  (none)")
        return
    for identifier, added_at, note in rows:
        stamp = added_at.isoformat(sep=" ", timespec="seconds") if added_at else ""
        tail = f"  — {note}" if note else ""
        print(f"  {identifier}  [{stamp}]{tail}")


def cmd_list(_: argparse.Namespace) -> int:
    db = SessionLocal()
    try:
        emails = db.query(ApprovedEmail).order_by(ApprovedEmail.email).all()
        domains = db.query(ApprovedDomain).order_by(ApprovedDomain.domain).all()
        _print_rows("Approved emails", [(r.email, r.added_at, r.note) for r in emails])
        _print_rows("Approved domains", [(f"@{r.domain}", r.added_at, r.note) for r in domains])
        return 0
    finally:
        db.close()


def cmd_seed(_: argparse.Namespace) -> int:
    """Approve every currently registered user so nobody is locked out after deploy."""
    db = SessionLocal()
    try:
        users = db.query(User).all()
        added = 0
        for user in users:
            email = (user.email or "").strip().lower()
            if not email:
                continue
            if db.query(ApprovedEmail).filter(ApprovedEmail.email == email).first():
                continue
            db.add(ApprovedEmail(email=email, note="seeded from existing users"))
            added += 1
        db.commit()
        print(f"seeded {added} emails from {len(users)} users")
        return 0
    finally:
        db.close()


def main() -> int:
    parser = argparse.ArgumentParser(prog="manage_approved.py")
    sub = parser.add_subparsers(dest="command", required=True)

    p_add = sub.add_parser("add", help="Approve a specific email")
    p_add.add_argument("email")
    p_add.add_argument("--note")
    p_add.set_defaults(func=cmd_add)

    p_remove = sub.add_parser("remove", help="Remove a specific email")
    p_remove.add_argument("email")
    p_remove.set_defaults(func=cmd_remove)

    p_add_domain = sub.add_parser("add-domain", help="Approve an entire domain")
    p_add_domain.add_argument("domain")
    p_add_domain.add_argument("--note")
    p_add_domain.set_defaults(func=cmd_add_domain)

    p_remove_domain = sub.add_parser("remove-domain", help="Remove a domain approval")
    p_remove_domain.add_argument("domain")
    p_remove_domain.set_defaults(func=cmd_remove_domain)

    p_list = sub.add_parser("list", help="Show every approved email + domain")
    p_list.set_defaults(func=cmd_list)

    p_seed = sub.add_parser("seed", help="Approve every currently registered user")
    p_seed.set_defaults(func=cmd_seed)

    args = parser.parse_args()
    try:
        return args.func(args)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
