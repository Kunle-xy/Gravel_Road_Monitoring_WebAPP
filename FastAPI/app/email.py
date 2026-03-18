import logging
from datetime import timedelta
from app.config import settings
from app.auth import create_access_token

logger = logging.getLogger(__name__)


def create_verification_token(email: str) -> str:
    return create_access_token(
        data={"sub": email, "purpose": "email_verify"},
        expires_delta=timedelta(hours=settings.EMAIL_VERIFY_EXPIRE_HOURS),
    )


def send_verification_email(to_email: str, first_name: str | None = None):
    token = create_verification_token(to_email)
    verify_url = f"{settings.FRONTEND_URL}/verify?token={token}"

    if settings.EMAIL_PROVIDER == "console":
        # Dev mode: log the link instead of sending an email
        logger.info(f"\n{'='*60}")
        logger.info(f"VERIFICATION LINK for {to_email}:")
        logger.info(f"{verify_url}")
        logger.info(f"{'='*60}\n")
        return

    if settings.EMAIL_PROVIDER == "ses":
        _send_via_ses(to_email, first_name, verify_url)
        return

    raise ValueError(f"Unknown EMAIL_PROVIDER: {settings.EMAIL_PROVIDER}")


def _send_via_ses(to_email: str, first_name: str | None, verify_url: str):
    import boto3
    name = first_name or "there"

    html = f"""
    <div style="font-family: Arial, sans-serif; max-width: 500px; margin: 0 auto; padding: 30px;">
        <h2 style="color: #7f1d1d;">Gravel Road Iowa</h2>
        <p>Hi {name},</p>
        <p>Thanks for signing up! Please verify your email address to activate your account.</p>
        <p style="text-align: center; margin: 30px 0;">
            <a href="{verify_url}"
               style="background-color: #991b1b; color: white; padding: 12px 30px;
                      text-decoration: none; border-radius: 8px; font-weight: bold;">
                Verify Email
            </a>
        </p>
        <p style="color: #666; font-size: 13px;">
            This link expires in {settings.EMAIL_VERIFY_EXPIRE_HOURS} hours.
            If you didn't create this account, you can ignore this email.
        </p>
        <hr style="border: none; border-top: 1px solid #eee; margin: 20px 0;">
        <p style="color: #999; font-size: 12px;">
            If the button doesn't work, copy and paste this link:<br>
            <a href="{verify_url}" style="color: #991b1b;">{verify_url}</a>
        </p>
    </div>
    """

    ses = boto3.client("ses", region_name=settings.AWS_REGION)

    ses.send_email(
        Source=f"Gravel Road Iowa <{settings.SES_FROM_EMAIL}>",
        Destination={"ToAddresses": [to_email]},
        Message={
            "Subject": {"Data": "Verify your email - Gravel Road Iowa"},
            "Body": {"Html": {"Data": html}},
        },
    )
    logger.info(f"Verification email sent to {to_email} via SES")
