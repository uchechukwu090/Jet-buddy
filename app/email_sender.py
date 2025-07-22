==============================================================================
# FILE: app/email_sender.py
# ==============================================================================
# --- Description:
# [ADJUSTMENT 3 - Implemented] Sends formatted email reports of the
# analysis results using SMTP.

import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from app.config import settings
from app.models import AnalysisOutput

def send_email_report(analysis: AnalysisOutput, symbol: str, recipients: List[str]):
    if not all([settings.smtp_server, settings.smtp_username, settings.smtp_password]):
        print("Email credentials not configured. Skipping email.")
        return

    msg = MIMEMultipart('alternative')
    msg['Subject'] = f"Jet Buddy AI Analysis for {symbol}"
    msg['From'] = settings.sender_email
    msg['To'] = ", ".join(recipients)

    html = f"""
    <html>
    <head>
        <style> /* CSS for styling the email */ </style>
    </head>
    <body>
        <div class="container">
            <div class="header">AI Trading Signal: {symbol}</div>
            <div class="field"><span class="label">Overall Bias:</span> <span class="value {analysis.trend_direction}">{analysis.trend_direction.title()}</span></div>
            <div class="field"><span class="label">Bias Confidence:</span> <span class="value">{analysis.bias_confidence * 100:.1f}%</span></div>
            <div class="field"><span class="label">News Sentiment:</span> <span class="value">{analysis.sentiment.title()}</span></div>
            <hr>
            <div class="field"><span class="label">Entry Zone:</span> <span class="value">{analysis.entry_zone}</span></div>
            <div class="field"><span class="label">Est. Time to Entry:</span> <span class="value">{analysis.estimated_entry_time}</span></div>
            <div class="field"><span class="label">Predicted Take-Profit:</span> <span class="value">{analysis.predicted_tp or 'N/A'}</span></div>
            <div class="field"><span class="label">Est. Time to TP:</span> <span class="value">{analysis.tp_eta}</span></div>
            <hr>
            <div class="field"><span class="label">Risk Profile:</span> <span class="value">{analysis.risk_profile.title()}</span></div>
            <div class="field"><span class="label">Suggested Lot Size:</span> <span class="value">{analysis.suggested_lot_size}</span></div>
            <p style="font-size: 12px; color: #888;">Note: {analysis.notes}</p>
        </div>
    </body>
    </html>
    """
    
    msg.attach(MIMEText(html, 'html'))

    try:
        with smtplib.SMTP(settings.smtp_server, settings.smtp_port) as server:
            server.starttls()
            server.login(settings.smtp_username, settings.smtp_password)
            server.sendmail(settings.sender_email, recipients, msg.as_string())
            print(f"Successfully sent email report for {symbol} to {recipients}")
    except Exception as e:
        print(f"Failed to send email: {e}")
