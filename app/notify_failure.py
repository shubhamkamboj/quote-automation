import os
import smtplib
import ssl
import sys
from email.message import EmailMessage


def main():
    required = ["SMTP_HOST", "SMTP_USERNAME", "SMTP_PASSWORD", "ALERT_TO_EMAIL"]
    missing = [key for key in required if not os.getenv(key)]
    if missing:
        print(f"Failure email skipped; missing secrets: {', '.join(missing)}")
        return

    port = int(os.getenv("SMTP_PORT", "587"))
    sender = os.getenv("ALERT_FROM_EMAIL", os.environ["SMTP_USERNAME"])
    subject = os.getenv("ALERT_SUBJECT", "Instagram Quotes Automation Failed")
    run_url = os.getenv("GITHUB_SERVER_URL", "https://github.com") + "/" + os.getenv("GITHUB_REPOSITORY", "") + "/actions/runs/" + os.getenv("GITHUB_RUN_ID", "")
    body = (
        "Daily Instagram Quotes workflow failed.\n\n"
        f"Repository: {os.getenv('GITHUB_REPOSITORY', '')}\n"
        f"Workflow: {os.getenv('GITHUB_WORKFLOW', '')}\n"
        f"Run: {run_url}\n\n"
        "Check the GitHub Actions logs for the exact error."
    )

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = sender
    message["To"] = os.environ["ALERT_TO_EMAIL"]
    message.set_content(body)

    context = ssl.create_default_context()
    with smtplib.SMTP(os.environ["SMTP_HOST"], port, timeout=30) as server:
        server.starttls(context=context)
        server.login(os.environ["SMTP_USERNAME"], os.environ["SMTP_PASSWORD"])
        server.send_message(message)

    print("Failure email sent.")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"Could not send failure email: {exc}", file=sys.stderr)
        # Never hide the original workflow failure.
        sys.exit(0)
