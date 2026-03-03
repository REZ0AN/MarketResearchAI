import aiosmtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from app.core.config import settings


async def _send(to: str, subject: str, html: str) -> None:
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = settings.EMAILS_FROM
    msg["To"]      = to
    msg.attach(MIMEText(html, "html"))

    await aiosmtplib.send(
        msg,
        hostname=settings.SMTP_HOST,
        port=settings.SMTP_PORT,
        username=settings.SMTP_USER,
        password=settings.SMTP_PASS,
        start_tls=True,
    )


async def send_verification_email(to: str, token: str) -> None:
    url  = f"{settings.FRONTEND_URL}/verify-email?token={token}"
    html = f"""
    <div style="font-family:sans-serif;max-width:480px;margin:auto">
      <h2>Verify your email</h2>
      <p>Click the button below to activate your account.
         The link expires in <strong>24 hours</strong>.</p>
      <a href="{url}"
         style="display:inline-block;padding:12px 24px;background:#1a73e8;
                color:#fff;border-radius:6px;text-decoration:none;font-weight:600">
        Verify Email
      </a>
      <p style="color:#888;font-size:12px;margin-top:24px">
        Or copy this link: {url}
      </p>
    </div>
    """
    await _send(to, "Verify your Gemini MVP account", html)


async def send_password_reset_email(to: str, token: str) -> None:
    url  = f"{settings.FRONTEND_URL}/reset-password?token={token}"
    html = f"""
    <div style="font-family:sans-serif;max-width:480px;margin:auto">
      <h2>Reset your password</h2>
      <p>This link expires in <strong>1 hour</strong>.</p>
      <a href="{url}"
         style="display:inline-block;padding:12px 24px;background:#d93025;
                color:#fff;border-radius:6px;text-decoration:none;font-weight:600">
        Reset Password
      </a>
      <p style="color:#888;font-size:12px;margin-top:24px">
        If you didn't request this, ignore this email.
      </p>
    </div>
    """
    await _send(to, "Reset your Gemini MVP password", html)